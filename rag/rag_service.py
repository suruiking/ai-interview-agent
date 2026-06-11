"""
RAG 回答服务：改写 → 检索 → 过滤 → 重排序 → 拼 prompt → 带引用回答
"""
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from rag.vector_store import VectorStoreService
from model.factory import chat_model
from sentence_transformers import CrossEncoder
from pathlib import Path


class RagService:
    MAX_DISTANCE = 0.8       # 距离阈值：超过此值视为不相关
    INITIAL_K = 20           # 粗筛取 20 条
    RERANK_TOP_K = 3         # 精排后取 3 条

    def __init__(self):
        self.vector_store = VectorStoreService()
        self.model = chat_model

        # 重排序模型：Cross-Encoder 精排（中文，278MB，启动时加载一次）
        self.reranker = CrossEncoder("BAAI/bge-reranker-base")

        prompt_path = Path(__file__).parent.parent / "prompts" / "rag_prompt.txt"
        self.prompt_template = PromptTemplate.from_template(
            prompt_path.read_text(encoding="utf-8")
        )

    def _rewrite_query(self, user_query: str) -> str:
        """Query Rewriting：口语问题 → 精确检索关键词"""
        prompt = f"""你是一个搜索优化助手。把以下用户问题改写成更适合向量检索的关键词。
规则：
1. 去掉口语化表达（"我想问""帮我看看"），提取核心概念
2. 保留专业术语的原文（如 Self-Attention、ReAct、ChromaDB）
3. 用空格分隔多个关键词
4. 只返回改写后的文本，不要解释

用户问题：{user_query}
改写："""
        try:
            response = self.model.invoke(prompt)
            rewritten = response.content.strip()
            if rewritten:
                return rewritten
        except Exception:
            pass
        return user_query

    def _rerank(self, query: str, docs: list[Document]) -> list[Document]:
        """Rerank 重排序：Cross-Encoder 逐条打分，取最高的 top_k 条"""
        if len(docs) <= self.RERANK_TOP_K:
            return docs

        pairs = [[query, doc.page_content] for doc in docs]
        scores = self.reranker.predict(pairs)
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in ranked[:self.RERANK_TOP_K]]

    def search(self, query: str) -> str:
        """完整 RAG 流程：改写 → 粗筛 → 过滤 → 精排 → 拼 prompt → LLM"""

        # 1. Query Rewriting
        search_query = self._rewrite_query(query)

        # 2. 向量检索：粗筛 20 条
        docs_with_score = self.vector_store.search_with_score(search_query, k=self.INITIAL_K)

        # 3. 距离阈值过滤
        valid = [doc for doc, score in docs_with_score if score <= self.MAX_DISTANCE]

        # 4. 空结果兜底
        if not valid:
            return "当前题库暂未收录该问题。\n建议：换个方向提问，或联系管理员补充题目。"

        # 5. Rerank 精排：Cross-Encoder 从候选里挑最好的 3 条
        top_docs = self._rerank(query, valid)

        # 6. 拼接参考资料（带来源信息）
        context = ""
        for i, doc in enumerate(top_docs, start=1):
            source = doc.metadata.get("source", "未知")
            context += f"【来源{i}】出处: {source}\n内容: {doc.page_content}\n\n"

        # 7. LLM 生成
        chain = self.prompt_template | self.model | StrOutputParser()
        return chain.invoke({"input": query, "context": context})

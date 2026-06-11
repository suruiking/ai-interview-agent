"""
RAG 回答服务：改写 → 粗筛 → 过滤 → 精排 → 拼 prompt → LLM
"""
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from rag.vector_store import VectorStoreService
from model.factory import chat_model
from sentence_transformers import CrossEncoder
from pathlib import Path
import re


class RagService:
    MAX_DISTANCE = 0.8
    INITIAL_K = 5
    RERANK_TOP_K = 3

    def __init__(self):
        self.vector_store = VectorStoreService()
        self.model = chat_model

        # 重排序模型（中文，启动加载一次）
        self.reranker = CrossEncoder("BAAI/bge-reranker-base")

        prompt_path = Path(__file__).parent.parent / "prompts" / "rag_prompt.txt"
        self.prompt_template = PromptTemplate.from_template(
            prompt_path.read_text(encoding="utf-8")
        )

    # 进阶1：问题重写
    def _rewrite_query(self, user_query: str) -> str:
        """把用户口语问题改写成精确检索关键词"""
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
        return user_query  # 改写失败用原文兜底

    # 进阶3：引用验证
    def _verify_citations(self, answer: str, valid_count: int) -> dict:
        """检查 LLM 引用的【来源N】是否真实存在"""
        cited = set(int(n) for n in re.findall(r'【来源(\d+)】', answer))
        fake = [n for n in cited if n > valid_count]
        if fake:
            return {"pass": False, "fake": fake}
        return {"pass": True}

    # 进阶2：Rerank 重排序
    def _rerank(self, query: str, docs: list) -> list:
        """Cross-Encoder 逐条打分，取最高分的 top_k 条"""
        if len(docs) <= self.RERANK_TOP_K:
            return docs

        pairs = [[query, doc.page_content] for doc in docs]
        scores = self.reranker.predict(pairs)
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in ranked[:self.RERANK_TOP_K]]

    def search(self, query: str) -> str:
        """完整 RAG：改写 → 粗筛 → 过滤 → 精排 → LLM 生成"""

        # 1. Query Rewriting
        search_query = self._rewrite_query(query)

        # 2. 向量粗筛 20 条
        docs_with_score = self.vector_store.search_with_score(search_query, k=self.INITIAL_K)

        # 3. 距离阈值过滤
        valid = [doc for doc, score in docs_with_score if score <= self.MAX_DISTANCE]

        # 4. 空结果兜底
        if not valid:
            return "当前题库暂未收录该问题。\n建议：换个方向提问，或联系管理员补充题目。"

        # 5. Rerank 精排取 top 3
        top_docs = self._rerank(query, valid)

        # 6. 拼参考资料
        context = ""
        for i, doc in enumerate(top_docs, start=1):
            source = doc.metadata.get("source", "未知")
            context += f"【来源{i}】出处: {source}\n内容: {doc.page_content}\n\n"

        # 7. LLM 生成 + 引用验证
        chain = self.prompt_template | self.model | StrOutputParser()
        answer = chain.invoke({"input": query, "context": context})

        # 8. 验证引用是否真实存在
        check = self._verify_citations(answer, len(top_docs))
        if not check["pass"]:
            fixed_context = (
                f"{context}\n\n注意：你上一轮回答引用了不存在的来源编号：{check['fake']}。"
                f"可用的来源编号范围是 1 到 {len(top_docs)}。请移除虚假引用后重新生成。"
            )
            answer = chain.invoke({"input": query, "context": fixed_context})
        return answer

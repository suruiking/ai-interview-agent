"""
RAG 回答服务：检索 → 阈值过滤 → 拼 prompt → 调 LLM → 带引用回答
"""
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from rag.vector_store import VectorStoreService
from model.factory import chat_model
from pathlib import Path


class RagService:
    # ChromaDB 返回的是 L2 距离，越小越相似。0.8 以上视为不相关
    MAX_DISTANCE = 0.8

    def __init__(self):
        self.vector_store = VectorStoreService()
        self.model = chat_model

        # 加载模板
        prompt_path = Path(__file__).parent.parent / "prompts" / "rag_prompt.txt"
        self.prompt_template = PromptTemplate.from_template(
            prompt_path.read_text(encoding="utf-8")
        )

    def search(self, query: str) -> str:
        """完整 RAG 流程：检索 → 过滤 → 拼 prompt → LLM 生成"""

        # 1. 带分数的检索（多取几条方便过滤）
        docs_with_score = self.vector_store.search_with_score(query, k=5)

        # 2. 距离阈值过滤（越小越相似）
        valid = [(doc, score) for doc, score in docs_with_score if score <= self.MAX_DISTANCE]

        # 3. 空结果兜底
        if not valid:
            return (
                "当前题库暂未收录该问题。\n"
                "建议：换个方向提问，或联系管理员补充题目。"
            )

        # 4. 拼接参考资料（带来源信息）
        context = ""
        for i, (doc, score) in enumerate(valid[:3], start=1):
            source = doc.metadata.get("source", "未知")
            match = "高度匹配" if score < 0.4 else ("相关" if score < 0.6 else "弱相关")
            context += f"【来源{i}】出处: {source}（{match}）\n内容: {doc.page_content}\n\n"

        # 5. 走 LLM 流水线
        chain = self.prompt_template | self.model | StrOutputParser()
        return chain.invoke({"input": query, "context": context})

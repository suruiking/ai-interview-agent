"""
向量库服务：加载文档 → 切块 → Embedding → 存 ChromaDB → 提供检索器
"""
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_chroma import Chroma
from model.factory import embed_model

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent
#知识文档
DATA_DIR = ROOT_DIR / "data"
#向量库
CHROMA_DIR = ROOT_DIR / "chroma_db"

# 切块配置
CHUNK_SIZE = 300      # 300 字一块，适合 Q&A 条目
CHUNK_OVERLAP = 30    # 块间重叠 30 字，防止关键句被切断


class VectorStoreService:
    """封装 ChromaDB 向量库的加载和检索"""

    def __init__(self):
        self.vector_store = self._build_or_load()

    def _build_or_load(self):
        """如果本地已有向量库就直接加载，否则从文档创建新的"""
        if CHROMA_DIR.exists() and any(CHROMA_DIR.iterdir()):
            return Chroma(
                persist_directory=str(CHROMA_DIR),
                embedding_function=embed_model,
            )

        # 1. 加载所有文档
        documents = []
        for file_path in DATA_DIR.iterdir():
            if file_path.suffix in (".txt", ".md"):
                loader = TextLoader(str(file_path), encoding="utf-8")
                documents.extend(loader.load())

        if not documents:
            raise FileNotFoundError(f"数据文件夹 {DATA_DIR} 中没有 txt/md 文档")

        # 2. 切块
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", "。", "！", "？", "，", " ", ""],
        )
        chunks = splitter.split_documents(documents)

        # 3. 文本向量化 → 写入本地 Chroma 向量库     
        vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=embed_model,
            persist_directory=str(CHROMA_DIR),
        )

        return vector_store

    def get_retriever(self, k: int = 5):
        """普通检索"""
        return self.vector_store.as_retriever(search_kwargs={"k": k})

    def search_with_score(self, query: str, k: int = 5):
        """带分数的语义检索"""
        return self.vector_store.similarity_search_with_score(query, k=k)

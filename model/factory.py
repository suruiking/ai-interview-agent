"""
模型工厂：聊天用 DeepSeek，向量用千问
"""
import os
from dotenv import load_dotenv, find_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import DashScopeEmbeddings
import yaml
from pathlib import Path

load_dotenv(find_dotenv())

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "rag.yml"
with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
    _config = yaml.safe_load(f)

chat_model = ChatOpenAI(
    model=_config["chat_model_name"],
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
    temperature=0.7,
    max_tokens=4000,
)

embed_model = DashScopeEmbeddings(model=_config["embedding_model_name"])

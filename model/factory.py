"""
模型工厂：聊天用 DeepSeek，向量用千问
"""
#读取环境变量
import os
#加载系统环境变量
from dotenv import load_dotenv, find_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import DashScopeEmbeddings
#解析 YAML 格式配置文件，转为 Python 字典
import yaml
#处理文件和文件夹路径
from pathlib import Path

load_dotenv(find_dotenv())

 #拼接配置文件完整路径
_CONFIG_PATH = Path(__file__).parent.parent / "config" / "rag.yml"
# 读取并解析 yml 配置
with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
    _config = yaml.safe_load(f)

#聊天模型
chat_model = ChatOpenAI(
    model=_config["chat_model_name"],
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
    temperature=0.7,
    max_tokens=4000,
)

#向量模型
embed_model = DashScopeEmbeddings(model=_config["embedding_model_name"])

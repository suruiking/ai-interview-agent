"""加载提示词模板"""
from pathlib import Path

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"


def load_system_prompts() -> str:
    """加载主提示词"""
    path = _PROMPT_DIR / "main_prompt.txt"
    if not path.exists():
        return "你是一个 AI 面试辅导 Agent，帮助用户准备技术面试。"
    return path.read_text(encoding="utf-8")


def load_rag_prompts() -> str:
    """加载 RAG 提示词模板"""
    path = _PROMPT_DIR / "rag_prompt.txt"
    if not path.exists():
        return "你是专注于面试辅导的AI助手。\n参考资料：{context}\n用户提问：{input}\n请基于参考资料回答。"
    return path.read_text(encoding="utf-8")

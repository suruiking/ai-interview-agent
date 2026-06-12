"""
自研工具层：面试辅导 Agent 的 5 个工具
纯 Python 函数 + JSON Schema + TOOL_HANDLERS 分发字典
"""
import random
from rag.rag_service import RagService
from model.factory import chat_model
from mcp.mcp_manager import connect_mcp

rag = RagService()

# 知识点列表（自动从题库提取太难 → 手维护一份）
TOPICS = [
    "LLM 基础原理（Transformer、Attention、Tokenizer）",
    "Agent 范式（ReAct、Reflection、Plan-Execute、Multi-Agent）",
    "RAG 全流程（Chunk、Embedding、Retrieval、Rerank）",
    "Prompt 工程（Few-Shot、CoT、ReAct、结构化输出、动态切换）",
    "Function Calling 与 MCP 协议",
    "Python 异步工程（async/await、SSE、asyncio）",
    "Agent 工程化（权限、Hook、上下文压缩、长期记忆）",
    "系统设计（AI 应用架构、Harness 底层）",
]

# 题目模板
QUESTION_TEMPLATES = [
    "请解释 {topic} 的核心原理，并举一个实际应用场景。",
    "你项目中用到了 {topic} 吗？具体是怎么实现的？",
    "如果让你从零实现 {topic}，你会怎么设计？有哪些坑？",
    "对比一下 {topic} 的几种实现方案，各自的优缺点是什么？",
    "{topic} 在生产环境中会遇到什么问题？怎么解决？",
    "面试官问你 {topic}，你打算怎么回答？请组织一段 2 分钟的表述。",
]


# ==================== 工具函数 ====================

def rag_search(query: str) -> str:
    """从面试题库检索专业知识"""
    return rag.search(query)


def ask_question(topic: str = "") -> str:
    """随机出一道面试题"""
    if not topic or topic not in str(TOPICS):
        topic = random.choice(TOPICS)
    template = random.choice(QUESTION_TEMPLATES)
    return f"【{topic}】\n{template.format(topic=topic)}"


def evaluate_answer(question: str, user_answer: str) -> str:
    """点评用户的回答"""
    prompt = f"""你是一个专业的面试评分官。请点评以下回答。

## 面试题目
{question}

## 答题者回答
{user_answer}

## 请从以下 3 个维度评分（每项 1-10 分）：
1. **准确性**：回答是否准确、没有事实性错误
2. **完整性**：是否覆盖了题目要求的要点
3. **表达结构**：是否逻辑清晰、有层次

## 输出格式：
  准确性：X/10 — 简要说明
  完整性：X/10 — 简要说明
  表达结构：X/10 — 简要说明
  改进建议：（1-2 条具体建议）"""

    response = chat_model.invoke(prompt)
    return response.content.strip()


def analyze_resume(resume_text: str, jd_text: str = "") -> str:
    """分析简历和岗位的匹配度"""
    jd_section = f"\n## 岗位要求\n{jd_text}" if jd_text else ""
    prompt = f"""你是职业规划顾问。请分析以下简历与目标岗位的匹配情况。

## 求职者简历
{resume_text}{jd_section}

## 请输出：
1. **匹配点**：（简历中哪些内容符合岗位要求）
2. **差距**：（岗位要求中哪些是简历没有体现的）
3. **简历优化建议**：（2-3 条具体修改建议）
4. **准备重点**：（面试中最可能被追问的方向）"""

    response = chat_model.invoke(prompt)
    return response.content.strip()


def get_topics() -> str:
    """列出知识库覆盖的知识点"""
    return "当前题库覆盖以下方向：\n" + "\n".join(f"  - {t}" for t in TOPICS)


# ==================== TOOLS：给 LLM 看的工具描述 ====================
TOOLS = [
    {
        "name": "rag_search",
        "description": "从 AI 面试知识库检索专业资料。参数 query 为检索关键词。回答会标注来源编号。",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "检索关键词"}},
            "required": ["query"],
        },
    },
    {
        "name": "ask_question",
        "description": "随机出一道面试题供用户练习。可选参数 topic 指定知识点方向，不填则随机。",
        "input_schema": {
            "type": "object",
            "properties": {"topic": {"type": "string", "description": "知识点方向"}},
            "required": [],
        },
    },
    {
        "name": "evaluate_answer",
        "description": "从准确性、完整性、表达结构三个维度点评用户回答，给出 1-10 评分和改进建议。",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "原面试题"},
                "user_answer": {"type": "string", "description": "用户的回答"},
            },
            "required": ["question", "user_answer"],
        },
    },
    {
        "name": "analyze_resume",
        "description": "分析简历与岗位要求的匹配度，列出匹配点、差距和优化建议。",
        "input_schema": {
            "type": "object",
            "properties": {
                "resume_text": {"type": "string", "description": "简历全文"},
                "jd_text": {"type": "string", "description": "岗位 JD 全文（可选）"},
            },
            "required": ["resume_text"],
        },
    },
    {
        "name": "get_topics",
        "description": "列出当前题库覆盖的所有知识点方向。",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "connect_mcp",
        "description": "连接外部 MCP 工具服务器（question-bank: 题库服务器, code-runner: 代码执行沙箱）。连上后自动获得服务器上的工具。",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "服务器名"}},
            "required": ["name"],
        },
    },
]

# ==================== TOOL_HANDLERS：执行分发字典 ====================
TOOL_HANDLERS = {
    "rag_search": rag_search,
    "ask_question": ask_question,
    "evaluate_answer": evaluate_answer,
    "analyze_resume": analyze_resume,
    "get_topics": get_topics,
    "connect_mcp": connect_mcp,
}

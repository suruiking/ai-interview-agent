"""
MCP 工具管理器：动态连接外部工具服务器，自动发现工具并拼入工具池。
教学版用 mock 服务器，真实 MCP 用 stdio + JSON-RPC。
"""
import re
import random

mcp_clients: dict[str, "MCPClient"] = {}
_DISALLOWED = re.compile(r'[^a-zA-Z0-9_-]')


class MCPClient:
    """MCP 工具服务器客户端（mock）"""

    def __init__(self, name: str):
        self.name = name
        self.tools: list[dict] = []
        self._handlers: dict[str, callable] = {}

    def register(self, tool_defs: list[dict], handlers: dict[str, callable]):
        self.tools = tool_defs
        self._handlers = handlers

    def call_tool(self, tool_name: str, args: dict) -> str:
        handler = self._handlers.get(tool_name)
        if not handler:
            return f"MCP 错误: 未知工具 '{tool_name}'"
        try:
            return handler(**args)
        except Exception as e:
            return f"MCP 错误: {e}"


def _normalize(name: str) -> str:
    return _DISALLOWED.sub('_', name)


def connect_mcp(name: str) -> str:
    """连接外部 MCP 工具服务器，自动发现工具"""
    if name in mcp_clients:
        return f"MCP 服务器 '{name}' 已连接"

    factory = _MOCK_SERVERS.get(name)
    if not factory:
        available = ", ".join(_MOCK_SERVERS.keys())
        return f"未知服务器 '{name}'。可用: {available}"

    client = factory()
    mcp_clients[name] = client
    tool_names = [t["name"] for t in client.tools]
    return f"已连接 '{name}'。发现 {len(client.tools)} 个工具: {tool_names}"


def assemble_tool_pool(builtin_tools: list[dict], builtin_handlers: dict) -> tuple[list[dict], dict]:
    """内置工具 + 所有已连 MCP 工具 → 拼成完整工具池"""
    tools = list(builtin_tools)
    handlers = dict(builtin_handlers)
    for server_name, client in mcp_clients.items():
        safe_srv = _normalize(server_name)
        for t in client.tools:
            prefixed = f"mcp__{safe_srv}__{_normalize(t['name'])}"
            tools.append({
                "name": prefixed,
                "description": t.get("description", ""),
                "input_schema": t.get("input_schema", {}),
            })
            handlers[prefixed] = (
                lambda *, c=client, tn=t["name"], **kw: c.call_tool(tn, kw))
    return tools, handlers


# ==================== Mock MCP 服务器 ====================

def _mock_server_question_bank():
    """Mock：面试题库服务器"""
    client = MCPClient("question-bank")
    questions = [
        "请解释 Transformer 的 Self-Attention 机制",
        "ReAct 和 Plan-Execute 范式有什么区别",
        "RAG 管道中 Rerank 的作用是什么",
        "长期记忆和短期上下文的区别",
        "MCP 协议解决了什么问题",
    ]
    client.register(
        tool_defs=[
            {"name": "get_random_question",
             "description": "从题库随机抽取一道面试题。(readOnly)",
             "input_schema": {"type": "object",
                              "properties": {"topic": {"type": "string"}},
                              "required": []}},
            {"name": "get_hot_topics",
             "description": "获取近期面试热点话题。(readOnly)",
             "input_schema": {"type": "object", "properties": {},
                              "required": []}},
        ],
        handlers={
            "get_random_question": lambda topic="": random.choice(questions),
            "get_hot_topics": lambda: "Agent/RAG/MCP 是当前 AI 应用开发面试三大热点",
        },
    )
    return client


def _mock_server_code_runner():
    """Mock：代码执行服务器"""
    client = MCPClient("code-runner")
    client.register(
        tool_defs=[
            {"name": "run_python",
             "description": "在沙箱执行 Python 代码并返回结果。(destructive)",
             "input_schema": {"type": "object",
                              "properties": {"code": {"type": "string"}},
                              "required": ["code"]}},
        ],
        handlers={
            "run_python": lambda code: f"[沙箱输出]\n>>> {code.split(chr(10))[0]}\n42",
        },
    )
    return client


_MOCK_SERVERS = {
    "question-bank": _mock_server_question_bank,
    "code-runner": _mock_server_code_runner,
}

"""
MCP 工具管理器：动态连接外部工具服务器，自动发现工具并拼入工具池。
支持 mock（函数回调）和真实 stdio（子进程 + JSON-RPC）两种模式。
"""
import re
import json
import random
import subprocess
import sys
from pathlib import Path

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


class StdioMCPClient(MCPClient):
    """真实 MCP 客户端：启动子进程，通过 stdin/stdout JSON-RPC 通信"""

    def __init__(self, name: str, command: list[str]):
        super().__init__(name)
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        # 初始化握手
        init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05",
                               "capabilities": {}, "clientInfo": {"name": "agent"}}}
        self._send(init_req)
        resp = self._read()
        if "error" in resp:
            raise RuntimeError(f"MCP 握手失败: {resp['error']}")

        # 发现工具
        tools_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        self._send(tools_req)
        tools_resp = self._read()
        tool_list = tools_resp.get("result", {}).get("tools", [])
        self.register(
            tool_defs=[{
                "name": t["name"], "description": t.get("description", ""),
                "input_schema": t.get("inputSchema", {}),
            } for t in tool_list],
            handlers={},
        )

    def _send(self, data: dict):
        self.process.stdin.write(json.dumps(data) + "\n")
        self.process.stdin.flush()

    def _read(self) -> dict:
        line = self.process.stdout.readline()
        return json.loads(line)

    def call_tool(self, tool_name: str, args: dict) -> str:
        req = {"jsonrpc": "2.0", "id": 100, "method": "tools/call",
               "params": {"name": tool_name, "arguments": args}}
        self._send(req)
        resp = self._read()
        content = resp.get("result", {}).get("content", [])
        return "\n".join(c.get("text", "") for c in content)


def connect_mcp(name: str) -> str:
    """连接外部 MCP 工具服务器，自动发现工具。先查真实连接，再查 mock"""
    if name in mcp_clients:
        return f"MCP 服务器 '{name}' 已连接"

    # 真实 stdio MCP 服务器
    if name == "coding-tools":
        server_path = Path(__file__).parent / "coding_server.py"
        try:
            client = StdioMCPClient(name, [sys.executable, str(server_path)])
            mcp_clients[name] = client
            tool_names = [t["name"] for t in client.tools]
            return f"已连接 '{name}'（真实进程）。发现 {len(client.tools)} 个工具: {tool_names}"
        except Exception as e:
            return f"连接 '{name}' 失败: {e}"

    # Mock 服务器
    factory = _MOCK_SERVERS.get(name)
    if not factory:
        available = ", ".join(list(_MOCK_SERVERS.keys()) + ["coding-tools (真实)"])
        return f"未知服务器 '{name}'。可用: {available}"

    client = factory()
    mcp_clients[name] = client
    tool_names = [t["name"] for t in client.tools]
    return f"已连接 '{name}'（mock）。发现 {len(client.tools)} 个工具: {tool_names}"


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

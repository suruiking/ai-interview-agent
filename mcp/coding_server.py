"""
真正的 stdio MCP 服务器 — 提供代码分析工具
Agent 启动这个进程，通过 JSON-RPC 通信。
"""
import sys
import json
import subprocess


def _send(data: dict):
    """发 JSON-RPC 消息到 stdout"""
    sys.stdout.write(json.dumps(data) + "\n")
    sys.stdout.flush()


def _read():
    """从 stdin 读一行 JSON-RPC 消息"""
    return json.loads(sys.stdin.readline())


def handle_request(req: dict):
    """分发 JSON-RPC 请求"""
    method = req.get("method", "")
    req_id = req.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "coding-tools", "version": "1.0"},
            "capabilities": {"tools": {}},
        }}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": [
            {"name": "count_lines",
             "description": "统计代码文件行数。(readOnly)",
             "inputSchema": {"type": "object",
                             "properties": {"filepath": {"type": "string"}},
                             "required": ["filepath"]}},
            {"name": "check_syntax",
             "description": "检查 Python 文件语法。(readOnly)",
             "inputSchema": {"type": "object",
                             "properties": {"filepath": {"type": "string"}},
                             "required": ["filepath"]}},
            {"name": "run_tests",
             "description": "运行 pytest 测试。(destructive)",
             "inputSchema": {"type": "object",
                             "properties": {"path": {"type": "string"}},
                             "required": ["path"]}},
        ]}}

    if method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        if tool_name == "count_lines":
            try:
                with open(tool_args["filepath"], "r") as f:
                    count = len(f.readlines())
                result = [{"type": "text", "text": f"文件共 {count} 行"}]
            except Exception as e:
                result = [{"type": "text", "text": f"错误: {e}"}]

        elif tool_name == "check_syntax":
            try:
                subprocess.run(["python", "-m", "py_compile", tool_args["filepath"]],
                               capture_output=True, timeout=10, check=True)
                result = [{"type": "text", "text": "语法检查通过 ✓"}]
            except subprocess.CalledProcessError as e:
                result = [{"type": "text", "text": f"语法错误:\n{e.stderr.decode()}"}]
            except Exception as e:
                result = [{"type": "text", "text": f"检查失败: {e}"}]

        elif tool_name == "run_tests":
            try:
                r = subprocess.run(["pytest", tool_args["path"], "-q"],
                                   capture_output=True, text=True, timeout=30)
                result = [{"type": "text", "text": r.stdout + r.stderr}]
            except subprocess.TimeoutExpired:
                result = [{"type": "text", "text": "测试超时 (30s)"}]
            except Exception as e:
                result = [{"type": "text", "text": f"运行失败: {e}"}]
        else:
            result = [{"type": "text", "text": f"未知工具: {tool_name}"}]

        return {"jsonrpc": "2.0", "id": req_id, "result": {"content": result}}

    return {"jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": f"未知方法: {method}"}}


if __name__ == "__main__":
    # 初始化握手
    init_req = _read()
    _send(handle_request(init_req))

    # 循环处理请求
    for line in sys.stdin:
        try:
            req = json.loads(line.strip())
            resp = handle_request(req)
            _send(resp)
        except json.JSONDecodeError:
            continue
        except EOFError:
            break

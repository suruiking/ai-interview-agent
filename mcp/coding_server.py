"""
真正的 stdio MCP 服务器 — 提供代码分析工具
Agent 启动这个进程，通过 JSON-RPC 通信。
"""
import sys
import json
import subprocess

#发消息去客户端和接收客户端消息。还有处理客户端请求

def _send(data: dict):
    """发 JSON-RPC 消息到 stdout"""
    #转字符串，向标准输出写字符串
    sys.stdout.write(json.dumps(data) + "\n")
    #刷新缓冲区
    sys.stdout.flush()


def _read():
    """从 stdin 读一行 JSON-RPC 消息"""
    #从标准输入读取一行
    return json.loads(sys.stdin.readline())


#接收客户端发来的完整 RPC 请求字典，根据 method（调用方法名）分发到不同逻辑处理。
def handle_request(req: dict):
    """分发 JSON-RPC 请求"""
    #取出请求中的方法和id
    method = req.get("method", "")
    req_id = req.get("id")

    #客户端启动后首先会发初始化请求
    if method == "initialize":
        #返回协议版本，回传id，结果
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "protocolVersion": "2024-11-05",#mcp版本协议
            "serverInfo": {"name": "coding-tools", "version": "1.0"},#服务名，版本。
            "capabilities": {"tools": {}},#服务能力
        }}
    
    #列出所有可用工具
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
    
    #客户端指定调用某个工具
    if method == "tools/call":
        params = req.get("params", {})#参数包
        tool_name = params.get("name", "")#工具名
        tool_args = params.get("arguments", {})#工具的入参
        
        #统计文件行数
        if tool_name == "count_lines":
            try:
                with open(tool_args["filepath"], "r") as f:
                    count = len(f.readlines())
                result = [{"type": "text", "text": f"文件共 {count} 行"}]
            except Exception as e:
                result = [{"type": "text", "text": f"错误: {e}"}]
        
        #Python 语法检查
        elif tool_name == "check_syntax":
            try:
                subprocess.run(["python", "-m", "py_compile", tool_args["filepath"]],
                               capture_output=True, timeout=10, check=True)
                result = [{"type": "text", "text": "语法检查通过 ✓"}]
            except subprocess.CalledProcessError as e:
                result = [{"type": "text", "text": f"语法错误:\n{e.stderr.decode()}"}]
            except Exception as e:
                result = [{"type": "text", "text": f"检查失败: {e}"}]
        
        #运行 pytest 测试
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
    #先读取客户端第一条 initialize 握手请求。
    init_req = _read()
    #处理请求、返回握手响应
    _send(handle_request(init_req))

    # 循环处理请求
    for line in sys.stdin:
        try:
            req = json.loads(line.strip())#解析请求
            resp = handle_request(req)#路由处理
            _send(resp)#发送结果
        except json.JSONDecodeError:
            continue
        except EOFError:
            break

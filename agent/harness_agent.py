"""
自研 Agent 引擎：ReAct 循环 + 工具分发 + 流式输出 + 长期记忆
"""
import json
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent.tools.harness_tools import TOOLS, TOOL_HANDLERS
from memory.memory_manager import read_memory_index, extract_memories
from agent.context_compact import prepare_context

MAX_TURNS = 8

# ===== s03：权限三道门 =====
_DENY_LIST = ["delete", "drop", "rm ", "sudo", "shutdown"]
_DESTRUCTIVE_TOOLS = ["write_file", "edit_file", "bash"]  # 本 Agent 没这些工具，但预留

def _check_permission(tool_name: str, tool_args: dict) -> str | None:
    """三道门安全检查。返回 None=通过，返回字符串=拒绝原因"""
    # ① 硬黑名单
    for keyword in _DENY_LIST:
        if keyword in str(tool_args).lower():
            return f"操作含危险关键词 '{keyword}'"

    # ② 破坏性工具（当前 Agent 不会用到，但架构预留）
    if tool_name in _DESTRUCTIVE_TOOLS:
        return f"工具 '{tool_name}' 当前不在允许列表中"

    # ③ 敏感操作 flag
    if tool_name == "analyze_resume" and len(str(tool_args.get("resume_text", ""))) > 10000:
        return "简历文本过长（>10000字），请精简后再试"

    return None  # 通过


class HarnessAgent:

    def __init__(self):
        self.model = chat_model
        base_prompt = load_system_prompts()
        memories = read_memory_index()
        if memories:
            base_prompt += (
                f"\n\n## 长期记忆（用户历史和偏好）\n"
                f"{memories}\n"
                f"根据以上记忆调整出题方向和点评重点。"
            )
        self.system_prompt = base_prompt

    def _build_tools(self) -> list[dict]:
        """TOOLS → OpenAI tools 格式"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in TOOLS
        ]

    def _parse_tool_calls(self, response) -> list[dict]:
        """从 LLM 回复里提取 tool call（带 id）"""
        tool_calls = []

        # 方式1：标准 OpenAI tools 格式 response.tool_calls
        if hasattr(response, "tool_calls") and response.tool_calls:
            for tc in response.tool_calls:
                tc_id = getattr(tc, "id", "") if hasattr(tc, "id") else ""
                if hasattr(tc, "function"):
                    func = tc.function
                    name = getattr(func, "name", "")
                    args_str = getattr(func, "arguments", "{}")
                elif isinstance(tc, dict):
                    tc_id = tc.get("id", tc_id)
                    func = tc.get("function", tc)
                    name = func.get("name", tc.get("name", ""))
                    args_str = func.get("arguments", tc.get("arguments", "{}"))
                else:
                    continue
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append({"id": tc_id, "name": name, "arguments": args})
            return tool_calls

        # 方式2：additional_kwargs（千问 ChatTongyi）
        ak = getattr(response, "additional_kwargs", {})
        raw = ak.get("tool_calls", [])
        for tc in raw:
            func = tc.get("function", {})
            name = func.get("name", "")
            args_str = func.get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                args = {}
            tool_calls.append({"name": name, "arguments": args})

        return tool_calls

    def execute_stream(self, query: str):
        """流式执行，跟 Streamlit 兼容"""

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": query},
        ]

        for _ in range(MAX_TURNS):
            # 每轮前压缩上下文
            messages = prepare_context(messages)

            # 调 LLM
            response = self.model.invoke(
                messages,
                tools=self._build_tools(),
                tool_choice="auto",
            )

            content = response.content if hasattr(response, "content") else ""

            # 没调工具 → 最终回答，流式吐出
            tool_calls = self._parse_tool_calls(response)
            if not tool_calls:
                if content:
                    yield content + "\n"
                break

            # 存助手消息（带 tool_calls）
            msg = {"role": "assistant", "content": content or ""}
            if hasattr(response, "tool_calls") and response.tool_calls:
                msg["tool_calls"] = response.tool_calls
            messages.append(msg)

            # 调了工具 → 执行
            for tc in tool_calls:
                tool_name = tc["name"]
                tool_args = tc["arguments"]

                # s03：权限三道门 — 预防 LLM 幻觉调用危险操作
                blocked = _check_permission(tool_name, tool_args)
                if blocked:
                    result = f"权限拒绝：{blocked}"
                else:
                    handler = TOOL_HANDLERS.get(tool_name)
                    if handler:
                        try:
                            result = str(handler(**tool_args))
                        except Exception as e:
                            result = f"工具执行失败: {e}"
                    else:
                        result = f"未知工具: {tool_name}"

                # 结果喂回（带 tool_call_id 配对）
                messages.append({
                    "role": "tool",
                    "name": tool_name,
                    "tool_call_id": tc.get("id", ""),
                    "content": result,
                })

        # 对话结束后提取长期记忆
        dialogue = [m["content"] if isinstance(m.get("content"), str)
                    else str(m.get("content", "")) for m in messages]
        try:
            extract_memories(dialogue)
        except Exception:
            pass

        yield "\n\n> 以上是面试辅导 Agent 的回答。继续练习或问我新的问题。"

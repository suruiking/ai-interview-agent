"""
上下文压缩管道：四层瘦身，防止长对话撑爆 LLM 窗口。
L1 → L2 → L3 → L4，前三层免费，L4 调一次 LLM。
"""
import json
import time
from pathlib import Path
from model.factory import chat_model
from utils.logger import get_logger

logger = get_logger("compact")

TRANSCRIPT_DIR = Path(__file__).parent.parent / ".transcripts"
KEEP_RECENT = 3          # L2：保留最近 3 条完整 tool_result
MAX_MESSAGES = 40        # L1：消息超过 40 条就裁
CONTEXT_LIMIT = 30000    # 总字符数超过 3 万触发 L4


def _estimate_size(messages: list) -> int:
    """估算消息总大小"""
    return len(json.dumps(messages, default=str, ensure_ascii=False))


# ============== L1：消息数量裁剪 ==============
def snip_compact(messages: list) -> list:
    """消息超过 MAX_MESSAGES 条 → 保留头 3 + 尾 N，中间换一句话"""
    if len(messages) <= MAX_MESSAGES:
        return messages
    keep_head, keep_tail = 3, MAX_MESSAGES - 3
    snipped = len(messages) - keep_head - keep_tail
    return (messages[:keep_head]
            + [{"role": "user", "content": f"[已裁剪 {snipped} 条中间消息]"}]
            + messages[-keep_tail:])


# ============== L2：旧 tool_result 缩成占位符 ==============
def micro_compact(messages: list) -> list:
    """只保留最近 KEEP_RECENT 条 tool_result 完整内容，更早的改占位符"""
    found = []
    for mi, msg in enumerate(messages):
        if msg.get("role") != "tool":
            continue
        found.append((mi, msg))

    if len(found) <= KEEP_RECENT:
        return messages

    for mi, msg in found[:-KEEP_RECENT]:
        content = msg.get("content", "")
        if len(str(content)) > 120:
            messages[mi]["content"] = "[旧的工具结果已压缩，需要可重新执行。]"

    return messages


# ============== L3：超大 tool_result 写磁盘 ==============
def tool_result_budget(messages: list) -> list:
    """单条 tool_result 超过 5000 字符 → 写磁盘，内存只留预览"""
    last = messages[-1] if messages else None
    if not last or last.get("role") != "tool":
        return messages

    content = last.get("content", "")
    if len(str(content)) <= 5000:
        return messages

    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    path = TRANSCRIPT_DIR / f"tool_result_{int(time.time())}.txt"
    path.write_text(str(content), encoding="utf-8")
    messages[-1]["content"] = (
        f"[完整输出已保存到 {path}]\n预览:{str(content)[:500]}..."
    )
    return messages


# ============== L4：LLM 摘要 ==============
def compact_history(messages: list) -> list:
    """调 LLM 把全部对话总结成一段摘要"""
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    backup = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.jsonl"
    backup.write_text(
        json.dumps(messages, default=str, ensure_ascii=False),
        encoding="utf-8"
    )

    conversation = json.dumps(messages, default=str, ensure_ascii=False)[:12000]
    prompt = (
        "总结这段面试辅导对话，保留：1) 练了哪些方向 2) 用户表现和弱项 "
        "3) 尚未完成的事。尽量精简。\n\n" + conversation
    )
    try:
        response = chat_model.invoke(prompt)
        summary = response.content.strip() if hasattr(response, "content") else str(response)
    except Exception:
        summary = "对话过长已压缩。"

    return [{"role": "user", "content": f"[对话已压缩]\n\n{summary}"}]


# ============== 总入口：每轮前跑一遍 ==============
def prepare_context(messages: list) -> list:
    """四层压缩：便宜的先上，贵的最后用"""
    messages[:] = tool_result_budget(messages)   # L3：先处理超大单条
    messages[:] = micro_compact(messages)         # L2：旧结果占位符
    messages[:] = snip_compact(messages)          # L1：消息数量裁剪

    if _estimate_size(messages) > CONTEXT_LIMIT:
        logger.warning("触发 L4 LLM 摘要压缩（消息总大小 %d 字）", _estimate_size(messages))
        messages[:] = compact_history(messages)

    return messages

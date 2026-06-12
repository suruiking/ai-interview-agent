"""
长期记忆系统：对话后提取关键信息，存 .memory/，下次启动自动注入。
"""
import json
from pathlib import Path
from model.factory import chat_model

MEMORY_DIR = Path(__file__).parent.parent / ".memory"
MEMORY_DIR.mkdir(exist_ok=True)
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """拆出 YAML 头和正文"""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, parts[2].strip()


def write_memory(name: str, mem_type: str, description: str, body: str):
    """写一条记忆文件（带 YAML 头）"""
    slug = name.lower().replace(" ", "-")
    (MEMORY_DIR / f"{slug}.md").write_text(
        f"---\nname: {name}\ndescription: {description}\ntype: {mem_type}\n---\n\n{body}\n",
        encoding="utf-8"
    )
    _rebuild_index()


def _rebuild_index():
    """重建 MEMORY.md 索引"""
    lines = []
    for f in sorted(MEMORY_DIR.glob("*.md")):
        if f.name == "MEMORY.md":
            continue
        raw = f.read_text(encoding="utf-8")
        meta, _ = _parse_frontmatter(raw)
        name = meta.get("name", f.stem)
        desc = meta.get("description", "")
        lines.append(f"- [{name}]({f.name}) — {desc}")
    MEMORY_INDEX.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")


def read_memory_index() -> str:
    """读 MEMORY.md 索引"""
    if not MEMORY_INDEX.exists():
        return ""
    return MEMORY_INDEX.read_text(encoding="utf-8").strip()


def extract_memories(dialogue: list[str]):
    """从一轮对话中提取弱项和偏好"""
    text = "\n".join(dialogue[-30:])  # 取最近 30 条
    if not text.strip():
        return

    existing = ""
    if MEMORY_INDEX.exists():
        existing = MEMORY_INDEX.read_text(encoding="utf-8")[:1000]

    prompt = f"""从以下面试辅导对话中提取用户的关键信息。
返回 JSON 数组，每项：{{"name":"kebab-case标识","type":"weakness/preference","description":"一句话","body":"完整细节"}}。

如果对话中没有任何值得长期记录的信息，返回 []。

已有记忆：
{existing}

对话：
{text[:3000]}"""

    try:
        response = chat_model.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        # 抠出 JSON
        start = content.find("[")
        end = content.rfind("]") + 1
        if start >= 0 and end > start:
            items = json.loads(content[start:end])
            for item in items:
                if item.get("description") and item.get("body"):
                    write_memory(
                        name=item.get("name", "memory"),
                        mem_type=item.get("type", "weakness"),
                        description=item.get("description", ""),
                        body=item.get("body", ""),
                    )
    except Exception:
        pass

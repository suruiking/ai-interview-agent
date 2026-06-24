"""
长期记忆系统：对话后提取关键信息，存 .memory/，下次启动自动注入。

.memory/
├── MEMORY.md          ← 唯一的总索引文件（目录清单）
├── pointer-mistake.md ← 单条记忆文件1
├── prefer-code-example.md ← 单条记忆文件2
└── weak-network-basics.md ← 单条记忆文件3
"""
import json
from pathlib import Path
from model.factory import chat_model
from utils.logger import get_logger

logger = get_logger("memory")

MEMORY_DIR = Path(__file__).parent.parent / ".memory"
MEMORY_DIR.mkdir(exist_ok=True)
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"

#返回字典和正文
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

"""
---
name: 原始名称
description: 描述内容
type: 记忆类型
---
正文内容
"""
#记忆名字，类型，描述，正文
def write_memory(name: str, mem_type: str, description: str, body: str):
    """写一条记忆文件（带 YAML 头）"""
    #生成安全文件名 slug
    slug = name.lower().replace(" ", "-")
    (MEMORY_DIR / f"{slug}.md").write_text(
        f"---\nname: {name}\ndescription: {description}\ntype: {mem_type}\n---\n\n{body}\n",
        encoding="utf-8"
    )
    _rebuild_index()


def _rebuild_index():
    """更新 MEMORY.md 索引"""
    lines = []
    #遍历目录下所有 .md 文件
    for f in sorted(MEMORY_DIR.glob("*.md")):
        #跳过索引文件自身
        if f.name == "MEMORY.md":
            continue
        #读取文件 + 解析元数据
        raw = f.read_text(encoding="utf-8")
        meta, _ = _parse_frontmatter(raw)
        #提取名称和描述
        name = meta.get("name", f.stem)
        desc = meta.get("description", "")
        #拼接
        lines.append(f"- [{name}]({f.name}) — {desc}")
    #写入索引文件
    MEMORY_INDEX.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")


def read_memory_index() -> str:
    """读 MEMORY.md 索引"""
    if not MEMORY_INDEX.exists():
        return ""
    return MEMORY_INDEX.read_text(encoding="utf-8").strip()

#分析历史对话 → 提炼用户弱项 / 偏好 → 自动生成本地记忆文件。
def extract_memories(dialogue: list[str]):
    """从一轮对话中提取弱项和偏好"""
    text = "\n".join(dialogue[-30:])  # 取最近 30条
    if not text.strip():
        return
     
    #读取已有记忆，用于去重
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
    
    #调用大模型
    try:
        response = chat_model.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        # 从回复中获取纯json
        start = content.find("[")
        end = content.rfind("]") + 1
        if start >= 0 and end > start:
            items = json.loads(content[start:end])
            logger.info("提取到 %d 条长期记忆", len(items))
            #遍历结果，自动写入记忆文件
            for item in items:
                if item.get("description") and item.get("body"):
                    write_memory(
                        name=item.get("name", "memory"),
                        mem_type=item.get("type", "weakness"),
                        description=item.get("description", ""),
                        body=item.get("body", ""),
                    )
        else:
            logger.debug("长期记忆 LLM 返回格式无法解析 JSON")
    except json.JSONDecodeError as e:
        logger.warning("长期记忆 JSON 解析失败: %s", e)
    except Exception as e:
        logger.warning("长期记忆提取异常: %s", e)

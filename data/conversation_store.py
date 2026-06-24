"""
对话持久化：SQLite 存储，上限 50 场，超过自动清理最旧的
"""
import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "conversations.db"
MAX_CONVERSATIONS = 50


@contextmanager
def _get_db():
    """获取数据库连接，自动提交/关闭"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """建表（幂等）"""
    with _get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)


def create_conversation(title: str) -> int:
    """新建一场对话，返回 ID"""
    with _get_db() as conn:
        cur = conn.execute(
            "INSERT INTO conversations (title, created_at) VALUES (?, ?)",
            (title, time.time()),
        )
        return cur.lastrowid


def save_message(conversation_id: int, role: str, content: str):
    """存一条消息"""
    with _get_db() as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, time.time()),
        )


def get_conversation(conversation_id: int) -> dict:
    """读一场对话的所有消息"""
    with _get_db() as conn:
        conv = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            return {}
        msgs = conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
        return {
            "id": conv["id"],
            "title": conv["title"],
            "created_at": conv["created_at"],
            "messages": [{"role": m["role"], "content": m["content"]} for m in msgs],
        }


def list_conversations(limit: int = 50) -> list[dict]:
    """列出所有对话（最新的在前）"""
    with _get_db() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at FROM conversations ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"id": r["id"], "title": r["title"], "created_at": r["created_at"]}
            for r in rows
        ]


def delete_conversation(conversation_id: int):
    """删除一场对话及其消息"""
    with _get_db() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))


def trim_conversations():
    """超过上限时删最旧的"""
    with _get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        if count > MAX_CONVERSATIONS:
            excess = count - MAX_CONVERSATIONS
            old_ids = conn.execute(
                "SELECT id FROM conversations ORDER BY created_at ASC LIMIT ?",
                (excess,),
            ).fetchall()
            for row in old_ids:
                cid = row["id"]
                conn.execute("DELETE FROM messages WHERE conversation_id = ?", (cid,))
                conn.execute("DELETE FROM conversations WHERE id = ?", (cid,))

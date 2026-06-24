"""
日志系统：文件落盘 + 内存环形缓冲（给前端面板用）
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from collections import deque

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ── 内存环形缓冲：保留最近 200 条，前端面板读取 ──
log_buffer: deque = deque(maxlen=200)

# ── 格式 ──
FORMAT = logging.Formatter(
    "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%m-%d %H:%M:%S",
)


class BufferHandler(logging.Handler):
    """每条日志同时写入内存环形缓冲"""
    def emit(self, record):
        log_buffer.append(self.format(record))


def get_logger(name: str) -> logging.Logger:
    """获取模块级 logger，含 BufferHandler，方便前端展示"""
    logger = logging.getLogger(name)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # 终端输出（INFO 级别以上）
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(FORMAT)
    logger.addHandler(console)

    # 文件落盘（DEBUG 全量，按大小切割 10MB，保留 5 个）
    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(FORMAT)
    logger.addHandler(file_handler)

    # 内存环形缓冲（给 Streamlit 面板，DEBUG 全量）
    buf = BufferHandler()
    buf.setLevel(logging.DEBUG)
    buf.setFormatter(FORMAT)
    logger.addHandler(buf)

    return logger


def get_recent_logs(n: int = 50, level: str = "ALL") -> list[str]:
    """读取最近 N 条日志（前端面板调用）"""
    entries = list(log_buffer)
    if level != "ALL":
        entries = [e for e in entries if f"| {level} " in e]
    return entries[-n:]

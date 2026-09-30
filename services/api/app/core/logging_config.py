"""日志配置模块。

配置 Python logging RotatingFileHandler 以实现日志轮转：
- 单文件最大 10MB
- 保留 5 个备份文件
"""

from __future__ import annotations

import logging
import os
import queue
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path
from typing import Any


# 日志目录配置（支持 env 覆盖：容器内用 QUANT_LOG_DIR=/app/logs 挂载卷持久化）
LOG_DIR_API = Path(os.getenv("QUANT_LOG_DIR", "/home/djy/Quant/services/api/logs"))
# Freqtrade 日志目录（支持 env 覆盖，避免本地绝对路径硬编码）
LOG_DIR_FREQTRADE = Path(os.getenv("QUANT_FREQTRADE_LOG_DIR", "/home/djy/Quant/infra/freqtrade/user_data/logs"))

# 日志轮转配置
MAX_BYTES = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5  # 保留5个备份



class BoundedQueueHandler(QueueHandler):
    """日志输出阻塞时限制积压，避免请求线程跟着等待或无限占用内存。"""

    def __init__(self, log_queue) -> None:
        """记录被丢弃的日志数量，便于运维查看。"""
        super().__init__(log_queue)
        self.dropped_records = 0

    def enqueue(self, record) -> None:
        """队列已满时仅计数，不向可能同样阻塞的 stderr 写错误。"""
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            self.dropped_records += 1


def setup_logging(
    log_dir: Path | None = None,
    max_bytes: int = MAX_BYTES,
    backup_count: int = BACKUP_COUNT,
    level: int = logging.INFO,
) -> logging.Logger:
    """配置带 RotatingFileHandler 的日志系统。

    Args:
        log_dir: 日志目录路径
        max_bytes: 单文件最大大小（字节）
        backup_count: 保留的备份文件数量
        level: 日志级别

    Returns:
        配置好的根日志器
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 重复初始化直接复用，避免遗留日志线程和打开的文件。
    if any(isinstance(handler, BoundedQueueHandler) for handler in root_logger.handlers):
        return root_logger
    root_logger.handlers.clear()
    sinks = []

    # 确保日志目录存在
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"

        # 创建 RotatingFileHandler
        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)

        sinks.append(file_handler)

    # 添加控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    sinks.append(console_handler)

    # 文件和控制台都交给后台消费；Docker 日志管道阻塞也不能卡住事件循环。
    log_queue = queue.Queue(maxsize=max(1, int(os.getenv("QUANT_LOG_QUEUE_LIMIT", "1000"))))
    queue_handler = BoundedQueueHandler(log_queue)
    listener = QueueListener(log_queue, *sinks, respect_handler_level=True)
    queue_handler.listener = listener
    root_logger.addHandler(queue_handler)
    listener.start()

    return root_logger


def get_log_config() -> dict[str, Any]:
    """获取当前日志配置信息。

    Returns:
        日志配置字典
    """
    return {
        "max_bytes": MAX_BYTES,
        "max_bytes_mb": MAX_BYTES / (1024 * 1024),
        "backup_count": BACKUP_COUNT,
        "dropped_records": sum(
            handler.dropped_records for handler in logging.getLogger().handlers
            if isinstance(handler, BoundedQueueHandler)
        ),
        "log_dir_api": str(LOG_DIR_API),
        "log_dir_freqtrade": str(LOG_DIR_FREQTRADE),
    }


# 在模块导入时自动配置日志（可选）
if os.getenv("QUANT_AUTO_SETUP_LOGGING", "false").lower() == "true":
    setup_logging(LOG_DIR_API)
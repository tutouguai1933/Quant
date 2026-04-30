"""日志配置模块。

配置 Python logging RotatingFileHandler 以实现日志轮转：
- 单文件最大 10MB
- 保留 5 个备份文件
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


# 日志目录配置
LOG_DIR_API = Path("/home/djy/Quant/services/api/logs")
LOG_DIR_FREQTRADE = Path("/home/djy/Quant/infra/freqtrade/user_data/logs")

# 日志轮转配置
MAX_BYTES = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5  # 保留5个备份


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

    # 清除已有的 handlers
    root_logger.handlers.clear()

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
        root_logger.addHandler(file_handler)

    # 添加控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

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
        "log_dir_api": str(LOG_DIR_API),
        "log_dir_freqtrade": str(LOG_DIR_FREQTRADE),
    }


# 在模块导入时自动配置日志（可选）
if os.getenv("QUANT_AUTO_SETUP_LOGGING", "false").lower() == "true":
    setup_logging(LOG_DIR_API)
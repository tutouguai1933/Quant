"""清理旧日志脚本。

用于定期清理超过指定天数的日志文件，防止日志占用过多磁盘空间。
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


# 日志目录配置
LOG_DIRS = [
    Path("/home/djy/Quant/services/api/logs"),
    Path("/home/djy/Quant/infra/freqtrade/user_data/logs"),
]

# 默认保留天数
DEFAULT_DAYS_TO_KEEP = 30


def cleanup_old_logs(days_to_keep: int = DEFAULT_DAYS_TO_KEEP) -> dict[str, Any]:
    """清理超过指定天数的日志文件。

    Args:
        days_to_keep: 保留的日志天数，默认 30 天

    Returns:
        清理结果统计
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
    cutoff_timestamp = cutoff_time.timestamp()

    result = {
        "cutoff_date": cutoff_time.isoformat(),
        "days_to_keep": days_to_keep,
        "directories_processed": [],
        "files_deleted": 0,
        "bytes_freed": 0,
        "errors": [],
    }

    for log_dir in LOG_DIRS:
        dir_result = {
            "path": str(log_dir),
            "files_deleted": 0,
            "bytes_freed": 0,
        }

        if not log_dir.exists():
            dir_result["status"] = "not_found"
            result["directories_processed"].append(dir_result)
            continue

        try:
            for log_file in log_dir.iterdir():
                if not log_file.is_file():
                    continue

                # 检查文件修改时间
                try:
                    file_mtime = log_file.stat().st_mtime
                    file_size = log_file.stat().st_size

                    if file_mtime < cutoff_timestamp:
                        # 文件太旧，删除
                        log_file.unlink()
                        dir_result["files_deleted"] += 1
                        dir_result["bytes_freed"] += file_size
                        result["files_deleted"] += 1
                        result["bytes_freed"] += file_size

                except OSError as e:
                    result["errors"].append(
                        f"处理文件 {log_file} 时出错: {e}"
                    )

            dir_result["status"] = "success"
        except Exception as e:
            dir_result["status"] = "error"
            dir_result["error"] = str(e)
            result["errors"].append(f"处理目录 {log_dir} 时出错: {e}")

        result["directories_processed"].append(dir_result)

    # 格式化结果
    result["bytes_freed_mb"] = round(result["bytes_freed"] / (1024 * 1024), 2)

    return result


def get_log_sizes() -> dict[str, Any]:
    """获取各日志文件大小统计。

    Returns:
        日志文件大小统计
    """
    result = {
        "total_size_bytes": 0,
        "total_size_mb": 0.0,
        "directories": [],
        "oldest_file": None,
        "largest_file": None,
    }

    oldest_time = float("inf")
    largest_size = 0
    oldest_file_path = None
    largest_file_path = None

    for log_dir in LOG_DIRS:
        dir_result = {
            "path": str(log_dir),
            "exists": log_dir.exists(),
            "total_size_bytes": 0,
            "total_size_mb": 0.0,
            "files": [],
        }

        if not log_dir.exists():
            result["directories"].append(dir_result)
            continue

        try:
            for log_file in log_dir.iterdir():
                if not log_file.is_file():
                    continue

                try:
                    file_stat = log_file.stat()
                    file_size = file_stat.st_size
                    file_mtime = file_stat.st_mtime

                    file_info = {
                        "name": log_file.name,
                        "size_bytes": file_size,
                        "size_kb": round(file_size / 1024, 2),
                        "modified": datetime.fromtimestamp(
                            file_mtime, tz=timezone.utc
                        ).isoformat(),
                        "age_days": round(
                            (time.time() - file_mtime) / 86400, 1
                        ),
                    }

                    dir_result["files"].append(file_info)
                    dir_result["total_size_bytes"] += file_size

                    # 更新最大/最旧文件统计
                    if file_size > largest_size:
                        largest_size = file_size
                        largest_file_path = str(log_file)

                    if file_mtime < oldest_time:
                        oldest_time = file_mtime
                        oldest_file_path = str(log_file)

                except OSError:
                    pass  # 忽略无法访问的文件

            dir_result["total_size_mb"] = round(
                dir_result["total_size_bytes"] / (1024 * 1024), 2
            )
            result["total_size_bytes"] += dir_result["total_size_bytes"]

        except Exception as e:
            dir_result["error"] = str(e)

        result["directories"].append(dir_result)

    result["total_size_mb"] = round(
        result["total_size_bytes"] / (1024 * 1024), 2
    )

    if oldest_file_path:
        result["oldest_file"] = {
            "path": oldest_file_path,
            "modified": datetime.fromtimestamp(
                oldest_time, tz=timezone.utc
            ).isoformat(),
            "age_days": round((time.time() - oldest_time) / 86400, 1),
        }

    if largest_file_path:
        result["largest_file"] = {
            "path": largest_file_path,
            "size_bytes": largest_size,
            "size_mb": round(largest_size / (1024 * 1024), 2),
        }

    return result


def check_log_rotation_needed(max_size_mb: float = 50.0) -> dict[str, Any]:
    """检查是否需要日志轮转或清理。

    Args:
        max_size_mb: 最大允许的日志总大小（MB）

    Returns:
        检查结果和建议
    """
    log_sizes = get_log_sizes()

    result = {
        "current_total_mb": log_sizes["total_size_mb"],
        "threshold_mb": max_size_mb,
        "needs_cleanup": log_sizes["total_size_mb"] > max_size_mb,
        "recommendation": None,
    }

    if result["needs_cleanup"]:
        excess_mb = log_sizes["total_size_mb"] - max_size_mb
        result["recommendation"] = (
            f"日志总大小 {log_sizes['total_size_mb']:.2f}MB 超过阈值 "
            f"{max_size_mb:.2f}MB，建议清理 {excess_mb:.2f}MB"
        )
    else:
        result["recommendation"] = (
            f"日志大小正常，当前 {log_sizes['total_size_mb']:.2f}MB"
        )

    return result


if __name__ == "__main__":
    # 直接运行脚本时的示例
    import argparse

    parser = argparse.ArgumentParser(description="日志清理工具")
    parser.add_argument(
        "--status",
        action="store_true",
        help="显示日志大小统计",
    )
    parser.add_argument(
        "--cleanup",
        type=int,
        nargs="?",
        const=DEFAULT_DAYS_TO_KEEP,
        default=None,
        help="清理超过指定天数的日志（默认 30 天）",
    )
    parser.add_argument(
        "--check",
        type=float,
        nargs="?",
        const=50.0,
        default=None,
        help="检查是否需要清理（默认阈值 50MB）",
    )

    args = parser.parse_args()

    if args.status:
        sizes = get_log_sizes()
        print(f"日志总大小: {sizes['total_size_mb']:.2f} MB")
        for dir_info in sizes["directories"]:
            print(f"  目录: {dir_info['path']}")
            print(f"    存在: {dir_info['exists']}")
            print(f"    大小: {dir_info['total_size_mb']:.2f} MB")
            for file_info in dir_info.get("files", []):
                print(f"      {file_info['name']}: {file_info['size_kb']:.2f} KB")

    if args.cleanup is not None:
        result = cleanup_old_logs(args.cleanup)
        print(f"清理完成: 删除 {result['files_deleted']} 个文件")
        print(f"释放空间: {result['bytes_freed_mb']:.2f} MB")

    if args.check is not None:
        result = check_log_rotation_needed(args.check)
        print(result["recommendation"])

    if not (args.status or args.cleanup is not None or args.check is not None):
        # 默认显示状态
        sizes = get_log_sizes()
        print(f"日志总大小: {sizes['total_size_mb']:.2f} MB")
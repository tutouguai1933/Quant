"""OpenClaw 重启历史服务。

管理重启历史和节流控制，防止服务被频繁重启。
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json


class OpenclawRestartHistoryService:
    """管理重启历史和节流控制。"""

    RESTART_THROTTLE_CONFIG = {
        "max_attempts_per_window": 3,
        "window_seconds": 3600,
        "cooldown_seconds": 300,
        "consecutive_failure_limit": 2,
    }

    def __init__(self, state_path: Path):
        """初始化重启历史服务。

        Args:
            state_path: 存储重启历史的文件路径
        """
        self._state_path = state_path
        self._history: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """从文件加载重启历史。"""
        if self._state_path.exists():
            try:
                with open(self._state_path, "r", encoding="utf-8") as f:
                    self._history = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._history = {}
        else:
            self._history = {}

    def _save(self) -> None:
        """保存重启历史到文件。"""
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump(self._history, f, ensure_ascii=False, indent=2)

    def _get_service_history(self, service: str) -> dict[str, Any]:
        """获取服务的历史记录，如不存在则创建默认结构。"""
        if service not in self._history:
            self._history[service] = {
                "attempts": [],
                "last_attempt_at": None,
                "last_success_at": None,
                "consecutive_failures": 0,
                "total_attempts": 0,
                "total_successes": 0,
            }
        return self._history[service]

    def record_restart(self, service: str, success: bool) -> dict:
        """记录一次重启尝试。

        Args:
            service: 服务名称
            success: 重启是否成功

        Returns:
            更新后的服务历史记录
        """
        now = datetime.now(timezone.utc).isoformat()
        history = self._get_service_history(service)

        # 记录本次尝试
        attempt = {
            "attempted_at": now,
            "success": success,
        }
        history["attempts"].append(attempt)

        # 只保留最近的尝试记录
        max_records = self.RESTART_THROTTLE_CONFIG["max_attempts_per_window"] * 2
        if len(history["attempts"]) > max_records:
            history["attempts"] = history["attempts"][-max_records:]

        # 更新统计信息
        history["last_attempt_at"] = now
        history["total_attempts"] += 1

        if success:
            history["last_success_at"] = now
            history["consecutive_failures"] = 0
            history["total_successes"] += 1
        else:
            history["consecutive_failures"] += 1

        self._save()
        return dict(history)

    def get_history(self, service: str) -> dict:
        """获取指定服务的重启历史。

        Args:
            service: 服务名称

        Returns:
            服务的重启历史记录
        """
        return dict(self._get_service_history(service))

    def can_restart(self, service: str) -> tuple[bool, str]:
        """检查服务是否可以重启。

        根据节流配置检查：
        1. 时间窗口内的最大尝试次数
        2. 上次尝试后的冷却时间
        3. 连续失败次数限制

        Args:
            service: 服务名称

        Returns:
            (是否允许重启, 原因说明)
        """
        history = self._get_service_history(service)
        now = datetime.now(timezone.utc)

        # 检查冷却时间
        last_attempt_at = history.get("last_attempt_at")
        if last_attempt_at:
            try:
                last_time = datetime.fromisoformat(last_attempt_at)
                elapsed = (now - last_time).total_seconds()
                cooldown = self.RESTART_THROTTLE_CONFIG["cooldown_seconds"]
                if elapsed < cooldown:
                    remaining = int(cooldown - elapsed)
                    return False, f"冷却中，还需等待 {remaining} 秒"
            except (ValueError, TypeError):
                pass

        # 检查时间窗口内的尝试次数
        window_seconds = self.RESTART_THROTTLE_CONFIG["window_seconds"]
        window_start = datetime.fromtimestamp(now.timestamp() - window_seconds, tz=timezone.utc)

        attempts = history.get("attempts", [])
        recent_attempts = []
        for attempt in attempts:
            try:
                attempt_time = datetime.fromisoformat(str(attempt.get("attempted_at", "")))
                if attempt_time >= window_start:
                    recent_attempts.append(attempt)
            except (ValueError, TypeError):
                continue

        max_attempts = self.RESTART_THROTTLE_CONFIG["max_attempts_per_window"]
        if len(recent_attempts) >= max_attempts:
            return False, f"已达时间窗口内最大尝试次数 {max_attempts}"

        # 检查连续失败次数
        consecutive_failures = history.get("consecutive_failures", 0)
        limit = self.RESTART_THROTTLE_CONFIG["consecutive_failure_limit"]
        if consecutive_failures >= limit:
            return False, f"连续失败 {consecutive_failures} 次，已达限制 {limit} 次，需人工介入"

        return True, "允许重启"

    def get_all_history(self) -> dict:
        """获取所有服务的重启历史。

        Returns:
            所有服务的重启历史记录
        """
        return dict(self._history)


# 默认实例
openclaw_restart_history_service = OpenclawRestartHistoryService(
    state_path=Path(".runtime/openclaw_restart_history.json")
)
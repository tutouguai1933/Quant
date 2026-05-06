"""自动化周期历史记录服务。

保存每轮自动化运行的记录，方便查看系统运行情况。
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AutomationCycleHistoryService:
    """自动化周期历史记录服务。"""

    MAX_RECORDS = 200  # 最多保存200条记录

    def __init__(self, state_path: Path | None = None):
        self._state_path = state_path or Path(".runtime/automation_cycle_history.json")
        self._records: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        """从文件加载历史记录。"""
        if self._state_path.exists():
            try:
                with open(self._state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._records = list(data.get("records", []))
            except (json.JSONDecodeError, IOError):
                self._records = []
        else:
            self._records = []

    def _save(self) -> None:
        """保存历史记录到文件。"""
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump({"records": self._records}, f, ensure_ascii=False, indent=2)

    def record_cycle(self, summary: dict[str, Any]) -> None:
        """记录一轮自动化结果。

        Args:
            summary: 自动化周期结果摘要
        """
        now = datetime.now(timezone.utc)
        record = {
            "recorded_at": now.isoformat(),
            "status": str(summary.get("status", "unknown")),
            "mode": str(summary.get("mode", "manual")),
            "recommended_symbol": str(summary.get("recommended_symbol", "")),
            "next_action": str(summary.get("next_action", "")),
            "message": str(summary.get("message", "")),
            "failure_reason": str(summary.get("failure_reason", "")),
            "armed_symbol": str(summary.get("armed_symbol", "")),
        }

        with self._lock:
            self._records.insert(0, record)
            # 保留最近200条
            if len(self._records) > self.MAX_RECORDS:
                self._records = self._records[:self.MAX_RECORDS]
            self._save()

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取历史记录。

        Args:
            limit: 返回的最大记录数

        Returns:
            历史记录列表，按时间倒序
        """
        with self._lock:
            return list(self._records[:limit])

    def get_summary(self) -> dict[str, Any]:
        """获取历史记录摘要。"""
        with self._lock:
            total = len(self._records)
            if total == 0:
                return {
                    "total": 0,
                    "success_count": 0,
                    "waiting_count": 0,
                    "failed_count": 0,
                    "last_run_at": "",
                    "last_status": "",
                }

            success_count = sum(1 for r in self._records if r.get("status") == "succeeded")
            waiting_count = sum(1 for r in self._records if r.get("status") == "waiting")
            failed_count = sum(1 for r in self._records if r.get("status") in ("failed", "attention_required"))

            return {
                "total": total,
                "success_count": success_count,
                "waiting_count": waiting_count,
                "failed_count": failed_count,
                "last_run_at": self._records[0].get("recorded_at", "") if self._records else "",
                "last_status": self._records[0].get("status", "") if self._records else "",
            }

    def clear(self) -> None:
        """清空历史记录。"""
        with self._lock:
            self._records = []
            self._save()


# 全局实例
automation_cycle_history_service = AutomationCycleHistoryService()

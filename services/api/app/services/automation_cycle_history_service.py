"""自动化周期历史记录服务。

保存每轮自动化运行的记录，方便查看系统运行情况。
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.api.app.services.rsi_cache_service import rsi_cache


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

        # 计算显示状态
        raw_status = str(summary.get("status", "unknown"))
        failure_reason = str(summary.get("failure_reason", ""))
        display_status = self._compute_display_status(raw_status, failure_reason)

        # 提取候选币种列表
        candidates = self._extract_candidates(summary)

        # 提取 RSI 快照
        rsi_snapshot = self._extract_rsi_snapshot(summary)

        # 提取任务执行摘要
        task_summary = self._extract_task_summary(summary)

        record = {
            "recorded_at": now.isoformat(),
            "status": raw_status,
            "display_status": display_status,
            "mode": str(summary.get("mode", "manual")),
            "recommended_symbol": str(summary.get("recommended_symbol", "")),
            "next_action": str(summary.get("next_action", "")),
            "message": str(summary.get("message", "")),
            "failure_reason": failure_reason,
            "armed_symbol": str(summary.get("armed_symbol", "")),
            "candidates": candidates,
            "rsi_snapshot": rsi_snapshot,
            "task_summary": task_summary,
        }

        with self._lock:
            self._records.insert(0, record)
            # 保留最近200条
            if len(self._records) > self.MAX_RECORDS:
                self._records = self._records[:self.MAX_RECORDS]
            self._save()

    def _compute_display_status(self, raw_status: str, failure_reason: str) -> str:
        """计算用户友好的显示状态。"""
        if raw_status == "succeeded":
            return "succeeded"
        if raw_status in ("failed", "attention_required"):
            return "failed"
        if failure_reason == "candidate_blocked":
            return "blocked"
        if failure_reason == "cycle_cooldown_active":
            return "cooldown"
        if failure_reason == "daily_limit_reached":
            return "limited"
        return "waiting"

    def _extract_candidates(self, summary: dict[str, Any]) -> list[dict[str, Any]]:
        """提取候选币种列表（TOP 5）。"""
        candidates = []
        # 从 priority_queue 或 candidates 中提取
        pq = summary.get("priority_queue", {})
        items = pq.get("items", [])
        if items:
            for item in items[:5]:
                candidates.append({
                    "symbol": str(item.get("symbol", "")),
                    "score": str(item.get("score", "")),
                    "status": str(item.get("status", "")),
                    "blocked_reason": str(item.get("blocked_reason", "")),
                })

        # 如果没有 priority_queue，尝试从其他字段提取
        if not candidates and summary.get("recommended_symbol"):
            candidates.append({
                "symbol": str(summary.get("recommended_symbol", "")),
                "score": "",
                "status": "recommended",
                "blocked_reason": str(summary.get("failure_reason", "")),
            })

        return candidates

    def _extract_rsi_snapshot(self, summary: dict[str, Any]) -> dict[str, Any]:
        """提取 RSI 快照数据。

        从 RSI 缓存中获取相关币种的当前 RSI 值。
        """
        rsi_data = {}

        # 确定需要提取 RSI 的币种列表
        symbols_to_fetch = set()

        # 添加推荐币种
        recommended_symbol = summary.get("recommended_symbol", "")
        if recommended_symbol:
            symbols_to_fetch.add(recommended_symbol)

        # 添加候选币种
        pq = summary.get("priority_queue", {})
        items = pq.get("items", [])
        for item in items[:5]:
            symbol = item.get("symbol", "")
            if symbol:
                symbols_to_fetch.add(symbol)

        if not symbols_to_fetch:
            return rsi_data

        # 从 RSI 缓存获取数据
        try:
            cached = rsi_cache.get(interval="1d")
            if cached and "items" in cached:
                # 构建符号到 RSI 的映射
                rsi_map = {}
                for item in cached.get("items", []):
                    symbol = item.get("symbol", "")
                    if symbol:
                        rsi_map[symbol] = item.get("rsi")

                # 只提取相关币种的 RSI
                for symbol in symbols_to_fetch:
                    if symbol in rsi_map:
                        rsi_data[symbol] = rsi_map[symbol]
        except Exception:
            pass

        return rsi_data

    def _extract_task_summary(self, summary: dict[str, Any]) -> dict[str, Any]:
        """提取任务执行摘要。"""
        task_summary = {}

        for task_key in ["train_task", "infer_task", "signal_task", "review_task"]:
            task = summary.get(task_key, {})
            if task and isinstance(task, dict):
                task_name = task_key.replace("_task", "")
                task_summary[task_name] = {
                    "status": str(task.get("status", "")),
                    "duration_seconds": self._compute_duration(task),
                }

        return task_summary

    def _compute_duration(self, task: dict[str, Any]) -> float:
        """计算任务执行时长（秒）。"""
        started = task.get("started_at", "")
        finished = task.get("finished_at", "")
        if started and finished:
            try:
                start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
                return (end_dt - start_dt).total_seconds()
            except (ValueError, TypeError):
                pass
        return 0

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取历史记录。

        Args:
            limit: 返回的最大记录数

        Returns:
            历史记录列表，按时间倒序
        """
        # 每次都从文件重新加载，确保获取最新数据
        self._load()
        with self._lock:
            return list(self._records[:limit])

    def get_summary(self) -> dict[str, Any]:
        """获取历史记录摘要。"""
        with self._lock:
            total = len(self._records)
            if total == 0:
                return {
                    "total": 0,
                    "succeeded_count": 0,
                    "blocked_count": 0,
                    "cooldown_count": 0,
                    "failed_count": 0,
                    "waiting_count": 0,
                    "last_run_at": "",
                    "last_status": "",
                    "last_display_status": "",
                }

            # 按 display_status 分类统计
            succeeded_count = 0
            blocked_count = 0
            cooldown_count = 0
            failed_count = 0
            waiting_count = 0

            for r in self._records:
                display_status = r.get("display_status", "waiting")
                if display_status == "succeeded":
                    succeeded_count += 1
                elif display_status == "blocked":
                    blocked_count += 1
                elif display_status == "cooldown":
                    cooldown_count += 1
                elif display_status == "failed":
                    failed_count += 1
                else:
                    waiting_count += 1

            return {
                "total": total,
                "succeeded_count": succeeded_count,
                "blocked_count": blocked_count,
                "cooldown_count": cooldown_count,
                "failed_count": failed_count,
                "waiting_count": waiting_count,
                "last_run_at": self._records[0].get("recorded_at", "") if self._records else "",
                "last_status": self._records[0].get("status", "") if self._records else "",
                "last_display_status": self._records[0].get("display_status", "") if self._records else "",
            }

    def clear(self) -> None:
        """清空历史记录。"""
        with self._lock:
            self._records = []
            self._save()


# 全局实例
automation_cycle_history_service = AutomationCycleHistoryService()

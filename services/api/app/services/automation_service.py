"""自动化状态服务。

这个文件负责保存自动化模式、停机状态、最近告警和健康摘要。
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.api.app.adapters.freqtrade.client import freqtrade_client
from services.api.app.core.settings import Settings
from services.api.app.services.risk_service import risk_service
from services.api.app.services.workbench_config_service import (
    _build_automation_preset_catalog,
    _build_operations_preset_catalog,
    _describe_catalog_item,
    workbench_config_service,
)


AUTOMATION_MODES = {"manual", "auto_dry_run", "auto_live"}
MAX_BACKUP_COUNT = 3


def _utc_now() -> str:
    """返回当前 UTC 时间字符串。"""

    return datetime.now(timezone.utc).isoformat()


class AutomationService:
    """保存自动化控制状态，并对外提供健康摘要。"""

    def __init__(self) -> None:
        self._state_path = self._resolve_state_path()
        self._mode = "manual"
        self._paused = False
        self._paused_reason = ""
        self._manual_takeover = False
        self._updated_at = _utc_now()
        self._last_cycle: dict[str, object] = {}
        self._alerts: list[dict[str, object]] = []
        self._next_alert_id = 1
        self._armed_symbol = ""
        self._armed_at = ""
        self._daily_summary = self._new_daily_summary()
        self._consecutive_failure_count = 0
        self._last_success_at = ""
        self._last_failure_at = ""
        self._paused_at = ""
        self._manual_takeover_at = ""
        self._load_state()

    def get_state(self) -> dict[str, object]:
        """返回当前自动化状态。"""

        settings = Settings.from_env()
        last_cycle = self._build_cycle_summary(self._last_cycle)
        return {
            "mode": self._mode,
            "paused": self._paused,
            "paused_reason": self._paused_reason,
            "manual_takeover": self._manual_takeover,
            "armed_symbol": self._armed_symbol,
            "armed_at": self._armed_at,
            "updated_at": self._updated_at,
            "runtime_mode": settings.runtime_mode,
            "allow_live_execution": settings.allow_live_execution,
            "last_cycle": last_cycle,
            "alerts": list(self._alerts),
            "daily_summary": dict(self._daily_summary),
            "consecutive_failure_count": self._consecutive_failure_count,
            "last_success_at": self._last_success_at,
            "last_failure_at": self._last_failure_at,
            "paused_at": self._paused_at,
            "manual_takeover_at": self._manual_takeover_at,
        }

    @staticmethod
    def _build_cycle_summary(payload: dict[str, object]) -> dict[str, object]:
        """只返回任务页真正需要的最近工作流摘要。"""

        row = dict(payload or {})
        dispatch = dict(row.get("dispatch") or {})
        dispatch_meta = dict(dispatch.get("meta") or {})
        dispatch_item = dict(dispatch.get("item") or {})
        dispatch_order = dict(dispatch_item.get("order") or {})
        return {
            "status": str(row.get("status", "")).strip() or "unknown",
            "mode": str(row.get("mode", "")).strip(),
            "source": str(row.get("source", "")).strip(),
            "recommended_symbol": str(row.get("recommended_symbol", "")).strip().upper(),
            "recommended_strategy_id": row.get("recommended_strategy_id") or "",
            "next_action": str(row.get("next_action", "")).strip(),
            "message": str(row.get("message", "")).strip(),
            "failure_reason": str(row.get("failure_reason", "")).strip(),
            "recorded_at": str(row.get("recorded_at", "")).strip(),
            "dispatch": {
                "status": str(dispatch.get("status", "")).strip(),
                "meta": {
                    "source": str(dispatch_meta.get("source", "")).strip(),
                },
                "item": {
                    "order": {
                        "symbol": str(dispatch_order.get("symbol", "")).strip().upper(),
                        "status": str(dispatch_order.get("status", "")).strip(),
                    }
                },
            },
        }

    def get_status(self, *, task_health: dict[str, object] | None = None) -> dict[str, object]:
        """返回当前状态和健康摘要。"""

        if task_health is None:
            from services.api.app.tasks.scheduler import task_scheduler

            task_health = task_scheduler.get_health_summary()
        health = self.build_health_summary(task_health=task_health or {})
        alert_summary = dict(health.get("alert_summary") or {})
        return {
            "state": self.get_state(),
            "health": health,
            "operations": self._get_operations_config(),
            "automation_config": self._get_automation_config(),
            "execution_policy": self._get_execution_policy(),
            "active_blockers": list(health.get("active_blockers") or []),
            "operator_actions": list(health.get("operator_actions") or []),
            "control_actions": list(health.get("control_actions") or []),
            "takeover_summary": dict(health.get("takeover_summary") or {}),
            "alert_summary": alert_summary,
            "severity_summary": dict(health.get("severity_summary") or {}),
            "resume_checklist": list(health.get("resume_checklist") or []),
            "alerts_count": len(self._alerts),
            "history_alerts_count": int(alert_summary.get("history_count", 0) or 0),
            "active_alerts_count": int(alert_summary.get("alert_count", 0) or 0),
            "latest_alert_level": str(self._alerts[0]["level"]) if self._alerts else "",
            "latest_alert_title": str(self._alerts[0]["message"]) if self._alerts else "",
            "current_alert_level": str(alert_summary.get("latest_level", "") or ""),
            "current_alert_title": str(alert_summary.get("latest_message", "") or ""),
            "daily_summary": dict(self._daily_summary),
        }

    def set_mode(self, mode: str) -> dict[str, object]:
        """切换自动化模式。"""

        normalized = mode.strip().lower().replace("-", "_")
        if normalized not in AUTOMATION_MODES:
            raise ValueError("automation mode must be manual, auto_dry_run or auto_live")
        self._mode = normalized
        if normalized == "manual":
            self._paused = False
            self._paused_reason = ""
            self._manual_takeover = False
            self._paused_at = ""
            self._manual_takeover_at = ""
            self._armed_symbol = ""
            self._armed_at = ""
        self._updated_at = _utc_now()
        self._persist_state()
        return self.get_state()

    def configure_mode(self, mode: str, *, actor: str = "user") -> dict[str, object]:
        """兼容路由层的模式切换入口。"""

        self.record_alert(level="info", code="automation_mode_changed", message=f"自动化模式已切到 {mode}", source=actor)
        return {
            **self.set_mode(mode),
            "actor": actor,
        }

    def enable_dry_run_only(self, *, actor: str = "user") -> dict[str, object]:
        """切到只保留 dry-run 的安全模式。"""

        state = self.set_mode("auto_dry_run")
        self._paused = False
        self._paused_reason = ""
        self._manual_takeover = False
        self._paused_at = ""
        self._manual_takeover_at = ""
        self._updated_at = _utc_now()
        self.record_alert(level="warning", code="dry_run_only_enabled", message="系统已切到 dry-run only", source=actor)
        self._persist_state()
        return {
            **state,
            "actor": actor,
        }

    def kill_switch(self, *, actor: str = "user") -> dict[str, object]:
        """触发一键停机。"""

        self._mode = "manual"
        self._paused = True
        self._paused_reason = "kill_switch"
        self._manual_takeover = True
        if not self._paused_at:
            self._paused_at = _utc_now()
        self._manual_takeover_at = self._paused_at
        self.clear_armed_symbol()
        self._apply_execution_guard(paused=True, stop_executor=True)
        self._updated_at = _utc_now()
        self.record_alert(level="error", code="kill_switch_enabled", message="Kill Switch 已触发，自动化已停机", source=actor)
        self._persist_state()
        return {
            **self.get_state(),
            "actor": actor,
        }

    def pause(self, reason: str = "manual_pause", *, actor: str = "user") -> dict[str, object]:
        """暂停自动化。"""

        self._paused = True
        self._paused_reason = reason.strip() or "manual_pause"
        self._manual_takeover = False
        if not self._paused_at:
            self._paused_at = _utc_now()
        self._manual_takeover_at = ""
        self._apply_execution_guard(paused=True, stop_executor=False)
        self._updated_at = _utc_now()
        self.record_alert(level="warning", code="automation_paused", message="自动化已暂停", source=actor)
        self._persist_state()
        return {
            **self.get_state(),
            "actor": actor,
        }

    def manual_takeover(self, reason: str = "manual_takeover", *, actor: str = "user") -> dict[str, object]:
        """显式进入人工接管。"""

        self._paused = True
        self._paused_reason = reason.strip() or "manual_takeover"
        self._manual_takeover = True
        if not self._paused_at:
            self._paused_at = _utc_now()
        self._manual_takeover_at = _utc_now()
        self._apply_execution_guard(paused=True, stop_executor=False)
        self._updated_at = _utc_now()
        self.record_alert(
            level="warning",
            code="manual_takeover_enabled",
            message="已进入人工接管，自动执行链已暂停",
            source=actor,
            detail=self._paused_reason,
        )
        self._persist_state()
        return {
            **self.get_state(),
            "actor": actor,
        }

    def resume(self, *, actor: str = "user") -> dict[str, object]:
        """恢复自动化。"""

        from services.api.app.tasks.scheduler import task_scheduler

        task_health = task_scheduler.get_health_summary()
        health_before = self.build_health_summary(task_health=task_health or {})
        resume_checklist = [dict(item) for item in list(health_before.get("resume_checklist") or [])]
        if self._mode == "manual" and not self._paused and not self._manual_takeover:
            return {
                **self.get_state(),
                "actor": actor,
                "status": "blocked",
                "blocked_reason": "manual_mode_requires_target",
                "message": "当前还是手动模式，先切到 dry-run only 或自动模式，再继续自动化。",
                "pending_items": [],
                "resume_checklist": resume_checklist,
            }
        pending_items = [item for item in resume_checklist if str(item.get("status", "") or "").strip().lower() == "pending"]
        if pending_items:
            return {
                **self.get_state(),
                "actor": actor,
                "status": "blocked",
                "blocked_reason": "resume_checklist_pending",
                "pending_items": pending_items,
                "resume_checklist": resume_checklist,
            }
        if self._mode == "auto_live" and not self._armed_symbol:
            return {
                **self.get_state(),
                "actor": actor,
                "status": "blocked",
                "blocked_reason": "resume_requires_dry_run_only",
                "message": "当前还没有 dry-run 验证通过的候选，先只恢复到 dry-run，再决定是否重新进入 live。",
                "pending_items": [],
                "resume_checklist": resume_checklist,
            }

        self._paused = False
        self._paused_reason = ""
        self._manual_takeover = False
        self._paused_at = ""
        self._manual_takeover_at = ""
        self._apply_execution_guard(paused=False, stop_executor=False)
        self._updated_at = _utc_now()
        self.record_alert(level="info", code="automation_resumed", message="自动化已恢复", source=actor)
        self._persist_state()
        health_after = self.build_health_summary(task_health=task_health or {})
        return {
            **self.get_state(),
            "actor": actor,
            "status": "succeeded",
            "pending_items": [],
            "resume_checklist": [dict(item) for item in list(health_after.get("resume_checklist") or [])],
        }

    def arm_symbol(self, symbol: str) -> dict[str, object]:
        """记录已通过 dry-run 的候选，供后续 live 验证使用。"""

        normalized = symbol.strip().upper()
        self._armed_symbol = normalized
        self._armed_at = _utc_now() if normalized else ""
        self._updated_at = _utc_now()
        self._persist_state()
        return self.get_state()

    def clear_armed_symbol(self) -> dict[str, object]:
        """清掉当前已 armed 的候选。"""

        self._armed_symbol = ""
        self._armed_at = ""
        self._updated_at = _utc_now()
        self._persist_state()
        return self.get_state()

    def record_cycle(self, payload: dict[str, object], *, count_towards_daily: bool = True) -> None:
        """记录最近一次工作流结果。"""

        self._ensure_daily_summary()
        self._last_cycle = {
            **dict(payload),
            "recorded_at": _utc_now(),
        }
        status = str(payload.get("status", "")).strip() or "unknown"
        if status == "succeeded":
            self._consecutive_failure_count = 0
            self._last_success_at = _utc_now()
        elif status == "attention_required":
            self._consecutive_failure_count += 1
            self._last_failure_at = _utc_now()
        if count_towards_daily:
            self._daily_summary["cycle_count"] = int(self._daily_summary.get("cycle_count", 0)) + 1
            status_counts = dict(self._daily_summary.get("status_counts") or {})
            status_counts[status] = int(status_counts.get(status, 0) or 0) + 1
            self._daily_summary["status_counts"] = status_counts
        self._updated_at = _utc_now()
        self._persist_state()

    def record_alert(self, *, level: str, code: str, message: str, source: str, detail: str = "") -> dict[str, object]:
        """记录自动化告警。"""

        self._ensure_daily_summary()
        item = {
            "id": self._next_alert_id,
            "level": level,
            "code": code,
            "message": message,
            "source": source,
            "detail": detail,
            "created_at": _utc_now(),
        }
        self._next_alert_id += 1
        self._alerts.insert(0, item)
        self._alerts = self._alerts[:20]
        self._daily_summary["alert_count"] = int(self._daily_summary.get("alert_count", 0)) + 1
        level_counts = dict(self._daily_summary.get("alert_level_counts") or {})
        level_counts[level] = int(level_counts.get(level, 0) or 0) + 1
        self._daily_summary["alert_level_counts"] = level_counts
        self._updated_at = _utc_now()
        self._persist_state()
        return dict(item)

    def _pop_alert(self, alert_id: int) -> dict[str, object] | None:
        """按 ID 弹出告警项。"""

        remaining: list[dict[str, object]] = []
        found: dict[str, object] | None = None
        for alert in self._alerts:
            if alert.get("id") == alert_id and found is None:
                found = alert
                continue
            remaining.append(alert)
        self._alerts = remaining
        return found

    def confirm_alert(self, alert_id: int, *, actor: str = "user") -> dict[str, object]:
        """确认单条告警并记录操作提醒。"""

        alert = self._pop_alert(alert_id)
        if alert is None:
            raise ValueError("alert not found")
        self._updated_at = _utc_now()
        self._persist_state()
        return alert

    def clear_alerts(self, *, levels: list[str] | None = None, actor: str = "user") -> list[dict[str, object]]:
        """按级别清空告警并记录清理信息。"""

        levels_set = {item.lower() for item in (levels or ["info", "warning"])}
        removed = []
        kept = []
        for alert in self._alerts:
            if str(alert.get("level", "")).lower() in levels_set:
                removed.append(alert)
            else:
                kept.append(alert)
        if not removed:
            return []
        self._alerts = kept
        self._updated_at = _utc_now()
        self._persist_state()
        return removed

    def build_health_summary(self, *, task_health: dict[str, object]) -> dict[str, Any]:
        """构造自动化健康摘要。"""

        latest_status = dict(task_health.get("latest_status_by_type") or {})
        latest_failure = dict(task_health.get("latest_failure_by_type") or {})
        failure_counts = dict(task_health.get("consecutive_failure_count_by_type") or {})
        last_cycle = dict(self._last_cycle)
        alert_summary = self._build_alert_summary()
        last_alert = dict(alert_summary.get("latest_alert") or {}) or None
        run_health = self._build_run_health(
            latest_status=latest_status,
            latest_failure=latest_failure,
            failure_counts=failure_counts,
            last_alert=last_alert,
        )
        active_blockers = self._build_active_blockers(
            latest_status=latest_status,
            latest_failure=latest_failure,
            last_alert=last_alert,
            run_health=run_health,
        )
        takeover_summary = self._build_takeover_summary(active_blockers=active_blockers, run_health=run_health)
        operator_actions = self._build_operator_actions(latest_status=latest_status, run_health=run_health)
        control_actions = self._build_control_actions()
        focus_cards = self._build_focus_cards(
            alert_summary=alert_summary,
            takeover_summary=takeover_summary,
            operator_actions=operator_actions,
            last_alert=last_alert,
            run_health=run_health,
        )
        alert_story = self._build_alert_story(
            alert_summary=alert_summary,
            active_blockers=active_blockers,
            operator_actions=operator_actions,
            last_alert=last_alert,
            run_health=run_health,
        )
        severity_summary = self._build_severity_summary(
            active_blockers=active_blockers,
            last_alert=last_alert,
            run_health=run_health,
            alert_summary=alert_summary,
        )
        resume_checklist = self._build_resume_checklist(
            latest_status=latest_status,
            active_blockers=active_blockers,
            last_alert=last_alert,
            alert_summary=alert_summary,
        )
        return {
            "mode": self._mode,
            "paused": self._paused,
            "manual_takeover": self._manual_takeover,
            "paused_reason": self._paused_reason,
            "armed_symbol": self._armed_symbol,
            "armed_at": self._armed_at,
            "updated_at": self._updated_at,
            "last_cycle_status": str(last_cycle.get("status", "idle")),
            "last_cycle_action": str(last_cycle.get("next_action", "")),
            "last_cycle_symbol": str(last_cycle.get("recommended_symbol", "")),
            "latest_train_status": str(latest_status.get("research_train", "unknown")),
            "latest_infer_status": str(latest_status.get("research_infer", "unknown")),
            "latest_sync_status": str(latest_status.get("sync", "unknown")),
            "latest_review_status": str(latest_status.get("review", "unknown")),
            "alert_count": int(alert_summary.get("alert_count", 0) or 0),
            "history_alert_count": int(alert_summary.get("history_count", 0) or 0),
            "last_alert": dict(last_alert) if last_alert else None,
            "daily_summary_date": str(self._daily_summary.get("date", "")),
            "takeover_summary": takeover_summary,
            "active_blockers": active_blockers,
            "operator_actions": operator_actions,
            "control_actions": control_actions,
            "alert_summary": alert_summary,
            "alert_story": alert_story,
            "run_health": run_health,
            "focus_cards": focus_cards,
            "severity_summary": severity_summary,
            "resume_checklist": resume_checklist,
        }

    def _build_alert_summary(self) -> dict[str, object]:
        """汇总最近告警级别，给前端直接展示。"""

        automation = self._get_automation_config()
        cleanup_minutes = int(automation.get("alert_cleanup_minutes", 15) or 15)
        active_alerts = self._filter_active_alerts(cleanup_minutes=cleanup_minutes)
        current_summary = self._summarize_alert_collection(active_alerts)
        history_summary = self._summarize_alert_collection(self._alerts)
        summary = {
            "error_count": int(current_summary.get("error_count", 0) or 0),
            "warning_count": int(current_summary.get("warning_count", 0) or 0),
            "info_count": int(current_summary.get("info_count", 0) or 0),
            "active_error_count": int(current_summary.get("error_count", 0) or 0),
            "active_warning_count": int(current_summary.get("warning_count", 0) or 0),
            "active_info_count": int(current_summary.get("info_count", 0) or 0),
            "alert_count": int(current_summary.get("alert_count", 0) or 0),
            "latest_code": str(current_summary.get("latest_code", "") or ""),
            "latest_message": str(current_summary.get("latest_message", "") or ""),
            "latest_level": str(current_summary.get("latest_level", "") or ""),
            "latest_source": str(current_summary.get("latest_source", "") or ""),
            "latest_alert": dict(current_summary.get("latest_alert") or {}),
            "cleanup_minutes": cleanup_minutes,
            "groups": list(current_summary.get("groups") or []),
            "history_error_count": int(history_summary.get("error_count", 0) or 0),
            "history_warning_count": int(history_summary.get("warning_count", 0) or 0),
            "history_info_count": int(history_summary.get("info_count", 0) or 0),
            "history_count": int(history_summary.get("alert_count", 0) or 0),
            "history_latest_code": str(history_summary.get("latest_code", "") or ""),
            "history_latest_message": str(history_summary.get("latest_message", "") or ""),
            "history_latest_level": str(history_summary.get("latest_level", "") or ""),
            "history_latest_source": str(history_summary.get("latest_source", "") or ""),
            "history_latest_alert": dict(history_summary.get("latest_alert") or {}),
            "history_groups": list(history_summary.get("groups") or []),
        }
        return summary

    @staticmethod
    def _summarize_alert_collection(items: list[dict[str, object]]) -> dict[str, object]:
        """把一组告警压成当前页面可直接消费的摘要。"""

        summary = {
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "alert_count": len(items),
            "latest_code": "",
            "latest_message": "",
            "latest_level": "",
            "latest_source": "",
            "latest_alert": {},
            "groups": [],
        }
        if items:
            latest = dict(items[0])
            summary["latest_code"] = str(latest.get("code", "") or "")
            summary["latest_message"] = str(latest.get("message", "") or "")
            summary["latest_level"] = str(latest.get("level", "") or "")
            summary["latest_source"] = str(latest.get("source", "") or "")
            summary["latest_alert"] = latest
        groups: dict[str, dict[str, object]] = {}
        for item in items:
            level = str(item.get("level", "")).strip().lower()
            if level == "error":
                summary["error_count"] = int(summary["error_count"]) + 1
            elif level == "warning":
                summary["warning_count"] = int(summary["warning_count"]) + 1
            elif level == "info":
                summary["info_count"] = int(summary["info_count"]) + 1
            code = str(item.get("code", "")).strip() or "unknown"
            row = groups.get(code)
            created_at = str(item.get("created_at", "")).strip()
            if row is None:
                row = {
                    "code": code,
                    "level": level,
                    "message": str(item.get("message", "")).strip(),
                    "source": str(item.get("source", "")).strip(),
                    "occurrence_count": 0,
                    "first_seen_at": created_at,
                    "last_seen_at": created_at,
                }
                groups[code] = row
            row["occurrence_count"] = int(row.get("occurrence_count", 0) or 0) + 1
            if created_at:
                first_seen = str(row.get("first_seen_at", "") or "")
                last_seen = str(row.get("last_seen_at", "") or "")
                if not first_seen or created_at < first_seen:
                    row["first_seen_at"] = created_at
                if not last_seen or created_at > last_seen:
                    row["last_seen_at"] = created_at
        summary["groups"] = sorted(
            (dict(item) for item in groups.values()),
            key=lambda item: (
                -int(item.get("occurrence_count", 0) or 0),
                str(item.get("last_seen_at", "") or ""),
                str(item.get("code", "") or ""),
            ),
            reverse=False,
        )
        return summary

    def _build_takeover_summary(self, *, active_blockers: list[dict[str, str]], run_health: dict[str, object]) -> dict[str, str]:
        """给出当前是否接管、为什么接管、恢复时先做什么。"""

        if self._paused_reason == "kill_switch":
            state_label = "Kill Switch 已触发"
        elif self._manual_takeover:
            state_label = "人工接管中"
        elif self._paused:
            state_label = "已暂停"
        elif self._mode == "manual":
            state_label = "手动模式"
        else:
            state_label = "自动化运行中"

        if self._paused_reason == "kill_switch":
            note = "Kill Switch 已触发，恢复前应先确认执行器、仓位和账户同步都正常。"
        elif self._manual_takeover:
            note = "当前已切到人工接管，恢复前先看阻塞原因和最近执行状态。"
        elif self._paused:
            note = "自动化已暂停，恢复前先确认暂停原因是否已经处理。"
        elif self._mode == "manual":
            note = "当前处于手动模式，系统不会自动推进，需你先人工确认再决定是否切回自动模式。"
        else:
            note = "当前没有接管或暂停，系统可以继续自动推进。"
        primary_blocker = active_blockers[0] if active_blockers else {}
        reason = self._paused_reason or "当前没有接管原因"

        return {
            "state_label": state_label,
            "reason": reason,
            "reason_label": self._describe_pause_reason(reason),
            "suggested_mode": "manual" if self._manual_takeover or self._paused or self._mode == "manual" else self._mode,
            "note": note,
            "primary_blocker_code": str(primary_blocker.get("code", "")),
            "primary_blocker_detail": str(primary_blocker.get("detail", "")),
            "next_step": (
                "先处理阻塞原因，再恢复自动化"
                if self._manual_takeover or self._paused
                else "当前保持手动，先人工确认再决定是否切回自动化"
                if self._mode == "manual"
                else "可以继续下一轮自动化"
            ),
            "paused_since": self._paused_at,
            "takeover_since": self._manual_takeover_at,
            "last_failure_at": str(run_health.get("last_failure_at", "")),
        }

    def _build_active_blockers(
        self,
        *,
        latest_status: dict[str, object],
        latest_failure: dict[str, object],
        last_alert: dict[str, object] | None,
        run_health: dict[str, object],
    ) -> list[dict[str, str]]:
        """把当前真正阻塞自动化继续推进的原因整理成列表。"""

        blockers: list[dict[str, str]] = []
        if self._paused_reason == "kill_switch":
            blockers.append(
                {
                    "code": "kill_switch",
                    "severity": "error",
                    "label": "Kill Switch 已触发",
                    "detail": "系统当前处于停机保护状态，需先确认执行器、仓位和同步都已收口。",
                }
            )
        if self._manual_takeover:
            blockers.append(
                {
                    "code": "manual_takeover",
                    "severity": "warning",
                    "label": "当前处于人工接管",
                    "detail": "当前处于人工接管状态，自动执行链不会继续推进。",
                }
            )
        if self._paused and self._paused_reason != "kill_switch":
            blockers.append(
                {
                    "code": "paused",
                    "severity": "warning",
                    "label": "自动化已暂停",
                    "detail": f"自动化当前已暂停，原因：{self._paused_reason or 'manual_pause'}",
                }
            )
        elif self._mode == "manual":
            blockers.append(
                {
                    "code": "manual_mode",
                    "severity": "info",
                    "label": "当前处于手动模式",
                    "detail": "系统当前不会自动推进，只有你切回自动模式后才会继续下一轮。",
                }
            )
        latest_sync_status = str(latest_status.get("sync", "unknown"))
        latest_sync_failure = dict(latest_failure.get("sync") or {})
        if latest_sync_status == "failed" and str(run_health.get("stale_sync_state", "")) == "stale":
            blockers.append(
                {
                    "code": "sync_failed",
                    "severity": "error",
                    "label": "执行结果还没有同步收口",
                    "detail": f"最近一次同步失败还没有收口：{str(latest_sync_failure.get('error_message', '未返回错误详情')) or '未返回错误详情'}",
                }
            )
        if last_alert and str(last_alert.get("level", "")).lower() == "error":
            blockers.append(
                {
                    "code": str(last_alert.get("code", "alert_error")) or "alert_error",
                    "severity": "error",
                    "label": "最近存在错误告警",
                    "detail": str(last_alert.get("message", "最近一次错误告警需要先处理。")),
                }
            )
        if not blockers:
            blockers.append(
                {
                    "code": "none",
                    "severity": "info",
                    "label": "当前没有阻塞",
                    "detail": "当前没有明显阻塞，自动化可以按既定顺序继续推进。",
                }
            )
        return blockers

    def _build_operator_actions(self, *, latest_status: dict[str, object], run_health: dict[str, object]) -> list[dict[str, str]]:
        """给前端一组直接可执行的恢复步骤。"""

        actions: list[dict[str, str]] = []
        resumable_mode = self._mode in {"auto_dry_run", "auto_live"}
        if (self._paused or self._manual_takeover) and resumable_mode:
            actions.append(
                {
                    "action": "automation_resume",
                    "label": "恢复自动化",
                    "detail": "确认阻塞原因已处理后，再恢复当前自动化模式。",
                }
            )
        elif self._mode == "manual":
            actions.append(
                {
                    "action": "automation_dry_run_only",
                    "label": "先切回 dry-run only",
                    "detail": "如果你想重新打开自动化，先从 dry-run 开始更安全。",
                }
            )
        if str(latest_status.get("sync", "unknown")) == "failed":
            actions.append(
                {
                    "action": "automation_run_cycle",
                    "label": "重跑一轮同步链",
                    "detail": f"最近同步已失败 {int(run_health.get('sync_failure_count', 0) or 0)} 次，先重跑一轮训练、推理、执行和复盘，确认同步是否恢复。",
                }
            )
        if self._armed_symbol:
            actions.append(
                {
                    "action": "review_execution_state",
                    "label": "查看执行器",
                    "detail": f"先确认 {self._armed_symbol} 的 dry-run/live 状态，再决定是否继续推进。",
                }
            )
        if not actions:
            actions.append(
                {
                    "action": "automation_run_cycle",
                    "label": "继续下一轮" if self._mode != "manual" else "继续人工确认",
                    "detail": (
                        "当前没有额外恢复步骤，可以直接继续下一轮自动化工作流。"
                        if self._mode != "manual"
                        else "当前处于手动模式，先人工确认，再决定是否切回自动化。"
                    ),
                }
            )
        return actions

    def _build_control_actions(self) -> list[dict[str, object]]:
        """给任务页和策略页统一一组最常用的控制入口。"""

        resumable_mode = self._mode in {"auto_dry_run", "auto_live"}
        if self._manual_takeover:
            actions: list[dict[str, object]] = []
            if resumable_mode:
                actions.append(
                    {
                        "action": "automation_resume",
                        "label": "确认后恢复自动化",
                        "detail": "只有在告警、同步和接管原因都处理完后，才恢复当前自动化模式。",
                        "danger": False,
                    }
                )
            actions.extend(
                [
                    {
                        "action": "automation_dry_run_only",
                        "label": "只恢复到 dry-run",
                        "detail": "如果你还不想放开真实资金，先切回只保留 dry-run。",
                        "danger": False,
                    },
                    {
                        "action": "automation_mode_manual",
                        "label": "保持手动",
                        "detail": "结束当前接管恢复链，继续停在手动模式，先人工判断。",
                        "danger": False,
                    },
                    {
                        "action": "automation_kill_switch",
                        "label": "Kill Switch",
                        "detail": "一键停机，继续保持最保守状态。",
                        "danger": True,
                    },
                ]
            )
            return actions
        if self._paused:
            return [
                {
                    "action": "automation_resume",
                    "label": "确认后恢复自动化",
                    "detail": "只有在告警、同步和暂停原因都处理完后，才恢复当前自动化模式。",
                    "danger": False,
                },
                {
                    "action": "automation_dry_run_only",
                    "label": "只恢复到 dry-run",
                    "detail": "如果你还不想放开真实资金，先切回只保留 dry-run。",
                    "danger": False,
                },
                {
                    "action": "automation_mode_manual",
                    "label": "切到手动",
                    "detail": "不再保持暂停恢复链，直接切到手动模式，后续由你人工判断。",
                    "danger": False,
                },
                {
                    "action": "automation_kill_switch",
                    "label": "Kill Switch",
                    "detail": "一键停机，继续保持最保守状态。",
                    "danger": True,
                },
            ]
        if self._mode == "manual":
            return [
                {
                    "action": "automation_mode_manual",
                    "label": "保持手动",
                    "detail": "继续只保留人工操作，不让系统自动推进。",
                    "danger": False,
                },
                {
                    "action": "automation_dry_run_only",
                    "label": "切到 dry-run only",
                    "detail": "先恢复到自动 dry-run，不直接放开真实资金。",
                    "danger": False,
                },
                {
                    "action": "automation_kill_switch",
                    "label": "Kill Switch",
                    "detail": "一键停机，继续保持最保守状态。",
                    "danger": True,
                },
            ]
        return [
            {
                "action": "automation_pause",
                "label": "暂停自动化",
                "detail": "先停住后续自动推进，回到人工判断。",
                "danger": False,
            },
            {
                "action": "automation_manual_takeover",
                "label": "转人工接管",
                "detail": "立刻切到人工接管，先人工确认，再决定下一步。",
                "danger": True,
            },
            {
                "action": "automation_mode_manual",
                "label": "切到手动",
                "detail": "直接改成手动模式，不再继续自动推进。",
                "danger": False,
            },
            {
                "action": "automation_dry_run_only",
                "label": "只保留 dry-run",
                "detail": "继续自动研究和 dry-run，但不进入真实小额 live。",
                "danger": False,
            },
            {
                "action": "automation_kill_switch",
                "label": "Kill Switch",
                "detail": "一键停机，立即切回最保守状态。",
                "danger": True,
            },
        ]

    def _build_focus_cards(
        self,
        *,
        alert_summary: dict[str, object],
        takeover_summary: dict[str, str],
        operator_actions: list[dict[str, str]],
        last_alert: dict[str, object] | None,
        run_health: dict[str, object],
    ) -> dict[str, dict[str, str]]:
        """把任务页最常看的三组信息压成前端可直接渲染的卡片。"""

        return {
            "alert": self._build_alert_focus_card(
                alert_summary=alert_summary,
                last_alert=last_alert,
                run_health=run_health,
            ),
            "takeover": self._build_takeover_focus_card(
                takeover_summary=takeover_summary,
                run_health=run_health,
                alert_summary=alert_summary,
            ),
            "recovery": self._build_recovery_focus_card(
                operator_actions=operator_actions,
                takeover_summary=takeover_summary,
                run_health=run_health,
                alert_summary=alert_summary,
            ),
        }

    def _build_alert_story(
        self,
        *,
        alert_summary: dict[str, object],
        active_blockers: list[dict[str, str]],
        operator_actions: list[dict[str, str]],
        last_alert: dict[str, object] | None,
        run_health: dict[str, object],
    ) -> dict[str, str]:
        """把告警压成“发生了什么 / 该做什么”的统一摘要。"""

        latest_code = str(alert_summary.get("latest_code", "") or "")
        latest_level = str(alert_summary.get("latest_level", "") or "").lower()
        latest_message = str(alert_summary.get("latest_message", "") or "")
        latest_source = str(alert_summary.get("latest_source", "") or "tasks")
        escalation_level = str(run_health.get("escalation_level", "normal") or "normal")
        primary_blocker = active_blockers[0] if active_blockers else {}
        primary_action = operator_actions[0] if operator_actions else {}
        target_page = self._resolve_alert_target_page(
            code=latest_code,
            level=latest_level,
            source=latest_source,
        )
        target_href = target_page

        if not latest_code and not latest_message:
            return {
                "tone": "ok",
                "headline": "当前没有需要立即处理的告警",
                "what_happened": "最近没有新的错误或警告，自动化可以继续观察下一轮。",
                "what_to_do": "你现在该做什么：继续观察下一轮自动化结果，按恢复清单定期复核即可。",
                "action_label": str(primary_action.get("label", "") or "继续观察"),
                "target_page": target_page,
                "target_href": target_href,
            }

        alert_label = self._describe_alert_label(code=latest_code, message=latest_message)
        blocker_detail = str(primary_blocker.get("detail", "") or "")
        action_detail = str(primary_action.get("detail", "") or "")
        if latest_level == "error" or escalation_level == "critical":
            headline = f"{alert_label}，先不要继续自动化"
        elif latest_level == "warning":
            headline = f"{alert_label}，这轮先别急着放开自动化"
        else:
            headline = f"{alert_label}，先确认后再继续观察"

        what_happened = f"最近发生了什么：{latest_message or blocker_detail or '系统刚刚捕获到一条需要关注的告警。'}"
        what_to_do = (
            f"你现在该做什么：{action_detail}"
            if action_detail
            else "你现在该做什么：先看任务页和执行页，再决定是否恢复自动化。"
        )
        return {
            "tone": "critical" if latest_level == "error" or escalation_level == "critical" else "warning" if latest_level == "warning" else "info",
            "headline": headline,
            "what_happened": what_happened,
            "what_to_do": what_to_do,
            "action_label": str(primary_action.get("label", "") or "去处理"),
            "target_page": target_page,
            "target_href": target_href,
        }

    @staticmethod
    def _build_alert_focus_card(
        *,
        alert_summary: dict[str, object],
        last_alert: dict[str, object] | None,
        run_health: dict[str, object],
    ) -> dict[str, str]:
        """整理最近告警强度，给任务页直接展示。"""

        latest_code = str(alert_summary.get("latest_code", "") or "")
        latest_message = str(alert_summary.get("latest_message", "") or "")
        latest_level = str(alert_summary.get("latest_level", "") or "").lower()
        error_count = int(alert_summary.get("error_count", 0) or 0)
        warning_count = int(alert_summary.get("warning_count", 0) or 0)
        info_count = int(alert_summary.get("info_count", 0) or 0)
        groups = list(alert_summary.get("groups") or [])
        group_codes = {str(item.get("code", "") or "") for item in groups}
        if (
            latest_level == "error"
            or error_count > 0
            or "sync_failed" in group_codes
            or str(run_health.get("escalation_level", "")) == "critical"
        ):
            critical_detail = latest_message or f"当前已有 {error_count} 条错误告警，需要先人工处理。"
            if "sync_failed" in group_codes or "stale_data" in group_codes:
                critical_detail = "执行器离线或同步陈旧，先人工暂停自动化并确认同步链是否恢复。"
            return {
                "tone": "critical",
                "value": f"高风险 / {latest_code or '错误告警'}",
                "detail": critical_detail,
            }
        if latest_level == "warning" or warning_count > 0 or str(run_health.get("stale_sync_state", "")) == "stale":
            return {
                "tone": "warning",
                "value": f"需要关注 / {latest_code or '警告告警'}",
                "detail": latest_message
                or f"当前有 {warning_count} 条警告，建议先确认同步和执行状态。",
            }
        if latest_level == "info" or info_count > 0 or last_alert:
            return {
                "tone": "info",
                "value": f"最新提示 / {latest_code or '提示告警'}",
                "detail": latest_message or "当前有新的运行提示，继续观察即可。",
            }
        return {
            "tone": "ok",
            "value": "当前没有高风险告警",
            "detail": "最近没有新的错误或警告，自动化可以继续观察下一轮。",
        }

    @staticmethod
    def _build_takeover_focus_card(
        *,
        takeover_summary: dict[str, str],
        run_health: dict[str, object],
        alert_summary: dict[str, object],
    ) -> dict[str, str]:
        """整理人工接管原因，方便前端直接展示。"""

        state_label = str(takeover_summary.get("state_label", "") or "自动化运行中")
        reason_label = str(takeover_summary.get("reason_label", "") or "当前没有接管原因")
        note = str(takeover_summary.get("note", "") or "")
        blocker_detail = str(takeover_summary.get("primary_blocker_detail", "") or "")
        if state_label == "人工接管中":
            return {
                "tone": "critical",
                "value": state_label,
                "detail": f"{reason_label}；{note or blocker_detail or '恢复前先确认阻塞原因。'}",
            }
        if state_label == "已暂停":
            return {
                "tone": "warning",
                "value": state_label,
                "detail": f"{reason_label}；{note or blocker_detail or '恢复前先确认暂停原因。'}",
            }
        groups = list(alert_summary.get("groups") or [])
        group_codes = {str(item.get("code", "") or "") for item in groups}
        if (
            str(run_health.get("escalation_level", "")) == "critical"
            or int(alert_summary.get("error_count", 0) or 0) > 0
            or "sync_failed" in group_codes
        ):
            return {
                "tone": "critical",
                "value": "建议立即人工接管",
                "detail": "先人工暂停自动化，再处理执行器离线、同步失败或其他关键阻塞。",
            }
        return {
            "tone": "ok",
            "value": "暂不需要人工接管",
            "detail": note or "当前没有接管或暂停，系统会继续自动推进。",
        }

    @staticmethod
    def _build_recovery_focus_card(
        *,
        operator_actions: list[dict[str, str]],
        takeover_summary: dict[str, str],
        run_health: dict[str, object],
        alert_summary: dict[str, object],
    ) -> dict[str, str]:
        """整理恢复前最该做的事。"""

        action_summaries = []
        for item in operator_actions:
            label = str(item.get("label", "") or "").strip()
            detail = str(item.get("detail", "") or "").strip()
            if not label:
                continue
            action_summaries.append(f"{label}：{detail}" if detail else label)
        groups = list(alert_summary.get("groups") or [])
        group_codes = {str(item.get("code", "") or "") for item in groups}
        should_escalate = (
            str(run_health.get("escalation_level", "")) == "critical"
            or int(alert_summary.get("error_count", 0) or 0) > 0
            or "sync_failed" in group_codes
        )
        if action_summaries:
            if should_escalate:
                return {
                    "tone": "critical",
                    "value": f"恢复前先做 {len(action_summaries)} 件事",
                    "detail": "先人工暂停自动化并处理阻塞，确认无误后再恢复自动化。",
                }
            tone = "critical" if should_escalate else "warning"
            total = len(action_summaries)
            return {
                "tone": tone,
                "value": f"恢复前先做 {total} 件事",
                "detail": " / ".join(action_summaries[:3]),
            }
        if should_escalate:
            return {
                "tone": "critical",
                "value": "恢复前先人工确认",
                "detail": "先人工暂停自动化并处理阻塞，确认无误后再恢复自动化。",
            }
        return {
            "tone": "ok",
            "value": str(takeover_summary.get("next_step", "") or "可以继续下一轮自动化"),
            "detail": "当前没有额外恢复动作，继续观察下一轮自动化结果即可。",
        }

    def _build_severity_summary(
        self,
        *,
        active_blockers: list[dict[str, str]],
        last_alert: dict[str, object] | None,
        run_health: dict[str, object],
        alert_summary: dict[str, object],
    ) -> dict[str, str]:
        """整理当前风险等级，方便任务页直接判断是否该停手。"""

        escalation_level = str(run_health.get("escalation_level", "normal") or "normal")
        groups = list(alert_summary.get("groups") or [])
        group_codes = {str(item.get("code", "") or "") for item in groups}
        if (
            int(alert_summary.get("error_count", 0) or 0) > 0
            or "sync_failed" in group_codes
        ) and escalation_level == "normal":
            escalation_level = "critical"
        if escalation_level == "critical":
            label = "需要立刻人工接管"
            detail = "当前已有关键阻塞或错误告警，先停下自动化并人工确认。"
        elif escalation_level == "high":
            label = "建议先人工确认"
            detail = "系统已暂停或进入人工接管，恢复前先按清单逐项确认。"
        else:
            label = "当前风险可控"
            detail = "当前没有关键阻塞，可以继续按既定顺序推进。"
        primary_blocker = active_blockers[0] if active_blockers else {}
        return {
            "level": escalation_level,
            "label": label,
            "detail": detail,
            "latest_alert_code": str(last_alert.get("code", "")) if last_alert else "",
            "primary_blocker": str(primary_blocker.get("label", "")),
        }

    @staticmethod
    def _describe_alert_label(*, code: str, message: str) -> str:
        """把告警码翻译成更直白的标题。"""

        normalized = str(code or "").strip().lower()
        mapping = {
            "executor_offline": "执行器离线",
            "sync_failed": "同步失败",
            "sync_delayed": "同步延迟",
            "stale_data": "数据已经陈旧",
            "train_failed": "自动训练失败",
            "infer_failed": "自动推理失败",
            "dispatch_execution_failed": "执行派发失败",
        }
        if normalized in mapping:
            return mapping[normalized]
        return str(message or code or "当前有新的告警").strip()

    @staticmethod
    def _resolve_alert_target_page(*, code: str, level: str, source: str) -> str:
        """按告警类型给出最合适的处理页面。"""

        normalized_code = str(code or "").strip().lower()
        normalized_source = str(source or "").strip().lower()
        normalized_level = str(level or "").strip().lower()
        if any(key in normalized_code for key in ("train", "infer", "research")):
            return "/research"
        if any(key in normalized_code for key in ("backtest", "gate", "evaluation")):
            return "/evaluation"
        if any(key in normalized_code for key in ("executor", "execution", "dispatch", "order", "position")):
            return "/strategies"
        if "sync" in normalized_code or normalized_source == "sync":
            return "/tasks"
        if normalized_level == "warning":
            return "/evaluation"
        return "/tasks"

    def _build_resume_checklist(
        self,
        *,
        latest_status: dict[str, object],
        active_blockers: list[dict[str, str]],
        last_alert: dict[str, object] | None,
        alert_summary: dict[str, object],
    ) -> list[dict[str, str]]:
        """给出恢复自动化前最小检查清单。"""

        latest_sync_status = str(latest_status.get("sync", "unknown") or "unknown")
        groups = list(alert_summary.get("groups") or [])
        group_codes = {str(item.get("code", "") or "") for item in groups}
        has_error_alert = bool(last_alert and str(last_alert.get("level", "")).lower() == "error") or int(alert_summary.get("error_count", 0) or 0) > 0 or "sync_failed" in group_codes
        hard_pause_reasons = {
            "kill_switch",
            "risk_guard_triggered",
            "consecutive_failure_guard_triggered",
            "stale_sync_guard_triggered",
            "workflow_train_failed",
            "workflow_infer_failed",
            "workflow_signal_output_failed",
            "dispatch_execution_failed",
        }
        primary_blocker_code = str((active_blockers[0] if active_blockers else {}).get("code", "") or "")
        manual_pending_reasons = hard_pause_reasons | {"manual_takeover", "manual_review"}
        has_manual_reason_pending = self._manual_takeover or self._paused_reason in manual_pending_reasons
        return [
            {
                "label": "告警强度",
                "status": "pending" if has_error_alert else "ready",
                "detail": "如果最近告警还是 error，先处理它，再恢复自动化。",
            },
            {
                "label": "人工接管原因",
                "status": "pending" if has_manual_reason_pending else "ready",
                "detail": "如果这次暂停或接管来自风控、连续失败或执行异常，先把根因处理完。",
            },
            {
                "label": "同步状态",
                "status": "pending" if latest_sync_status not in {"succeeded", "unknown"} else "ready",
                "detail": "先确认最近一次同步已经成功，避免研究结果和账户状态错位。",
            },
            {
                "label": "恢复前先做什么",
                "status": (
                    "pending"
                    if active_blockers and primary_blocker_code not in {"none", "manual_mode", "paused", "manual_takeover"}
                    else "ready"
                ),
                "detail": "按阻塞清单和恢复建议逐项处理完，再按恢复按钮继续自动化。",
            },
        ]

    @staticmethod
    def _describe_pause_reason(reason: str) -> str:
        """把接管原因转成更直白的中文。"""

        normalized = str(reason or "").strip()
        mapping = {
            "kill_switch": "Kill Switch 已触发",
            "manual_pause": "人工暂停自动化",
            "manual_stop": "人工暂停自动化",
            "manual_takeover": "人工主动接管",
            "manual_review": "人工复核中",
            "risk_guard_triggered": "风控触发人工接管",
            "consecutive_failure_guard_triggered": "连续失败阈值触发人工接管",
            "stale_sync_guard_triggered": "同步陈旧阈值触发人工接管",
            "workflow_train_failed": "自动训练失败",
            "workflow_infer_failed": "自动推理失败",
            "workflow_signal_output_failed": "研究信号输出失败",
            "dispatch_execution_failed": "执行派发失败",
        }
        if not normalized:
            return "当前没有接管原因"
        return mapping.get(normalized, normalized)

    def _build_run_health(
        self,
        *,
        latest_status: dict[str, object],
        latest_failure: dict[str, object],
        failure_counts: dict[str, object],
        last_alert: dict[str, object] | None,
    ) -> dict[str, object]:
        """补充长期运行最关心的失败连续性和升级级别。"""

        operations = self._get_operations_config()
        latest_sync_status = str(latest_status.get("sync", "unknown"))
        latest_sync_failure = dict(latest_failure.get("sync") or {})
        stale_sync_threshold = int(operations.get("stale_sync_failure_threshold", 1) or 1)
        pause_after_failures = int(operations.get("pause_after_consecutive_failures", 2) or 2)
        raw_sync_failure_count = failure_counts.get("sync", 0)
        sync_failure_count = int(raw_sync_failure_count or 0)
        if sync_failure_count <= 0 and latest_sync_status not in {"succeeded", "unknown"}:
            sync_failure_count = self._consecutive_failure_count
        stale_sync_state = (
            "stale"
            if latest_sync_status not in {"succeeded", "unknown"}
            and sync_failure_count >= stale_sync_threshold
            else "fresh"
        )
        escalation_level = "normal"
        if self._paused_reason == "kill_switch":
            escalation_level = "critical"
        elif self._manual_takeover or self._paused:
            escalation_level = "high"
        if self._consecutive_failure_count >= pause_after_failures or stale_sync_state == "stale":
            escalation_level = "critical"
        if last_alert and str(last_alert.get("level", "")).lower() == "error":
            escalation_level = "critical"
        return {
            "consecutive_failure_count": self._consecutive_failure_count,
            "sync_failure_count": sync_failure_count,
            "last_success_at": self._last_success_at,
            "last_failure_at": self._last_failure_at,
            "last_sync_failure_at": str(latest_sync_failure.get("finished_at", "")),
            "stale_sync_state": stale_sync_state,
            "escalation_level": escalation_level,
            "pause_after_consecutive_failures": pause_after_failures,
            "stale_sync_failure_threshold": stale_sync_threshold,
            "auto_pause_on_error": bool(operations.get("auto_pause_on_error", True)),
            "review_limit": int(operations.get("review_limit", 10) or 10),
            "paused_since": self._paused_at,
            "takeover_since": self._manual_takeover_at,
        }

    @staticmethod
    def _get_operations_config() -> dict[str, object]:
        """读取长期运行配置。"""

        config = workbench_config_service.get_config()
        operations = dict(config.get("operations") or {})
        preset_key = str(operations.get("operations_preset_key", "balanced_guard"))
        catalog = _build_operations_preset_catalog()
        return {
            "operations_preset_key": preset_key,
            "operations_preset_detail": _describe_catalog_item(
                catalog,
                key=preset_key,
                title="长期运行预设",
            ),
            "available_operations_presets": [str(item.get("key", "")) for item in catalog if str(item.get("key", "")).strip()],
            "operations_preset_catalog": catalog,
            "pause_after_consecutive_failures": int(operations.get("pause_after_consecutive_failures", 2) or 2),
            "stale_sync_failure_threshold": int(operations.get("stale_sync_failure_threshold", 1) or 1),
            "auto_pause_on_error": bool(operations.get("auto_pause_on_error", True)),
            "review_limit": int(operations.get("review_limit", 10) or 10),
            "comparison_run_limit": int(operations.get("comparison_run_limit", 5) or 5),
            "cycle_cooldown_minutes": int(operations.get("cycle_cooldown_minutes", 15) or 15),
            "max_daily_cycle_count": int(operations.get("max_daily_cycle_count", 8) or 8),
        }

    @staticmethod
    def _get_execution_policy() -> dict[str, object]:
        """读取当前执行安全门配置。"""

        config = workbench_config_service.get_config()
        execution = dict(config.get("execution") or {})
        candidate_scope = workbench_config_service.build_candidate_scope_contract(config)
        return {
            **candidate_scope,
            "live_max_stake_usdt": str(execution.get("live_max_stake_usdt", "")),
            "live_max_open_trades": str(execution.get("live_max_open_trades", "")),
        }

    @staticmethod
    def _get_automation_config() -> dict[str, object]:
        """读取自动化长期运行配置。"""

        config = workbench_config_service.get_config()
        automation = dict(config.get("automation") or {})
        preset_key = str(automation.get("automation_preset_key", "balanced_runtime"))
        catalog = _build_automation_preset_catalog()
        return {
            "automation_preset_key": preset_key,
            "automation_preset_detail": _describe_catalog_item(
                catalog,
                key=preset_key,
                title="自动化运行预设",
            ),
            "available_automation_presets": [str(item.get("key", "")) for item in catalog if str(item.get("key", "")).strip()],
            "automation_preset_catalog": catalog,
            "long_run_seconds": int(automation.get("long_run_seconds", 300) or 300),
            "alert_cleanup_minutes": int(automation.get("alert_cleanup_minutes", 15) or 15),
        }

    def _filter_active_alerts(self, *, cleanup_minutes: int) -> list[dict[str, object]]:
        """按清理窗口筛出仍算活跃的告警。"""

        if cleanup_minutes <= 0:
            return list(self._alerts)
        threshold = datetime.now(timezone.utc).timestamp() - cleanup_minutes * 60
        active: list[dict[str, object]] = []
        for item in self._alerts:
            created_at = str(item.get("created_at", "") or "").strip()
            if not created_at:
                continue
            try:
                created = datetime.fromisoformat(created_at)
            except ValueError:
                continue
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created.astimezone(timezone.utc).timestamp() >= threshold:
                active.append(item)
        return active

    def run_cycle(self, *, actor: str = "user") -> dict[str, object]:
        """兼容路由层的统一自动化周期入口。"""

        from services.api.app.tasks.scheduler import task_scheduler

        return task_scheduler.run_named_task(
            task_type="automation_cycle",
            source=actor,
            target_type="system",
            payload={"source": actor},
        )

    def _resolve_state_path(self) -> Path:
        """解析自动化状态文件路径。"""

        raw_path = Settings.from_env().automation_state_path
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        return candidate

    def _load_state(self) -> None:
        """在服务启动时恢复最近一次自动化状态。"""

        if not self._state_path.exists():
            return
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception:
            # Try to restore from backup if primary state file is corrupted
            payload = self._restore_from_backup()
            if payload is None:
                return
        if not isinstance(payload, dict):
            payload = self._restore_from_backup()
            if payload is None:
                return
        self._apply_state_payload(payload)

    def _persist_state(self) -> None:
        """把当前自动化状态写回本地状态文件，使用原子写入。"""

        payload = {
            "mode": self._mode,
            "paused": self._paused,
            "paused_reason": self._paused_reason,
            "manual_takeover": self._manual_takeover,
            "updated_at": self._updated_at,
            "last_cycle": self._last_cycle,
            "alerts": self._alerts,
            "next_alert_id": self._next_alert_id,
            "armed_symbol": self._armed_symbol,
            "armed_at": self._armed_at,
            "daily_summary": self._daily_summary,
            "consecutive_failure_count": self._consecutive_failure_count,
            "last_success_at": self._last_success_at,
            "last_failure_at": self._last_failure_at,
            "paused_at": self._paused_at,
            "manual_takeover_at": self._manual_takeover_at,
        }
        self._state_path.parent.mkdir(parents=True, exist_ok=True)

        # Create backup before writing new state
        self._backup_state()

        # Atomic write: write to temp file then rename
        temp_path = self._state_path.with_suffix(".tmp")
        try:
            temp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            # Ensure data is flushed to disk
            with open(temp_path, "r+b") as f:
                f.flush()
                os.fsync(f.fileno())
            # Atomic rename
            shutil.move(str(temp_path), str(self._state_path))
        except Exception:
            # Clean up temp file if write failed
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            raise

    def _backup_state(self) -> None:
        """备份当前状态文件，保留最近 MAX_BACKUP_COUNT 个备份。"""

        if not self._state_path.exists():
            return

        backup_dir = self._state_path.parent
        base_name = self._state_path.stem
        suffix = self._state_path.suffix

        # Create new backup with timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        new_backup = backup_dir / f"{base_name}_backup_{timestamp}{suffix}"

        try:
            shutil.copy2(str(self._state_path), str(new_backup))
        except OSError:
            return

        # Clean up old backups, keep only the most recent ones
        backups = sorted(
            backup_dir.glob(f"{base_name}_backup_*{suffix}"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old_backup in backups[MAX_BACKUP_COUNT:]:
            try:
                old_backup.unlink()
            except OSError:
                pass

    def _restore_from_backup(self) -> dict[str, object] | None:
        """从备份恢复状态，按修改时间优先。"""

        backup_dir = self._state_path.parent
        base_name = self._state_path.stem
        suffix = self._state_path.suffix

        backups = sorted(
            backup_dir.glob(f"{base_name}_backup_*{suffix}"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for backup in backups:
            try:
                payload = json.loads(backup.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return payload
            except Exception:
                continue

        return None

    def _apply_state_payload(self, payload: dict[str, object]) -> None:
        """把状态载荷恢复到当前实例。"""

        mode = str(payload.get("mode", "manual")).strip().lower().replace("-", "_")
        if mode in AUTOMATION_MODES:
            self._mode = mode
        self._paused = bool(payload.get("paused"))
        self._paused_reason = str(payload.get("paused_reason", ""))
        self._manual_takeover = bool(payload.get("manual_takeover"))
        self._updated_at = str(payload.get("updated_at", _utc_now()))
        self._last_cycle = dict(payload.get("last_cycle") or {})
        self._alerts = [dict(item) for item in list(payload.get("alerts") or []) if isinstance(item, dict)][:20]
        self._next_alert_id = int(payload.get("next_alert_id", len(self._alerts) + 1) or (len(self._alerts) + 1))
        self._armed_symbol = str(payload.get("armed_symbol", "")).strip().upper()
        self._armed_at = str(payload.get("armed_at", ""))
        daily_summary = dict(payload.get("daily_summary") or {})
        self._daily_summary = daily_summary if daily_summary else self._new_daily_summary()
        self._consecutive_failure_count = int(payload.get("consecutive_failure_count", 0) or 0)
        self._last_success_at = str(payload.get("last_success_at", ""))
        self._last_failure_at = str(payload.get("last_failure_at", ""))
        self._paused_at = str(payload.get("paused_at", ""))
        self._manual_takeover_at = str(payload.get("manual_takeover_at", ""))
        if self._mode == "manual" and not self._paused:
            self._manual_takeover = False
            self._manual_takeover_at = ""
        if self._mode != "manual" and self._paused_reason in {"manual_pause", "manual_stop"} and self._paused:
            self._manual_takeover = False
            self._manual_takeover_at = ""
        self._ensure_daily_summary()

    def _apply_execution_guard(self, *, paused: bool, stop_executor: bool) -> None:
        """同步全局风控开关，并尽量把执行器状态收口。"""

        risk_service.set_global_pause(paused)
        if not paused:
            return
        action = "stop" if stop_executor else "pause"
        strategy_ids = self._resolve_executor_strategy_ids()
        for strategy_id in strategy_ids:
            try:
                freqtrade_client.control_strategy(strategy_id, action)
            except Exception:
                self.record_alert(
                    level="warning",
                    code="executor_control_failed",
                    message="自动化已暂停，但执行器状态确认失败",
                    source="automation-service",
                    detail=f"{action}:{strategy_id}",
                )

    @staticmethod
    def _resolve_executor_strategy_ids() -> list[int]:
        """尽量解析执行器里可控制的策略列表。"""

        try:
            snapshot = freqtrade_client.get_snapshot()
            raw_strategies = getattr(snapshot, "strategies", None)
        except Exception:
            return [1]
        if not isinstance(raw_strategies, list):
            return [1]
        strategy_ids: list[int] = []
        for item in raw_strategies:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id")
            if isinstance(raw_id, int) and raw_id > 0:
                strategy_ids.append(raw_id)
                continue
            if isinstance(raw_id, str) and raw_id.isdigit():
                strategy_ids.append(int(raw_id))
        return sorted(set(strategy_ids)) if strategy_ids else [1]

    @staticmethod
    def _new_daily_summary() -> dict[str, object]:
        """创建当日自动化摘要。"""

        return {
            "date": _utc_now()[:10],
            "cycle_count": 0,
            "status_counts": {},
            "alert_count": 0,
            "alert_level_counts": {},
        }

    def _ensure_daily_summary(self) -> None:
        """跨天时自动重置日报摘要。"""

        current_date = _utc_now()[:10]
        if str(self._daily_summary.get("date", "")) != current_date:
            self._daily_summary = self._new_daily_summary()


automation_service = AutomationService()

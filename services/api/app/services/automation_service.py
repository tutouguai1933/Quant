"""自动化状态服务。

这个文件负责保存自动化模式、停机状态、最近告警和健康摘要。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.api.app.adapters.freqtrade.client import freqtrade_client
from services.api.app.core.settings import Settings
from services.api.app.services.risk_service import risk_service


AUTOMATION_MODES = {"manual", "auto_dry_run", "auto_live"}


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
        self._load_state()

    def get_state(self) -> dict[str, object]:
        """返回当前自动化状态。"""

        settings = Settings.from_env()
        last_cycle = dict(self._last_cycle)
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
        }

    def get_status(self, *, task_health: dict[str, object] | None = None) -> dict[str, object]:
        """返回当前状态和健康摘要。"""

        if task_health is None:
            from services.api.app.tasks.scheduler import task_scheduler

            task_health = task_scheduler.get_health_summary()
        health = self.build_health_summary(task_health=task_health or {})
        return {
            "state": self.get_state(),
            "health": health,
            "active_blockers": list(health.get("active_blockers") or []),
            "operator_actions": list(health.get("operator_actions") or []),
            "takeover_summary": dict(health.get("takeover_summary") or {}),
            "alert_summary": dict(health.get("alert_summary") or {}),
            "alerts_count": len(self._alerts),
            "latest_alert_level": str(self._alerts[0]["level"]) if self._alerts else "",
            "latest_alert_title": str(self._alerts[0]["message"]) if self._alerts else "",
            "daily_summary": dict(self._daily_summary),
        }

    def set_mode(self, mode: str) -> dict[str, object]:
        """切换自动化模式。"""

        normalized = mode.strip().lower().replace("-", "_")
        if normalized not in AUTOMATION_MODES:
            raise ValueError("automation mode must be manual, auto_dry_run or auto_live")
        self._mode = normalized
        self._manual_takeover = normalized == "manual"
        if normalized == "manual":
            self.clear_armed_symbol()
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
        self._manual_takeover = True
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

        self._mode = "manual"
        self._paused = True
        self._paused_reason = reason.strip() or "manual_takeover"
        self._manual_takeover = True
        self.clear_armed_symbol()
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

        self._paused = False
        self._paused_reason = ""
        self._manual_takeover = self._mode == "manual"
        self._apply_execution_guard(paused=False, stop_executor=False)
        self._updated_at = _utc_now()
        self.record_alert(level="info", code="automation_resumed", message="自动化已恢复", source=actor)
        self._persist_state()
        return {
            **self.get_state(),
            "actor": actor,
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

    def record_cycle(self, payload: dict[str, object]) -> None:
        """记录最近一次自动化工作流结果。"""

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

    def build_health_summary(self, *, task_health: dict[str, object]) -> dict[str, Any]:
        """构造自动化健康摘要。"""

        latest_status = dict(task_health.get("latest_status_by_type") or {})
        last_cycle = dict(self._last_cycle)
        last_alert = self._alerts[0] if self._alerts else None
        alert_summary = self._build_alert_summary()
        active_blockers = self._build_active_blockers(latest_status=latest_status, last_alert=last_alert)
        takeover_summary = self._build_takeover_summary(active_blockers=active_blockers)
        operator_actions = self._build_operator_actions(latest_status=latest_status)
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
            "alert_count": len(self._alerts),
            "last_alert": dict(last_alert) if last_alert else None,
            "daily_summary_date": str(self._daily_summary.get("date", "")),
            "takeover_summary": takeover_summary,
            "active_blockers": active_blockers,
            "operator_actions": operator_actions,
            "alert_summary": alert_summary,
            "run_health": self._build_run_health(latest_status=latest_status, last_alert=last_alert),
        }

    def _build_alert_summary(self) -> dict[str, object]:
        """汇总最近告警级别，给前端直接展示。"""

        summary = {
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "latest_code": "",
            "latest_message": "",
            "latest_level": "",
            "latest_source": "",
        }
        if self._alerts:
            summary["latest_code"] = str(self._alerts[0].get("code", ""))
            summary["latest_message"] = str(self._alerts[0].get("message", ""))
            summary["latest_level"] = str(self._alerts[0].get("level", ""))
            summary["latest_source"] = str(self._alerts[0].get("source", ""))
        for item in self._alerts:
            level = str(item.get("level", "")).strip().lower()
            if level == "error":
                summary["error_count"] = int(summary["error_count"]) + 1
            elif level == "warning":
                summary["warning_count"] = int(summary["warning_count"]) + 1
            elif level == "info":
                summary["info_count"] = int(summary["info_count"]) + 1
        return summary

    def _build_takeover_summary(self, *, active_blockers: list[dict[str, str]]) -> dict[str, str]:
        """给出当前是否接管、为什么接管、恢复时先做什么。"""

        if self._manual_takeover:
            state_label = "人工接管中"
        elif self._paused:
            state_label = "已暂停"
        else:
            state_label = "自动化运行中"

        if self._paused_reason == "kill_switch":
            note = "Kill Switch 已触发，恢复前应先确认执行器、仓位和账户同步都正常。"
        elif self._manual_takeover:
            note = "当前已切到人工接管，恢复前先看阻塞原因和最近执行状态。"
        elif self._paused:
            note = "自动化已暂停，恢复前先确认暂停原因是否已经处理。"
        else:
            note = "当前没有接管或暂停，系统可以继续自动推进。"
        primary_blocker = active_blockers[0] if active_blockers else {}

        return {
            "state_label": state_label,
            "reason": self._paused_reason or "当前没有接管原因",
            "suggested_mode": "manual" if self._manual_takeover or self._paused else self._mode,
            "note": note,
            "primary_blocker_code": str(primary_blocker.get("code", "")),
            "primary_blocker_detail": str(primary_blocker.get("detail", "")),
            "next_step": "先处理阻塞原因，再恢复自动化" if self._manual_takeover or self._paused else "可以继续下一轮自动化",
        }

    def _build_active_blockers(
        self,
        *,
        latest_status: dict[str, object],
        last_alert: dict[str, object] | None,
    ) -> list[dict[str, str]]:
        """把当前真正阻塞自动化继续推进的原因整理成列表。"""

        blockers: list[dict[str, str]] = []
        if self._paused:
            blockers.append(
                {
                    "code": "paused",
                    "severity": "warning",
                    "label": "自动化已暂停",
                    "detail": f"自动化当前已暂停，原因：{self._paused_reason or 'manual_pause'}",
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
        latest_sync_status = str(latest_status.get("sync", "unknown"))
        if latest_sync_status == "failed":
            blockers.append(
                {
                    "code": "sync_failed",
                    "severity": "error",
                    "label": "执行结果还没有同步收口",
                    "detail": "最近一次同步失败，执行结果和账户状态还没有完全收口。",
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

    def _build_operator_actions(self, *, latest_status: dict[str, object]) -> list[dict[str, str]]:
        """给前端一组直接可执行的恢复步骤。"""

        actions: list[dict[str, str]] = []
        if self._paused or self._manual_takeover:
            actions.append(
                {
                    "action": "automation_resume",
                    "label": "恢复自动化",
                    "detail": "确认阻塞原因已处理后，再恢复当前自动化模式。",
                }
            )
        if str(latest_status.get("sync", "unknown")) == "failed":
            actions.append(
                {
                    "action": "automation_run_cycle",
                    "label": "重跑一轮同步链",
                    "detail": "先重新跑一轮训练、推理、执行和复盘，确认同步是否恢复。",
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
                    "label": "继续下一轮",
                    "detail": "当前没有额外恢复步骤，可以直接继续下一轮自动化工作流。",
                }
            )
        return actions

    def _build_run_health(
        self,
        *,
        latest_status: dict[str, object],
        last_alert: dict[str, object] | None,
    ) -> dict[str, object]:
        """补充长期运行最关心的失败连续性和升级级别。"""

        latest_sync_status = str(latest_status.get("sync", "unknown"))
        stale_sync_state = "stale" if latest_sync_status not in {"succeeded", "unknown"} else "fresh"
        escalation_level = "normal"
        if self._paused_reason == "kill_switch":
            escalation_level = "critical"
        elif self._manual_takeover or self._paused:
            escalation_level = "high"
        if self._consecutive_failure_count >= 2 or stale_sync_state == "stale":
            escalation_level = "critical"
        if last_alert and str(last_alert.get("level", "")).lower() == "error":
            escalation_level = "critical"
        return {
            "consecutive_failure_count": self._consecutive_failure_count,
            "last_success_at": self._last_success_at,
            "stale_sync_state": stale_sync_state,
            "escalation_level": escalation_level,
        }

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
            return
        if not isinstance(payload, dict):
            return
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
        self._ensure_daily_summary()

    def _persist_state(self) -> None:
        """把当前自动化状态写回本地状态文件。"""

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
        }
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

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

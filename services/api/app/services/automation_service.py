"""自动化状态服务。

这个文件负责保存自动化模式、停机状态、最近告警和健康摘要。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.api.app.core.settings import Settings
from services.api.app.services.workbench_config_service import workbench_config_service


AUTOMATION_MODES = {"manual", "auto_dry_run", "auto_live"}

_last_state_path: Path | None = None
_last_state_payload: dict[str, object] | None = None


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
            "automation_config": workbench_config_service.get_config().get("automation", {}),
        }

    def get_status(self, *, task_health: dict[str, object] | None = None) -> dict[str, object]:
        """返回当前状态和健康摘要。"""

        if task_health is None:
            from services.api.app.tasks.scheduler import task_scheduler

            task_health = task_scheduler.get_health_summary()
        return {
            "state": self.get_state(),
            "health": self.build_health_summary(task_health=task_health or {}),
            "alerts_count": len(self._alerts),
            "latest_alert_level": str(self._alerts[0]["level"]) if self._alerts else "",
            "latest_alert_title": str(self._alerts[0]["message"]) if self._alerts else "",
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

    def pause(self, reason: str = "manual_pause", *, actor: str = "user") -> dict[str, object]:
        """暂停自动化。"""

        self._paused = True
        self._paused_reason = reason.strip() or "manual_pause"
        self._manual_takeover = True
        self._updated_at = _utc_now()
        self.record_alert(level="warning", code="automation_paused", message="自动化已暂停", source=actor)
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

        self._last_cycle = {
            **dict(payload),
            "recorded_at": _utc_now(),
        }
        self._updated_at = _utc_now()
        self._persist_state()

    def record_alert(self, *, level: str, code: str, message: str, source: str, detail: str = "") -> dict[str, object]:
        """记录自动化告警。"""

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
        self._updated_at = _utc_now()
        self._persist_state()
        return dict(item)

    def build_health_summary(self, *, task_health: dict[str, object]) -> dict[str, Any]:
        """构造自动化健康摘要。"""

        latest_status = dict(task_health.get("latest_status_by_type") or {})
        last_cycle = dict(self._last_cycle)
        last_alert = self._alerts[0] if self._alerts else None
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

        for candidate in self._state_path_candidates():
            if not candidate.exists():
                continue
            payload = self._read_state_payload(candidate)
            if payload is None:
                continue
            self._apply_state_payload(payload)
            self._state_path = candidate
            return
        if _last_state_payload is not None:
            self._apply_state_payload(_last_state_payload)

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
        }
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        global _last_state_path, _last_state_payload
        _last_state_path = self._state_path
        _last_state_payload = dict(payload)

    def _state_path_candidates(self) -> list[Path]:
        """按照优先级返回可用的状态文件路径。"""

        candidates: list[Path] = []
        if _last_state_path and _last_state_path != self._state_path:
            candidates.append(_last_state_path)
        candidates.append(self._state_path)
        return candidates

    def _read_state_payload(self, path: Path) -> dict[str, object] | None:
        """从指定路径读取状态载荷。"""

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _apply_state_payload(self, payload: dict[str, object]) -> None:
        """把读取到的状态写入实例。"""

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

automation_service = AutomationService()

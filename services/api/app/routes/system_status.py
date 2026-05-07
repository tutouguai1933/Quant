"""系统综合状态 API。

提供系统各组件运行状态的统一查询接口。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from services.api.app.services.scheduled_patrol_service import scheduled_patrol_service
from services.api.app.services.automation_service import automation_service
from services.api.app.services.vpn_switch_service import vpn_switch_service

router = APIRouter(prefix="/api/v1/system", tags=["system"])


def _success(data: dict[str, Any]) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {"source": "system-status"}}


@router.get("/status")
def get_system_status() -> dict[str, Any]:
    """获取系统综合状态。

    返回各组件的运行状态，用于前端监控面板显示。

    Returns:
        - patrol: 定时巡检状态
        - automation: 自动化状态
        - proxy: 代理状态
        - daily_summary: 今日统计
    """
    result: dict[str, Any] = {
        "patrol": {},
        "automation": {},
        "proxy": {},
        "daily_summary": {},
    }

    # 1. 定时巡检状态
    try:
        patrol_status = scheduled_patrol_service.get_schedule_status()
        result["patrol"] = {
            "running": patrol_status.get("running", False),
            "interval_minutes": patrol_status.get("interval_minutes", 0),
            "last_run_at": patrol_status.get("last_run_at"),
            "last_run_status": patrol_status.get("last_run_status"),
            "total_runs": patrol_status.get("total_runs", 0),
            "failed_runs": patrol_status.get("failed_runs", 0),
        }
    except Exception:
        result["patrol"] = {"running": False, "error": True}

    # 2. 自动化状态
    try:
        auto_state = automation_service.get_state()
        result["automation"] = {
            "mode": auto_state.get("mode", "manual"),
            "paused": auto_state.get("paused", False),
            "manual_takeover": auto_state.get("manual_takeover", False),
            "armed_symbol": auto_state.get("armed_symbol", ""),
            "consecutive_failure_count": auto_state.get("consecutive_failure_count", 0),
            "last_cycle_status": auto_state.get("last_cycle", {}).get("status", ""),
        }

        # 今日统计
        daily_summary = auto_state.get("daily_summary", {})
        result["daily_summary"] = {
            "date": daily_summary.get("date", ""),
            "cycle_count": daily_summary.get("cycle_count", 0),
            "alert_count": daily_summary.get("alert_count", 0),
        }
    except Exception:
        result["automation"] = {"error": True}
        result["daily_summary"] = {}

    # 3. 代理状态
    try:
        current_node = vpn_switch_service.current_node
        exit_ip = vpn_switch_service.get_current_exit_ip_sync()
        # 有出口IP就算连接成功
        result["proxy"] = {
            "connected": bool(exit_ip),
            "current_node": current_node or "",
            "exit_ip": exit_ip or "",
        }
    except Exception:
        result["proxy"] = {"connected": False, "error": True}

    return _success(result)

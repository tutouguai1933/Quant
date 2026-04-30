"""交易报告API路由。

提供以下接口:
- GET /api/v1/report/daily - 日报
- GET /api/v1/report/weekly - 周报
- GET /api/v1/report/history - 报告历史
- POST /api/v1/report/generate - 手动生成报告
- GET /api/v1/report/status - 服务状态
"""

from __future__ import annotations

from typing import Any

from services.api.app.services.report_service import report_service
from services.api.app.services.auth_service import auth_service


try:
    from fastapi import APIRouter, Header
except ImportError:
    class APIRouter:  # pragma: no cover - lightweight local fallback
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def get(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

        def post(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    def Header(default: str = "") -> str:  # pragma: no cover - fallback stub
        return default


router = APIRouter(prefix="/api/v1/report", tags=["report"])


def _success(data: dict, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def _error(code: str, message: str, meta: dict | None = None) -> dict:
    return {"data": None, "error": {"code": code, "message": message}, "meta": meta or {}}


def _unauthorized() -> dict:
    return _error("unauthorized", "authentication required", {"source": "control-plane-api"})


def _build_meta(action: str, **kwargs: object) -> dict[str, object]:
    """构建统一的元数据结构。"""
    meta: dict[str, object] = {
        "source": "control-plane-api",
        "action": action,
    }
    meta.update(kwargs)
    return meta


@router.get("")
def get_report_status() -> dict:
    """获取报告服务状态。"""
    status = report_service.get_service_status()
    return _success(status, _build_meta("status"))


@router.get("/daily")
def get_daily_report(date: str | None = None, format: str = "json") -> dict:
    """获取每日交易报告。

    Args:
        date: YYYY-MM-DD 格式的日期，默认为今天
        format: 输出格式 (json/markdown)
    """
    # 首先检查缓存
    if date:
        cached = report_service.get_cached_daily_report(date)
        if cached:
            if format == "markdown":
                return _success(
                    {"markdown": cached.markdown_content, "date": cached.date},
                    _build_meta("daily-report", date=cached.date, format="markdown", cached=True),
                )
            return _success(
                {"report": cached.to_dict()},
                _build_meta("daily-report", date=cached.date, format="json", cached=True),
            )

    # 生成新报告
    report = report_service.generate_daily_report(date=date)

    if format == "markdown":
        return _success(
            {"markdown": report.markdown_content, "date": report.date},
            _build_meta("daily-report", date=report.date, format="markdown", cached=False),
        )

    return _success(
        {"report": report.to_dict()},
        _build_meta(
            "daily-report",
            date=report.date,
            format="json",
            cached=False,
            trade_count=report.trade_summary.get("trade_count", 0),
        ),
    )


@router.get("/weekly")
def get_weekly_report(week_start: str | None = None, format: str = "json") -> dict:
    """获取每周交易报告。

    Args:
        week_start: YYYY-MM-DD 格式的周一日期，默认为本周
        format: 输出格式 (json/markdown)
    """
    # 首先检查缓存
    if week_start:
        cached = report_service.get_cached_weekly_report(week_start)
        if cached:
            if format == "markdown":
                return _success(
                    {"markdown": cached.markdown_content, "week_start": cached.week_start},
                    _build_meta("weekly-report", week_start=cached.week_start, format="markdown", cached=True),
                )
            return _success(
                {"report": cached.to_dict()},
                _build_meta("weekly-report", week_start=cached.week_start, format="json", cached=True),
            )

    # 生成新报告
    report = report_service.generate_weekly_report(week_start=week_start)

    if format == "markdown":
        return _success(
            {"markdown": report.markdown_content, "week_start": report.week_start},
            _build_meta("weekly-report", week_start=report.week_start, format="markdown", cached=False),
        )

    return _success(
        {"report": report.to_dict()},
        _build_meta(
            "weekly-report",
            week_start=report.week_start,
            week_end=report.week_end,
            format="json",
            cached=False,
        ),
    )


@router.get("/history")
def get_report_history(report_type: str = "daily", limit: int = 10) -> dict:
    """获取报告历史。

    Args:
        report_type: 报告类型 (daily/weekly)
        limit: 返回数量限制
    """
    if report_type not in ["daily", "weekly"]:
        report_type = "daily"

    if limit < 1 or limit > 100:
        limit = 10

    history = report_service.get_report_history(report_type=report_type, limit=limit)
    return _success(
        {"history": history, "report_type": report_type},
        _build_meta(
            "report-history",
            report_type=report_type,
            count=len(history),
            limit=limit,
        ),
    )


@router.post("/generate")
def generate_report(
    payload: dict[str, Any],
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """手动生成报告（需要认证）。

    Args:
        payload: {report_type: "daily"|"weekly", date: "YYYY-MM-DD"}
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    report_type = payload.get("report_type", "daily")
    target_date = payload.get("date")

    if report_type == "daily":
        report = report_service.generate_daily_report(date=target_date)
        return _success(
            {"report": report.to_dict()},
            _build_meta("generate-report", report_type="daily", date=report.date),
        )
    elif report_type == "weekly":
        report = report_service.generate_weekly_report(week_start=target_date)
        return _success(
            {"report": report.to_dict()},
            _build_meta("generate-report", report_type="weekly", week_start=report.week_start),
        )
    else:
        return _error("invalid_request", "report_type must be 'daily' or 'weekly'")


@router.post("/schedule/start")
def start_schedule(
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """启动定时报告生成（需要认证）。"""
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    result = report_service.schedule_report_generation()
    return _success(result, _build_meta("start-schedule", status=result.get("message")))


@router.post("/schedule/stop")
def stop_schedule(
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """停止定时报告生成（需要认证）。"""
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    result = report_service.stop_schedule()
    return _success(result, _build_meta("stop-schedule", status=result.get("message")))
"""Signal query routes for the Control Plane API skeleton."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from services.api.app.services.auth_service import auth_service
from services.api.app.services.strategy_engine import apply_research_soft_gate
from services.api.app.services.strategy_engine import evaluate_trend_breakout
from services.api.app.services.strategy_engine import evaluate_trend_pullback
from services.api.app.services.market_service import MarketService
from services.api.app.services.research_service import research_service
from services.api.app.services.signal_service import SignalPipelineUnavailableError, signal_service
from services.api.app.services.strategy_catalog import strategy_catalog_service


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


router = APIRouter(prefix="/api/v1/signals", tags=["signals"])
market_service = MarketService()


def _success(data: dict, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def _unauthorized() -> dict:
    return {
        "data": None,
        "error": {"code": "unauthorized", "message": "authentication required"},
        "meta": {"source": "control-plane-api"},
    }


@router.get("")
def list_signals(limit: int = 100) -> dict:
    items = signal_service.list_signals(limit=limit)
    return _success(
        {"items": items},
        {
            "limit": limit,
            "source": "control-plane-api",
            "available_sources": ["mock", "qlib", "rule-based"],
        },
    )


@router.get("/research/latest")
def get_latest_research() -> dict:
    item = research_service.get_latest_result()
    return _success({"item": item}, {"source": "control-plane-api", "action": "research-latest"})


@router.get("/research/candidates")
def get_research_candidates() -> dict:
    snapshot = research_service.get_factory_snapshot()
    return _success(
        {"items": snapshot.get("candidates", []), "summary": snapshot.get("summary", {})},
        {
            "source": "control-plane-api",
            "action": "research-candidates",
            "status": snapshot.get("status", "unavailable"),
        },
    )


@router.get("/research/candidates/{symbol}")
def get_research_candidate(symbol: str) -> dict:
    item = research_service.get_factory_symbol(symbol)
    return _success(
        {"item": item},
        {
            "source": "control-plane-api",
            "action": "research-candidate",
            "symbol": symbol.strip().upper(),
        },
    )


@router.post("/research/train")
def run_research_training(token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    try:
        item = research_service.run_training()
        return _success({"item": item}, {"source": "control-plane-api", "action": "research-train"})
    except Exception as exc:
        return {
            "data": None,
            "error": {"code": "research_training_unavailable", "message": str(exc)},
            "meta": {"source": "control-plane-api", "action": "research-train"},
        }


@router.post("/research/infer")
def run_research_inference(token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    try:
        item = research_service.run_inference()
        return _success({"item": item}, {"source": "control-plane-api", "action": "research-infer"})
    except Exception as exc:
        return {
            "data": None,
            "error": {"code": "research_inference_unavailable", "message": str(exc)},
            "meta": {"source": "control-plane-api", "action": "research-infer"},
        }


@router.get("/{signal_id}")
def get_signal(signal_id: int) -> dict:
    item = signal_service.get_signal(signal_id)
    return _success({"item": item}, {"signal_id": signal_id, "source": "control-plane-api"})


@router.post("/ingest")
def ingest_signal(payload: dict) -> dict:
    item = signal_service.ingest_signal(payload)
    return _success({"item": item}, {"source": "control-plane-api", "action": "ingest"})


@router.post("/pipeline/run")
def run_signal_pipeline(source: str = "mock", token: str = "", authorization: str = Header("")) -> dict:
    if source == "qlib":
        try:
            auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
        except PermissionError:
            return _unauthorized()
    try:
        result = signal_service.run_pipeline(source=source)
        return _success({"run": result}, {"source": "control-plane-api", "action": "pipeline-run"})
    except SignalPipelineUnavailableError as exc:
        return {
            "data": None,
            "error": {"code": "pipeline_unavailable", "message": str(exc)},
            "meta": {"source": "control-plane-api", "requested_source": source},
        }


@router.post("/strategy/run")
def run_strategy(payload: dict[str, object]) -> dict:
    strategy_id = _normalize_text(payload.get("strategy_id"))
    symbol_value = payload.get("symbol")
    if not isinstance(symbol_value, str) or not symbol_value.strip():
        return {
            "data": None,
            "error": {"code": "invalid_request", "message": "symbol is required"},
            "meta": {"source": "control-plane-api", "requested_strategy_id": strategy_id},
        }
    symbol = symbol_value.strip()

    strategy_handlers = {
        "trend_breakout": {
            "evaluator": evaluate_trend_breakout,
            "extra_param_key": "breakout_buffer_pct",
        },
        "trend_pullback": {
            "evaluator": evaluate_trend_pullback,
            "extra_param_key": "pullback_depth_pct",
        },
    }
    strategy_handler = strategy_handlers.get(strategy_id)
    if strategy_handler is None:
        return {
            "data": None,
            "error": {
                "code": "unsupported_strategy",
                "message": "当前阶段只支持 trend_breakout 和 trend_pullback",
            },
            "meta": {
                "source": "control-plane-api",
                "requested_strategy_id": strategy_id,
                "symbol": symbol,
            },
        }
    strategy_params, params_error = _get_strategy_params(strategy_id)
    if params_error is not None:
        result = _build_strategy_unavailable_result(
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe="",
            lookback_bars=None,
            extra_param_key=str(strategy_handler["extra_param_key"]),
            extra_param_value=None,
            reason=params_error,
        )
        return _success(
            {"item": result},
            {
                "source": "control-plane-api",
                "action": "strategy-run",
                "strategy_id": strategy_id,
                "symbol": symbol,
                "decision": result["decision"],
                "reason": result["reason"],
            },
        )

    timeframe = _require_text_param(strategy_params.get("timeframe"))
    if timeframe is None:
        result = _build_strategy_unavailable_result(
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe="",
            lookback_bars=None,
            extra_param_key=str(strategy_handler["extra_param_key"]),
            extra_param_value=None,
            reason="missing_timeframe",
        )
        return _success(
            {"item": result},
            {
                "source": "control-plane-api",
                "action": "strategy-run",
                "strategy_id": strategy_id,
                "symbol": symbol,
                "decision": result["decision"],
                "reason": result["reason"],
            },
        )

    lookback_bars, lookback_error = _parse_positive_int_param(strategy_params.get("lookback_bars"), "invalid_lookback_bars")
    if lookback_error is not None:
        result = _build_strategy_unavailable_result(
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe=timeframe,
            lookback_bars=None,
            extra_param_key=str(strategy_handler["extra_param_key"]),
            extra_param_value=None,
            reason=lookback_error,
        )
        return _success(
            {"item": result},
            {
                "source": "control-plane-api",
                "action": "strategy-run",
                "strategy_id": strategy_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "lookback_bars": strategy_params.get("lookback_bars"),
                "decision": result["decision"],
                "reason": result["reason"],
            },
        )

    extra_param_key = str(strategy_handler["extra_param_key"])
    extra_param_value, extra_param_error = _parse_decimal_param(strategy_params.get(extra_param_key), f"invalid_{extra_param_key}")
    if extra_param_error is not None:
        result = _build_strategy_unavailable_result(
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe=timeframe,
            lookback_bars=lookback_bars,
            extra_param_key=extra_param_key,
            extra_param_value=None,
            reason=extra_param_error,
        )
        return _success(
            {"item": result},
            {
                "source": "control-plane-api",
                "action": "strategy-run",
                "strategy_id": strategy_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "lookback_bars": lookback_bars,
                "decision": result["decision"],
                "reason": result["reason"],
            },
        )

    whitelist = tuple(strategy_catalog_service.get_whitelist())
    normalized_symbol = symbol.upper()

    if lookback_bars <= 0:
        result = _build_strategy_unavailable_result(
            strategy_id=strategy_id,
            symbol=normalized_symbol,
            timeframe=timeframe,
            lookback_bars=lookback_bars,
            extra_param_key=extra_param_key,
            extra_param_value=extra_param_value,
            reason="invalid_lookback_bars",
        )
        return _success(
            {"item": result},
            {
                "source": "control-plane-api",
                "action": "strategy-run",
                "strategy_id": strategy_id,
                "symbol": normalized_symbol,
                "timeframe": timeframe,
                "lookback_bars": lookback_bars,
                extra_param_key: extra_param_value,
                "decision": result["decision"],
                "reason": result["reason"],
            },
        )

    if normalized_symbol not in whitelist:
        result = _build_strategy_unavailable_result(
            strategy_id=strategy_id,
            symbol=normalized_symbol,
            timeframe=timeframe,
            lookback_bars=lookback_bars,
            extra_param_key=extra_param_key,
            extra_param_value=extra_param_value,
            reason="symbol_not_in_market_whitelist",
        )
        return _success(
            {"item": result},
            {
                "source": "control-plane-api",
                "action": "strategy-run",
                "strategy_id": strategy_id,
                "symbol": normalized_symbol,
                "timeframe": timeframe,
                "lookback_bars": lookback_bars,
                extra_param_key: extra_param_value,
                "decision": result["decision"],
                "reason": result["reason"],
            },
        )

    chart = market_service.get_symbol_chart(
        symbol=normalized_symbol,
        interval=timeframe,
        limit=lookback_bars + 1,
        allowed_symbols=whitelist,
    )
    items = list(chart.get("items", []))
    if not items:
        result = _build_strategy_unavailable_result(
            strategy_id=strategy_id,
            symbol=normalized_symbol,
            timeframe=timeframe,
            lookback_bars=lookback_bars,
            extra_param_key=extra_param_key,
            extra_param_value=extra_param_value,
            reason="empty_chart",
            overlays=chart.get("overlays", {}),
        )
    else:
        result = strategy_handler["evaluator"](
            normalized_symbol,
            items,
            timeframe=timeframe,
            lookback_bars=lookback_bars,
            **{extra_param_key: extra_param_value},
        )
    result = apply_research_soft_gate(result, research_service.get_symbol_research(normalized_symbol))

    return _success(
        {"item": result},
        {
            "source": "control-plane-api",
            "action": "strategy-run",
            "strategy_id": strategy_id,
            "symbol": normalized_symbol,
            "timeframe": timeframe,
            "lookback_bars": lookback_bars,
            extra_param_key: extra_param_value,
            "decision": result["decision"],
            "reason": result["reason"],
        },
    )


def _get_strategy_params(strategy_id: str) -> tuple[dict[str, object] | None, str | None]:
    """从目录里取当前策略的参数。"""

    catalog = strategy_catalog_service.get_catalog()
    for strategy in catalog.get("strategies", []):
        if strategy.get("key") == strategy_id:
            default_params = strategy.get("default_params")
            if not isinstance(default_params, dict):
                return None, "missing_default_params"
            return dict(default_params), None
    return None, "strategy_not_in_catalog"


def _normalize_text(value: object) -> str:
    """把文本参数统一成可比较的字符串。"""

    if isinstance(value, str):
        return value.strip()
    return ""


def _require_text_param(value: object) -> str | None:
    """读取必填文本参数。"""

    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _parse_positive_int_param(value: object, error_reason: str) -> tuple[int | None, str | None]:
    """读取必须为正整数的参数。"""

    try:
        parsed_decimal = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return None, error_reason

    if parsed_decimal != parsed_decimal.to_integral_value():
        return None, error_reason

    parsed_value = int(parsed_decimal)
    if parsed_value <= 0:
        return None, error_reason
    return parsed_value, None


def _parse_decimal_param(value: object, error_reason: str) -> tuple[object | None, str | None]:
    """读取必须能转成数值的参数。"""

    try:
        return Decimal(str(value)), None
    except (TypeError, ValueError, InvalidOperation):
        return None, error_reason


def _build_strategy_unavailable_result(
    *,
    strategy_id: str,
    symbol: str,
    timeframe: str,
    lookback_bars: object,
    extra_param_key: str,
    extra_param_value: object,
    reason: str,
    overlays: dict[str, object] | None = None,
) -> dict[str, object]:
    """构造策略暂不可评估时的统一结果。"""

    result = {
        "strategy_id": strategy_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "lookback_bars": lookback_bars,
        extra_param_key: extra_param_value,
        "decision": "evaluation_unavailable",
        "reason": reason,
        "overlays": overlays or {"sample_size": 0},
    }
    return result

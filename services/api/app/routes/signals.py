"""Signal query routes for the Control Plane API skeleton."""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from services.api.app.services.auth_service import auth_service
from services.api.app.services.strategy_engine import apply_research_soft_gate
from services.api.app.services.strategy_engine import evaluate_trend_breakout
from services.api.app.services.strategy_engine import evaluate_trend_pullback
from services.api.app.services.strategy_engine import apply_scoring_gate, prepare_market_data_for_scoring
from services.api.app.services.market_service import MarketService
from services.api.app.services.research_runtime_service import research_runtime_service
from services.api.app.services.research_service import research_service
from services.api.app.services.signal_service import SignalPipelineUnavailableError, signal_service
from services.api.app.services.strategy_catalog import strategy_catalog_service
from services.api.app.services.direction_short_service import build_sim_client, direction_short_service
from services.api.app.routes._helpers import _success, _unauthorized

logger = logging.getLogger(__name__)


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


@router.get("/research/report")
def get_research_report() -> dict:
    item = research_service.get_factory_report()
    return _success(
        {"item": item},
        {
            "source": "control-plane-api",
            "action": "research-report",
            "status": item.get("status", "unavailable"),
        },
    )


@router.get("/research/runtime")
def get_research_runtime() -> dict:
    item = research_runtime_service.get_status()
    return _success(
        {"item": item},
        {
            "source": "control-plane-api",
            "action": "research-runtime",
            "status": item.get("status", "idle"),
        },
    )


def _market_direction_item() -> dict[str, Any]:
    """汇总最近一次推理的 16 币平均上涨概率（市场方向判断）。

    market-direction 与 direction-short-status 两个接口共用，
    保证前端看到的平均分数和调度器使用的口径完全一致。
    """
    item = research_service.get_latest_result()
    inference = dict(item.get("latest_inference") or {})
    signals = list(inference.get("signals") or [])
    if not signals:
        return {
            "avg_score": None,
            "direction": "unknown",
            "signal_count": 0,
            "model_version": str(inference.get("model_version", "")),
            "generated_at": str(inference.get("generated_at", "")),
            "short_trigger": False,
            "flat_trigger": False,
        }
    scores = [float(str(s.get("score", "0"))) for s in signals]
    avg_score = sum(scores) / len(scores)
    return {
        "avg_score": round(avg_score, 4),
        "direction": "bearish" if avg_score < 0.38 else ("bullish" if avg_score > 0.55 else "neutral"),
        "signal_count": len(scores),
        "model_version": str(inference.get("model_version", "")),
        "generated_at": str(inference.get("generated_at", "")),
        "short_trigger": avg_score < 0.38,
        "flat_trigger": avg_score > 0.45,
    }


@router.get("/research/market-direction")
def get_market_direction() -> dict:
    """返回模型的市场方向判断（16 币平均上涨概率）。

    供方向做空调度使用：平均分数 < 0.38 视为极度看跌（做空信号），
    > 0.45 视为转暖（平空信号）。数据来自最近一次推理的 signals。
    """
    item = _market_direction_item()
    status = "ok" if item.get("signal_count") else "no_signals"
    return _success(item, {"source": "control-plane-api", "action": "market-direction", "status": status})


# 交易历史条目里需要透出给前端的字段（保持原始值，避免逐字段猜类型）
_DIRECTION_SHORT_TRADE_FIELDS = (
    "trade_id",
    "pair",
    "is_open",
    "is_short",
    "amount",
    "stake_amount",
    "open_rate",
    "current_rate",
    "close_rate",
    "profit_abs",
    "profit_pct",
    "realized_profit",
    "realized_profit_ratio",
    "open_date",
    "close_date",
    "exit_reason",
    "enter_tag",
)


def _summarize_trade(trade: dict[str, Any]) -> dict[str, Any]:
    """把 freqtrade 交易原始条目裁剪成状态接口需要的字段子集。"""
    return {key: trade.get(key) for key in _DIRECTION_SHORT_TRADE_FIELDS}


def _is_short_trade(trade: dict[str, Any]) -> bool:
    """判断交易是否为做空（兼容布尔/字符串两种返回值）。"""
    value = trade.get("is_short")
    return value is True or str(value).lower() == "true"


@router.get("/research/direction-short-status")
def get_direction_short_status() -> dict:
    """返回方向做空（模拟盘）的完整状态。

    数据来源三部分：
    1. market：模型 16 币平均分数（与 market-direction 同一口径）
    2. state：调度器持久化状态（direction_short_state.json）
    3. simulation：模拟盘真实持仓 + 最近一笔平仓记录（以模拟盘为准）

    当状态文件记录“已开空”但模拟盘实际无空仓时，position_state_mismatch=true，
    前端据此提示“已平仓（调度状态待同步）”，不掩盖真实持仓。
    """
    market_item = _market_direction_item()
    state = direction_short_service.get_state()

    simulation: dict[str, Any] = {
        "connected": False,
        "open_position": None,
        "last_closed_trade": None,
        "message": "",
    }
    try:
        sim_client = build_sim_client()
        # 在场持仓走 /status（list_open_trades）；已平仓历史走 /trades（list_trades），
        # 两者分开读取并独立降级，单边失败不影响另一边
        try:
            open_trades = sim_client.list_open_trades()
            simulation["connected"] = True
            short_open = [t for t in open_trades if _is_short_trade(t)]
            simulation["open_position"] = _summarize_trade(short_open[0]) if short_open else None
        except Exception as status_exc:
            logger.warning("方向做空状态接口读取在场持仓失败: %s", status_exc)
            if not simulation["message"]:
                simulation["message"] = f"在场持仓读取失败: {status_exc}"
        try:
            closed_trades = sim_client.list_trades(limit=10)
            simulation["last_closed_trade"] = _summarize_trade(closed_trades[0]) if closed_trades else None
        except Exception as trades_exc:
            logger.warning("方向做空状态接口读取平仓历史失败: %s", trades_exc)
            if not simulation["message"]:
                simulation["message"] = f"平仓历史读取失败: {trades_exc}"
    except Exception as exc:
        # 模拟盘完全不可达时保留状态文件数据，并明确标记连接失败
        logger.warning("方向做空状态接口读取模拟盘失败: %s", exc)
        simulation["message"] = str(exc)

    # 只有在模拟盘确认可达且确实无空仓时，才判定状态文件与真实持仓不一致
    position_state_mismatch = bool(state.get("has_short_position")) and simulation["connected"] and simulation["open_position"] is None

    return _success(
        {
            "market": market_item,
            "state": state,
            "simulation": simulation,
            "position_state_mismatch": position_state_mismatch,
        },
        {"source": "control-plane-api", "action": "direction-short-status"},
    )


@router.post("/research/train")
def run_research_training(token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    try:
        item = research_runtime_service.start_training()
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
        item = research_runtime_service.start_inference()
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
    try:
        item = signal_service.ingest_signal(payload)
    except (KeyError, TypeError, ValueError) as exc:
        return {
            "data": None,
            "error": {"code": "invalid_request", "message": str(exc)},
            "meta": {"source": "control-plane-api", "action": "ingest"},
        }
    return _success({"item": item}, {"source": "control-plane-api", "action": "ingest"})


@router.post("/pipeline/run")
def run_signal_pipeline(source: str = "mock", token: str = "", authorization: str = Header("")) -> dict:
    if source == "qlib":
        try:
            auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
        except PermissionError:
            return _unauthorized()
        try:
            result = research_runtime_service.start_pipeline()
            return _success({"run": result}, {"source": "control-plane-api", "action": "pipeline-run"})
        except Exception as exc:
            return {
                "data": None,
                "error": {"code": "pipeline_unavailable", "message": str(exc)},
                "meta": {"source": "control-plane-api", "requested_source": source},
            }
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

    # 应用评分门控：评分>=阈值才触发买入
    market_data = prepare_market_data_for_scoring(items)
    result = apply_scoring_gate(result, normalized_symbol, market_data)

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

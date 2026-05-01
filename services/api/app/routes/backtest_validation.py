"""回测验证路由。"""

from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path

try:
    from fastapi import APIRouter
except ImportError:

    class APIRouter:  # pragma: no cover - lightweight local fallback
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def post(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def get(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator


from services.api.app.services.backtest_validation_service import (
    BacktestConfig,
    BacktestValidationService,
    backtest_validation_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])
service = backtest_validation_service

# In-memory storage for backtest results (could be replaced with database)
_backtest_results_store: dict[str, dict] = {}

# Validation thresholds from strategy_tuning.json
VALIDATION_THRESHOLDS = {
    "win_rate": 0.55,
    "profit_factor": 1.5,
    "max_drawdown": 0.15,
    "sharpe_ratio": 1.0,
}


def _success(data: dict, meta: dict | None = None) -> dict:
    """统一成功 envelope。"""
    return {"data": data, "error": None, "meta": meta or {}}


def _error(message: str, code: str = "backtest_error") -> dict:
    """统一错误 envelope。"""
    return {"data": None, "error": {"code": code, "message": message}, "meta": {}}


def _parse_decimal(value: object) -> Decimal | None:
    """解析 Decimal 值。"""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return None


@router.post("/run")
def run_backtest(request: dict) -> dict:
    """执行单次回测。

    Request body:
    {
        "symbol": "BTCUSDT",
        "strategy_type": "trend_breakout",
        "timeframe": "4h",
        "lookback_bars": 20,
        "days": 30,
        "initial_capital": "10000",
        "fee_bps": 10,
        "slippage_bps": 5,
        "position_size_pct": "100",
        "stop_loss_pct": "5",
        "take_profit_pct": "10",
        "breakout_buffer_pct": "0.5",
        "pullback_depth_pct": "3"
    }
    """
    try:
        symbol = str(request.get("symbol", "BTCUSDT")).strip().upper()
        strategy_type = str(request.get("strategy_type", "trend_breakout")).strip()
        timeframe = str(request.get("timeframe", "4h")).strip()
        lookback_bars = int(request.get("lookback_bars", 20))
        days = int(request.get("days", 30))
        fee_bps = int(request.get("fee_bps", 10))
        slippage_bps = int(request.get("slippage_bps", 5))

        initial_capital = _parse_decimal(request.get("initial_capital")) or Decimal("10000")
        position_size_pct = _parse_decimal(request.get("position_size_pct")) or Decimal("100")
        stop_loss_pct = _parse_decimal(request.get("stop_loss_pct")) or Decimal("5")
        take_profit_pct = _parse_decimal(request.get("take_profit_pct")) or Decimal("10")
        breakout_buffer_pct = _parse_decimal(request.get("breakout_buffer_pct")) or Decimal("0.5")
        pullback_depth_pct = _parse_decimal(request.get("pullback_depth_pct")) or Decimal("3")

        # 参数验证
        if strategy_type not in ("trend_breakout", "trend_pullback"):
            return _error(f"Invalid strategy_type: {strategy_type}", "invalid_parameter")

        if lookback_bars < 5:
            return _error("lookback_bars must be at least 5", "invalid_parameter")

        if days < 1 or days > 365:
            return _error("days must be between 1 and 365", "invalid_parameter")

        config = BacktestConfig(
            symbol=symbol,
            strategy_type=strategy_type,
            timeframe=timeframe,
            lookback_bars=lookback_bars,
            initial_capital=initial_capital,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            position_size_pct=position_size_pct,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            breakout_buffer_pct=breakout_buffer_pct,
            pullback_depth_pct=pullback_depth_pct,
        )

        result = service.simulate_trades(config)

        # 生成唯一ID并存储结果
        backtest_id = str(uuid.uuid4())
        from datetime import datetime, timezone
        created_at = datetime.now(timezone.utc).isoformat()

        result_data = {
            "status": result.status,
            "symbol": config.symbol,
            "strategy_type": config.strategy_type,
            "timeframe": config.timeframe,
            "start_time": result.start_time,
            "end_time": result.end_time,
            "metrics": {
                "total_return": str(result.metrics.total_return),
                "total_return_pct": str(result.metrics.total_return_pct),
                "annualized_return_pct": str(result.metrics.annualized_return_pct),
                "sharpe_ratio": str(result.metrics.sharpe_ratio),
                "max_drawdown": str(result.metrics.max_drawdown),
                "max_drawdown_pct": str(result.metrics.max_drawdown_pct),
                "win_rate": str(result.metrics.win_rate),
                "total_trades": result.metrics.total_trades,
                "winning_trades": result.metrics.winning_trades,
                "losing_trades": result.metrics.losing_trades,
                "avg_profit": str(result.metrics.avg_profit),
                "avg_loss": str(result.metrics.avg_loss),
                "profit_factor": str(result.metrics.profit_factor),
                "avg_trade_duration_hours": str(result.metrics.avg_trade_duration_hours),
                "max_consecutive_wins": result.metrics.max_consecutive_wins,
                "max_consecutive_losses": result.metrics.max_consecutive_losses,
            },
            "trades": [
                {
                    "entry_time": trade.entry_time,
                    "exit_time": trade.exit_time,
                    "entry_price": str(trade.entry_price),
                    "exit_price": str(trade.exit_price),
                    "quantity": str(trade.quantity),
                    "side": trade.side,
                    "pnl": str(trade.pnl),
                    "pnl_pct": str(trade.pnl_pct),
                    "reason": trade.reason,
                }
                for trade in result.trades
            ],
            "equity_curve": result.equity_curve[:100] if result.equity_curve else [],
            "error": result.error,
            "created_at": created_at,
        }

        _backtest_results_store[backtest_id] = result_data

        return _success(
            {
                "backtest_id": backtest_id,
                "status": result.status,
                "symbol": config.symbol,
                "strategy_type": config.strategy_type,
                "timeframe": config.timeframe,
                "start_time": result.start_time,
                "end_time": result.end_time,
                "metrics": result_data["metrics"],
                "trades": result_data["trades"],
                "equity_curve": result_data["equity_curve"],
                "error": result.error,
                "created_at": created_at,
            },
            {"days": days, "lookback_bars": lookback_bars},
        )

    except Exception as e:
        return _error(str(e), "internal_error")


@router.post("/compare")
def compare_backtests(request: dict) -> dict:
    """对比多个策略配置的回测结果。

    Request body:
    {
        "symbol": "BTCUSDT",
        "days": 30,
        "configs": [
            {
                "strategy_type": "trend_breakout",
                "timeframe": "4h",
                "lookback_bars": 20,
                "stop_loss_pct": "5",
                "take_profit_pct": "10"
            },
            {
                "strategy_type": "trend_pullback",
                "timeframe": "4h",
                "lookback_bars": 20,
                "stop_loss_pct": "3",
                "take_profit_pct": "8"
            }
        ]
    }
    """
    try:
        symbol = str(request.get("symbol", "BTCUSDT")).strip().upper()
        days = int(request.get("days", 30))
        raw_configs = list(request.get("configs", []))

        if not raw_configs:
            return _error("configs is required", "invalid_parameter")

        if days < 1 or days > 365:
            return _error("days must be between 1 and 365", "invalid_parameter")

        # 加载共享的历史数据
        timeframe = str(raw_configs[0].get("timeframe", "4h")).strip() if raw_configs else "4h"
        klines = service.load_historical_data(symbol=symbol, days=days, interval=timeframe)

        configs = []
        for raw_config in raw_configs:
            strategy_type = str(raw_config.get("strategy_type", "trend_breakout")).strip()
            if strategy_type not in ("trend_breakout", "trend_pullback"):
                continue

            config = BacktestConfig(
                symbol=symbol,
                strategy_type=strategy_type,
                timeframe=str(raw_config.get("timeframe", timeframe)).strip(),
                lookback_bars=int(raw_config.get("lookback_bars", 20)),
                initial_capital=_parse_decimal(raw_config.get("initial_capital")) or Decimal("10000"),
                fee_bps=int(raw_config.get("fee_bps", 10)),
                slippage_bps=int(raw_config.get("slippage_bps", 5)),
                position_size_pct=_parse_decimal(raw_config.get("position_size_pct")) or Decimal("100"),
                stop_loss_pct=_parse_decimal(raw_config.get("stop_loss_pct")) or Decimal("5"),
                take_profit_pct=_parse_decimal(raw_config.get("take_profit_pct")) or Decimal("10"),
                breakout_buffer_pct=_parse_decimal(raw_config.get("breakout_buffer_pct")) or Decimal("0.5"),
                pullback_depth_pct=_parse_decimal(raw_config.get("pullback_depth_pct")) or Decimal("3"),
            )
            configs.append(config)

        if not configs:
            return _error("No valid configurations provided", "invalid_parameter")

        results = service.compare_strategies(configs, klines)

        return _success(
            {
                "symbol": symbol,
                "days": days,
                "timeframe": timeframe,
                "comparison": results,
                "best_strategy": results[0] if results else None,
            },
            {"total_configs": len(configs)},
        )

    except Exception as e:
        return _error(str(e), "internal_error")


@router.get("/metrics")
def get_metrics_info() -> dict:
    """获取可用指标说明。"""
    return _success(
        {
            "metrics": [
                {
                    "key": "total_return",
                    "label": "Total Return",
                    "description": "Total profit/loss from all trades",
                    "unit": "quote_currency",
                },
                {
                    "key": "total_return_pct",
                    "label": "Total Return %",
                    "description": "Total return as percentage of initial capital",
                    "unit": "percent",
                },
                {
                    "key": "annualized_return_pct",
                    "label": "Annualized Return %",
                    "description": "Annualized return rate",
                    "unit": "percent",
                },
                {
                    "key": "sharpe_ratio",
                    "label": "Sharpe Ratio",
                    "description": "Risk-adjusted return metric",
                    "unit": "ratio",
                },
                {
                    "key": "max_drawdown",
                    "label": "Max Drawdown",
                    "description": "Maximum peak-to-trough decline",
                    "unit": "quote_currency",
                },
                {
                    "key": "max_drawdown_pct",
                    "label": "Max Drawdown %",
                    "description": "Maximum drawdown as percentage",
                    "unit": "percent",
                },
                {
                    "key": "win_rate",
                    "label": "Win Rate",
                    "description": "Percentage of profitable trades",
                    "unit": "percent",
                },
                {
                    "key": "total_trades",
                    "label": "Total Trades",
                    "description": "Total number of trades executed",
                    "unit": "count",
                },
                {
                    "key": "avg_profit",
                    "label": "Average Profit",
                    "description": "Average profit per winning trade",
                    "unit": "quote_currency",
                },
                {
                    "key": "avg_loss",
                    "label": "Average Loss",
                    "description": "Average loss per losing trade",
                    "unit": "quote_currency",
                },
                {
                    "key": "profit_factor",
                    "label": "Profit Factor",
                    "description": "Ratio of total profits to total losses",
                    "unit": "ratio",
                },
            ],
            "strategies": [
                {
                    "key": "trend_breakout",
                    "label": "Trend Breakout",
                    "description": "Buy when price breaks above recent high with buffer, sell on stop loss, take profit, or breakdown",
                },
                {
                    "key": "trend_pullback",
                    "label": "Trend Pullback",
                    "description": "Buy when price pulls back to support level in uptrend, sell on invalidation, take profit, or trend reversal",
                },
            ],
        }
    )


@router.get("/result/{backtest_id}")
def get_backtest_result(backtest_id: str) -> dict:
    """获取回测结果。

    Args:
        backtest_id: 回测结果ID

    Returns:
        存储的回测结果
    """
    if backtest_id not in _backtest_results_store:
        return _error(f"Backtest result not found: {backtest_id}", "not_found")

    stored = _backtest_results_store[backtest_id]
    return _success(
        {
            "backtest_id": backtest_id,
            "status": stored.get("status"),
            "symbol": stored.get("symbol"),
            "strategy_type": stored.get("strategy_type"),
            "timeframe": stored.get("timeframe"),
            "metrics": stored.get("metrics"),
            "trades": stored.get("trades", []),
            "equity_curve": stored.get("equity_curve", []),
            "created_at": stored.get("created_at"),
        }
    )


@router.post("/validate")
def validate_strategy_params(request: dict) -> dict:
    """验证策略参数是否满足指标要求。

    验证指标（来自 strategy_tuning.json）：
    - win_rate >= 0.55
    - profit_factor >= 1.5
    - max_drawdown <= 0.15
    - sharpe_ratio >= 1.0

    Request body:
    {
        "symbol": "BTCUSDT",
        "strategy_type": "trend_breakout",
        "timeframe": "4h",
        "lookback_bars": 20,
        "days": 30,
        "initial_capital": "10000",
        "fee_bps": 10,
        "slippage_bps": 5,
        "position_size_pct": "100",
        "stop_loss_pct": "5",
        "take_profit_pct": "10",
        "breakout_buffer_pct": "0.5",
        "pullback_depth_pct": "3"
    }
    """
    try:
        # 执行回测
        run_request = {
            "symbol": request.get("symbol", "BTCUSDT"),
            "strategy_type": request.get("strategy_type", "trend_breakout"),
            "timeframe": request.get("timeframe", "4h"),
            "lookback_bars": request.get("lookback_bars", 20),
            "days": request.get("days", 30),
            "initial_capital": request.get("initial_capital", "10000"),
            "fee_bps": request.get("fee_bps", 10),
            "slippage_bps": request.get("slippage_bps", 5),
            "position_size_pct": request.get("position_size_pct", "100"),
            "stop_loss_pct": request.get("stop_loss_pct", "5"),
            "take_profit_pct": request.get("take_profit_pct", "10"),
            "breakout_buffer_pct": request.get("breakout_buffer_pct", "0.5"),
            "pullback_depth_pct": request.get("pullback_depth_pct", "3"),
        }

        result = run_backtest(run_request)

        if result.get("error"):
            return _error(result["error"]["message"], result["error"]["code"])

        metrics = result.get("data", {}).get("metrics", {})

        # 解析指标值
        win_rate = float(metrics.get("win_rate", "0"))
        profit_factor = float(metrics.get("profit_factor", "0"))
        max_drawdown_pct = float(metrics.get("max_drawdown_pct", "0"))
        sharpe_ratio = float(metrics.get("sharpe_ratio", "0"))

        # 执行验证
        validations = {
            "win_rate": {
                "value": win_rate,
                "threshold": VALIDATION_THRESHOLDS["win_rate"] * 100,  # Convert to percentage
                "passed": win_rate >= VALIDATION_THRESHOLDS["win_rate"] * 100,
                "condition": ">= 55%",
            },
            "profit_factor": {
                "value": profit_factor,
                "threshold": VALIDATION_THRESHOLDS["profit_factor"],
                "passed": profit_factor >= VALIDATION_THRESHOLDS["profit_factor"],
                "condition": ">= 1.5",
            },
            "max_drawdown": {
                "value": max_drawdown_pct,
                "threshold": VALIDATION_THRESHOLDS["max_drawdown"] * 100,  # Convert to percentage
                "passed": max_drawdown_pct <= VALIDATION_THRESHOLDS["max_drawdown"] * 100,
                "condition": "<= 15%",
            },
            "sharpe_ratio": {
                "value": sharpe_ratio,
                "threshold": VALIDATION_THRESHOLDS["sharpe_ratio"],
                "passed": sharpe_ratio >= VALIDATION_THRESHOLDS["sharpe_ratio"],
                "condition": ">= 1.0",
            },
        }

        all_passed = all(v["passed"] for v in validations.values())

        # 生成建议
        recommendations = []
        if not validations["win_rate"]["passed"]:
            recommendations.append(
                f"Win rate ({win_rate:.1f}%) below threshold. Consider loosening entry criteria or improving signal quality."
            )
        if not validations["profit_factor"]["passed"]:
            recommendations.append(
                f"Profit factor ({profit_factor:.2f}) below threshold. Consider adjusting take-profit/stop-loss ratios."
            )
        if not validations["max_drawdown"]["passed"]:
            recommendations.append(
                f"Max drawdown ({max_drawdown_pct:.1f}%) exceeds threshold. Consider reducing position size or tightening stop-loss."
            )
        if not validations["sharpe_ratio"]["passed"]:
            recommendations.append(
                f"Sharpe ratio ({sharpe_ratio:.2f}) below threshold. Consider filtering volatile periods or improving risk management."
            )

        if all_passed:
            recommendations.append("All validation criteria passed. Strategy parameters are acceptable.")

        return _success(
            {
                "valid": all_passed,
                "validations": validations,
                "summary": {
                    "total_checks": len(validations),
                    "passed_checks": sum(1 for v in validations.values() if v["passed"]),
                    "failed_checks": sum(1 for v in validations.values() if not v["passed"]),
                },
                "metrics": metrics,
                "recommendations": recommendations,
                "backtest_result": result.get("data"),
            }
        )

    except Exception as e:
        logger.exception("Validation error")
        return _error(str(e), "validation_error")


@router.get("/optimization")
def get_optimization_suggestions() -> dict:
    """获取参数优化建议。

    从 strategy_tuning.json 加载优化建议。
    """
    try:
        tuning_path = Path("/home/djy/Quant/services/data/config/strategy_tuning.json")
        if not tuning_path.exists():
            return _error("strategy_tuning.json not found", "config_missing")

        with open(tuning_path) as f:
            tuning_config = json.load(f)

        parameters = tuning_config.get("parameters", {})
        market_adjustments = tuning_config.get("market_condition_adjustments", {})

        suggestions = []

        for param_name, param_config in parameters.items():
            if "recommended" in param_config and "current" in param_config:
                suggestions.append(
                    {
                        "parameter": param_name,
                        "current_value": param_config["current"],
                        "recommended_value": param_config["recommended"],
                        "reason": param_config.get("reason", ""),
                        "range": param_config.get("range", {}),
                    }
                )

        return _success(
            {
                "optimization_suggestions": suggestions,
                "market_condition_adjustments": market_adjustments,
                "validation_thresholds": VALIDATION_THRESHOLDS,
                "tuning_status": tuning_config.get("tuning_status"),
                "last_updated": tuning_config.get("last_updated"),
            }
        )

    except json.JSONDecodeError as e:
        return _error(f"Invalid JSON in strategy_tuning.json: {e}", "config_error")
    except Exception as e:
        logger.exception("Optimization suggestions error")
        return _error(str(e), "internal_error")
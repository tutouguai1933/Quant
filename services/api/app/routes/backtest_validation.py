"""回测验证路由。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

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

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])
service = backtest_validation_service


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

        return _success(
            {
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
                "equity_curve": result.equity_curve[:100] if result.equity_curve else [],  # 限制返回数量
                "error": result.error,
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
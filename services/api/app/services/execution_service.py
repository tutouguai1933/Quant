"""Execution mapping service for Quant phase 1."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from decimal import InvalidOperation
from decimal import ROUND_CEILING
from pathlib import Path

from services.api.app.adapters.binance.market_client import BinanceMarketClient
from services.api.app.adapters.freqtrade.client import freqtrade_client
from services.api.app.core.settings import Settings
from services.api.app.domain.contracts import ExecutionActionContract, ExecutionActionType
from services.api.app.services.signal_service import signal_service
from services.api.app.services.workbench_config_service import workbench_config_service


class ExecutionService:
    """Maps control-plane signals to execution actions."""

    _REJECTIONS_PATH = Path(".runtime/trade_rejections.jsonl")
    _SLIPPAGE_PATH = Path(".runtime/trade_slippage.jsonl")

    def __init__(self, market_client: BinanceMarketClient | None = None) -> None:
        self._market_client = market_client or BinanceMarketClient()
        self._pre_trade_validator = None
        self._slippage_model = None

    def build_execution_action(self, signal_id: int, strategy_context_id: int | None = None) -> dict[str, object]:
        signal = signal_service.get_signal(signal_id)
        if signal is None:
            raise ValueError(f"signal {signal_id} not found")

        side = signal["side"]
        action_type = self._resolve_action_type(str(side))
        quantity = self._resolve_quantity(str(signal["target_weight"]))

        action = ExecutionActionContract(
            action_type=action_type,
            symbol=str(signal["symbol"]),
            side=side,
            quantity=quantity,
            source_signal_id=signal_id,
            strategy_id=signal.get("strategy_id") or strategy_context_id,
            account_id=1,
        )
        return action.to_dict()

    def dispatch_signal(self, signal_id: int, strategy_context_id: int | None = None) -> dict[str, object]:
        settings = Settings.from_env()
        runtime_mode = settings.runtime_mode
        runtime_snapshot = freqtrade_client.get_runtime_snapshot()
        if runtime_mode == "dry-run":
            if settings.has_freqtrade_rest_config():
                if runtime_snapshot.get("backend") != "rest":
                    raise PermissionError("dry-run 模式下检测到 Freqtrade 配置，但执行器没有切到 REST 后端")
                if runtime_snapshot.get("connection_status") != "connected":
                    raise PermissionError("dry-run 模式下无法确认远端 Freqtrade 连接状态")
                if runtime_snapshot.get("mode") != "dry-run":
                    raise PermissionError("dry-run 模式下远端 Freqtrade 没有切到 dry-run 运行模式")
            elif runtime_snapshot.get("mode") != "dry-run":
                raise PermissionError("dry-run 模式下执行器没有切到 dry-run 运行模式")

        action = self.build_execution_action(signal_id, strategy_context_id=strategy_context_id)
        reference_price = None
        if runtime_mode == "live":
            self._guard_live_execution(action=action, settings=settings, runtime_snapshot=runtime_snapshot)
            if settings.pre_trade_enabled:
                reference_price = self._compute_reference_price(str(action["symbol"]))
                report = self._run_pre_trade_validation(
                    action=action,
                    settings=settings,
                    reference_price=reference_price,
                )
                if report is not None and report.blocked:
                    blocked_reasons = [
                        c.detail for c in report.checks
                        if c.severity == "block" and not c.passed
                    ]
                    self._record_rejection(
                        symbol=str(action["symbol"]),
                        side=str(action["side"]),
                        reasons=blocked_reasons,
                    )
                    self._send_pre_trade_alert(
                        symbol=str(action["symbol"]),
                        side=str(action["side"]),
                        reasons=blocked_reasons,
                    )
                    raise PermissionError(
                        f"pre-trade validation blocked: {'; '.join(blocked_reasons)}"
                    )

        if reference_price is not None:
            action["reference_price"] = str(reference_price)

        # 记录交易延迟
        start_time = time.time()
        order = freqtrade_client.submit_execution_action(action)
        duration_ms = (time.time() - start_time) * 1000

        # 记录成交滑点
        if reference_price is not None:
            self._record_slippage(
                symbol=str(action["symbol"]),
                side=str(action["side"]),
                reference_price=reference_price,
                order=order,
            )

        # 延迟导入以避免循环依赖
        from services.api.app.services.performance_monitor_service import (
            performance_monitor_service,
        )

        # 根据运行模式确定订单类型
        order_type = f"signal_dispatch_{runtime_mode}"
        performance_monitor_service.track_trade_latency(
            order_type=order_type,
            duration_ms=duration_ms,
            metadata={
                "signal_id": signal_id,
                "action_type": action.get("action_type"),
                "symbol": action.get("symbol"),
            },
        )

        return {
            "action": action,
            "order": order,
            "runtime": runtime_snapshot,
            "execution_latency_ms": duration_ms,
        }

    def _compute_reference_price(self, symbol: str) -> Decimal:
        compact = self._compact_symbol(symbol)
        return self._get_last_price(compact)

    def _run_pre_trade_validation(
        self,
        action: dict[str, object],
        settings: Settings,
        reference_price: Decimal,
    ) -> object | None:
        try:
            from services.api.app.adapters.binance.account_client import binance_account_client
            from services.api.app.services.pre_trade_validator import (
                PreTradeConfig,
                PreTradeValidator,
            )
            from services.api.app.services.slippage_model import (
                SlippageConfig,
                SlippageModel,
            )

            config = PreTradeConfig(
                enabled=settings.pre_trade_enabled,
                min_depth_coverage=settings.pre_trade_min_depth_coverage,
                max_spread_bps=settings.pre_trade_max_spread_bps,
                max_deviation_bps=settings.pre_trade_max_deviation_bps,
                max_slippage_bps=settings.pre_trade_max_slippage_bps,
            )
            validator = PreTradeValidator(
                market_client=self._market_client,
                account_client=binance_account_client,
                config=config,
            )
            side_raw = str(action["side"])
            if side_raw in ("flat", "sell"):
                validate_side = "sell"
            else:
                validate_side = "buy"
            symbol = self._compact_symbol(str(action["symbol"]))
            stake_amount = Decimal(str(action.get("stake_amount", "0")))
            report = validator.validate(
                symbol=symbol,
                side=validate_side,
                stake_amount=stake_amount,
                reference_price=reference_price,
            )

            if not report.blocked:
                slippage_config = SlippageConfig(
                    max_slippage_bps=settings.pre_trade_max_slippage_bps,
                )
                slippage_model = SlippageModel(config=slippage_config)
                order_book = self._market_client.get_order_book(symbol)
                candles_4h = self._market_client.get_klines(symbol, interval="4h", limit=20)
                normalized_candles = [
                    {"open_time": c[0], "open": c[1], "high": c[2], "low": c[3], "close": c[4], "volume": c[5]}
                    for c in candles_4h if isinstance(c, list) and len(c) >= 6
                ]
                slippage_estimate = slippage_model.estimate(
                    symbol=symbol,
                    side=validate_side,
                    stake_amount=stake_amount,
                    order_book=order_book,
                    candles_4h=normalized_candles,
                )
                report.slippage = slippage_estimate
                if slippage_estimate.worst_case_bps > Decimal(str(settings.pre_trade_max_slippage_bps)):
                    report.blocked = True
                    report.warnings.append(
                        f"滑点 worst_case={slippage_estimate.worst_case_bps} bps > {settings.pre_trade_max_slippage_bps}"
                    )

            self._pre_trade_validator = validator
            self._slippage_model = slippage_model if not report.blocked else None
            return report
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("pre-trade validation error: %s", exc)
            return None

    def _record_rejection(self, symbol: str, side: str, reasons: list[str]) -> None:
        try:
            self._REJECTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                "side": side,
                "reason": "; ".join(reasons),
            }
            with open(self._REJECTIONS_PATH, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _send_pre_trade_alert(self, symbol: str, side: str, reasons: list[str]) -> None:
        try:
            from services.api.app.services.feishu_push_service import (
                AlertCardMessage,
                FeishuAlertLevel,
                feishu_push_service,
            )
            alert = AlertCardMessage(
                level=FeishuAlertLevel.ERROR,
                title="Pre-trade Validation Blocked",
                message=f"{symbol} {side} 下单被拦截",
                details={
                    "symbol": symbol,
                    "side": side,
                    "reasons": "; ".join(reasons),
                },
            )
            feishu_push_service.send_alert(alert)
        except Exception:
            pass

    def _record_slippage(
        self,
        symbol: str,
        side: str,
        reference_price: Decimal,
        order: dict[str, object],
    ) -> None:
        try:
            fill_price_str = order.get("avgPrice", "0")
            if fill_price_str in (None, "", "0.0000000000", 0):
                return
            fill_price = Decimal(str(fill_price_str))
            if fill_price <= 0:
                return
            slippage_bps = (fill_price - reference_price) / reference_price * 10000
            self._SLIPPAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                "side": side,
                "ref_price": str(reference_price),
                "fill_price": str(fill_price),
                "slippage_bps": str(slippage_bps.quantize(Decimal("0.01"))),
            }
            with open(self._SLIPPAGE_PATH, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    @staticmethod
    def _resolve_action_type(side: str) -> ExecutionActionType:
        if side == "flat":
            return ExecutionActionType.CLOSE_POSITION
        return ExecutionActionType.OPEN_POSITION

    @staticmethod
    def _resolve_quantity(target_weight: str) -> Decimal:
        try:
            weight = Decimal(str(target_weight)).copy_abs()
        except InvalidOperation as exc:
            raise ValueError("target_weight must be decimal-compatible") from exc
        if not weight.is_finite():
            raise ValueError("target_weight must be finite")
        base_quantity = Decimal("0.0400000000")
        quantity = max(Decimal("0.0010000000"), weight * base_quantity)
        return quantity.quantize(Decimal("0.0000000001"))

    def _guard_live_execution(
        self,
        action: dict[str, object],
        settings: Settings,
        runtime_snapshot: dict[str, object],
    ) -> None:
        """在 live 模式下执行本地安全门检查。"""

        if not settings.allow_live_execution:
            raise PermissionError("live 模式下需要设置 QUANT_ALLOW_LIVE_EXECUTION=true 才允许执行")
        if runtime_snapshot.get("backend") != "rest":
            raise PermissionError("live 模式必须连接真实的 Freqtrade REST 执行器")
        if runtime_snapshot.get("connection_status") != "connected":
            raise PermissionError("live 模式下无法确认远端 Freqtrade 连接状态")
        if runtime_snapshot.get("mode") != "live":
            raise PermissionError("live 模式下远端 Freqtrade 没有切到 live 运行模式")
        if runtime_snapshot.get("trading_mode") != "spot":
            raise PermissionError("当前阶段 live 只允许 Binance Spot")

        symbol = self._compact_symbol(str(action["symbol"]))
        side = str(action["side"])
        if side != "flat":
            execution_policy = self._get_execution_policy(settings=settings)
            if not execution_policy["live_allowed_symbols"]:
                raise PermissionError("live 模式需要先配置 QUANT_LIVE_ALLOWED_SYMBOLS")
            if symbol not in execution_policy["live_allowed_symbols"]:
                raise PermissionError(
                    f"live 模式当前只允许这些币种: {', '.join(execution_policy['live_allowed_symbols'])}"
                )

            stake_amount = self._read_decimal(
                runtime_snapshot.get("stake_amount"),
                field_name="stake_amount",
            )
            if execution_policy["live_max_stake_usdt"] is None:
                raise PermissionError("live 模式需要先配置 QUANT_LIVE_MAX_STAKE_USDT")
            if stake_amount > execution_policy["live_max_stake_usdt"]:
                raise PermissionError(
                    f"远端 Freqtrade 当前 stake_amount={stake_amount} USDT，已超过本地 live 上限 {execution_policy['live_max_stake_usdt']} USDT"
                )

            if execution_policy["live_max_open_trades"] is None:
                raise PermissionError("live 模式需要先配置 QUANT_LIVE_MAX_OPEN_TRADES")
            remote_max_open_trades = runtime_snapshot.get("max_open_trades")
            if remote_max_open_trades is None:
                raise PermissionError("live 模式下无法确认远端 max_open_trades")
            try:
                parsed_remote_max_open_trades = int(remote_max_open_trades)
            except (TypeError, ValueError) as exc:
                raise PermissionError(f"无法解析远端 max_open_trades={remote_max_open_trades}") from exc
            if parsed_remote_max_open_trades > execution_policy["live_max_open_trades"]:
                raise PermissionError(
                    f"远端 Freqtrade 当前 max_open_trades={parsed_remote_max_open_trades}，已超过本地 live 上限 {execution_policy['live_max_open_trades']}"
                )
            open_positions = freqtrade_client.get_snapshot().positions
            if len(open_positions) >= execution_policy["live_max_open_trades"]:
                raise PermissionError("live 模式已达到允许的最大持仓数")

            min_notional = self._get_min_notional(symbol)
            if stake_amount < min_notional:
                raise PermissionError(
                    f"{symbol} 的最小下单额是 {min_notional} USDT，当前 Freqtrade stake_amount={stake_amount} USDT"
                )
            safe_exit_stake = self._get_safe_exit_stake(symbol=symbol, min_notional=min_notional)
            if stake_amount < safe_exit_stake:
                raise PermissionError(
                    f"{symbol} 当前至少需要 {safe_exit_stake} USDT，才能在扣除手续费并按交易步长取整后仍满足最小卖出额；"
                    f"当前 Freqtrade stake_amount={stake_amount} USDT"
                )
            action["stake_amount"] = f"{stake_amount:.10f}"

    @staticmethod
    def _get_execution_policy(settings: Settings) -> dict[str, object]:
        """优先读取工作台里的执行安全门，再回退到环境变量。"""

        config = workbench_config_service.get_config()
        execution = dict(config.get("execution") or {})
        raw_symbols = [str(item).strip().upper() for item in list(execution.get("live_allowed_symbols") or []) if str(item).strip()]
        live_allowed_symbols = tuple(raw_symbols) if raw_symbols else settings.live_allowed_symbols

        raw_max_stake = execution.get("live_max_stake_usdt")
        live_max_stake_usdt = settings.live_max_stake_usdt
        if raw_max_stake not in (None, ""):
            live_max_stake_usdt = ExecutionService._read_decimal(raw_max_stake, field_name="execution.live_max_stake_usdt")

        raw_max_open_trades = execution.get("live_max_open_trades")
        live_max_open_trades = settings.live_max_open_trades
        if raw_max_open_trades not in (None, ""):
            try:
                live_max_open_trades = int(raw_max_open_trades)
            except (TypeError, ValueError) as exc:
                raise PermissionError("execution.live_max_open_trades 必须是整数") from exc
            if live_max_open_trades <= 0:
                raise PermissionError("execution.live_max_open_trades 必须大于 0")

        return {
            "live_allowed_symbols": live_allowed_symbols,
            "live_max_stake_usdt": live_max_stake_usdt,
            "live_max_open_trades": live_max_open_trades,
        }

    def _get_min_notional(self, symbol: str) -> Decimal:
        """读取交易所对该币种的最小下单额。"""

        payload = self._market_client.get_exchange_info((symbol,))
        for item in list(payload.get("symbols", [])):
            if str(item.get("symbol", "")).upper() != symbol:
                continue
            for raw_filter in list(item.get("filters", [])):
                filter_type = str(raw_filter.get("filterType", "")).upper()
                if filter_type == "NOTIONAL":
                    value = raw_filter.get("minNotional")
                    if value not in (None, ""):
                        return self._read_decimal(value, field_name=f"{symbol}.minNotional")
                if filter_type == "MIN_NOTIONAL":
                    value = raw_filter.get("minNotional")
                    if value not in (None, ""):
                        return self._read_decimal(value, field_name=f"{symbol}.minNotional")
        raise PermissionError(f"无法读取 {symbol} 的最小下单额规则")

    def _get_safe_exit_stake(self, symbol: str, min_notional: Decimal) -> Decimal:
        """估算一笔 live 买入至少要多大，后续才不会因为最小卖出额失败。"""

        exchange_info = self._market_client.get_exchange_info((symbol,))
        step_size = self._get_lot_step_size(exchange_info=exchange_info, symbol=symbol)
        last_price = self._get_last_price(symbol)
        fee_ratio = Decimal("0.001")

        minimum_sell_quantity = self._round_up_to_step(min_notional / last_price, step_size)
        required_buy_quantity = self._round_up_to_step(minimum_sell_quantity / (Decimal("1") - fee_ratio), step_size)
        safe_stake = required_buy_quantity * last_price
        return safe_stake.quantize(Decimal("0.0000000001"))

    def _get_lot_step_size(self, exchange_info: dict[str, object], symbol: str) -> Decimal:
        """读取交易对的最小数量步长。"""

        for item in list(exchange_info.get("symbols", [])):
            if str(item.get("symbol", "")).upper() != symbol:
                continue
            for raw_filter in list(item.get("filters", [])):
                filter_type = str(raw_filter.get("filterType", "")).upper()
                if filter_type != "LOT_SIZE":
                    continue
                value = raw_filter.get("stepSize")
                if value not in (None, ""):
                    return self._read_decimal(value, field_name=f"{symbol}.stepSize")
        raise PermissionError(f"无法读取 {symbol} 的交易步长规则")

    def _get_last_price(self, symbol: str) -> Decimal:
        """读取最新成交价，用于估算最小可卖出金额。"""

        for item in list(self._market_client.get_tickers()):
            if str(item.get("symbol", "")).upper() != symbol:
                continue
            price = item.get("lastPrice") or item.get("last_price") or item.get("price")
            if price not in (None, ""):
                return self._read_decimal(price, field_name=f"{symbol}.lastPrice")
        raise PermissionError(f"无法读取 {symbol} 的最新价格")

    @staticmethod
    def _round_up_to_step(value: Decimal, step: Decimal) -> Decimal:
        """按交易步长向上取整。"""

        units = (value / step).to_integral_value(rounding=ROUND_CEILING)
        return units * step

    @staticmethod
    def _compact_symbol(symbol: str) -> str:
        """把 DOGE/USDT 这种格式压成 DOGEUSDT。"""

        return symbol.strip().upper().replace("/", "")

    @staticmethod
    def _read_decimal(value: object, field_name: str) -> Decimal:
        """把运行时金额字段转成 Decimal。"""

        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise PermissionError(f"无法解析 {field_name}={value}") from exc
        if parsed <= 0:
            raise PermissionError(f"{field_name} 必须大于 0")
        return parsed


execution_service = ExecutionService()

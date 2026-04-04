"""Execution mapping service for Quant phase 1."""

from __future__ import annotations

from decimal import Decimal
from decimal import InvalidOperation
from decimal import ROUND_CEILING

from services.api.app.adapters.binance.market_client import BinanceMarketClient
from services.api.app.adapters.freqtrade.client import freqtrade_client
from services.api.app.core.settings import Settings
from services.api.app.domain.contracts import ExecutionActionContract, ExecutionActionType
from services.api.app.services.signal_service import signal_service


class ExecutionService:
    """Maps control-plane signals to execution actions."""

    def __init__(self, market_client: BinanceMarketClient | None = None) -> None:
        self._market_client = market_client or BinanceMarketClient()

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
        if runtime_mode == "live":
            self._guard_live_execution(action=action, settings=settings, runtime_snapshot=runtime_snapshot)
        order = freqtrade_client.submit_execution_action(action)
        return {
            "action": action,
            "order": order,
            "runtime": runtime_snapshot,
        }

    @staticmethod
    def _resolve_action_type(side: str) -> ExecutionActionType:
        if side == "flat":
            return ExecutionActionType.CLOSE_POSITION
        return ExecutionActionType.OPEN_POSITION

    @staticmethod
    def _resolve_quantity(target_weight: str) -> Decimal:
        weight = Decimal(target_weight).copy_abs()
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
            if not settings.live_allowed_symbols:
                raise PermissionError("live 模式需要先配置 QUANT_LIVE_ALLOWED_SYMBOLS")
            if symbol not in settings.live_allowed_symbols:
                raise PermissionError(f"live 模式当前只允许这些币种: {', '.join(settings.live_allowed_symbols)}")

            stake_amount = self._read_decimal(
                runtime_snapshot.get("stake_amount"),
                field_name="stake_amount",
            )
            if settings.live_max_stake_usdt is None:
                raise PermissionError("live 模式需要先配置 QUANT_LIVE_MAX_STAKE_USDT")
            if stake_amount > settings.live_max_stake_usdt:
                raise PermissionError(
                    f"远端 Freqtrade 当前 stake_amount={stake_amount} USDT，已超过本地 live 上限 {settings.live_max_stake_usdt} USDT"
                )

            if settings.live_max_open_trades is None:
                raise PermissionError("live 模式需要先配置 QUANT_LIVE_MAX_OPEN_TRADES")
            remote_max_open_trades = runtime_snapshot.get("max_open_trades")
            if remote_max_open_trades is None:
                raise PermissionError("live 模式下无法确认远端 max_open_trades")
            try:
                parsed_remote_max_open_trades = int(remote_max_open_trades)
            except (TypeError, ValueError) as exc:
                raise PermissionError(f"无法解析远端 max_open_trades={remote_max_open_trades}") from exc
            if parsed_remote_max_open_trades > settings.live_max_open_trades:
                raise PermissionError(
                    f"远端 Freqtrade 当前 max_open_trades={parsed_remote_max_open_trades}，已超过本地 live 上限 {settings.live_max_open_trades}"
                )
            open_positions = freqtrade_client.get_snapshot().positions
            if len(open_positions) >= settings.live_max_open_trades:
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

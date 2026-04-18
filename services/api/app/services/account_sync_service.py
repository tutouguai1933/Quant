"""账户同步整理服务。

这个文件把 Binance 账户原始数据整理成控制平面可以直接返回的统一结构。
"""

from __future__ import annotations

import inspect
from decimal import Decimal, InvalidOperation, ROUND_DOWN

from services.api.app.adapters.binance.market_client import BinanceMarketClient
from services.api.app.core.settings import Settings
from services.api.app.adapters.binance.account_client import binance_account_client


def normalize_balance_row(row: dict[str, object]) -> dict[str, object]:
    """把余额行统一成 asset / available / locked。"""

    asset = row.get("asset") or row.get("coin") or ""
    available = row.get("available")
    if available is None:
        available = row.get("free")
    if available is None:
        available = row.get("availableBalance")
    locked = row.get("locked")
    if locked is None:
        locked = row.get("freeze")
    return {
        "asset": str(asset),
        "available": str(available if available is not None else ""),
        "locked": str(locked if locked is not None else ""),
    }


def _read_decimal(value: object) -> Decimal:
    """把金额值转成 Decimal，异常时回退到 0。"""

    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _format_decimal(value: Decimal) -> str:
    """把 Decimal 稳定输出成普通字符串。"""

    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f").rstrip("0").rstrip(".")


def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    """按交易步长向下取整。"""

    if step <= 0:
        return value
    units = (value / step).to_integral_value(rounding=ROUND_DOWN)
    return units * step


def _normalize_order_row(row: dict[str, object]) -> dict[str, object]:
    """把订单行统一成前端稳定字段。"""

    normalized = dict(row)
    normalized["id"] = str(
        normalized.get("id")
        or normalized.get("orderId")
        or normalized.get("clientOrderId")
        or normalized.get("venueOrderId")
        or ""
    )
    normalized["symbol"] = str(normalized.get("symbol", ""))
    normalized["status"] = str(normalized.get("status", ""))
    normalized["side"] = str(normalized.get("side", "")).lower()
    normalized["quantity"] = str(normalized.get("quantity", normalized.get("origQty", "0.0000000000")))
    normalized["executedQty"] = str(normalized.get("executedQty", "0.0000000000"))
    normalized["price"] = str(normalized.get("price", "0.0000000000"))
    order_type = str(
        normalized.get("orderType")
        or normalized.get("order_type")
        or normalized.get("type")
        or ""
    )
    normalized["orderType"] = order_type
    normalized["order_type"] = order_type
    normalized["lifecycle"] = _resolve_order_lifecycle(
        status=str(normalized.get("status", "")),
        side=str(normalized.get("side", "")),
    )
    return normalized


def _order_sort_timestamp(row: dict[str, object]) -> int:
    """提取订单最新优先排序所需的时间戳。"""

    for key in ("updateTime", "time", "transactTime"):
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            try:
                return int(float(str(value)))
            except (TypeError, ValueError):
                continue
    return 0


def _normalize_position_row(row: dict[str, object]) -> dict[str, object]:
    """把持仓行统一成前端稳定字段。"""

    normalized = dict(row)
    symbol = str(normalized.get("symbol") or normalized.get("asset") or normalized.get("coin") or "")
    position_id = normalized.get("id")
    if not position_id and symbol:
        position_id = f"position-{symbol}"
    normalized["id"] = str(position_id or "")
    normalized["symbol"] = symbol
    normalized["side"] = str(normalized.get("side", "long")).lower()
    normalized["quantity"] = str(normalized.get("quantity", normalized.get("size", "0.0000000000")))
    normalized["unrealizedPnl"] = str(normalized.get("unrealizedPnl", "0.0000000000"))
    normalized["entryPrice"] = str(normalized.get("entryPrice", "0.0000000000"))
    normalized["markPrice"] = str(normalized.get("markPrice", "0.0000000000"))
    normalized["positionStatus"] = "open" if _read_decimal(normalized["quantity"]) > 0 else "closed"
    return normalized


def _resolve_order_lifecycle(*, status: str, side: str) -> str:
    """把订单状态压成更适合页面和健康摘要的生命周期。"""

    normalized_status = status.strip().upper()
    normalized_side = side.strip().lower()
    if normalized_side == "sell" and normalized_status in {"NEW", "PARTIALLY_FILLED"}:
        return "pending_exit"
    if normalized_side == "buy" and normalized_status in {"NEW", "PARTIALLY_FILLED"}:
        return "pending_entry"
    if normalized_side == "sell" and normalized_status in {"FILLED", "CLOSED"}:
        return "filled_exit"
    if normalized_side == "buy" and normalized_status in {"FILLED", "CLOSED"}:
        return "filled_entry"
    return "idle"


class AccountSyncService:
    """把账户数据标准化后提供给路由层。"""

    def __init__(self, client: object | None = None, market_client: object | None = None) -> None:
        self._client = client or binance_account_client
        self._market_client = market_client or BinanceMarketClient()

    def list_balances(self, limit: int = 100) -> list[dict[str, object]]:
        """返回标准化后的余额列表。"""

        settings = Settings.from_env()
        balances = self._call_client_list("get_balances")
        normalized = [normalize_balance_row(row) for row in balances[:limit]]
        return self._annotate_balances(normalized, settings=settings)

    def list_orders(self, limit: int = 100, symbols: tuple[str, ...] | None = None) -> list[dict[str, object]]:
        """返回账户订单列表。"""

        settings = Settings.from_env()
        order_symbols = symbols or settings.account_sync_order_symbols
        orders: list[dict[str, object]] = []
        for symbol in order_symbols:
            orders.extend(
                _normalize_order_row(row)
                for row in self._call_client_list("get_orders", symbol=symbol, limit=limit)
            )
        orders.sort(key=_order_sort_timestamp, reverse=True)
        return orders[:limit]

    def list_positions(self, limit: int = 100) -> list[dict[str, object]]:
        """返回账户持仓列表。"""

        positions = self._call_client_list("get_positions")
        return [_normalize_position_row(row) for row in positions[:limit]]

    def _call_client_list(self, method_name: str, **kwargs) -> list[dict[str, object]]:
        method = getattr(self._client, method_name, None)
        if method is None:
            return []
        if kwargs:
            try:
                signature = inspect.signature(method)
            except (TypeError, ValueError):
                signature = None
            if signature is not None:
                parameters = signature.parameters
                accepts_kwargs = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in parameters.values())
                accepts_all_kwargs = accepts_kwargs or all(name in parameters for name in kwargs)
                items = method(**kwargs) if accepts_all_kwargs else method()
            else:
                items = method(**kwargs)
        else:
            items = method()
        if items is None:
            return []
        return list(items)

    def _annotate_balances(
        self,
        balances: list[dict[str, object]],
        *,
        settings: Settings,
    ) -> list[dict[str, object]]:
        """给余额补充可交易状态，避免把零头资产误判成打开中的仓位。"""

        symbols = tuple(
            dict.fromkeys(
                tuple(symbol.strip().upper() for symbol in settings.market_symbols)
                + tuple(symbol.strip().upper() for symbol in settings.live_allowed_symbols)
            )
        )

        # 使用超时保护的并发调用，避免阻塞
        exchange_info: dict[str, object] = {}
        latest_prices: dict[str, Decimal] = {}

        try:
            exchange_info = self._market_client.get_exchange_info(symbols or None)
        except Exception:
            pass  # 降级：无交易规则时仍返回基础余额

        try:
            latest_prices = self._build_price_map(symbols)
        except Exception:
            pass  # 降级：无价格时仍返回基础余额

        symbol_rules = self._build_symbol_rules(exchange_info=exchange_info)
        enriched: list[dict[str, object]] = []

        for item in balances:
            available = _read_decimal(item.get("available"))
            locked = _read_decimal(item.get("locked"))
            asset = str(item.get("asset", "")).upper()
            annotated = dict(item)
            annotated["id"] = str(item.get("id") or f"balance-{asset.lower()}")
            annotated["tradeStatus"] = "idle"
            annotated["tradeHint"] = "当前没有可用余额"
            annotated["sellableQuantity"] = "0"
            annotated["dustQuantity"] = "0"

            if locked > 0 and available <= 0:
                annotated["tradeStatus"] = "locked"
                annotated["tradeHint"] = "当前余额处于冻结状态，暂时不能直接使用"
                enriched.append(annotated)
                continue

            if available <= 0 and locked <= 0:
                enriched.append(annotated)
                continue

            if asset == "USDT":
                annotated["tradeStatus"] = "tradable"
                annotated["tradeHint"] = "这是基础计价资产，可以直接用于下单"
                annotated["sellableQuantity"] = _format_decimal(available)
                enriched.append(annotated)
                continue

            symbol = f"{asset}USDT"
            rule = symbol_rules.get(symbol)
            price = latest_prices.get(symbol)
            if not rule or price is None:
                annotated["tradeStatus"] = "untracked"
                annotated["tradeHint"] = "当前没有拿到完整交易规则，先按持有资产显示"
                annotated["sellableQuantity"] = _format_decimal(available)
                enriched.append(annotated)
                continue

            step_size = rule["step_size"]
            min_notional = rule["min_notional"]
            sellable_quantity = _floor_to_step(available, step_size)
            dust_quantity = available - sellable_quantity

            if sellable_quantity <= 0 or (sellable_quantity * price) < min_notional:
                annotated["tradeStatus"] = "dust"
                annotated["tradeHint"] = "这部分余额低于当前可卖门槛，属于交易所零头资产"
                annotated["sellableQuantity"] = _format_decimal(Decimal("0"))
                annotated["dustQuantity"] = _format_decimal(available)
                enriched.append(annotated)
                continue

            annotated["tradeStatus"] = "tradable"
            if dust_quantity > 0:
                annotated["tradeHint"] = "当前有可卖部分，但还带着一部分交易所零头"
            else:
                annotated["tradeHint"] = "当前余额满足最小下单额和步长要求，可正常卖出"
            annotated["sellableQuantity"] = _format_decimal(sellable_quantity)
            annotated["dustQuantity"] = _format_decimal(dust_quantity)
            enriched.append(annotated)

        return enriched

    def _build_symbol_rules(self, exchange_info: dict[str, object]) -> dict[str, dict[str, Decimal]]:
        """把交易规则整理成更容易读取的结构。"""

        rules: dict[str, dict[str, Decimal]] = {}
        for item in list(exchange_info.get("symbols", [])):
            symbol = str(item.get("symbol", "")).upper()
            if not symbol:
                continue
            step_size = Decimal("0")
            min_notional = Decimal("0")
            for raw_filter in list(item.get("filters", [])):
                filter_type = str(raw_filter.get("filterType", "")).upper()
                if filter_type == "LOT_SIZE":
                    step_size = _read_decimal(raw_filter.get("stepSize"))
                if filter_type in {"NOTIONAL", "MIN_NOTIONAL"}:
                    min_notional = _read_decimal(raw_filter.get("minNotional"))
            if step_size > 0 and min_notional > 0:
                rules[symbol] = {"step_size": step_size, "min_notional": min_notional}
        return rules

    def _build_price_map(self, symbols: tuple[str, ...]) -> dict[str, Decimal]:
        """读取最新成交价，用于判断余额是不是零头。"""

        price_map: dict[str, Decimal] = {}
        for item in list(self._market_client.get_tickers(symbols or None)):
            symbol = str(item.get("symbol", "")).upper()
            if not symbol:
                continue
            price = item.get("lastPrice") or item.get("last_price") or item.get("price")
            parsed = _read_decimal(price)
            if parsed > 0:
                price_map[symbol] = parsed
        return price_map


account_sync_service = AccountSyncService()

"""账户同步整理服务。

这个文件把 Binance 账户原始数据整理成控制平面可以直接返回的统一结构。
"""

from __future__ import annotations

import inspect

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
    return normalized


class AccountSyncService:
    """把账户数据标准化后提供给路由层。"""

    def __init__(self, client: object | None = None) -> None:
        self._client = client or binance_account_client

    def list_balances(self, limit: int = 100) -> list[dict[str, object]]:
        """返回标准化后的余额列表。"""

        balances = self._call_client_list("get_balances")
        return [normalize_balance_row(row) for row in balances[:limit]]

    def list_orders(self, limit: int = 100) -> list[dict[str, object]]:
        """返回账户订单列表。"""

        settings = Settings.from_env()
        orders: list[dict[str, object]] = []
        for symbol in settings.market_symbols:
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


account_sync_service = AccountSyncService()

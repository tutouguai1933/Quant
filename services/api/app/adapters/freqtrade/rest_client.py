"""Freqtrade REST 客户端。

这个文件负责和真实的 Freqtrade REST API 通信，并把 HTTP 细节收敛成统一的控制平面接口。
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib import error, request

def utc_now() -> datetime:
    """返回当前 UTC 时间。"""

    return datetime.now(timezone.utc)


def _normalize_symbol(symbol: str) -> str:
    """把控制平面的交易对符号归一成 Freqtrade 使用的 pair。"""

    compact = symbol.strip().upper().replace("/", "")
    if not compact:
        raise ValueError("symbol must not be empty")
    if compact.endswith("USDT") and len(compact) > 4:
        return f"{compact[:-4]}/USDT"
    return compact


def _payload_items(payload: Any, key: str) -> list[dict[str, object]]:
    """从不同响应形状里提取列表数据。"""

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for candidate in (key, "items", "data", "result"):
            value = payload.get(candidate)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = value.get(key)
                if isinstance(nested, list):
                    return [item for item in nested if isinstance(item, dict)]
        if key in payload and isinstance(payload[key], dict):
            nested_value = payload[key]
            for nested_key in ("items", "data", "result"):
                nested_items = nested_value.get(nested_key)
                if isinstance(nested_items, list):
                    return [item for item in nested_items if isinstance(item, dict)]
    return []


def _to_decimal_string(value: object, default: str = "0.0000000000") -> str:
    """把金额类值统一成字符串。"""

    if value is None:
        return default
    try:
        return f"{Decimal(str(value)):.10f}"
    except Exception:
        return default


def _trade_sort_key(item: dict[str, object]) -> tuple[int, str]:
    """给 trade 列表提供稳定的“最新优先”排序键。"""

    raw_trade_id = item.get("trade_id") or item.get("id") or 0
    try:
        numeric_id = int(str(raw_trade_id))
    except Exception:
        numeric_id = 0
    return numeric_id, str(raw_trade_id)


@dataclass(frozen=True)
class FreqtradeRestConfig:
    """Freqtrade REST 连接配置。"""

    base_url: str
    username: str
    password: str
    timeout_seconds: float = 10.0
    max_retries: int = 3
    base_delay: float = 0.5
    max_total_timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        normalized_url = self.base_url.strip().rstrip("/")
        if not normalized_url:
            raise ValueError("base_url must not be empty")
        if not normalized_url.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0")
        if self.max_retries < 1:
            raise ValueError("max_retries must be at least 1")
        if self.base_delay <= 0:
            raise ValueError("base_delay must be greater than 0")
        if self.max_total_timeout_seconds <= 0:
            raise ValueError("max_total_timeout_seconds must be greater than 0")
        object.__setattr__(self, "base_url", normalized_url)


class FreqtradeRestError(RuntimeError):
    """Freqtrade REST 请求失败。"""


class FreqtradeRestClient:
    """面向 Freqtrade REST API 的最小客户端。"""

    # 快照缓存 TTL（秒）
    _SNAPSHOT_CACHE_TTL = 5.0

    def __init__(self, config: FreqtradeRestConfig) -> None:
        self._config = config
        self._access_token: str | None = None
        self._next_order_id = 1
        self._opener = request.build_opener(request.ProxyHandler({}))
        # 快照缓存
        self._snapshot_cache: Any = None
        self._snapshot_cache_time: float = 0.0

    @classmethod
    def from_settings(cls, settings: Settings) -> "FreqtradeRestClient":
        """从运行配置构建 REST 客户端。"""

        return cls(
            FreqtradeRestConfig(
                base_url=settings.freqtrade_api_url,
                username=settings.freqtrade_api_username,
                password=settings.freqtrade_api_password,
                timeout_seconds=settings.freqtrade_api_timeout_seconds,
            )
        )

    def ping(self) -> dict[str, object]:
        """检查 API 是否可用。"""

        return self._request_json("GET", "/api/v1/ping", auth=False)

    def control_strategy(self, strategy_id: int, action: str) -> dict[str, object]:
        """控制 Freqtrade bot 的运行状态。"""

        if action not in {"start", "pause", "stop"}:
            raise ValueError("action must be start, pause or stop")
        response = self._request_json("POST", f"/api/v1/{action}", auth=True)
        status_map = {"start": "running", "pause": "paused", "stop": "stopped"}
        normalized_status = status_map[action]
        raw_status = str(response.get("status", ""))
        if raw_status in {"running", "paused", "stopped"}:
            normalized_status = raw_status
        return {
            "id": 1,
            "name": response.get("name", "Freqtrade Bot"),
            "producerType": response.get("producerType", "freqtrade-rest"),
            "status": normalized_status,
            "executor": "freqtrade",
            "exchange": response.get("exchange", "binance"),
            "scope": "executor",
            "controlled_strategy_id": strategy_id,
            "updatedAt": utc_now().isoformat(),
        }

    def submit_execution_action(self, action: dict[str, object]) -> dict[str, object]:
        """把控制平面的执行动作提交给 Freqtrade。"""

        symbol = _normalize_symbol(str(action["symbol"]))
        side = str(action["side"])
        quantity = Decimal(str(action["quantity"]))
        if side == "flat":
            explicit_trade_id = action.get("trade_id") or action.get("venue_trade_id")
            target_trades = self._resolve_flat_trades(symbol, trade_id=explicit_trade_id)
            primary_trade = target_trades[0]
            response: dict[str, object] = {}
            hydrated_trade: dict[str, object] | None = None
            for target_trade in target_trades:
                response = self._request_json(
                    "POST",
                    "/api/v1/forceexit",
                    auth=True,
                    payload={"tradeid": target_trade["trade_id"]},
                )
                current_trade = self._find_trade_history(symbol, trade_id=target_trade["trade_id"]) or target_trade
                if str(target_trade["trade_id"]) == str(primary_trade["trade_id"]):
                    hydrated_trade = current_trade
            # 平仓成功后推送飞书通知
            self._push_trade_notification(
                signal_type="sell",
                symbol=symbol,
                side=side,
                trade=hydrated_trade,
                response=response,
            )
        else:
            stake_amount = self._resolve_action_stake_amount(action)
            response = self._request_json(
                "POST",
                "/api/v1/forceenter",
                auth=True,
                payload={
                    "pair": symbol,
                    "side": side,
                    "stakeamount": float(stake_amount),
                    "ordertype": "market",
                    "entry_tag": "quant-control-plane",
                },
            )
            trade_id = response.get("trade_id") or response.get("id")
            hydrated_trade = self._find_open_trade(symbol, trade_id=trade_id) or self._find_trade_history(symbol, trade_id=trade_id)
            # 开仓成功后推送飞书通知
            self._push_trade_notification(
                signal_type="buy",
                symbol=symbol,
                side=side,
                trade=hydrated_trade,
                response=response,
            )

        return self._build_order_feedback(
            action=action,
            symbol=symbol,
            side=side,
            requested_quantity=quantity,
            response=response,
            hydrated_trade=hydrated_trade,
        )

    def _resolve_action_stake_amount(self, action: dict[str, object]) -> Decimal:
        """优先使用控制平面已经校验过的 stake_amount。"""

        explicit_stake_amount = action.get("stake_amount")
        if explicit_stake_amount not in (None, ""):
            try:
                parsed = Decimal(str(explicit_stake_amount))
            except Exception as exc:
                raise FreqtradeRestError(f"invalid explicit stake_amount: {explicit_stake_amount}") from exc
            if parsed <= 0:
                raise FreqtradeRestError("explicit stake_amount must be greater than 0")
            return parsed
        return self._resolve_stake_amount(default=Decimal("50"))

    def _resolve_stake_amount(self, default: Decimal) -> Decimal:
        """读取远端 stake_amount，确保 forceenter 使用正确的计价币金额。"""

        try:
            payload = self._request_json("GET", "/api/v1/show_config", auth=True)
        except FreqtradeRestError:
            return default

        raw_value = payload.get("stake_amount")
        if raw_value in (None, "", "unlimited"):
            return default
        try:
            parsed = Decimal(str(raw_value))
        except Exception:
            return default
        if parsed <= 0:
            return default
        return parsed

    def get_snapshot(self) -> Any:
        """读取余额、持仓、订单和策略列表（带缓存）。"""

        # 检查缓存是否有效
        now = time.time()
        if self._snapshot_cache is not None and (now - self._snapshot_cache_time) < self._SNAPSHOT_CACHE_TTL:
            print(f"[CACHE] get_snapshot() 使用缓存，TTL剩余 {self._SNAPSHOT_CACHE_TTL - (now - self._snapshot_cache_time):.1f}s")
            return self._snapshot_cache

        print("[CACHE] get_snapshot() 缓存未命中，开始计算...")

        from services.api.app.adapters.freqtrade.client import FreqtradeSnapshot

        snapshot = FreqtradeSnapshot(
            balances=self._get_balances(),
            positions=self._get_positions(),
            orders=self._get_orders(),
            strategies=self._get_strategies(),
        )
        self._snapshot_cache = snapshot
        self._snapshot_cache_time = now
        return snapshot

    def get_runtime_snapshot(self) -> dict[str, object]:
        """返回执行器运行视图。"""

        remote_mode = "unknown"
        connection_status = "error"
        config_summary: dict[str, object] = {}
        try:
            config_summary = self._get_remote_config_summary()
            remote_mode = str(config_summary.get("mode", "unknown"))
            connection_status = "connected" if remote_mode != "unknown" else "configured"
        except FreqtradeRestError:
            connection_status = "error"
        return {
            "executor": "freqtrade",
            "backend": "rest",
            "mode": remote_mode,
            "connection_status": connection_status,
            "base_url": self._config.base_url,
            "stake_amount": config_summary.get("stake_amount", ""),
            "max_open_trades": config_summary.get("max_open_trades"),
            "trading_mode": config_summary.get("trading_mode", ""),
            "bot_state": config_summary.get("bot_state", ""),
        }

    def _get_status_items(self) -> list[dict[str, object]]:
        """读取远端当前状态列表。"""

        payload = self._request_json("GET", "/api/v1/status", auth=True)
        return _payload_items(payload, "status")

    def _get_balances(self) -> list[dict[str, object]]:
        """读取账户余额列表。"""

        payload = self._request_json("GET", "/api/v1/balance", auth=True)
        # Freqtrade balance API 返回 "currencies" 字段，需要特殊处理
        items = _payload_items(payload, "balances")
        if not items:
            items = _payload_items(payload, "currencies")
        return [dict(item) for item in items]

    def _get_positions(self) -> list[dict[str, object]]:
        """读取当前持仓列表。"""

        items = self._get_status_items()
        positions: list[dict[str, object]] = []
        for item in items:
            symbol = str(item.get("pair") or item.get("symbol") or "")
            compact_symbol = symbol.replace("/", "").upper()
            positions.append(
                {
                    "id": str(item.get("trade_id") or item.get("id") or compact_symbol or "position"),
                    "symbol": symbol or compact_symbol,
                    "side": str(item.get("side") or "long"),
                    "quantity": _to_decimal_string(item.get("amount") or item.get("amount_requested") or item.get("stake_amount")),
                    "entryPrice": _to_decimal_string(item.get("open_rate") or item.get("entry_price") or item.get("price")),
                    "markPrice": _to_decimal_string(item.get("current_rate") or item.get("mark_price") or item.get("price")),
                    "unrealizedPnl": _to_decimal_string(item.get("profit_abs") or item.get("profit")),
                    "updatedAt": utc_now().isoformat(),
                    "strategyId": item.get("strategy_id"),
                }
            )
        return positions

    def _get_orders(self) -> list[dict[str, object]]:
        """读取交易历史列表。"""

        runtime_mode = self._get_remote_mode(default="unknown")
        payload = self._request_json("GET", "/api/v1/trades", auth=True)
        items = _payload_items(payload, "trades")
        orders: list[dict[str, object]] = []
        for item in items:
            symbol = str(item.get("pair") or item.get("symbol") or "")
            compact_symbol = symbol.replace("/", "").upper()
            orders.append(
                {
                    "id": str(item.get("trade_id") or item.get("id") or compact_symbol or "order"),
                    "venueOrderId": str(item.get("order_id") or item.get("trade_id") or item.get("id") or compact_symbol or "order"),
                    "runtimeMode": runtime_mode,
                    "symbol": symbol or compact_symbol,
                    "side": str(item.get("side") or "long"),
                    "orderType": str(item.get("order_type") or item.get("type") or "market"),
                    "status": str(item.get("status") or "filled"),
                    "quantity": _to_decimal_string(item.get("amount") or item.get("stake_amount")),
                    "executedQty": _to_decimal_string(item.get("amount") or item.get("stake_amount")),
                    "avgPrice": _to_decimal_string(item.get("open_rate") or item.get("average_price") or item.get("price")),
                    "sourceSignalId": item.get("signal_id"),
                    "strategyId": item.get("strategy_id"),
                    "updatedAt": utc_now().isoformat(),
                }
            )
        if orders:
            return orders

        status_items = self._get_status_items()
        for item in status_items:
            symbol = str(item.get("pair") or item.get("symbol") or "")
            compact_symbol = symbol.replace("/", "").upper()
            for nested_order in item.get("orders", []) if isinstance(item.get("orders"), list) else []:
                order_id = str(nested_order.get("order_id") or nested_order.get("id") or compact_symbol or "order")
                filled_amount = nested_order.get("filled") or nested_order.get("amount") or item.get("amount")
                price = (
                    nested_order.get("safe_price")
                    or nested_order.get("average_price")
                    or item.get("open_rate")
                    or item.get("price")
                )
                side = str(nested_order.get("ft_order_side") or nested_order.get("side") or "buy")
                normalized_side = "flat" if side in {"sell", "exit"} else "long"
                orders.append(
                    {
                        "id": order_id,
                        "venueOrderId": order_id,
                        "runtimeMode": runtime_mode,
                        "symbol": symbol or compact_symbol,
                        "side": normalized_side,
                        "orderType": str(nested_order.get("order_type") or nested_order.get("type") or "market"),
                        "status": str(nested_order.get("status") or "filled"),
                        "quantity": _to_decimal_string(filled_amount),
                        "executedQty": _to_decimal_string(filled_amount),
                        "avgPrice": _to_decimal_string(price),
                        "sourceSignalId": None,
                        "strategyId": item.get("strategy_id"),
                        "updatedAt": utc_now().isoformat(),
                    }
                )
        return orders

    def _find_open_trade(self, symbol: str, trade_id: object | None = None) -> dict[str, object] | None:
        """按交易对或 trade_id 查找当前仍在状态列表里的交易。"""

        normalized_symbol = _normalize_symbol(symbol)
        normalized_trade_id = str(trade_id) if trade_id not in (None, "") else None
        symbol_matches = self._list_open_trades(normalized_symbol)
        if normalized_trade_id:
            for item in symbol_matches:
                item_trade_id = str(item.get("trade_id") or item.get("id") or "")
                if item_trade_id == normalized_trade_id:
                    return dict(item)
            return None
        if not symbol_matches:
            return None
        return dict(symbol_matches[0])

    def _list_open_trades(self, symbol: str) -> list[dict[str, object]]:
        """按交易对收集当前所有打开交易，并把最新的排在前面。"""

        normalized_symbol = _normalize_symbol(symbol)
        symbol_matches: list[dict[str, object]] = []
        for item in self._get_status_items():
            raw_pair = str(item.get("pair") or item.get("symbol") or "").strip()
            if not raw_pair:
                continue
            pair = _normalize_symbol(raw_pair)
            if pair == normalized_symbol:
                symbol_matches.append(dict(item))
        symbol_matches.sort(key=_trade_sort_key, reverse=True)
        return symbol_matches

    def _find_trade_history(self, symbol: str, trade_id: object | None = None) -> dict[str, object] | None:
        """按交易对或 trade_id 查找历史成交。"""

        normalized_symbol = _normalize_symbol(symbol)
        normalized_trade_id = str(trade_id) if trade_id not in (None, "") else None
        payload = self._request_json("GET", "/api/v1/trades", auth=True)
        symbol_matches: list[dict[str, object]] = []
        for item in _payload_items(payload, "trades"):
            raw_pair = str(item.get("pair") or item.get("symbol") or "").strip()
            if not raw_pair:
                continue
            pair = _normalize_symbol(raw_pair)
            item_trade_id = str(item.get("trade_id") or item.get("id") or "")
            if normalized_trade_id and item_trade_id == normalized_trade_id:
                return dict(item)
            if pair == normalized_symbol:
                symbol_matches.append(dict(item))
        if not symbol_matches:
            return None
        symbol_matches.sort(key=_trade_sort_key, reverse=True)
        return symbol_matches[0]

    def _resolve_flat_trades(self, symbol: str, trade_id: object | None = None) -> list[dict[str, object]]:
        """解析平仓目标：默认平当前币种全部打开交易，也支持只平指定 trade_id。"""

        if trade_id not in (None, ""):
            trade = self._find_open_trade(symbol, trade_id=trade_id)
            if trade is None:
                raise FreqtradeRestError(f"Freqtrade 当前没有可平的 {symbol} 交易 {trade_id}")
            return [trade]

        trades = self._list_open_trades(symbol)
        if not trades:
            orphan_balance = self._find_nonzero_spot_balance(symbol)
            if orphan_balance is not None:
                raise FreqtradeRestError(
                    f"Binance 账户里仍有 {symbol} 现货余额 {orphan_balance}，"
                    "但当前 Freqtrade 没有打开交易记录，无法直接平仓"
                )
            raise FreqtradeRestError(f"Freqtrade 当前没有可平的 {symbol} 持仓")
        return trades

    def _find_nonzero_spot_balance(self, symbol: str) -> str | None:
        """查找指定交易对基础币是否仍有非零现货余额。"""

        base_asset = _normalize_symbol(symbol).split("/", 1)[0]
        for item in self._get_balances():
            asset = str(item.get("asset") or item.get("currency") or "").strip().upper()
            if asset != base_asset:
                continue
            candidates = (
                item.get("available"),
                item.get("free"),
                item.get("total"),
                item.get("balance"),
            )
            for value in candidates:
                try:
                    parsed = Decimal(str(value))
                except (ArithmeticError, ValueError, TypeError):
                    continue
                if parsed > 0:
                    return _to_decimal_string(parsed)
        return None

    def _build_order_feedback(
        self,
        action: dict[str, object],
        symbol: str,
        side: str,
        requested_quantity: Decimal,
        response: dict[str, object],
        hydrated_trade: dict[str, object] | None,
    ) -> dict[str, object]:
        """优先使用远端交易结果拼出执行回执。"""

        timestamp = utc_now().isoformat()
        trade = hydrated_trade or {}
        nested_order = self._extract_nested_order(trade)
        trade_id = trade.get("trade_id") or trade.get("id") or response.get("trade_id") or response.get("id")
        order_id = (
            nested_order.get("order_id")
            or nested_order.get("id")
            or response.get("order_id")
            or response.get("id")
            or trade_id
            or f"ft-rest-order-{self._next_order_id}"
        )
        if str(order_id).startswith("ft-rest-order-"):
            self._next_order_id += 1

        quantity_value = (
            nested_order.get("filled")
            or nested_order.get("amount")
            or trade.get("amount")
            or trade.get("amount_requested")
            or trade.get("stake_amount")
            or requested_quantity
        )
        price_value = (
            nested_order.get("safe_price")
            or nested_order.get("average_price")
            or trade.get("open_rate")
            or trade.get("current_rate")
            or trade.get("average_price")
            or trade.get("price")
            or response.get("price")
        )
        status_value = (
            nested_order.get("status")
            or trade.get("status")
            or response.get("status")
            or "submitted"
        )
        order_type_value = (
            nested_order.get("order_type")
            or nested_order.get("type")
            or response.get("order_type")
            or "market"
        )

        return {
            "id": str(trade_id or order_id),
            "venueOrderId": str(order_id),
            "runtimeMode": self._get_remote_mode(default="unknown"),
            "symbol": symbol,
            "side": "flat" if side == "flat" else "long",
            "orderType": str(order_type_value),
            "status": str(status_value),
            "quantity": _to_decimal_string(quantity_value),
            "executedQty": _to_decimal_string(quantity_value),
            "avgPrice": _to_decimal_string(price_value),
            "sourceSignalId": action["source_signal_id"],
            "strategyId": action.get("strategy_id"),
            "updatedAt": timestamp,
        }

    @staticmethod
    def _extract_nested_order(trade: dict[str, object]) -> dict[str, object]:
        """从交易详情里取最后一笔订单。"""

        orders = trade.get("orders")
        if isinstance(orders, list) and orders:
            last_order = orders[-1]
            if isinstance(last_order, dict):
                return dict(last_order)
        return {}

    def _get_remote_mode(self, default: str | None = None) -> str:
        """读取远端 Freqtrade 实际运行模式。"""

        return str(self._get_remote_config_summary(default_mode=default).get("mode", default or "unknown"))

    def _get_remote_config_summary(self, default_mode: str | None = None) -> dict[str, object]:
        """读取远端关键配置，供运行快照和 live 安全门共用。"""

        try:
            payload = self._request_json("GET", "/api/v1/show_config", auth=True)
        except FreqtradeRestError:
            if default_mode is not None:
                return {"mode": default_mode}
            raise

        candidates = [payload]
        if isinstance(payload.get("data"), dict):
            candidates.append(payload["data"])
        if isinstance(payload.get("config"), dict):
            candidates.append(payload["config"])

        mode = default_mode or "unknown"
        stake_amount = ""
        max_open_trades: int | None = None
        trading_mode = ""
        bot_state = ""
        for item in candidates:
            dry_run = item.get("dry_run")
            if isinstance(dry_run, bool):
                mode = "dry-run" if dry_run else "live"
            raw_stake_amount = item.get("stake_amount")
            if raw_stake_amount not in (None, ""):
                stake_amount = str(raw_stake_amount)
            raw_max_open_trades = item.get("max_open_trades")
            if raw_max_open_trades not in (None, ""):
                try:
                    max_open_trades = int(raw_max_open_trades)
                except Exception:
                    max_open_trades = None
            raw_trading_mode = item.get("trading_mode")
            if raw_trading_mode not in (None, ""):
                trading_mode = str(raw_trading_mode)
            raw_state = item.get("state")
            if raw_state not in (None, ""):
                bot_state = str(raw_state)

        return {
            "mode": mode,
            "stake_amount": stake_amount,
            "max_open_trades": max_open_trades,
            "trading_mode": trading_mode,
            "bot_state": bot_state,
        }

    def _get_strategies(self) -> list[dict[str, object]]:
        """读取策略列表。"""

        try:
            payload = self._request_json("GET", "/api/v1/strategies", auth=True)
            items = _payload_items(payload, "strategies")
        except FreqtradeRestError:
            items = []

        if not items:
            fallback = self._build_runtime_strategy()
            return [fallback] if fallback else []

        strategies: list[dict[str, object]] = []
        for item in items:
            strategies.append(
                {
                    "id": item.get("id"),
                    "name": item.get("name") or item.get("strategy") or item.get("class_name") or "Strategy",
                    "producerType": item.get("producerType") or item.get("producer_type") or "freqtrade-rest",
                    "status": item.get("status") or "running",
                    "executor": "freqtrade",
                    "exchange": item.get("exchange") or "binance",
                    "updatedAt": utc_now().isoformat(),
                }
            )
        return strategies

    def _build_runtime_strategy(self) -> dict[str, object] | None:
        """在运行态接口不可用时，用运行配置回填一个执行器视图。"""

        try:
            payload = self._request_json("GET", "/api/v1/show_config", auth=True)
        except FreqtradeRestError:
            return None

        name = str(payload.get("strategy") or payload.get("bot_name") or "Freqtrade Bot")
        state = str(payload.get("state") or "running").lower()
        normalized_status = state if state in {"running", "paused", "stopped"} else "running"
        return {
            "id": 1,
            "name": name,
            "producerType": "freqtrade-rest",
            "status": normalized_status,
            "executor": "freqtrade",
            "exchange": payload.get("exchange") or "binance",
            "updatedAt": utc_now().isoformat(),
        }

    def _request_json(
        self,
        method: str,
        path: str,
        auth: bool,
        payload: dict[str, object] | None = None,
        retry_on_unauthorized: bool = True,
    ) -> dict[str, object]:
        """执行一次 JSON 请求并处理错误，带重试、指数退避和总超时检查。"""

        url = self._config.base_url + path
        headers = {"Accept": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {self._ensure_access_token()}"
        body = None
        if method in {"POST", "PUT", "PATCH"}:
            body = json.dumps(payload or {}).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if not auth and path == "/api/v1/token/login":
            raise FreqtradeRestError("token login must use auth=True")

        last_exception: Exception | None = None
        start_time = time.time()

        for attempt in range(self._config.max_retries):
            # Check total timeout before each attempt
            elapsed = time.time() - start_time
            if elapsed > self._config.max_total_timeout_seconds:
                raise FreqtradeRestError(
                    f"Freqtrade REST {method} {path} 总超时 ({elapsed:.1f}s > {self._config.max_total_timeout_seconds}s)"
                )

            token_request = request.Request(url, data=body, method=method, headers=headers)
            try:
                with self._opener.open(token_request, timeout=self._config.timeout_seconds) as response:
                    payload_text = response.read().decode("utf-8").strip()
                    if not payload_text:
                        return {}
                    loaded = json.loads(payload_text)
                    return loaded if isinstance(loaded, dict) else {"data": loaded}
            except error.HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace").strip()
                if auth and exc.code == 401 and retry_on_unauthorized:
                    self._access_token = None
                    return self._request_json(
                        method,
                        path,
                        auth=auth,
                        payload=payload,
                        retry_on_unauthorized=False,
                    )
                if exc.code >= 500:
                    last_exception = exc
                    if attempt < self._config.max_retries - 1:
                        delay = self._config.base_delay * (2 ** attempt)
                        # Check if delay would exceed total timeout
                        if elapsed + delay > self._config.max_total_timeout_seconds:
                            break
                        time.sleep(delay)
                    continue
                detail = error_body or exc.reason or "unknown error"
                raise FreqtradeRestError(f"Freqtrade REST {method} {path} 返回 {exc.code}: {detail}") from exc
            except error.URLError as exc:
                last_exception = exc
                if attempt < self._config.max_retries - 1:
                    delay = self._config.base_delay * (2 ** attempt)
                    if elapsed + delay > self._config.max_total_timeout_seconds:
                        break
                    time.sleep(delay)
                continue
            except (TimeoutError, OSError) as exc:
                last_exception = exc
                if attempt < self._config.max_retries - 1:
                    delay = self._config.base_delay * (2 ** attempt)
                    if elapsed + delay > self._config.max_total_timeout_seconds:
                        break
                    time.sleep(delay)
                continue
            except json.JSONDecodeError as exc:
                raise FreqtradeRestError(f"Freqtrade REST {method} {path} 返回的不是 JSON") from exc

        if isinstance(last_exception, error.HTTPError):
            error_body = last_exception.read().decode("utf-8", errors="replace").strip()
            detail = error_body or last_exception.reason or "unknown error"
            raise FreqtradeRestError(f"Freqtrade REST {method} {path} 返回 {last_exception.code}: {detail}") from last_exception
        elif isinstance(last_exception, error.URLError):
            reason = getattr(last_exception, "reason", last_exception)
            raise FreqtradeRestError(f"无法连接 Freqtrade REST {path}: {reason}") from last_exception
        else:
            raise FreqtradeRestError(f"Freqtrade REST {method} {path} 请求失败") from last_exception

    def _ensure_access_token(self) -> str:
        """获取或刷新访问令牌，带重试和指数退避。"""

        if self._access_token:
            return self._access_token
        login_url = f"{self._config.base_url}/api/v1/token/login"
        credentials = f"{self._config.username}:{self._config.password}".encode("utf-8")
        headers = {
            "Authorization": "Basic " + base64.b64encode(credentials).decode("ascii"),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        login_request = request.Request(login_url, data=b"{}", method="POST", headers=headers)

        last_exception: Exception | None = None

        for attempt in range(self._config.max_retries):
            try:
                with self._opener.open(login_request, timeout=self._config.timeout_seconds) as response:
                    payload = response.read().decode("utf-8").strip()
                    data = json.loads(payload) if payload else {}
                    token = data.get("access_token") or data.get("token")
                    if not token:
                        raise FreqtradeRestError("Freqtrade REST 登录响应缺少 access_token")
                    self._access_token = str(token)
                    return self._access_token
            except error.HTTPError as exc:
                if exc.code == 401:
                    error_body = exc.read().decode("utf-8", errors="replace").strip()
                    detail = error_body or exc.reason or "unknown error"
                    raise FreqtradeRestError(f"Freqtrade REST POST /api/v1/token/login 返回 {exc.code}: {detail}") from exc
                if exc.code >= 500:
                    last_exception = exc
                    if attempt < self._config.max_retries - 1:
                        delay = self._config.base_delay * (2 ** attempt)
                        time.sleep(delay)
                    continue
                error_body = exc.read().decode("utf-8", errors="replace").strip()
                detail = error_body or exc.reason or "unknown error"
                raise FreqtradeRestError(f"Freqtrade REST POST /api/v1/token/login 返回 {exc.code}: {detail}") from exc
            except error.URLError as exc:
                last_exception = exc
                if attempt < self._config.max_retries - 1:
                    delay = self._config.base_delay * (2 ** attempt)
                    time.sleep(delay)
                continue
            except (TimeoutError, OSError) as exc:
                last_exception = exc
                if attempt < self._config.max_retries - 1:
                    delay = self._config.base_delay * (2 ** attempt)
                    time.sleep(delay)
                continue
            except json.JSONDecodeError as exc:
                raise FreqtradeRestError("Freqtrade REST POST /api/v1/token/login 返回的不是 JSON") from exc

        if isinstance(last_exception, error.HTTPError):
            error_body = last_exception.read().decode("utf-8", errors="replace").strip()
            detail = error_body or last_exception.reason or "unknown error"
            raise FreqtradeRestError(f"Freqtrade REST POST /api/v1/token/login 返回 {last_exception.code}: {detail}") from last_exception
        elif isinstance(last_exception, error.URLError):
            reason = getattr(last_exception, "reason", last_exception)
            raise FreqtradeRestError(f"无法连接 Freqtrade REST /api/v1/token/login: {reason}") from last_exception
        else:
            raise FreqtradeRestError("Freqtrade REST POST /api/v1/token/login 请求失败") from last_exception

    def _push_trade_notification(
        self,
        signal_type: str,
        symbol: str,
        side: str,
        trade: dict[str, object] | None,
        response: dict[str, object],
    ) -> None:
        """交易成功后推送飞书通知。"""
        try:
            from services.api.app.services.feishu_push_service import send_feishu_trade_signal

            # 提取交易信息
            price = None
            quantity = None
            profit = None
            reason = None

            if trade:
                price = float(trade.get("open_rate") or trade.get("close_rate") or 0)
                quantity = float(trade.get("amount") or 0)
                if signal_type == "sell":
                    profit = float(trade.get("profit_abs") or trade.get("close_profit_abs") or 0)
                    reason = str(trade.get("exit_reason") or "手动平仓")

            if not price and response:
                price = float(response.get("price") or response.get("average") or 0)

            # 发送推送
            send_feishu_trade_signal(
                signal_type=signal_type,
                symbol=symbol,
                price=price or 0.0,
                quantity=quantity or 0.0,
                profit=profit,
                reason=reason,
                strategy="EnhancedStrategy",
            )
            logger.info("交易推送已发送: %s %s", signal_type, symbol)
        except Exception as exc:
            logger.warning("交易推送失败: %s", exc)

"""Freqtrade REST 客户端。

这个文件负责和真实的 Freqtrade REST API 通信，并把 HTTP 细节收敛成统一的控制平面接口。
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib import error, parse, request

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


@dataclass(frozen=True)
class FreqtradeRestConfig:
    """Freqtrade REST 连接配置。"""

    base_url: str
    username: str
    password: str
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        normalized_url = self.base_url.strip().rstrip("/")
        if not normalized_url:
            raise ValueError("base_url must not be empty")
        if not normalized_url.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0")
        object.__setattr__(self, "base_url", normalized_url)


class FreqtradeRestError(RuntimeError):
    """Freqtrade REST 请求失败。"""


class FreqtradeRestClient:
    """面向 Freqtrade REST API 的最小客户端。"""

    def __init__(self, config: FreqtradeRestConfig) -> None:
        self._config = config
        self._access_token: str | None = None
        self._next_order_id = 1

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
            self._request_json("POST", "/api/v1/forceexit", auth=True)
        else:
            params = parse.urlencode(
                {
                    "pair": symbol,
                    "side": side,
                    "stake_amount": str(quantity),
                    "order_type": "market",
                    "enter_tag": "quant-control-plane",
                }
            )
            self._request_json("POST", f"/api/v1/forceenter?{params}", auth=True)

        order_id = f"ft-rest-order-{self._next_order_id}"
        self._next_order_id += 1
        timestamp = utc_now().isoformat()
        return {
            "id": order_id,
            "venueOrderId": order_id,
            "runtimeMode": self._get_remote_mode(default="unknown"),
            "symbol": symbol,
            "side": side if side != "flat" else "flat",
            "orderType": "market",
            "status": "filled",
            "quantity": f"{quantity:.10f}",
            "executedQty": f"{quantity:.10f}",
            "avgPrice": "86000.0000000000",
            "sourceSignalId": action["source_signal_id"],
            "strategyId": action.get("strategy_id"),
            "updatedAt": timestamp,
        }

    def get_snapshot(self) -> Any:
        """读取余额、持仓、订单和策略列表。"""

        from services.api.app.adapters.freqtrade.client import FreqtradeSnapshot

        return FreqtradeSnapshot(
            balances=self._get_balances(),
            positions=self._get_positions(),
            orders=self._get_orders(),
            strategies=self._get_strategies(),
        )

    def get_runtime_snapshot(self) -> dict[str, object]:
        """返回执行器运行视图。"""

        remote_mode = "unknown"
        connection_status = "error"
        try:
            remote_mode = self._get_remote_mode()
            connection_status = "connected" if remote_mode != "unknown" else "configured"
        except FreqtradeRestError:
            connection_status = "error"
        return {
            "executor": "freqtrade",
            "backend": "rest",
            "mode": remote_mode,
            "connection_status": connection_status,
            "base_url": self._config.base_url,
        }

    def _get_balances(self) -> list[dict[str, object]]:
        """读取账户余额列表。"""

        payload = self._request_json("GET", "/api/v1/balance", auth=True)
        items = _payload_items(payload, "balances")
        return [dict(item) for item in items]

    def _get_positions(self) -> list[dict[str, object]]:
        """读取当前持仓列表。"""

        payload = self._request_json("GET", "/api/v1/status", auth=True)
        items = _payload_items(payload, "status")
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
                    "runtimeMode": self._get_remote_mode(default="unknown"),
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
        return orders

    def _get_remote_mode(self, default: str | None = None) -> str:
        """读取远端 Freqtrade 实际运行模式。"""

        try:
            payload = self._request_json("GET", "/api/v1/show_config", auth=True)
        except FreqtradeRestError:
            if default is not None:
                return default
            raise

        candidates = [payload]
        if isinstance(payload.get("data"), dict):
            candidates.append(payload["data"])
        if isinstance(payload.get("config"), dict):
            candidates.append(payload["config"])

        for item in candidates:
            dry_run = item.get("dry_run")
            if isinstance(dry_run, bool):
                return "dry-run" if dry_run else "live"
        return default or "unknown"

    def _get_strategies(self) -> list[dict[str, object]]:
        """读取策略列表。"""

        payload = self._request_json("GET", "/api/v1/strategies", auth=True)
        items = _payload_items(payload, "strategies")
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

    def _request_json(self, method: str, path: str, auth: bool) -> dict[str, object]:
        """执行一次 JSON 请求并处理错误。"""

        url = self._config.base_url + path
        headers = {"Accept": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {self._ensure_access_token()}"
        body = None
        if method in {"POST", "PUT", "PATCH"} and "?" not in path:
            body = b"{}"
            headers["Content-Type"] = "application/json"
        elif method in {"POST", "PUT", "PATCH"} and "?" in path:
            headers["Content-Type"] = "application/json"
        if not auth and path == "/api/v1/token/login":
            raise FreqtradeRestError("token login must use auth=True")

        token_request = request.Request(url, data=body, method=method, headers=headers)
        try:
            with request.urlopen(token_request, timeout=self._config.timeout_seconds) as response:
                payload = response.read().decode("utf-8").strip()
                if not payload:
                    return {}
                loaded = json.loads(payload)
                return loaded if isinstance(loaded, dict) else {"data": loaded}
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace").strip()
            detail = error_body or exc.reason or "unknown error"
            raise FreqtradeRestError(f"Freqtrade REST {method} {path} 返回 {exc.code}: {detail}") from exc
        except error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise FreqtradeRestError(f"无法连接 Freqtrade REST {path}: {reason}") from exc
        except json.JSONDecodeError as exc:
            raise FreqtradeRestError(f"Freqtrade REST {method} {path} 返回的不是 JSON") from exc

    def _ensure_access_token(self) -> str:
        """获取或刷新访问令牌。"""

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
        try:
            with request.urlopen(login_request, timeout=self._config.timeout_seconds) as response:
                payload = response.read().decode("utf-8").strip()
                data = json.loads(payload) if payload else {}
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace").strip()
            detail = error_body or exc.reason or "unknown error"
            raise FreqtradeRestError(f"Freqtrade REST POST /api/v1/token/login 返回 {exc.code}: {detail}") from exc
        except error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise FreqtradeRestError(f"无法连接 Freqtrade REST /api/v1/token/login: {reason}") from exc
        except json.JSONDecodeError as exc:
            raise FreqtradeRestError("Freqtrade REST POST /api/v1/token/login 返回的不是 JSON") from exc

        token = data.get("access_token") or data.get("token")
        if not token:
            raise FreqtradeRestError("Freqtrade REST 登录响应缺少 access_token")
        self._access_token = str(token)
        return self._access_token

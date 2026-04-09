"""Sync service that treats Freqtrade adapter state as the source of truth."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from services.api.app.core.settings import Settings
from services.api.app.services.account_sync_service import account_sync_service
from services.api.app.adapters.freqtrade.client import freqtrade_client


class SyncService:
    """Returns the latest adapter snapshot without maintaining a second truth source."""

    def sync_execution_state(self) -> dict[str, object]:
        return freqtrade_client.get_snapshot().to_dict()

    def sync_task_state(
        self,
        limit: int = 100,
        expected_symbol: str = "",
        expected_side: str = "",
        expected_order_id: str = "",
        expected_updated_at: str = "",
        expected_quantity: str = "",
    ) -> dict[str, object]:
        """为任务系统返回一次同步结果。"""

        settings = Settings.from_env()
        if settings.runtime_mode != "live":
            return self.sync_execution_state()
        order_symbols = self._resolve_live_order_symbols(settings=settings, expected_symbol=expected_symbol)
        result = {
            "balances": account_sync_service.list_balances(limit=limit),
            "orders": account_sync_service.list_orders(limit=limit, symbols=order_symbols),
            "positions": account_sync_service.list_positions(limit=limit),
            "strategies": [],
            "source": "binance-account-sync",
            "truth_source": "binance",
        }
        if expected_symbol or expected_order_id:
            confirmation = self._confirm_live_dispatch_sync(
                orders=list(result["orders"]),
                expected_symbol=expected_symbol,
                expected_side=expected_side,
                expected_order_id=expected_order_id,
                expected_updated_at=expected_updated_at,
                expected_quantity=expected_quantity,
            )
            result["confirmation"] = confirmation
            if not confirmation["matched"]:
                raise RuntimeError(str(confirmation["message"]))
        return result

    def get_runtime_snapshot(self) -> dict[str, object]:
        """返回执行器当前运行快照。"""

        snapshot = self.sync_execution_state()
        runtime = dict(freqtrade_client.get_runtime_snapshot())
        runtime.update(
            {
                "strategy_count": len(list(snapshot.get("strategies", []))),
                "order_count": len(list(snapshot.get("orders", []))),
                "position_count": len(list(snapshot.get("positions", []))),
            }
        )
        return runtime

    def list_orders(self, limit: int = 100) -> list[dict[str, object]]:
        snapshot = self.sync_execution_state()
        return list(snapshot["orders"])[:limit]

    def list_positions(self, limit: int = 100) -> list[dict[str, object]]:
        snapshot = self.sync_execution_state()
        return list(snapshot["positions"])[:limit]

    def list_strategies(self, limit: int = 50) -> list[dict[str, object]]:
        snapshot = self.sync_execution_state()
        return list(snapshot["strategies"])[:limit]

    def get_strategy(self, strategy_id: int) -> dict[str, object] | None:
        strategies = self.list_strategies(limit=200)
        for strategy in strategies:
            if strategy["id"] == strategy_id:
                return strategy
        return None

    @staticmethod
    def build_live_sync_payload(dispatch_result: dict[str, object]) -> dict[str, object]:
        """从派发结果里提取 live 同步确认所需字段。"""

        action = dict(dispatch_result.get("action") or {})
        order = dict(dispatch_result.get("order") or {})
        quantity = order.get("executedQty") or order.get("quantity") or action.get("quantity") or ""
        return {
            "expected_symbol": str(order.get("symbol") or action.get("symbol") or ""),
            "expected_side": str(action.get("side") or order.get("side") or ""),
            "expected_order_id": str(order.get("venueOrderId") or order.get("id") or ""),
            "expected_updated_at": str(order.get("updatedAt") or ""),
            "expected_quantity": str(quantity or ""),
            "source_signal_id": action.get("source_signal_id"),
        }

    def get_execution_health_summary(
        self,
        *,
        task_health: dict[str, object] | None = None,
        automation_state: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """返回执行链当前健康状态，给复盘和页面统一复用。"""

        runtime = self.get_runtime_snapshot()
        health = dict(task_health or {})
        latest_status = dict(health.get("latest_status_by_type") or {})
        latest_success = dict(health.get("latest_success_by_type") or {})
        latest_failure = dict(health.get("latest_failure_by_type") or {})
        latest_sync_status = str(latest_status.get("sync", "unknown"))
        latest_review_status = str(latest_status.get("review", "unknown"))
        latest_failed_sync = dict(latest_failure.get("sync") or {})
        account_shape = self._build_account_shape(runtime=runtime)
        execution_state = self._build_execution_state(runtime=runtime, automation_state=dict(automation_state or {}))
        return {
            "runtime_mode": str(runtime.get("mode", "")),
            "backend": str(runtime.get("backend", "")),
            "connection_status": str(runtime.get("connection_status", "")),
            "latest_sync_status": latest_sync_status,
            "latest_review_status": latest_review_status,
            "latest_successful_sync_at": str(latest_success.get("sync", "")),
            "latest_successful_review_at": str(latest_success.get("review", "")),
            "latest_failed_sync": latest_failed_sync,
            "sync_stale": latest_sync_status not in {"succeeded", "retrying"},
            "order_count": int(runtime.get("order_count", 0) or 0),
            "position_count": int(runtime.get("position_count", 0) or 0),
            "execution_state": execution_state,
            "retry_allowed": latest_sync_status in {"failed", "retrying"},
            "reconnect_required": str(runtime.get("backend", "")) == "rest"
            and str(runtime.get("connection_status", "")) not in {"connected", "not_configured"},
            "latest_error_message": str(
                latest_failed_sync.get("error_message")
                or latest_failed_sync.get("detail")
                or ""
            ),
            "recovery_action": self._resolve_recovery_action(
                execution_state=execution_state,
                latest_sync_status=latest_sync_status,
                runtime=runtime,
                account_shape=account_shape,
            ),
            **account_shape,
        }

    def _build_account_shape(self, *, runtime: dict[str, object]) -> dict[str, object]:
        """整理执行层账户状态，区分持仓、待平仓和零头。"""

        runtime_mode = str(runtime.get("mode", ""))
        if runtime_mode == "live":
            balances = account_sync_service.list_balances(limit=100)
            orders = account_sync_service.list_orders(limit=100)
            positions = account_sync_service.list_positions(limit=100)
        else:
            balances = []
            orders = self.list_orders(limit=100)
            positions = self.list_positions(limit=100)
        return {
            "dust_balance_count": sum(1 for item in balances if str(item.get("tradeStatus", "")).lower() == "dust"),
            "pending_exit_count": sum(1 for item in orders if str(item.get("lifecycle", "")).lower() == "pending_exit"),
            "open_position_count": sum(1 for item in positions if str(item.get("positionStatus", "open")).lower() == "open"),
        }

    @staticmethod
    def _build_execution_state(*, runtime: dict[str, object], automation_state: dict[str, object]) -> dict[str, object]:
        """把当前执行链压成固定状态机。"""

        if bool(automation_state.get("manual_takeover")):
            return {
                "state": "takeover",
                "detail": "当前处于人工接管状态，自动化不会继续推进",
                "allowed_transitions": ["manual", "dry-run", "live"],
            }
        if bool(automation_state.get("paused")):
            return {
                "state": "paused",
                "detail": "当前执行链已暂停，等待人工恢复",
                "allowed_transitions": ["manual", "dry-run", "live"],
            }
        runtime_mode = str(runtime.get("mode", ""))
        if runtime_mode == "live":
            return {
                "state": "live",
                "detail": "当前执行链正在小额 live 模式下运行",
                "allowed_transitions": ["paused", "takeover", "dry-run"],
            }
        if runtime_mode == "dry-run":
            return {
                "state": "dry-run",
                "detail": "当前执行链正在 dry-run 模式下运行",
                "allowed_transitions": ["live", "paused", "takeover"],
            }
        return {
            "state": "manual",
            "detail": "当前仍是手动或演示模式",
            "allowed_transitions": ["dry-run", "paused"],
        }

    @staticmethod
    def _resolve_recovery_action(
        *,
        execution_state: dict[str, object],
        latest_sync_status: str,
        runtime: dict[str, object],
        account_shape: dict[str, object],
    ) -> str:
        """给执行异常统一输出恢复方向。"""

        state = str(execution_state.get("state", ""))
        if state == "paused":
            return "resume_after_review"
        if state == "takeover":
            return "manual_takeover"
        if str(runtime.get("backend", "")) == "rest" and str(runtime.get("connection_status", "")) not in {"connected", "not_configured"}:
            return "reconnect_executor"
        if latest_sync_status in {"failed", "retrying"}:
            return "retry_sync"
        if int(account_shape.get("pending_exit_count", 0) or 0) > 0:
            return "watch_pending_exit"
        if int(account_shape.get("dust_balance_count", 0) or 0) > 0:
            return "review_dust"
        return "healthy"

    def _confirm_live_dispatch_sync(
        self,
        orders: list[dict[str, object]],
        expected_symbol: str,
        expected_side: str,
        expected_order_id: str,
        expected_updated_at: str,
        expected_quantity: str,
    ) -> dict[str, object]:
        """确认同步结果里确实出现了刚刚派发的那一笔订单。"""

        normalized_symbol = self._compact_symbol(expected_symbol)
        normalized_side = self._normalize_order_side(expected_side)
        expected_order_id = str(expected_order_id).strip()
        expected_timestamp = self._parse_iso_timestamp(expected_updated_at)
        filtered_orders = [
            order
            for order in orders
            if self._compact_symbol(str(order.get("symbol", ""))) == normalized_symbol
            and self._normalize_order_side(str(order.get("side", ""))) == normalized_side
        ]

        for order in filtered_orders:
            order_id = str(order.get("id") or order.get("venueOrderId") or "").strip()
            if expected_order_id and order_id == expected_order_id:
                return {
                    "matched": True,
                    "match_type": "order_id",
                    "message": f"已确认同步到订单 {expected_order_id}",
                }

        if expected_order_id:
            expected_target = expected_order_id or normalized_symbol
            return {
                "matched": False,
                "match_type": "none",
                "message": f"live 同步未确认到刚派发的订单 {expected_target}",
            }

        if expected_timestamp is not None:
            for order in filtered_orders:
                order_timestamp = self._extract_order_timestamp(order)
                if order_timestamp is None or order_timestamp < expected_timestamp - 30:
                    continue
                if expected_quantity and not self._quantity_matches(order, expected_quantity):
                    continue
                return {
                    "matched": True,
                    "match_type": "symbol+side+time",
                    "message": f"已通过时间窗口确认同步到 {normalized_symbol}",
                }

        expected_target = expected_order_id or normalized_symbol
        return {
            "matched": False,
            "match_type": "none",
            "message": f"live 同步未确认到刚派发的订单 {expected_target}",
        }

    def _resolve_live_order_symbols(self, settings: Settings, expected_symbol: str) -> tuple[str, ...]:
        """收敛 live 订单同步范围，并把本次派发的 symbol 一并加入。"""

        normalized_symbols = {
            item.strip().upper()
            for item in settings.account_sync_order_symbols
            if item.strip()
        }
        expected_compact_symbol = self._compact_symbol(expected_symbol)
        if expected_compact_symbol:
            normalized_symbols.add(expected_compact_symbol)
        return tuple(sorted(normalized_symbols))

    @staticmethod
    def _compact_symbol(symbol: str) -> str:
        """统一交易对格式，便于不同来源对齐。"""

        return symbol.strip().upper().replace("/", "")

    @staticmethod
    def _normalize_order_side(side: str) -> str:
        """统一订单方向，long/flat 映射到 buy/sell。"""

        normalized = side.strip().lower()
        if normalized in {"long", "buy", "entry"}:
            return "buy"
        if normalized in {"flat", "sell", "exit"}:
            return "sell"
        return normalized

    @staticmethod
    def _parse_iso_timestamp(value: str) -> float | None:
        """解析 ISO 时间，失败时返回空。"""

        raw = value.strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw).astimezone(timezone.utc).timestamp()
        except ValueError:
            return None

    @staticmethod
    def _extract_order_timestamp(order: dict[str, object]) -> float | None:
        """从 Binance 订单字段里提取时间戳。"""

        for key in ("updateTime", "time", "transactTime"):
            value = order.get(key)
            if value in (None, ""):
                continue
            try:
                return Decimal(str(value)).scaleb(-3)
            except Exception:
                continue
        return None

    @staticmethod
    def _quantity_matches(order: dict[str, object], expected_quantity: str) -> bool:
        """比较订单数量是否与派发结果一致。"""

        try:
            expected = Decimal(str(expected_quantity))
        except Exception:
            return False
        for key in ("executedQty", "quantity", "origQty"):
            value = order.get(key)
            if value in (None, ""):
                continue
            try:
                actual = Decimal(str(value))
            except Exception:
                continue
            if abs(actual - expected) <= Decimal("0.00000001"):
                return True
        return False


sync_service = SyncService()

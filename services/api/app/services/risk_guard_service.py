"""风控熔断服务。

这个文件负责实现风控熔断机制，包括每日亏损限制、交易频率限制和市场异常检测。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from typing import Callable

from services.api.app.adapters.binance.market_client import BinanceMarketClient
from services.api.app.adapters.freqtrade.client import freqtrade_client
from services.api.app.core.settings import Settings
from services.api.app.services.sync_service import sync_service


@dataclass(slots=True)
class RiskGuardCheckResult:
    """风控检查结果。"""

    passed: bool
    rule_name: str
    level: str
    reason: str
    current_value: Decimal | None = None
    threshold: Decimal | None = None
    evaluated_at: datetime | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "rule_name": self.rule_name,
            "level": self.level,
            "reason": self.reason,
            "current_value": str(self.current_value) if self.current_value is not None else None,
            "threshold": str(self.threshold) if self.threshold is not None else None,
            "evaluated_at": self.evaluated_at.isoformat() if self.evaluated_at else None,
        }


@dataclass(slots=True)
class CircuitBreakerState:
    """熔断状态记录。"""

    triggered: bool = False
    triggered_at: datetime | None = None
    trigger_reason: str = ""
    positions_closed: bool = False
    trading_paused: bool = False
    resolved_at: datetime | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "triggered": self.triggered,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "trigger_reason": self.trigger_reason,
            "positions_closed": self.positions_closed,
            "trading_paused": self.trading_paused,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass(frozen=True)
class RiskGuardConfig:
    """风控熔断配置。"""

    daily_max_loss_pct: Decimal = Decimal("3")
    max_trades_per_day: int = 5
    crash_threshold_pct: Decimal = Decimal("5")
    crash_lookback_hours: int = 1

    @classmethod
    def from_env(cls) -> "RiskGuardConfig":
        """从环境变量读取风控配置。"""

        raw_daily_max_loss = os.getenv("QUANT_RISK_DAILY_MAX_LOSS_PCT", "3").strip()
        try:
            daily_max_loss_pct = Decimal(raw_daily_max_loss)
        except InvalidOperation:
            daily_max_loss_pct = Decimal("3")
        if daily_max_loss_pct <= 0:
            daily_max_loss_pct = Decimal("3")

        raw_max_trades = os.getenv("QUANT_RISK_MAX_TRADES_PER_DAY", "5").strip()
        try:
            max_trades_per_day = int(raw_max_trades)
        except ValueError:
            max_trades_per_day = 5
        if max_trades_per_day <= 0:
            max_trades_per_day = 5

        raw_crash_threshold = os.getenv("QUANT_RISK_CRASH_THRESHOLD_PCT", "5").strip()
        try:
            crash_threshold_pct = Decimal(raw_crash_threshold)
        except InvalidOperation:
            crash_threshold_pct = Decimal("5")
        if crash_threshold_pct <= 0:
            crash_threshold_pct = Decimal("5")

        return cls(
            daily_max_loss_pct=daily_max_loss_pct,
            max_trades_per_day=max_trades_per_day,
            crash_threshold_pct=crash_threshold_pct,
        )


class RiskGuardService:
    """风控熔断服务，防止异常情况下连续亏损。"""

    def __init__(
        self,
        config: RiskGuardConfig | None = None,
        market_client: BinanceMarketClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._config = config or RiskGuardConfig.from_env()
        self._market_client = market_client or BinanceMarketClient()
        self._settings = settings or Settings.from_env()
        self._circuit_breaker = CircuitBreakerState()
        self._daily_trade_count: dict[str, int] = {}  # date -> count
        self._daily_pnl: dict[str, Decimal] = {}  # date -> pnl

    def check_all(self, strategy_id: int | None = None) -> dict[str, object]:
        """执行全部风控检查，返回综合结果。"""

        if self._circuit_breaker.triggered:
            return {
                "passed": False,
                "blocked": True,
                "circuit_breaker_active": True,
                "checks": [],
                "summary": "熔断已触发，交易已暂停",
                "circuit_breaker_state": self._circuit_breaker.to_dict(),
            }

        checks: list[dict[str, object]] = []
        any_blocked = False
        block_reasons: list[str] = []

        daily_loss_result = self.check_daily_loss_limit()
        checks.append(daily_loss_result.to_dict())
        if not daily_loss_result.passed:
            any_blocked = True
            block_reasons.append(daily_loss_result.reason)

        trade_freq_result = self.check_trade_frequency()
        checks.append(trade_freq_result.to_dict())
        if not trade_freq_result.passed:
            any_blocked = True
            block_reasons.append(trade_freq_result.reason)

        market_crash_result = self.check_market_crash()
        checks.append(market_crash_result.to_dict())
        if not market_crash_result.passed:
            any_blocked = True
            block_reasons.append(market_crash_result.reason)

        summary = "风控检查通过" if not any_blocked else f"风控检查未通过: {'; '.join(block_reasons)}"

        return {
            "passed": not any_blocked,
            "blocked": any_blocked,
            "circuit_breaker_active": False,
            "checks": checks,
            "summary": summary,
            "circuit_breaker_state": self._circuit_breaker.to_dict(),
        }

    def check_daily_loss_limit(self) -> RiskGuardCheckResult:
        """检查当日累计亏损是否超限。"""

        now = datetime.now(timezone.utc)
        today_key = now.strftime("%Y-%m-%d")
        evaluated_at = now

        daily_pnl = self._calculate_daily_pnl(today_key)
        threshold = self._config.daily_max_loss_pct

        if daily_pnl < Decimal("0"):
            loss_pct = daily_pnl.copy_abs()
            if loss_pct > threshold:
                return RiskGuardCheckResult(
                    passed=False,
                    rule_name="daily_loss_limit",
                    level="critical",
                    reason=f"当日累计亏损 {loss_pct:.2f}% 超过限制 {threshold:.2f}%",
                    current_value=loss_pct,
                    threshold=threshold,
                    evaluated_at=evaluated_at,
                )

        return RiskGuardCheckResult(
            passed=True,
            rule_name="daily_loss_limit",
            level="low",
            reason=f"当日累计亏损未超限，当前 {daily_pnl:.2f}%",
            current_value=daily_pnl.copy_abs() if daily_pnl < Decimal("0") else Decimal("0"),
            threshold=threshold,
            evaluated_at=evaluated_at,
        )

    def check_trade_frequency(self) -> RiskGuardCheckResult:
        """检查当日交易次数是否超限。"""

        now = datetime.now(timezone.utc)
        today_key = now.strftime("%Y-%m-%d")
        evaluated_at = now

        trade_count = self._get_daily_trade_count(today_key)
        threshold = self._config.max_trades_per_day

        if trade_count >= threshold:
            return RiskGuardCheckResult(
                passed=False,
                rule_name="trade_frequency_limit",
                level="high",
                reason=f"当日交易次数 {trade_count} 已达到上限 {threshold}",
                current_value=Decimal(trade_count),
                threshold=Decimal(threshold),
                evaluated_at=evaluated_at,
            )

        return RiskGuardCheckResult(
            passed=True,
            rule_name="trade_frequency_limit",
            level="low",
            reason=f"当日交易次数未超限，当前 {trade_count}/{threshold}",
            current_value=Decimal(trade_count),
            threshold=Decimal(threshold),
            evaluated_at=evaluated_at,
        )

    def check_market_crash(self) -> RiskGuardCheckResult:
        """检查市场是否异常（1小时跌幅超阈值）。"""

        now = datetime.now(timezone.utc)
        evaluated_at = now
        threshold = self._config.crash_threshold_pct

        try:
            crash_detected, max_drop_pct, affected_symbols = self._detect_market_crash()
        except Exception:
            # 市场数据获取失败时，不阻塞交易
            return RiskGuardCheckResult(
                passed=True,
                rule_name="market_crash_guard",
                level="low",
                reason="市场数据暂时不可用，跳过异常检测",
                current_value=None,
                threshold=threshold,
                evaluated_at=evaluated_at,
            )

        if crash_detected:
            symbols_str = ", ".join(affected_symbols[:3]) if affected_symbols else "未知"
            return RiskGuardCheckResult(
                passed=False,
                rule_name="market_crash_guard",
                level="critical",
                reason=f"检测到市场异常，{symbols_str} 等币种1小时跌幅超过 {threshold:.2f}%，最大跌幅 {max_drop_pct:.2f}%",
                current_value=max_drop_pct,
                threshold=threshold,
                evaluated_at=evaluated_at,
            )

        return RiskGuardCheckResult(
            passed=True,
            rule_name="market_crash_guard",
            level="low",
            reason=f"市场运行正常，最大1小时跌幅 {max_drop_pct:.2f}% 未超过阈值 {threshold:.2f}%",
            current_value=max_drop_pct,
            threshold=threshold,
            evaluated_at=evaluated_at,
        )

    def trigger_circuit_breaker(
        self,
        reason: str,
        close_positions: bool = True,
        pause_trading: bool = True,
    ) -> dict[str, object]:
        """触发熔断，平仓并停止交易。"""

        now = datetime.now(timezone.utc)

        if self._circuit_breaker.triggered:
            return {
                "status": "already_triggered",
                "message": "熔断已处于触发状态",
                "circuit_breaker_state": self._circuit_breaker.to_dict(),
            }

        self._circuit_breaker.triggered = True
        self._circuit_breaker.triggered_at = now
        self._circuit_breaker.trigger_reason = reason

        closed_positions: list[dict[str, object]] = []
        close_errors: list[str] = []

        if close_positions:
            try:
                closed_positions, close_errors = self._close_all_positions()
                self._circuit_breaker.positions_closed = len(close_errors) == 0
            except Exception as exc:
                close_errors.append(str(exc))
                self._circuit_breaker.positions_closed = False

        if pause_trading:
            try:
                self._pause_trading()
                self._circuit_breaker.trading_paused = True
            except Exception:
                self._circuit_breaker.trading_paused = False

        return {
            "status": "triggered",
            "message": f"熔断已触发: {reason}",
            "positions_closed": closed_positions,
            "close_errors": close_errors,
            "circuit_breaker_state": self._circuit_breaker.to_dict(),
        }

    def reset_circuit_breaker(self) -> dict[str, object]:
        """重置熔断状态，恢复交易。"""

        if not self._circuit_breaker.triggered:
            return {
                "status": "not_triggered",
                "message": "熔断未处于触发状态",
                "circuit_breaker_state": self._circuit_breaker.to_dict(),
            }

        now = datetime.now(timezone.utc)
        self._circuit_breaker.resolved_at = now

        # 重置状态
        self._circuit_breaker = CircuitBreakerState()

        # 重置当日计数
        today_key = now.strftime("%Y-%m-%d")
        self._daily_trade_count[today_key] = 0
        self._daily_pnl[today_key] = Decimal("0")

        return {
            "status": "reset",
            "message": "熔断已重置，交易已恢复",
            "circuit_breaker_state": self._circuit_breaker.to_dict(),
        }

    def get_circuit_breaker_state(self) -> dict[str, object]:
        """获取当前熔断状态。"""

        return self._circuit_breaker.to_dict()

    def increment_trade_count(self) -> None:
        """记录一次交易，增加当日计数。"""

        now = datetime.now(timezone.utc)
        today_key = now.strftime("%Y-%m-%d")
        current = self._daily_trade_count.get(today_key, 0)
        self._daily_trade_count[today_key] = current + 1

    def record_pnl(self, pnl: Decimal) -> None:
        """记录一笔交易的盈亏。"""

        now = datetime.now(timezone.utc)
        today_key = now.strftime("%Y-%m-%d")
        current = self._daily_pnl.get(today_key, Decimal("0"))
        self._daily_pnl[today_key] = current + pnl

    def _calculate_daily_pnl(self, today_key: str) -> Decimal:
        """计算当日累计盈亏百分比。"""

        # 从内存记录中获取
        recorded_pnl = self._daily_pnl.get(today_key, Decimal("0"))
        if recorded_pnl != Decimal("0"):
            return recorded_pnl

        # 尝试从 Freqtrade 快照中计算
        try:
            snapshot = freqtrade_client.get_snapshot()
            orders = list(snapshot.orders)
            positions = list(snapshot.positions)
        except Exception:
            return Decimal("0")

        # 计算已实现盈亏
        total_pnl = Decimal("0")
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        for order in orders:
            try:
                updated_at_str = str(order.get("updatedAt") or "")
                if not updated_at_str:
                    continue
                updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                if updated_at < today_start:
                    continue

                pnl_str = order.get("unrealizedPnl") or order.get("profit_abs") or "0"
                pnl = Decimal(str(pnl_str))
                total_pnl += pnl
            except Exception:
                continue

        # 加上当前持仓的未实现盈亏
        for position in positions:
            try:
                pnl_str = position.get("unrealizedPnl") or "0"
                pnl = Decimal(str(pnl_str))
                total_pnl += pnl
            except Exception:
                continue

        # 转换为百分比（假设基础资金为 10000 USDT）
        base_capital = Decimal("10000")
        pnl_pct = (total_pnl / base_capital) * Decimal("100")
        self._daily_pnl[today_key] = pnl_pct

        return pnl_pct

    def _get_daily_trade_count(self, today_key: str) -> int:
        """获取当日交易次数。"""

        recorded_count = self._daily_trade_count.get(today_key, 0)
        if recorded_count > 0:
            return recorded_count

        # 尝试从 Freqtrade 快照中计算
        try:
            snapshot = freqtrade_client.get_snapshot()
            orders = list(snapshot.orders)
        except Exception:
            return recorded_count

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        count = 0

        for order in orders:
            try:
                updated_at_str = str(order.get("updatedAt") or "")
                if not updated_at_str:
                    continue
                updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                if updated_at < today_start:
                    continue
                status = str(order.get("status") or "").lower()
                if status in {"filled", "closed", "complete"}:
                    count += 1
            except Exception:
                continue

        self._daily_trade_count[today_key] = count
        return count

    def _detect_market_crash(self) -> tuple[bool, Decimal, list[str]]:
        """检测市场是否出现异常大跌。"""

        settings = Settings.from_env()
        symbols = settings.market_symbols

        if not symbols:
            return False, Decimal("0"), []

        max_drop_pct = Decimal("0")
        affected_symbols: list[str] = []
        threshold = self._config.crash_threshold_pct

        try:
            tickers = self._market_client.get_tickers(symbols)
        except Exception:
            return False, Decimal("0"), []

        for ticker in tickers:
            try:
                symbol = str(ticker.get("symbol") or "").upper()
                price_change_pct = ticker.get("priceChangePercent")
                if price_change_pct is None:
                    continue

                change_pct = Decimal(str(price_change_pct))
                # 只关注下跌
                if change_pct < Decimal("0"):
                    drop_pct = change_pct.copy_abs()
                    if drop_pct > max_drop_pct:
                        max_drop_pct = drop_pct
                    if drop_pct > threshold:
                        affected_symbols.append(symbol)
            except Exception:
                continue

        crash_detected = len(affected_symbols) > 0
        return crash_detected, max_drop_pct, affected_symbols

    def _close_all_positions(self) -> tuple[list[dict[str, object]], list[str]]:
        """平掉所有持仓。"""

        closed_positions: list[dict[str, object]] = []
        errors: list[str] = []

        try:
            snapshot = freqtrade_client.get_snapshot()
            positions = list(snapshot.positions)
        except Exception as exc:
            errors.append(f"获取持仓失败: {exc}")
            return closed_positions, errors

        for position in positions:
            try:
                symbol = str(position.get("symbol") or "")
                if not symbol:
                    continue

                action = {
                    "action_type": "close_position",
                    "symbol": symbol,
                    "side": "flat",
                    "quantity": position.get("quantity") or "0",
                    "source_signal_id": None,
                    "strategy_id": position.get("strategyId"),
                }

                order = freqtrade_client.submit_execution_action(action)
                closed_positions.append({
                    "symbol": symbol,
                    "order_id": order.get("id"),
                    "status": order.get("status"),
                })
            except Exception as exc:
                errors.append(f"平仓 {position.get('symbol')} 失败: {exc}")

        return closed_positions, errors

    def _pause_trading(self) -> None:
        """暂停交易。"""

        try:
            freqtrade_client.control_strategy(1, "stop")
        except Exception:
            pass


risk_guard_service = RiskGuardService()
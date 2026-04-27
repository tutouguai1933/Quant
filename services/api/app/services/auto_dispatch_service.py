"""研究推荐自动派发服务。

这个文件负责从研究推荐到自动执行的闭环流程：
1. 获取评分最高的推荐候选
2. 检查候选是否通过所有门控
3. 检查风控熔断状态
4. 自动执行forceenter
5. 推送执行结果告警
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from services.api.app.services.alert_push_service import (
    AlertEventType,
    AlertLevel,
    AlertMessage,
    alert_push_service,
)
from services.api.app.services.automation_service import automation_service
from services.api.app.services.research_service import research_service
from services.api.app.services.risk_guard_service import risk_guard_service
from services.api.app.services.risk_service import risk_service
from services.api.app.services.signal_service import signal_service
from services.api.app.services.strategy_dispatch_service import strategy_dispatch_service
from services.api.app.services.sync_service import sync_service

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    """返回当前 UTC 时间字符串。"""
    return datetime.now(timezone.utc).isoformat()


class AutoDispatchConfig:
    """自动派发配置，从环境变量读取。"""

    def __init__(self) -> None:
        self.enabled = self._parse_bool_env("QUANT_AUTO_DISPATCH_ENABLED", default=False)
        self.interval_seconds = self._parse_int_env("QUANT_AUTO_DISPATCH_INTERVAL", default=300)
        self.min_score = self._parse_float_env("QUANT_AUTO_DISPATCH_MIN_SCORE", default=0.7)
        self.max_daily_dispatch_count = self._parse_int_env("QUANT_AUTO_DISPATCH_MAX_DAILY", default=5)
        self.require_dry_run_gate_passed = self._parse_bool_env("QUANT_AUTO_DISPATCH_REQUIRE_DRY_RUN_GATE", default=True)
        self.require_live_gate_passed = self._parse_bool_env("QUANT_AUTO_DISPATCH_REQUIRE_LIVE_GATE", default=False)

    @staticmethod
    def _parse_bool_env(key: str, default: bool) -> bool:
        raw = os.environ.get(key, "")
        if not raw:
            return default
        normalized = raw.strip().lower()
        return normalized in ("true", "1", "yes", "on")

    @staticmethod
    def _parse_int_env(key: str, default: int) -> int:
        raw = os.environ.get(key, "")
        if not raw:
            return default
        try:
            return int(raw.strip())
        except ValueError:
            return default

    @staticmethod
    def _parse_float_env(key: str, default: float) -> float:
        raw = os.environ.get(key, "")
        if not raw:
            return default
        try:
            return float(raw.strip())
        except ValueError:
            return default


class AutoDispatchState:
    """自动派发状态跟踪。"""

    def __init__(self) -> None:
        self._last_dispatch_at: str = ""
        self._daily_dispatch_count: int = 0
        self._daily_summary_date: str = ""
        self._last_dispatched_symbol: str = ""
        self._consecutive_failure_count: int = 0
        self._last_success_at: str = ""
        self._last_failure_at: str = ""
        self._lock = threading.Lock()

    def _ensure_daily_summary(self) -> None:
        """跨天时自动重置日报计数。"""
        current_date = _utc_now()[:10]
        if self._daily_summary_date != current_date:
            self._daily_dispatch_count = 0
            self._daily_summary_date = current_date

    def can_dispatch_today(self, max_count: int) -> bool:
        """检查今天是否还能派发。"""
        self._ensure_daily_summary()
        return self._daily_dispatch_count < max_count

    def record_dispatch(self, success: bool, symbol: str) -> None:
        """记录派发结果。"""
        self._ensure_daily_summary()
        self._last_dispatch_at = _utc_now()
        self._last_dispatched_symbol = symbol.strip().upper()
        if success:
            self._daily_dispatch_count += 1
            self._consecutive_failure_count = 0
            self._last_success_at = _utc_now()
        else:
            self._consecutive_failure_count += 1
            self._last_failure_at = _utc_now()

    def get_state(self) -> dict[str, Any]:
        """返回当前状态。"""
        self._ensure_daily_summary()
        return {
            "last_dispatch_at": self._last_dispatch_at,
            "daily_dispatch_count": self._daily_dispatch_count,
            "daily_summary_date": self._daily_summary_date,
            "last_dispatched_symbol": self._last_dispatched_symbol,
            "consecutive_failure_count": self._consecutive_failure_count,
            "last_success_at": self._last_success_at,
            "last_failure_at": self._last_failure_at,
        }


class AutoDispatchService:
    """研究推荐自动派发服务。"""

    MAX_CONSECUTIVE_FAILURES = 3  # 连续失败3次后暂停自动执行
    MIN_INTERVAL_SECONDS = 60  # 两次派发之间最小间隔

    def __init__(
        self,
        *,
        config: AutoDispatchConfig | None = None,
        state: AutoDispatchState | None = None,
    ) -> None:
        self._config = config or AutoDispatchConfig()
        self._state = state or AutoDispatchState()
        self._lock = threading.Lock()

    def get_config(self) -> dict[str, Any]:
        """返回当前配置。"""
        return {
            "enabled": self._config.enabled,
            "interval_seconds": self._config.interval_seconds,
            "min_score": self._config.min_score,
            "max_daily_dispatch_count": self._config.max_daily_dispatch_count,
            "require_dry_run_gate_passed": self._config.require_dry_run_gate_passed,
            "require_live_gate_passed": self._config.require_live_gate_passed,
        }

    def get_state(self) -> dict[str, Any]:
        """返回当前状态。"""
        return self._state.get_state()

    def get_top_recommendation(self) -> dict[str, Any] | None:
        """获取评分最高的推荐候选。

        Returns:
            推荐候选信息，如果没有候选则返回 None
        """
        try:
            recommendation = research_service.get_research_recommendation()
            if not recommendation:
                logger.info("没有研究推荐候选")
                return None

            # 检查评分是否达到最低阈值
            raw_score = str(recommendation.get("score", "0"))
            try:
                score = float(raw_score)
            except ValueError:
                score = 0.0

            if score < self._config.min_score:
                logger.info(
                    "候选评分 %s 低于最低阈值 %s，跳过自动派发",
                    score,
                    self._config.min_score,
                )
                return None

            return dict(recommendation)
        except Exception as exc:
            logger.warning("获取研究推荐失败: %s", exc)
            return None

    def check_gates_passed(self, recommendation: dict[str, Any]) -> tuple[bool, str]:
        """检查候选是否通过所有门控。

        Args:
            recommendation: 推荐候选信息

        Returns:
            (是否通过, 原因说明)
        """
        symbol = str(recommendation.get("symbol", "")).strip().upper()
        if not symbol:
            return False, "候选缺少交易对信息"

        # 检查是否允许进入 dry-run
        allowed_to_dry_run = bool(recommendation.get("allowed_to_dry_run"))
        if self._config.require_dry_run_gate_passed and not allowed_to_dry_run:
            dry_run_gate = dict(recommendation.get("dry_run_gate") or {})
            reasons = list(dry_run_gate.get("reasons") or [])
            reason_text = "; ".join(reasons) if reasons else "dry_run_gate 未通过"
            return False, f"dry_run_gate 未通过: {reason_text}"

        # 检查是否允许进入 live（可选）
        allowed_to_live = bool(recommendation.get("allowed_to_live"))
        if self._config.require_live_gate_passed and not allowed_to_live:
            live_gate = dict(recommendation.get("live_gate") or {})
            reasons = list(live_gate.get("reasons") or [])
            reason_text = "; ".join(reasons) if reasons else "live_gate 未通过"
            return False, f"live_gate 未通过: {reason_text}"

        # 检查是否被强制验证（强制验证候选通常有特殊处理）
        forced_for_validation = bool(recommendation.get("forced_for_validation"))
        if forced_for_validation:
            forced_reason = str(recommendation.get("forced_reason", "") or "未知原因")
            logger.info("候选 %s 被强制验证，原因: %s", symbol, forced_reason)

        return True, "所有门控检查通过"

    def check_risk_guard(self, strategy_id: int) -> tuple[bool, str, dict[str, Any]]:
        """检查风控熔断状态。

        Args:
            strategy_id: 策略ID

        Returns:
            (是否通过, 原因说明, 检查详情)
        """
        try:
            risk_guard_result = risk_guard_service.check_all(strategy_id=strategy_id)
            passed = bool(risk_guard_result.get("passed"))
            summary = str(risk_guard_result.get("summary") or "")
            checks = list(risk_guard_result.get("checks") or [])

            if not passed:
                logger.warning("风控熔断检查未通过: %s", summary)
                return False, summary, {"checks": checks, "passed": False}

            return True, "风控熔断检查通过", {"checks": checks, "passed": True}
        except Exception as exc:
            logger.warning("风控熔断检查异常: %s", exc)
            return False, f"风控熔断检查异常: {exc}", {"passed": False, "error": str(exc)}

    def check_automation_state(self) -> tuple[bool, str]:
        """检查自动化状态是否允许自动执行。

        Returns:
            (是否允许, 原因说明)
        """
        try:
            state = automation_service.get_state()
            mode = str(state.get("mode", "")).strip().lower()
            paused = bool(state.get("paused"))
            manual_takeover = bool(state.get("manual_takeover"))
            consecutive_failure_count = int(state.get("consecutive_failure_count", 0))

            # 检查全局开关
            if not self._config.enabled:
                return False, "自动派发功能已禁用 (QUANT_AUTO_DISPATCH_ENABLED=false)"

            # 检查是否暂停
            if paused:
                paused_reason = str(state.get("paused_reason", "") or "unknown")
                return False, f"自动化已暂停: {paused_reason}"

            # 检查是否人工接管
            if manual_takeover:
                return False, "当前处于人工接管状态"

            # 检查是否手动模式
            if mode == "manual":
                return False, "当前为手动模式，不允许自动执行"

            # 检查连续失败次数
            if consecutive_failure_count >= self.MAX_CONSECUTIVE_FAILURES:
                return False, f"自动化连续失败 {consecutive_failure_count} 次，已超过阈值"

            # 检查今天的派发次数
            if not self._state.can_dispatch_today(self._config.max_daily_dispatch_count):
                return False, f"今日已派发 {self._state.get_state()['daily_dispatch_count']} 次，已达上限"

            # 检查上次派发间隔
            last_dispatch_at = str(self._state.get_state().get("last_dispatch_at", "") or "")
            if last_dispatch_at:
                try:
                    last_time = datetime.fromisoformat(last_dispatch_at)
                    elapsed_seconds = (datetime.now(timezone.utc) - last_time).total_seconds()
                    if elapsed_seconds < self.MIN_INTERVAL_SECONDS:
                        return False, f"距上次派发仅 {elapsed_seconds:.0f} 秒，小于最小间隔 {self.MIN_INTERVAL_SECONDS} 秒"
                except ValueError:
                    pass

            # 检查自身连续失败次数
            if self._state.get_state()["consecutive_failure_count"] >= self.MAX_CONSECUTIVE_FAILURES:
                return False, f"自动派发连续失败 {self._state.get_state()['consecutive_failure_count']} 次，已暂停"

            return True, "自动化状态正常"
        except Exception as exc:
            logger.warning("检查自动化状态异常: %s", exc)
            return False, f"检查自动化状态异常: {exc}"

    def should_auto_execute(self) -> tuple[bool, str, dict[str, Any] | None]:
        """综合判断是否应该自动执行。

        Returns:
            (是否应该执行, 原因说明, 推荐候选信息)
        """
        # 1. 检查自动化状态
        allowed, reason = self.check_automation_state()
        if not allowed:
            return False, reason, None

        # 2. 获取推荐候选
        recommendation = self.get_top_recommendation()
        if not recommendation:
            return False, "没有符合条件的推荐候选", None

        symbol = str(recommendation.get("symbol", "")).strip().upper()

        # 3. 检查门控
        gates_passed, gates_reason = self.check_gates_passed(recommendation)
        if not gates_passed:
            return False, gates_reason, recommendation

        # 4. 检查风控熔断
        strategy_id = 1  # 默认策略ID
        risk_passed, risk_reason, risk_details = self.check_risk_guard(strategy_id)
        if not risk_passed:
            return False, risk_reason, recommendation

        return True, f"候选 {symbol} 符合自动执行条件", recommendation

    def auto_dispatch_signal(self, recommendation: dict[str, Any]) -> dict[str, Any]:
        """自动执行信号派发。

        Args:
            recommendation: 推荐候选信息

        Returns:
            执行结果
        """
        symbol = str(recommendation.get("symbol", "")).strip().upper()
        strategy_id = 1  # 默认策略ID
        executed_at = _utc_now()

        logger.info("开始自动派发信号: %s", symbol)

        try:
            # 使用策略派发服务执行完整流程
            result = strategy_dispatch_service.dispatch_latest_signal(
                strategy_id=strategy_id,
                source="auto_dispatch",
            )

            success = str(result.get("status", "")).strip().lower() == "succeeded"
            message = str(result.get("message", "") or "")

            # 记录派发结果
            self._state.record_dispatch(success=success, symbol=symbol)

            if success:
                # 推送成功告警
                try:
                    alert_push_service.push_sync(
                        AlertMessage(
                            event_type=AlertEventType.TRADE_EXECUTED,
                            level=AlertLevel.INFO,
                            title="自动派发成功",
                            message=f"候选 {symbol} 已自动派发执行",
                            details={
                                "symbol": symbol,
                                "strategy_id": strategy_id,
                                "source": "auto_dispatch",
                                "executed_at": executed_at,
                                "dispatch_result": result,
                            },
                        )
                    )
                except Exception as alert_exc:
                    logger.warning("成功告警推送失败: %s", alert_exc)

                logger.info("自动派发成功: %s", symbol)
                return {
                    "success": True,
                    "symbol": symbol,
                    "executed_at": executed_at,
                    "message": f"候选 {symbol} 已自动派发执行",
                    "result": result,
                }
            else:
                error_code = str(result.get("error_code", "") or "unknown")
                error_message = str(result.get("message", "") or "派发失败")

                # 推送失败告警
                try:
                    alert_push_service.push_sync(
                        AlertMessage(
                            event_type=AlertEventType.SYSTEM_ERROR,
                            level=AlertLevel.ERROR,
                            title="自动派发失败",
                            message=f"候选 {symbol} 自动派发失败: {error_message}",
                            details={
                                "symbol": symbol,
                                "strategy_id": strategy_id,
                                "source": "auto_dispatch",
                                "executed_at": executed_at,
                                "error_code": error_code,
                                "dispatch_result": result,
                            },
                        )
                    )
                except Exception as alert_exc:
                    logger.warning("失败告警推送失败: %s", alert_exc)

                # 记录到自动化服务
                automation_service.record_alert(
                    level="error",
                    code="auto_dispatch_failed",
                    message=f"自动派发失败: {symbol}",
                    source="auto_dispatch",
                    detail=error_message,
                )

                logger.warning("自动派发失败: %s, 原因: %s", symbol, error_message)
                return {
                    "success": False,
                    "symbol": symbol,
                    "executed_at": executed_at,
                    "error_code": error_code,
                    "message": error_message,
                    "result": result,
                }

        except Exception as exc:
            self._state.record_dispatch(success=False, symbol=symbol)

            # 推送异常告警
            try:
                alert_push_service.push_sync(
                    AlertMessage(
                        event_type=AlertEventType.SYSTEM_ERROR,
                        level=AlertLevel.ERROR,
                        title="自动派发异常",
                        message=f"候选 {symbol} 自动派发异常: {exc}",
                        details={
                            "symbol": symbol,
                            "strategy_id": strategy_id,
                            "source": "auto_dispatch",
                            "executed_at": executed_at,
                            "error": str(exc)[:200],
                        },
                    )
                )
            except Exception as alert_exc:
                logger.warning("异常告警推送失败: %s", alert_exc)

            # 记录到自动化服务
            automation_service.record_alert(
                level="error",
                code="auto_dispatch_exception",
                message=f"自动派发异常: {symbol}",
                source="auto_dispatch",
                detail=str(exc),
            )

            logger.error("自动派发异常: %s, 错误: %s", symbol, exc)
            return {
                "success": False,
                "symbol": symbol,
                "executed_at": executed_at,
                "error_code": "exception",
                "message": str(exc),
                "result": None,
            }

    def run_auto_dispatch_cycle(self) -> dict[str, Any]:
        """执行一轮完整的自动派发流程。

        Returns:
            执行结果
        """
        executed_at = _utc_now()

        with self._lock:
            # 检查是否应该执行
            should_execute, reason, recommendation = self.should_auto_execute()

            if not should_execute:
                logger.info("本轮不执行自动派发: %s", reason)
                return {
                    "dispatched": False,
                    "executed_at": executed_at,
                    "reason": reason,
                    "recommendation": recommendation,
                }

            # 执行自动派发
            result = self.auto_dispatch_signal(recommendation)

            return {
                "dispatched": result.get("success", False),
                "executed_at": executed_at,
                "symbol": result.get("symbol", ""),
                "message": result.get("message", ""),
                "result": result,
            }


# 默认实例
auto_dispatch_service = AutoDispatchService()
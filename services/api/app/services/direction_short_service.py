"""方向做空调度服务。

基于模型市场方向判断（16 币平均上涨概率）调度做空：
- 平均分数 < 0.38（极度看跌）且无空仓 → 开空 BTCUSDT
- 平均分数 > 0.45（转暖）且有空仓 → 平空
- 其余 → 保持

状态持久化到 JSON 文件（重启不丢），供 openclaw 巡检每轮调用 decide()。

上涨超过阈值的低概率不能直接视为下跌概率；开仓须由执行层明确放行。
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 开空/平空阈值（来自 OOS 验证的最优阈值）
SHORT_TRIGGER_SCORE = 0.38
FLAT_TRIGGER_SCORE = 0.45
SHORT_SYMBOL = "BTCUSDT"
SHORT_FUTURES_SYMBOL = "BTC/USDT:USDT"
DIRECTION_SHORT_ENTRY_TAG_PREFIX = "quant-direction-short:"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_short_value(value: Any) -> bool:
    """判断 freqtrade 交易条目的 is_short 是否为真（兼容布尔/字符串）。"""
    return value is True or str(value).lower() == "true"


class DirectionShortService:
    """方向做空调度器。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state_path = Path(
            os.getenv("QUANT_DIRECTION_SHORT_STATE_PATH", "/app/.runtime/direction_short_state.json")
        )
        self._state: dict[str, Any] = {
            "has_short_position": False,
            "symbol": "",
            "trade_id": None,
            "opened_at": "",
            "closed_at": "",
            "last_avg_score": None,
            "last_decision_at": "",
            "retry_after": None,  # 开仓失败后的重试时间（ISO），未到不重复尝试
        }
        self._load_state()

    def _load_state(self) -> None:
        if not self._state_path.exists():
            return
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                self._state.update(payload)
        except (OSError, json.JSONDecodeError):
            logger.warning("方向做空状态文件损坏，使用默认状态")

    def _persist(self) -> None:
        tmp_path = self._state_path.with_suffix(f".tmp.{os.getpid()}")
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self._state_path)

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def decide(self, *, avg_score: float | None, has_short_position: bool | None = None, opening_allowed: bool = False) -> dict[str, Any]:
        """根据平均分数决策：open_short / close_short / hold。

        Args:
            avg_score: 模型 16 币平均上涨概率（None 表示无信号）
            has_short_position: 当前空仓状态（默认用内部状态）
        """
        with self._lock:
            position = self._state["has_short_position"] if has_short_position is None else has_short_position
            self._state["last_avg_score"] = avg_score
            self._state["last_decision_at"] = _utc_now()

            # 重试冷却：上次开仓失败后 5 分钟内不重复尝试（避免高频打挂的下游）
            retry_after = self._state.get("retry_after")
            if retry_after and not position:
                try:
                    retry_dt = datetime.fromisoformat(str(retry_after).replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) < retry_dt:
                        self._persist()
                        return {"action": "hold", "reason": f"retry_cooldown_until_{retry_after}"}
                except (ValueError, TypeError):
                    pass

            if avg_score is None:
                self._persist()
                return {"action": "hold", "reason": "no_signal"}

            if avg_score < SHORT_TRIGGER_SCORE and not position:
                self._persist()
                if not opening_allowed:
                    return {"action": "hold", "reason": "short_model_not_admitted"}
                return {"action": "open_short", "reason": f"bearish_avg_{avg_score:.3f}"}
            if avg_score > FLAT_TRIGGER_SCORE and position:
                self._persist()
                return {"action": "close_short", "reason": f"recovered_avg_{avg_score:.3f}"}
            self._persist()
            return {
                "action": "hold",
                "reason": "position_bearish" if position else "score_not_extreme",
            }

    def mark_retry(self, *, minutes: int = 5) -> None:
        """标记 N 分钟后再重试开空（开仓失败时调用）。"""
        with self._lock:
            retry_at = datetime.now(timezone.utc)
            from datetime import timedelta
            self._state["retry_after"] = (retry_at + timedelta(minutes=minutes)).isoformat()
            self._persist()

    def clear_retry(self) -> None:
        """清除重试标记（开仓成功或转暖平仓时）。"""
        with self._lock:
            self._state["retry_after"] = None
            self._persist()

    def mark_short_open(self, *, symbol: str = SHORT_SYMBOL, trade_id: int | str | None = None) -> None:
        """记录已确认方向空仓的实际符号与交易编号。"""
        with self._lock:
            self._state["has_short_position"] = True
            self._state["symbol"] = symbol
            self._state["trade_id"] = trade_id
            self._state["opened_at"] = _utc_now()
            self._state["closed_at"] = ""
            self._persist()
            logger.info("方向做空已开仓: %s", symbol)

    def mark_short_closed(self) -> None:
        """标记空仓已平。"""
        with self._lock:
            self._state["has_short_position"] = False
            self._state["trade_id"] = None
            self._state["closed_at"] = _utc_now()
            self._persist()
            logger.info("方向做空已平仓")

    @staticmethod
    def belongs_to_strategy(trade: dict[str, Any]) -> bool:
        """按 BTC 合约空仓及明确归属标签判断策略来源，兼容已平仓历史。"""
        symbols = {SHORT_SYMBOL, "BTC/USDT", SHORT_FUTURES_SYMBOL}
        return (
            _is_short_value(trade.get("is_short"))
            and str(trade.get("pair") or "").strip().upper() in symbols
            and str(trade.get("enter_tag") or "").startswith(DIRECTION_SHORT_ENTRY_TAG_PREFIX)
        )

    @classmethod
    def owned_short_trades(cls, open_trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """在明确归属的 BTC 合约空仓中，只返回实际仍在场的仓位。"""
        return [trade for trade in open_trades
                if _is_short_value(trade.get("is_open")) and cls.belongs_to_strategy(trade)]

    def reconcile_with_open_trades(self, open_trades: list[dict[str, Any]]) -> bool:
        """按明确归属的实际空仓同步状态，不认领 RSI 多仓或其他策略空仓。"""
        owned = self.owned_short_trades(open_trades)
        with self._lock:
            if not owned:
                if self._state["has_short_position"]:
                    self.mark_short_closed()
                    return True
                return False
            # 优先继续跟踪已持有的交易；存在多个归属仓位时执行层逐个管理。
            tracked = next((trade for trade in owned
                            if trade.get("trade_id") == self._state.get("trade_id")), owned[0])
            trade_id = tracked.get("trade_id")
            if (self._state["has_short_position"] and
                    self._state.get("trade_id") == trade_id and
                    self._state.get("symbol") == SHORT_FUTURES_SYMBOL):
                return False
            self.mark_short_open(symbol=SHORT_FUTURES_SYMBOL, trade_id=trade_id)
            return True


def build_sim_client():
    """构建方向做空专用的 freqtrade 客户端（默认指向模拟盘 9014）。

    与实盘客户端（9013）完全隔离；地址/凭据可通过环境变量切换，
    供巡检执行和状态查询接口共用，避免两处重复拼配置。
    """
    from services.api.app.adapters.freqtrade.rest_client import FreqtradeRestClient, FreqtradeRestConfig

    return FreqtradeRestClient(
        FreqtradeRestConfig(
            base_url=os.getenv("QUANT_DIRECTION_SHORT_FREQTRADE_URL", "http://127.0.0.1:9014").strip(),
            username=os.getenv("QUANT_DIRECTION_SHORT_FREQTRADE_USERNAME", "Freqtrader"),
            password=os.getenv("QUANT_DIRECTION_SHORT_FREQTRADE_PASSWORD", "jianyu0.0."),
            timeout_seconds=8,
            max_total_timeout_seconds=10,
        )
    )


# 默认实例
direction_short_service = DirectionShortService()

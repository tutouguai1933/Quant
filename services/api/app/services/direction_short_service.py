"""方向做空调度服务。

基于模型市场方向判断（16 币平均上涨概率）调度做空：
- 平均分数 < 0.38（极度看跌）且无空仓 → 开空 BTCUSDT
- 平均分数 > 0.45（转暖）且有空仓 → 平空
- 其余 → 保持

状态持久化到 JSON 文件（重启不丢），供 openclaw 巡检每轮调用 decide()。

方向做空验证结论（scripts/run_direction_short.py，OOS 隔离验证）：
TEST 段命中率 77.8%、平均收益 +2.58%/次——模型方向判断可靠。
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
            "opened_at": "",
            "closed_at": "",
            "last_avg_score": None,
            "last_decision_at": "",
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

    def decide(self, *, avg_score: float | None, has_short_position: bool | None = None) -> dict[str, Any]:
        """根据平均分数决策：open_short / close_short / hold。

        Args:
            avg_score: 模型 16 币平均上涨概率（None 表示无信号）
            has_short_position: 当前空仓状态（默认用内部状态）
        """
        with self._lock:
            position = self._state["has_short_position"] if has_short_position is None else has_short_position
            self._state["last_avg_score"] = avg_score
            self._state["last_decision_at"] = _utc_now()

            if avg_score is None:
                self._persist()
                return {"action": "hold", "reason": "no_signal"}

            if avg_score < SHORT_TRIGGER_SCORE and not position:
                self._persist()
                return {"action": "open_short", "reason": f"bearish_avg_{avg_score:.3f}"}
            if avg_score > FLAT_TRIGGER_SCORE and position:
                self._persist()
                return {"action": "close_short", "reason": f"recovered_avg_{avg_score:.3f}"}
            self._persist()
            return {
                "action": "hold",
                "reason": "position_bearish" if position else "score_not_extreme",
            }

    def mark_short_open(self, *, symbol: str = SHORT_SYMBOL) -> None:
        """标记空仓已开。"""
        with self._lock:
            self._state["has_short_position"] = True
            self._state["symbol"] = symbol
            self._state["opened_at"] = _utc_now()
            self._state["closed_at"] = ""
            self._persist()
            logger.info("方向做空已开仓: %s", symbol)

    def mark_short_closed(self) -> None:
        """标记空仓已平。"""
        with self._lock:
            self._state["has_short_position"] = False
            self._state["closed_at"] = _utc_now()
            self._persist()
            logger.info("方向做空已平仓")

    def reconcile_with_trades(self, trades: list[dict[str, Any]]) -> bool:
        """按模拟盘真实交易列表对齐内部状态（自愈）。

        空单被止损/策略平仓后，状态文件会残留 has_short_position=true，
        导致调度永远 hold、观察期僵死；反之亦然。巡检每轮决策前调用本方法，
        以真实持仓为准修正内部状态，返回是否发生了修正。
        """
        has_open_short = any(t.get("is_open") and _is_short_value(t.get("is_short")) for t in trades)
        with self._lock:
            need_close = bool(self._state["has_short_position"]) and not has_open_short
            need_open = not bool(self._state["has_short_position"]) and has_open_short

        if need_close:
            self.mark_short_closed()
            return True
        if need_open:
            self.mark_short_open(symbol=SHORT_SYMBOL)
            return True
        return False


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

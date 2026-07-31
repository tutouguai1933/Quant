"""双策略协同仲裁服务。

控制平面（ML 自动化策略）在向 freqtrade 派发买入前，检查目标币种是否已被
EnhancedStrategy 自主持仓、以及 freqtrade 全局名额（max_open_trades）是否已满，
避免对同一币种重复建仓或挤占共享名额。仲裁只约束 ML 侧，EnhancedStrategy 保持自主。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from services.api.app.core.settings import Settings

logger = logging.getLogger(__name__)

ML_ENTRY_TAG = "quant-control-plane"
ENHANCED_ENTRY_TAG = ""


@dataclass
class ArbitrationDecision:
    """一次仲裁的结论。"""

    allowed: bool
    symbol: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "symbol": self.symbol,
            "reasons": self.reasons,
        }


class StrategyArbitrationService:
    """在 ML 派发前对 freqtrade 实际持仓做协同检查。"""

    def __init__(self) -> None:
        self._settings: Settings | None = None

    def evaluate(self, symbol: str, freqtrade_client: object) -> ArbitrationDecision:
        """检查 symbol（如 BTCUSDT 或 BTC/USDT）是否可以由 ML 派发买入。"""
        settings = self._settings or Settings.from_env()
        if not settings.arbitration_enabled:
            return ArbitrationDecision(allowed=True, symbol=symbol)

        pair = self._normalize_pair(symbol)
        try:
            open_trades = freqtrade_client.list_open_trades()
            snapshot = freqtrade_client.get_runtime_snapshot()
        except Exception as exc:
            logger.error("仲裁器获取 freqtrade 持仓失败: %s", exc)
            if settings.arbitration_fail_open:
                decision = ArbitrationDecision(allowed=True, symbol=symbol)
            else:
                decision = ArbitrationDecision(
                    allowed=False,
                    symbol=symbol,
                    reasons=[f"arbitration_unavailable: {exc}"],
                )
            self._log(settings, decision, source=None)
            return decision

        max_open_trades = self._resolve_max_open_trades(snapshot)
        reasons: list[str] = []

        holding = [t for t in open_trades if str(t.get("pair") or "").upper() == pair]
        if holding:
            source = "ml" if holding[0].get("enter_tag") == ML_ENTRY_TAG else "enhanced"
            reasons.append(f"already_held (source={source}, {len(holding)} trade(s))")

        if max_open_trades is not None and len(open_trades) >= max_open_trades:
            reasons.append(f"max_open_trades ({len(open_trades)}/{max_open_trades})")

        decision = ArbitrationDecision(allowed=not reasons, symbol=symbol, reasons=reasons)
        if decision.allowed:
            logger.info("仲裁放行: %s, 当前持仓 %d/%s", pair, len(open_trades), max_open_trades)
        else:
            logger.warning("仲裁拦截: %s, 原因: %s", pair, "; ".join(reasons))
        self._log(settings, decision, source=holding[0].get("enter_tag") if holding else None)
        return decision

    @staticmethod
    def _normalize_pair(symbol: str) -> str:
        """把控制平面符号归一成 freqtrade pair 格式（BTCUSDT → BTC/USDT）。"""
        compact = symbol.strip().upper().replace("/", "")
        if compact.endswith("USDT") and len(compact) > 4:
            return f"{compact[:-4]}/USDT"
        return compact

    @staticmethod
    def _resolve_max_open_trades(snapshot: object) -> int | None:
        if not isinstance(snapshot, dict):
            return None
        raw = snapshot.get("max_open_trades")
        if raw is None:
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    def _log(self, settings: Settings, decision: ArbitrationDecision, *, source: object) -> None:
        try:
            path = Path(settings.arbitration_log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "symbol": decision.symbol,
                "allowed": decision.allowed,
                "reasons": decision.reasons,
                "holding_source": source,
            }
            with open(path, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass


strategy_arbitration_service = StrategyArbitrationService()

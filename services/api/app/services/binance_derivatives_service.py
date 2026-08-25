"""币安衍生品另类数据采集服务。

定期拉取持仓量/大户多空比/散户多空比/主动买卖比，增量存储到本地 jsonl。
用途：为策略研究积累另类数据（情绪/仓位维度），数据量足够后做有效性分析。

由 kline_sync_scheduler 循环顺带调用（每 15 分钟一轮）。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import urllib.request

logger = logging.getLogger(__name__)

FAPI = "https://fapi.binance.com"
SYMBOLS = ["BTCUSDT", "ETHUSDT"]
PERIOD = "4h"
LIMIT = "500"

# 端点与提取字段
# 注意：value 是完整路径（缺 /futures/data 前缀会打到不存在的路径返回 403）
ENDPOINTS = {
    "futures/data/openInterestHist": lambda r: float(r["sumOpenInterest"]),
    "futures/data/topLongShortPositionRatio": lambda r: float(r["longShortRatio"]),
    "futures/data/globalLongShortAccountRatio": lambda r: float(r["longShortRatio"]),
    "futures/data/takerlongshortRatio": lambda r: float(r["buySellRatio"]),
}


class BinanceDerivativesService:
    """币安衍生品数据采集与本地存储。"""

    def __init__(self, store_dir: str | None = None) -> None:
        self._store_dir = Path(store_dir or os.getenv("QUANT_DERIVATIVES_DIR", "/app/.runtime/derivatives"))
        self._store_dir.mkdir(parents=True, exist_ok=True)

    def _store_path(self, symbol: str, endpoint: str) -> Path:
        # 文件名取端点末段（endpoint 可能是 "futures/data/xxx" 完整路径）
        return self._store_dir / f"{symbol}_{endpoint.split('/')[-1]}.jsonl"

    def fetch(self, symbol: str, endpoint: str) -> list[dict[str, Any]]:
        """拉取端点数据（带浏览器 UA，币安对 Python 默认 UA 返回 403）。"""
        url = f"{FAPI}/{endpoint}?symbol={symbol}&period={PERIOD}&limit={LIMIT}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (quant-derivatives-sync)"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.load(resp)

    def sync_symbol(self, symbol: str) -> int:
        """同步单币全部端点，返回新增条数。"""
        added = 0
        for endpoint, extract in ENDPOINTS.items():
            path = self._store_path(symbol, endpoint)
            # 已存时间戳集合（去重）
            existing_ts: set[int] = set()
            if path.exists():
                for line in path.read_text(encoding="utf-8").splitlines():
                    try:
                        existing_ts.add(int(json.loads(line)["timestamp"]))
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
            try:
                rows = self.fetch(symbol, endpoint)
            except Exception as exc:
                logger.warning("衍生品数据拉取失败 %s/%s: %s", symbol, endpoint, exc)
                continue
            new_lines = []
            for row in sorted(rows, key=lambda x: int(x["timestamp"])):
                ts = int(row["timestamp"])
                if ts in existing_ts:
                    continue
                record = {"timestamp": ts, "value": extract(row), "synced_at": _utc_now()}
                new_lines.append(json.dumps(record, ensure_ascii=False))
            if new_lines:
                with path.open("a", encoding="utf-8") as f:
                    f.write("\n".join(new_lines) + "\n")
                added += len(new_lines)
        return added

    def sync_all(self) -> dict[str, int]:
        """同步全部监控币种。"""
        total = 0
        for symbol in SYMBOLS:
            total += self.sync_symbol(symbol)
        # 另类数据源（全市场共享，非单币种）
        try:
            total += self.sync_funding_rate("BTCUSDT")
        except Exception as exc:
            logger.warning("资金费率同步失败: %s", exc)
        try:
            total += self.sync_fear_greed()
        except Exception as exc:
            logger.warning("恐惧贪婪指数同步失败: %s", exc)
        return total

    def sync_funding_rate(self, symbol: str = "BTCUSDT") -> int:
        """同步资金费率历史（8 小时一次，反映多空持仓成本与拥挤度）。"""
        path = self._store_dir / f"{symbol}_fundingRate.jsonl"
        existing_ts: set[int] = set()
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    existing_ts.add(int(json.loads(line)["fundingTime"]))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        url = f"{FAPI}/fapi/v1/fundingRate?symbol={symbol}&limit=1000"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (quant-sync)"})
        rows = json.load(urllib.request.urlopen(req, timeout=20))
        new_lines = []
        for row in rows:
            ts = int(row["fundingTime"])
            if ts in existing_ts:
                continue
            new_lines.append(json.dumps({
                "timestamp": ts,
                "rate": float(row["fundingRate"]),
                "markPrice": float(row.get("markPrice", 0)),
                "synced_at": _utc_now(),
            }, ensure_ascii=False))
        if new_lines:
            with path.open("a", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
            logger.info("资金费率新增 %d 条 (%s)", len(new_lines), symbol)
        return len(new_lines)

    def sync_fear_greed(self) -> int:
        """同步 Fear & Greed Index（每日，alternative.me 免费API）。"""
        path = self._store_dir / "fear_greed_index.jsonl"
        existing_ts: set[int] = set()
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    existing_ts.add(int(json.loads(line)["timestamp"]))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        url = "https://api.alternative.me/fng/?limit=0&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (quant-sync)"})
        data = json.load(urllib.request.urlopen(req, timeout=20)).get("data") or []
        new_lines = []
        for row in data:
            ts = int(row["timestamp"])
            if ts in existing_ts:
                continue
            new_lines.append(json.dumps({
                "timestamp": ts,
                "value": int(row["value"]),
                "classification": row.get("value_classification", ""),
                "synced_at": _utc_now(),
            }, ensure_ascii=False))
        if new_lines:
            with path.open("a", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
            logger.info("Fear&Greed 新增 %d 条", len(new_lines))
        return len(new_lines)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# 默认实例
binance_derivatives_service = BinanceDerivativesService()

"""币安衍生品另类数据有效性研究：情绪/仓位指标与未来收益的关系。

用法（服务器容器内）：
    cd /app && PYTHONPATH=/app python3 scripts/run_derivatives_study.py

研究指标（fapi.binance.com 免费端点，4h 周期，BTCUSDT）：
- oi_change_pct：持仓量变化率（资金流入流出）
- top_ls_ratio：大户持仓多空比（聪明钱方向）
- global_ls_ratio：散户账户多空比（反向指标候选）
- taker_ratio：主动买卖比（即时攻击性）

分析：每个指标分 5 分位桶，统计各桶"未来 12 根 4h 收益率"的均值与上涨频率。
有效信号判定：最高分位与最低分位的收益差显著（且两端单调）。

结果写 /tmp/derivatives_study.json
"""

from __future__ import annotations

import json
import statistics
import sys
import time
import urllib.request
from typing import Any

FAPI = "https://fapi.binance.com"
SYMBOL = "BTCUSDT"
PERIOD = "4h"
LIMIT = 500          # 端点单次最大条数
FUTURE_BARS = 12     # 未来 12 根 4h ≈ 2 天（对齐策略持有窗口）


def fetch(endpoint: str, params: dict[str, str]) -> list[dict[str, Any]]:
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{FAPI}/{endpoint}?{qs}"
    with urllib.request.urlopen(url, timeout=20) as resp:
        return json.load(resp)


def load_klines() -> list[dict[str, Any]]:
    """读本地 4h K 线（kline_store jsonl）。"""
    from pathlib import Path

    path = Path("/app/.runtime/kline_store/BTCUSDT_4h.jsonl")
    bars = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    bars.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    bars.sort(key=lambda b: int(b["open_time"]))
    return bars


def main() -> int:
    started = time.time()

    # 1. K 线与未来收益
    bars = load_klines()
    closes = [float(b["close"]) for b in bars]
    open_times = [int(b["open_time"]) for b in bars]
    print(f"K线: {len(bars)} 根 ({bars[0]['open_time']} -> {bars[-1]['open_time']})", flush=True)

    def future_return(idx: int) -> float | None:
        """idx 收盘后持有 FUTURE_BARS 根的收益率。"""
        if idx + FUTURE_BARS >= len(closes):
            return None
        return (closes[idx + FUTURE_BARS] - closes[idx]) / closes[idx] * 100.0

    # 2. 拉取衍生品数据（timestamp 对齐到 K 线收盘时刻）
    indicators: dict[str, dict[int, float]] = {}
    specs = {
        "oi": ("futures/data/openInterestHist", lambda r: float(r["sumOpenInterest"])),
        "top_ls": ("futures/data/topLongShortPositionRatio", lambda r: float(r["longShortRatio"])),
        "global_ls": ("futures/data/globalLongShortAccountRatio", lambda r: float(r["longShortRatio"])),
        "taker": ("futures/data/takerlongshortRatio", lambda r: float(r["buySellRatio"])),
    }
    for name, (ep, extract) in specs.items():
        data = fetch(ep, {"symbol": SYMBOL, "period": PERIOD, "limit": str(LIMIT)})
        mapping: dict[int, float] = {}
        prev: float | None = None
        for row in sorted(data, key=lambda x: int(x["timestamp"])):
            ts = int(row["timestamp"])
            value = extract(row)
            # OI 用变化率，其余用原始值
            mapping[ts] = (value - prev) / prev * 100.0 if (name == "oi" and prev) else value
            prev = value
        indicators[name] = mapping
        print(f"{name}: {len(mapping)} 个时间点", flush=True)

    # 3. 组装样本：K线收盘时刻 -> (指标值, 未来收益)
    samples: list[dict[str, Any]] = []
    for idx in range(len(bars)):
        bar_close_ts = open_times[idx] + 4 * 3600 * 1000 - 1  # 该根收盘时刻
        fut = future_return(idx)
        if fut is None:
            continue
        sample: dict[str, Any] = {"future": fut}
        ok = True
        for name, mapping in indicators.items():
            # 取 <= 收盘时刻的最近一个衍生品数据点（无泄漏）
            prior = [t for t in mapping if t <= bar_close_ts]
            if not prior:
                ok = False
                break
            sample[name] = mapping[max(prior)]
        if ok:
            samples.append(sample)
    print(f"有效样本: {len(samples)}", flush=True)

    # 4. 分位分桶分析
    summary: dict[str, Any] = {"sample_count": len(samples), "indicators": {}}
    print("\n=== 分位分析（Q1=最低 20%，Q5=最高 20%；未来 2 天收益%）===")
    for name in indicators:
        values = sorted(s[name] for s in samples if name in s)
        if len(values) < 50:
            continue
        q = [values[int(len(values) * i / 5)] for i in range(1, 5)]
        buckets: list[list[float]] = [[], [], [], [], []]
        for s in samples:
            v = s.get(name)
            if v is None:
                continue
            bucket_idx = sum(1 for threshold in q if v >= threshold)
            buckets[bucket_idx].append(s["future"])
        rows = []
        for i, b in enumerate(buckets):
            if not b:
                rows.append({"q": i + 1, "count": 0})
                continue
            rows.append({
                "q": i + 1,
                "count": len(b),
                "avg_future": round(sum(b) / len(b), 4),
                "up_rate": round(sum(1 for x in b if x > 0) / len(b), 4),
            })
        summary["indicators"][name] = rows
        spread = (rows[-1]["avg_future"] or 0) - (rows[0]["avg_future"] or 0) if rows[0].get("avg_future") is not None and rows[-1].get("avg_future") is not None else 0
        detail = " | ".join(
            f"Q{r['q']}: {r['avg_future']:+.2f}%({r['up_rate']:.0%})" for r in rows if r.get("count")
        )
        print(f"[{name}] Q5-Q1 收益差={spread:+.2f}%\n   {detail}", flush=True)

    with open("/tmp/derivatives_study.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n耗时 {time.time() - started:.1f}s，结果已写入 /tmp/derivatives_study.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

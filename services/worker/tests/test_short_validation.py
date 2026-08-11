"""做空方向验证核心函数测试。"""

from scripts.run_short_validation import build_short_pairs, compute_short_hit_rate


def test_build_short_pairs_selects_lowest_scores() -> None:
    """选分数最低的 k 个作为做空候选。"""
    rows = [
        {"symbol": "A", "score": 0.6, "future_return_pct": "1.2"},
        {"symbol": "B", "score": 0.3, "future_return_pct": "-0.8"},
        {"symbol": "C", "score": 0.2, "future_return_pct": "-1.5"},
        {"symbol": "D", "score": 0.5, "future_return_pct": "0.4"},
    ]
    pairs = build_short_pairs(rows, top_k=2)
    assert [p["symbol"] for p in pairs] == ["C", "B"]  # 最低分优先


def test_compute_short_hit_rate() -> None:
    """做空命中率 = 未来收益为负的比例；做空收益 = -未来收益。"""
    pairs = [
        {"symbol": "A", "future_return_pct": "-1.0"},  # 命中（跌了，做空赚 1%）
        {"symbol": "B", "future_return_pct": "0.5"},   # 未命中（涨了，做空亏 0.5%）
        {"symbol": "C", "future_return_pct": "-0.2"},  # 命中
        {"symbol": "D", "future_return_pct": "0.0"},   # 平（不计入命中分母）
    ]
    result = compute_short_hit_rate(pairs)
    assert result["hit_rate"] == 0.5
    assert result["sample_count"] == 3
    assert result["avg_return"] == round((1.0 - 0.5 + 0.2) / 3, 4)  # 平均做空收益为正

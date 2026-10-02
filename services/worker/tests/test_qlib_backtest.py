"""ML 价格回放测试；旧未来标签回测断言已迁移到真实成交和账户净值。"""
from __future__ import annotations
import unittest
from services.worker.qlib_backtest import run_backtest, simulate_trades


def _price_rows(prices=(100, 100, 100.8), signals=None):
    """提供独立于未来标签的价格和模型信号。"""
    signals = signals or ["buy"] * len(prices)
    return [dict(symbol="BTCUSDT", generated_at=i * 1000 + 999,
                 open_time=i * 1000, close_time=i * 1000 + 999,
                 open=100 if i < 2 else prices[i - 1],
                 high=max(100 if i < 2 else prices[i - 1], price),
                 low=min(100 if i < 2 else prices[i - 1], price),
                 close=price, model_signal=signals[i],
                 future_return_pct="999", label="sell")
            for i, price in enumerate(prices)]


class QlibBacktestTests(unittest.TestCase):
    def test_backtest_report_contains_core_metrics(self):
        """报告沿用字符串指标与负回撤约定。"""
        report = run_backtest(rows=_price_rows(), holding_window="1-3d")
        self.assertEqual(report["evaluation_status"], "available")
        self.assertEqual(report["holding_window"], "1-3d")
        self.assertEqual(set(report["metrics"]), {
            "total_return_pct", "gross_return_pct", "net_return_pct", "cost_impact_pct",
            "max_drawdown_pct", "sharpe", "win_rate", "turnover", "sample_count",
            "max_loss_streak", "action_segment_count", "direction_switch_count",
            "trades_count", "final_nav", "exit_reasons"})
        self.assertEqual(report["assumptions"]["execution_rule"], "next_asset_open")

    def test_backtest_applies_fee_and_slippage_to_net_return(self):
        """买卖均扣费用与滑点，结果由净值计算而非收益标签减常数。"""
        report = run_backtest(rows=_price_rows(), holding_window="1-3d", fee_bps="10", slippage_bps="5")
        self.assertEqual(report["assumptions"]["round_trip_cost_pct"], "0.3000")
        self.assertEqual(report["metrics"]["gross_return_pct"], "0.8000")
        self.assertEqual(report["metrics"]["net_return_pct"], "0.4981")
        self.assertEqual(report["metrics"]["cost_impact_pct"], "0.3019")
        self.assertEqual(report["metrics"]["trades_count"], "1")

    def test_backtest_supports_zero_cost_baseline_model(self):
        """零成本诊断仍使用同一真实价格路径。"""
        report = run_backtest(rows=_price_rows(), holding_window="1-3d", fee_bps="10",
                              slippage_bps="5", cost_model="zero_cost_baseline")
        self.assertEqual(report["metrics"]["net_return_pct"], "0.8000")
        self.assertEqual(report["metrics"]["cost_impact_pct"], "0.0000")

    def test_backtest_turnover_stays_low_when_direction_is_stable(self):
        """连续模型买入不重复开仓。"""
        report = run_backtest(rows=_price_rows((100, 100, 100, 100)), holding_window="1-3d")
        self.assertEqual(report["metrics"]["turnover"], "0.2500")
        self.assertEqual(report["metrics"]["sample_count"], "4")
        self.assertEqual(report["metrics"]["max_loss_streak"], "0")

    def test_backtest_reports_max_loss_streak(self):
        """亏损段按逐时间账户净值统计。"""
        report = run_backtest(rows=_price_rows((100, 100, 99.5, 99)), holding_window="1-3d")
        self.assertEqual(report["metrics"]["max_loss_streak"], "2")

    def test_backtest_reports_segment_counts_and_switches(self):
        """动作段来自模型信号，训练标签不能参与。"""
        rows = _price_rows((100,) * 6, ["watch", "buy", "buy", "sell", "sell", "watch"])
        report = run_backtest(rows=rows, holding_window="1-3d")
        self.assertEqual(report["metrics"]["action_segment_count"], "2")
        self.assertEqual(report["metrics"]["direction_switch_count"], "1")


def test_simulate_trades_opens_and_closes():
    """下一开盘成交后依据真实低点触发止损。"""
    rows = _price_rows((100, 98, 98), ["buy", "watch", "watch"])
    result = simulate_trades(rows, stop_loss_pct=-1.5, take_profit_pct=5, fee_pct=.1)
    assert result["trades_count"] == 1
    assert result["trades"][0]["exit_reason"] == "stop_loss"
    assert result["trades"][0]["entry_bar"] == 1000
    assert result["final_nav"] < 1


def test_run_backtest_uses_simulation_metrics():
    """最终成交成本结算到最后一个净值点。"""
    report = run_backtest(rows=_price_rows(), holding_window="1-3d", fee_bps=10, slippage_bps=5)
    assert int(report["metrics"]["trades_count"]) == 1
    assert abs(float(report["metrics"]["final_nav"]) - report["series"]["performance"][-1]["strategy_nav"]) < .00005


def test_run_backtest_max_drawdown_is_negative():
    """回撤使用负值供下游门控读取。"""
    report = run_backtest(rows=_price_rows((100, 100, 95, 90)), holding_window="1-3d", fee_bps=10, slippage_bps=5)
    assert float(report["metrics"]["max_drawdown_pct"]) < 0


if __name__ == "__main__":
    unittest.main()

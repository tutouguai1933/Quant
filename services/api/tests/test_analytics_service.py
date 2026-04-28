"""数据分析服务和路由测试。

覆盖以下功能:
- AnalyticsService: 每日/每周统计、归因分析、策略表现
- analytics routes: API 端点响应格式验证
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.analytics_service import (
    AnalyticsService,
    TradeRecord,
    DailySummary,
    WeeklySummary,
    PnlAttribution,
    StrategyPerformance,
    analytics_service,
    _parse_decimal,
    _parse_timestamp,
    _start_of_day,
    _start_of_week,
    utc_now,
)
from services.api.app.routes.analytics import (
    router,
    get_analytics_status,
    get_daily_summary,
    get_weekly_summary,
    get_pnl_attribution,
    get_strategy_performance,
    get_trade_history,
)


class TestAnalyticsHelpers(unittest.TestCase):
    """测试辅助函数。"""

    def test_utc_now_returns_timezone_aware_datetime(self) -> None:
        """utc_now 应返回带 timezone 的 datetime。"""
        now = utc_now()
        self.assertIsInstance(now, datetime)
        self.assertEqual(now.tzinfo, timezone.utc)

    def test_parse_decimal_valid_values(self) -> None:
        """_parse_decimal 应正确解析有效值。"""
        self.assertEqual(_parse_decimal("123.45"), Decimal("123.45"))
        self.assertEqual(_parse_decimal(100), Decimal("100"))
        self.assertEqual(_parse_decimal(Decimal("50.5")), Decimal("50.5"))

    def test_parse_decimal_invalid_returns_default(self) -> None:
        """_parse_decimal 对无效值应返回默认值。"""
        self.assertEqual(_parse_decimal(None), Decimal("0"))
        self.assertEqual(_parse_decimal("invalid"), Decimal("0"))
        self.assertEqual(_parse_decimal(None, Decimal("99")), Decimal("99"))

    def test_parse_timestamp_valid_iso_format(self) -> None:
        """_parse_timestamp 应正确解析 ISO 格式时间戳。"""
        result = _parse_timestamp("2024-01-15T10:30:00Z")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 15)

    def test_parse_timestamp_invalid_returns_none(self) -> None:
        """_parse_timestamp 对无效值应返回 None。"""
        self.assertIsNone(_parse_timestamp(None))
        self.assertIsNone(_parse_timestamp("invalid-date"))

    def test_start_of_day_zeroes_time_components(self) -> None:
        """_start_of_day 应将时间组件归零。"""
        dt = datetime(2024, 1, 15, 14, 30, 45, 123456, tzinfo=timezone.utc)
        result = _start_of_day(dt)
        self.assertEqual(result.hour, 0)
        self.assertEqual(result.minute, 0)
        self.assertEqual(result.second, 0)
        self.assertEqual(result.microsecond, 0)

    def test_start_of_week_returns_monday(self) -> None:
        """_start_of_week 应返回周一。"""
        # 2024-01-15 是周一
        monday = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        result = _start_of_week(monday)
        self.assertEqual(result.day, 15)

        # 2024-01-18 是周四，应返回 1月15（周一）
        thursday = datetime(2024, 1, 18, 10, 0, 0, tzinfo=timezone.utc)
        result = _start_of_week(thursday)
        self.assertEqual(result.day, 15)


class TestTradeRecord(unittest.TestCase):
    """测试 TradeRecord 数据类。"""

    def test_trade_record_to_dict(self) -> None:
        """TradeRecord.to_dict 应返回正确的字典结构。"""
        trade = TradeRecord(
            trade_id="trade-001",
            symbol="BTCUSDT",
            side="buy",
            quantity=Decimal("0.5"),
            price=Decimal("50000"),
            pnl=Decimal("0"),
            executed_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            strategy_id=1,
            signal_id=100,
            source="freqtrade",
        )
        result = trade.to_dict()
        self.assertEqual(result["trade_id"], "trade-001")
        self.assertEqual(result["symbol"], "BTCUSDT")
        self.assertEqual(result["side"], "buy")
        self.assertEqual(result["quantity"], "0.5")
        self.assertEqual(result["price"], "50000")
        self.assertEqual(result["pnl"], "0")
        self.assertEqual(result["strategy_id"], 1)
        self.assertEqual(result["signal_id"], 100)


class TestDailySummary(unittest.TestCase):
    """测试 DailySummary 数据类。"""

    def test_daily_summary_to_dict(self) -> None:
        """DailySummary.to_dict 应返回正确的字典结构。"""
        summary = DailySummary(
            date="2024-01-15",
            trade_count=10,
            buy_count=5,
            sell_count=5,
            total_pnl=Decimal("100.5"),
            win_count=6,
            loss_count=4,
            win_rate=Decimal("0.6"),
            avg_pnl=Decimal("10.05"),
            max_profit=Decimal("50"),
            max_loss=Decimal("-20"),
            symbols=["BTCUSDT", "ETHUSDT"],
        )
        result = summary.to_dict()
        self.assertEqual(result["date"], "2024-01-15")
        self.assertEqual(result["trade_count"], 10)
        self.assertEqual(result["buy_count"], 5)
        self.assertEqual(result["sell_count"], 5)
        self.assertEqual(result["total_pnl"], "100.5")
        self.assertEqual(result["win_count"], 6)
        self.assertEqual(result["loss_count"], 4)
        self.assertEqual(result["win_rate"], "0.6")
        self.assertEqual(result["symbols"], ["BTCUSDT", "ETHUSDT"])


class TestWeeklySummary(unittest.TestCase):
    """测试 WeeklySummary 数据类。"""

    def test_weekly_summary_to_dict(self) -> None:
        """WeeklySummary.to_dict 应返回正确的字典结构。"""
        summary = WeeklySummary(
            week_start="2024-01-15",
            week_end="2024-01-21",
            trade_count=50,
            total_pnl=Decimal("500"),
            win_count=30,
            loss_count=20,
            win_rate=Decimal("0.6"),
            daily_breakdown=[{"date": "2024-01-15", "trade_count": 10}],
            best_day="2024-01-16",
            worst_day="2024-01-18",
        )
        result = summary.to_dict()
        self.assertEqual(result["week_start"], "2024-01-15")
        self.assertEqual(result["week_end"], "2024-01-21")
        self.assertEqual(result["trade_count"], 50)
        self.assertEqual(result["total_pnl"], "500")
        self.assertEqual(result["best_day"], "2024-01-16")
        self.assertEqual(result["worst_day"], "2024-01-18")


class TestAnalyticsService(unittest.TestCase):
    """测试 AnalyticsService 核心功能。"""

    def setUp(self) -> None:
        """创建新的服务实例进行测试。"""
        self.service = AnalyticsService()

    def test_service_initialization(self) -> None:
        """服务应正确初始化。"""
        self.assertIsInstance(self.service._trade_history, dict)
        self.assertEqual(len(self.service._trade_history), 0)
        self.assertIsInstance(self.service.history_days, int)
        self.assertGreater(self.service.history_days, 0)

    def test_get_daily_summary_empty_history(self) -> None:
        """无交易历史时应返回空统计。"""
        summary = self.service.get_daily_summary("2024-01-15")
        self.assertEqual(summary.trade_count, 0)
        self.assertEqual(summary.total_pnl, Decimal("0"))
        self.assertEqual(summary.win_rate, Decimal("0"))

    def test_get_weekly_summary_empty_history(self) -> None:
        """无交易历史时应返回空周统计（但仍有7天breakdown）。"""
        summary = self.service.get_weekly_summary("2024-01-15")
        self.assertEqual(summary.trade_count, 0)
        self.assertEqual(summary.total_pnl, Decimal("0"))
        # daily_breakdown 仍包含7天的空统计
        self.assertEqual(len(summary.daily_breakdown), 7)
        self.assertEqual(summary.best_day, "")

    def test_get_pnl_attribution_empty_history(self) -> None:
        """无交易历史时应返回空归因。"""
        attribution = self.service.get_pnl_attribution()
        self.assertEqual(len(attribution.by_symbol), 0)
        self.assertEqual(len(attribution.by_strategy), 0)
        self.assertEqual(len(attribution.top_profit_symbols), 0)

    def test_get_strategy_performance_empty_history(self) -> None:
        """无交易历史时应返回空策略表现列表。"""
        performances = self.service.get_strategy_performance()
        self.assertEqual(len(performances), 0)

    def test_get_trade_history_empty(self) -> None:
        """无交易历史时应返回空列表。"""
        trades = self.service.get_trade_history()
        self.assertEqual(len(trades), 0)

    def test_service_status(self) -> None:
        """get_service_status 应返回正确状态。"""
        status = self.service.get_service_status()
        self.assertEqual(status["status"], "ready")
        self.assertIn("history_days", status)
        self.assertIn("trade_count", status)

    def test_trade_history_with_mocked_trades(self) -> None:
        """添加模拟交易后应正确查询。"""
        now = utc_now()
        trade1 = TradeRecord(
            trade_id="t1",
            symbol="BTCUSDT",
            side="buy",
            quantity=Decimal("1"),
            price=Decimal("50000"),
            pnl=Decimal("0"),
            executed_at=now - timedelta(hours=2),
            strategy_id=1,
        )
        trade2 = TradeRecord(
            trade_id="t2",
            symbol="ETHUSDT",
            side="sell",
            quantity=Decimal("10"),
            price=Decimal("3000"),
            pnl=Decimal("100"),
            executed_at=now - timedelta(hours=1),
            strategy_id=2,
        )

        self.service._trade_history["t1"] = trade1
        self.service._trade_history["t2"] = trade2

        trades = self.service.get_trade_history(limit=10)
        self.assertEqual(len(trades), 2)

        # 按标的筛选
        btc_trades = self.service.get_trade_history(symbol="BTCUSDT")
        self.assertEqual(len(btc_trades), 1)

        # 按方向筛选
        buy_trades = self.service.get_trade_history(side="buy")
        self.assertEqual(len(buy_trades), 1)


class TestAnalyticsRoutes(unittest.TestCase):
    """测试 Analytics API 路由。"""

    def test_router_prefix(self) -> None:
        """路由应有正确的前缀。"""
        self.assertEqual(router.prefix, "/api/v1/analytics")

    def test_get_analytics_status_response_format(self) -> None:
        """状态 API 应返回正确格式。"""
        result = get_analytics_status()
        self.assertIn("data", result)
        self.assertIn("error", result)
        self.assertIn("meta", result)
        self.assertIsNone(result["error"])
        self.assertEqual(result["data"]["status"], "ready")

    def test_get_daily_summary_response_format(self) -> None:
        """每日统计 API 应返回正确格式。"""
        result = get_daily_summary(date="2024-01-15")
        self.assertIn("data", result)
        self.assertIn("error", result)
        self.assertIn("meta", result)
        self.assertIn("summary", result["data"])
        self.assertEqual(result["data"]["summary"]["date"], "2024-01-15")

    def test_get_weekly_summary_response_format(self) -> None:
        """每周统计 API 应返回正确格式。"""
        result = get_weekly_summary(week_start="2024-01-15")
        self.assertIn("data", result)
        self.assertIn("error", result)
        self.assertIn("meta", result)
        self.assertIn("summary", result["data"])
        self.assertEqual(result["data"]["summary"]["week_start"], "2024-01-15")

    def test_get_pnl_attribution_response_format(self) -> None:
        """归因分析 API 应返回正确格式。"""
        result = get_pnl_attribution(days=30)
        self.assertIn("data", result)
        self.assertIn("error", result)
        self.assertIn("meta", result)
        self.assertIn("attribution", result["data"])

    def test_get_strategy_performance_response_format(self) -> None:
        """策略表现 API 应返回正确格式。"""
        result = get_strategy_performance()
        self.assertIn("data", result)
        self.assertIn("error", result)
        self.assertIn("meta", result)
        self.assertIn("performances", result["data"])

    def test_get_trade_history_response_format(self) -> None:
        """交易历史 API 应返回正确格式。"""
        result = get_trade_history(limit=50)
        self.assertIn("data", result)
        self.assertIn("error", result)
        self.assertIn("meta", result)
        self.assertIn("trades", result["data"])
        self.assertIn("count", result["data"])


if __name__ == "__main__":
    unittest.main()
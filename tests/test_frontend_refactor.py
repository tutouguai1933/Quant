from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_APP = REPO_ROOT / "apps" / "web" / "app"
WEB_COMPONENTS = REPO_ROOT / "apps" / "web" / "components"


class FrontendRefactorTests(unittest.TestCase):
    def test_shared_shell_components_exist(self) -> None:
        expected_files = [
            WEB_COMPONENTS / "app-shell.tsx",
            WEB_COMPONENTS / "page-hero.tsx",
            WEB_COMPONENTS / "metric-grid.tsx",
            WEB_COMPONENTS / "feedback-banner.tsx",
            WEB_COMPONENTS / "data-table.tsx",
        ]
        for file_path in expected_files:
            self.assertTrue(file_path.exists(), f"missing file: {file_path}")

    def test_homepage_becomes_guided_dashboard(self) -> None:
        content = (WEB_APP / "page.tsx").read_text(encoding="utf-8")
        self.assertIn("驾驶舱", content)
        self.assertIn("推荐下一步", content)
        self.assertIn("成功链路", content)
        self.assertIn("异常链路", content)

    def test_login_page_has_real_submission_flow(self) -> None:
        content = (WEB_APP / "login" / "page.tsx").read_text(encoding="utf-8")
        self.assertIn('action="/login/submit"', content)
        self.assertIn("登录反馈", content)
        self.assertIn("继续前往", content)

    def test_protected_pages_have_action_forms_and_feedback(self) -> None:
        expectations = {
            WEB_APP / "strategies" / "page.tsx": ["action=\"/actions\"", "策略中心", "两套首批波段策略", "白名单摘要", "最近执行结果", "执行器状态", "research_cockpit", "推荐策略", "执行决策", "执行建议", "执行器控制", "整台 Freqtrade 执行器", "研究分数", "研究解释", "模型版本"],
            WEB_APP / "tasks" / "page.tsx": ["action=\"/actions\"", "任务反馈", "触发训练"],
            WEB_APP / "signals" / "page.tsx": ["action=\"/actions\"", "运行 Qlib 信号流水线", "运行演示信号流水线", "最新信号", "研究训练", "研究推理", "最近研究结果"],
        }
        for file_path, patterns in expectations.items():
            content = file_path.read_text(encoding="utf-8")
            for pattern in patterns:
                self.assertIn(pattern, content)

    def test_protected_forms_no_longer_expose_token_inputs(self) -> None:
        page_files = [
            WEB_APP / "page.tsx",
            WEB_APP / "strategies" / "page.tsx",
            WEB_APP / "tasks" / "page.tsx",
        ]
        for file_path in page_files:
            content = file_path.read_text(encoding="utf-8")
            self.assertNotIn('name="token"', content)

    def test_security_helpers_sanitize_redirects_and_validate_sessions(self) -> None:
        session_content = (REPO_ROOT / "apps" / "web" / "lib" / "session.ts").read_text(encoding="utf-8")
        actions_content = (WEB_APP / "actions" / "route.ts").read_text(encoding="utf-8")
        login_submit_content = (WEB_APP / "login" / "submit" / "route.ts").read_text(encoding="utf-8")
        api_content = (REPO_ROOT / "apps" / "web" / "lib" / "api.ts").read_text(encoding="utf-8")

        self.assertIn("normalizeAppPath", session_content)
        self.assertIn("getControlSessionState", session_content)
        self.assertNotIn("formData.get(\"token\")", actions_content)
        self.assertIn("normalizeAppPath", actions_content)
        self.assertIn("getAdminSession", actions_content)
        self.assertIn("/signals/pipeline/run?source=qlib", actions_content)
        self.assertIn("normalizeAppPath", login_submit_content)
        self.assertIn("/auth/model", api_content)
        self.assertIn("truthSource", api_content)

    def test_login_page_uses_real_session_state(self) -> None:
        content = (WEB_APP / "login" / "page.tsx").read_text(encoding="utf-8")
        self.assertIn("getControlSessionState", content)
        self.assertIn("isAuthenticated={session.isAuthenticated}", content)

    def test_navigation_tag_changes_with_session_state(self) -> None:
        content = (WEB_COMPONENTS / "app-shell.tsx").read_text(encoding="utf-8")
        self.assertIn('isAuthenticated ? "已解锁" : "需登录"', content)

    def test_balances_page_uses_real_api_and_summary_copy(self) -> None:
        content = (WEB_APP / "balances" / "page.tsx").read_text(encoding="utf-8")
        self.assertIn("listBalances", content)
        self.assertIn("余额", content)
        self.assertIn("真实账户余额", content)
        self.assertIn("交易所零头", content)
        self.assertIn("可交易资产", content)
        self.assertIn("source:", content)
        self.assertIn("truth source:", content)
        self.assertIn("Sellable", content)

    def test_orders_and_positions_pages_show_sync_source_copy(self) -> None:
        orders_content = (WEB_APP / "orders" / "page.tsx").read_text(encoding="utf-8")
        positions_content = (WEB_APP / "positions" / "page.tsx").read_text(encoding="utf-8")

        self.assertIn("同步来源", orders_content)
        self.assertIn("同步来源", positions_content)
        self.assertIn("交易所零头", orders_content)
        self.assertIn("交易所零头", positions_content)

    def test_strategies_page_focuses_on_execution_not_chart_explanation(self) -> None:
        content = (WEB_APP / "strategies" / "page.tsx").read_text(encoding="utf-8")

        self.assertIn("执行器状态", content)
        self.assertIn("执行器控制", content)
        self.assertIn("最近执行结果", content)
        self.assertIn("推荐策略", content)
        self.assertIn("执行决策", content)
        self.assertIn("当前跟进对象", content)
        self.assertIn("这里不再重复看图", content)
        self.assertIn("账户收口", content)
        self.assertIn("余额页", content)
        self.assertIn("订单页", content)
        self.assertIn("持仓页", content)
        self.assertNotIn("图表图层摘要", content)
        self.assertNotIn("止损参考", content)

    def test_strategy_card_drops_explanatory_research_fields(self) -> None:
        content = (WEB_APP / "strategies" / "page.tsx").read_text(encoding="utf-8")
        strategy_card_section = content.split("function StrategyCard", 1)[1]

        self.assertNotIn("研究倾向：", strategy_card_section)
        self.assertNotIn("判断信心：", strategy_card_section)
        self.assertNotIn("主判断：", strategy_card_section)
        self.assertNotIn("研究门控：", strategy_card_section)
        self.assertIn("研究解释：", strategy_card_section)
        self.assertIn("模型版本：", strategy_card_section)
        self.assertIn("研究分数：", strategy_card_section)


if __name__ == "__main__":
    unittest.main()

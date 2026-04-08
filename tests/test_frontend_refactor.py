from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_APP = REPO_ROOT / "apps" / "web" / "app"
WEB_COMPONENTS = REPO_ROOT / "apps" / "web" / "components"


class FrontendRefactorTests(unittest.TestCase):
    def test_frontend_source_does_not_mix_localhost_with_loopback_ip(self) -> None:
        excluded_parts = {"node_modules"}
        for file_path in (REPO_ROOT / "apps" / "web").rglob("*"):
            if not file_path.is_file():
                continue
            if any(part in excluded_parts or part.startswith(".next") for part in file_path.parts):
                continue
            content = file_path.read_text(encoding="utf-8")
            self.assertNotIn("localhost", content, f"frontend source should avoid localhost: {file_path}")

    def test_shared_shell_components_exist(self) -> None:
        expected_files = [
            WEB_COMPONENTS / "app-shell.tsx",
            WEB_COMPONENTS / "page-hero.tsx",
            WEB_COMPONENTS / "metric-grid.tsx",
            WEB_COMPONENTS / "feedback-banner.tsx",
            WEB_COMPONENTS / "data-table.tsx",
            WEB_COMPONENTS / "research-candidate-board.tsx",
            WEB_COMPONENTS / "form-submit-button.tsx",
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
        self.assertIn("autoComplete=\"current-password\"", content)
        self.assertNotIn("placeholder=\"1933\"", content)

    def test_login_submit_route_keeps_absolute_redirects(self) -> None:
        content = (WEB_APP / "login" / "submit" / "route.ts").read_text(encoding="utf-8")
        self.assertIn("buildRedirectUrl", content)
        self.assertIn('from "../../../lib/redirect"', content)
        self.assertIn("loginAdmin(username, password, request)", content)

    def test_frontend_redirect_routes_share_same_host_helper(self) -> None:
        actions_content = (WEB_APP / "actions" / "route.ts").read_text(encoding="utf-8")
        logout_content = (WEB_APP / "logout" / "submit" / "route.ts").read_text(encoding="utf-8")
        redirect_helper = (REPO_ROOT / "apps" / "web" / "lib" / "redirect.ts").read_text(encoding="utf-8")
        proxy_route = (WEB_APP / "api" / "control" / "[...path]" / "route.ts").read_text(encoding="utf-8")

        self.assertIn("buildRedirectUrl", actions_content)
        self.assertIn("buildRedirectUrl", logout_content)
        self.assertIn("buildProxyUrl", actions_content)
        self.assertIn("x-forwarded-host", redirect_helper)
        self.assertIn("automation_dry_run_only", actions_content)
        self.assertIn("automation_kill_switch", actions_content)
        self.assertIn("automation_manual_takeover", actions_content)
        self.assertIn("export async function POST", proxy_route)
        self.assertIn("Authorization", proxy_route)
        self.assertIn("buildUpstreamApiUrl", proxy_route)

    def test_frontend_debug_loopback_prefers_request_port(self) -> None:
        content = (REPO_ROOT / "apps" / "web" / "lib" / "api.ts").read_text(encoding="utf-8")

        marker = "const configuredBaseUrl = ("
        start = content.index(marker)
        end = content.index(").replace(", start)
        expression = content[start:end]

        self.assertLess(
            expression.index("deriveLocalApiBaseUrl(request)"),
            expression.index("process.env.QUANT_API_BASE_URL"),
        )

    def test_frontend_debug_loopback_reads_request_host_headers(self) -> None:
        content = (REPO_ROOT / "apps" / "web" / "lib" / "api.ts").read_text(encoding="utf-8")

        helper_section = content.split("function deriveLocalApiBaseUrl(request?: Request): string | null {", 1)[1].split(
            "function isLoopbackHost(",
            1,
        )[0]

        self.assertIn('request.headers.get("x-forwarded-host")', helper_section)
        self.assertIn('request.headers.get("host")', helper_section)

    def test_protected_pages_have_action_forms_and_feedback(self) -> None:
        expectations = {
            WEB_APP / "strategies" / "page.tsx": ["action=\"/actions\"", "策略中心", "双栏布局", "左边看判断", "右边看执行", "当前推荐执行候选", "研究候选", "自动化判断", "自动化推荐", "下一步动作", "执行器状态", "当前配置摘要", "研究范围", "研究 / dry-run 候选池", "live 子集", "验证策略", "自动化策略", "执行安全门配置", "live_allowed_symbols", "账户收口", "执行动作", "候选池摘要", "最近执行结果", "research_cockpit", "推荐策略", "整台 Freqtrade 执行器", "研究分数", "研究解释", "模型版本", "是否允许进入 dry-run", "为什么现在先推进这个币", "候选池先筛，live 子集后放", "运行中…"],
            WEB_APP / "tasks" / "page.tsx": ["action=\"/actions\"", "自动化控制台", "自动化模式", "统一调度入口", "统一复盘", "健康摘要", "最近告警", "今日摘要", "调度顺序", "失败规则", "dry-run only", "Kill Switch", "当前阻塞", "接管建议", "恢复步骤", "告警摘要", "风险等级摘要", "恢复清单", "执行安全门", "研究 / dry-run 候选池", "live 子集", "当前放行口径", "自动化冷却时间", "每日最大轮次", "自动化运行参数", "长时间接管阈值", "活跃告警窗口", "最近告警历史", "活跃告警", "comparison_run_limit", "现在先处理什么", "调度什么时候继续", "人工接管后怎么恢复", "运行中…"],
            WEB_APP / "signals" / "page.tsx": ["action=\"/actions\"", "运行 Qlib 信号流水线", "运行演示信号流水线", "自动化入口", "当前模式", "下一步动作", "最新信号", "研究训练", "研究推理", "最近研究结果", "候选排行榜", "可进入 dry-run", "下一步动作", "统一研究报告", "最近实验摘要", "筛选通过率", "当前最佳候选", "运行中…"],
        }
        for file_path, patterns in expectations.items():
            content = file_path.read_text(encoding="utf-8")
            for pattern in patterns:
                self.assertIn(pattern, content)
        tasks_content = (WEB_APP / "tasks" / "page.tsx").read_text(encoding="utf-8")
        automation_cycle_card_content = (WEB_COMPONENTS / "automation-last-cycle-card.tsx").read_text(encoding="utf-8")
        self.assertIn('action="automation_manual_takeover"', tasks_content)
        self.assertIn("AutomationLastCycleCard", tasks_content)
        for pattern in ["本轮自动化判断", "推荐策略实例", "派发结果", "失败原因"]:
            self.assertIn(pattern, automation_cycle_card_content)

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

        self.assertIn("双栏布局", content)
        self.assertIn("左边看判断", content)
        self.assertIn("右边看执行", content)
        self.assertIn("执行器状态", content)
        self.assertIn("当前配置摘要", content)
        self.assertIn("研究范围", content)
        self.assertIn("验证策略", content)
        self.assertIn("自动化策略", content)
        self.assertIn("执行安全门配置", content)
        self.assertIn("live_allowed_symbols", content)
        self.assertIn("为什么现在先推进这个币", content)
        self.assertIn("候选池先筛，live 子集后放", content)
        self.assertIn("执行动作", content)
        self.assertIn("最近执行结果", content)
        self.assertIn("推荐策略", content)
        self.assertIn("当前跟进对象", content)
        self.assertIn("账户收口", content)
        self.assertIn("余额页", content)
        self.assertIn("订单页", content)
        self.assertIn("持仓页", content)
        self.assertNotIn("图表图层摘要", content)
        self.assertNotIn("止损参考", content)
        self.assertNotIn("执行决策", content)
        self.assertNotIn("执行器控制", content)

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

    def test_research_candidate_fallback_does_not_claim_ready(self) -> None:
        content = (REPO_ROOT / "apps" / "web" / "lib" / "api.ts").read_text(encoding="utf-8")

        fallback_section = content.split("export function getResearchCandidatesFallback()", 1)[1].split("export function getPositionsPageModel()", 1)[0]
        self.assertIn("candidate_count: 0", fallback_section)
        self.assertIn("ready_count: 0", fallback_section)
        self.assertIn("candidates: []", fallback_section)

    def test_api_module_exposes_research_report_and_workspace_recommendation(self) -> None:
        content = (REPO_ROOT / "apps" / "web" / "lib" / "api.ts").read_text(encoding="utf-8")

        self.assertIn("getResearchReport", content)
        self.assertIn("research_recommendation", content)

    def test_research_candidate_board_shows_screening_and_backtest_copy(self) -> None:
        content = (WEB_COMPONENTS / "research-candidate-board.tsx").read_text(encoding="utf-8")

        self.assertIn("筛选通过率", content)
        self.assertIn("失败原因", content)
        self.assertIn("回测收益", content)
        self.assertIn("最大回撤", content)
        self.assertIn("Sharpe", content)

    def test_status_badge_compresses_long_internal_status_labels(self) -> None:
        content = (WEB_COMPONENTS / "status-badge.tsx").read_text(encoding="utf-8")

        self.assertIn("supportive_but_not_triggering", content)
        self.assertIn("支持但未触发", content)
        self.assertIn("replaceAll(\"_\", \" \")", content)

    def test_research_and_evaluation_pages_expose_split_and_threshold_fields(self) -> None:
        research_content = (WEB_APP / "research" / "page.tsx").read_text(encoding="utf-8")
        features_content = (WEB_APP / "features" / "page.tsx").read_text(encoding="utf-8")
        backtest_content = (WEB_APP / "backtest" / "page.tsx").read_text(encoding="utf-8")
        evaluation_content = (WEB_APP / "evaluation" / "page.tsx").read_text(encoding="utf-8")

        self.assertIn("name=\"model_key\"", research_content)
        self.assertIn("训练/验证/测试切分比例", research_content)
        self.assertIn("name=\"train_split_ratio\"", research_content)
        self.assertIn("name=\"validation_split_ratio\"", research_content)
        self.assertIn("name=\"test_split_ratio\"", research_content)
        self.assertIn("name=\"signal_confidence_floor\"", research_content)
        self.assertIn("name=\"holding_window_label\"", research_content)
        self.assertIn("name=\"label_trigger_basis\"", research_content)
        self.assertIn("name=\"trend_weight\"", research_content)
        self.assertIn("name=\"momentum_weight\"", research_content)
        self.assertIn("name=\"volume_weight\"", research_content)
        self.assertIn("name=\"oscillator_weight\"", research_content)
        self.assertIn("name=\"volatility_weight\"", research_content)
        self.assertIn("name=\"strict_penalty_weight\"", research_content)
        self.assertIn("name=\"force_validation_top_candidate\"", research_content)
        self.assertIn("window_majority", research_content)
        self.assertIn("balanced_v3", research_content)
        self.assertIn("标签目标与止损说明", research_content)
        self.assertIn("因子明细表", features_content)
        self.assertIn("当前选中角色", features_content)
        self.assertIn("为什么现在更适合", evaluation_content)
        self.assertIn("这一轮更值得推进什么", evaluation_content)
        self.assertIn("先推荐谁", evaluation_content)
        self.assertIn("先淘汰谁", evaluation_content)
        self.assertIn("研究和执行差几步", evaluation_content)
        self.assertIn("还差什么才能进入下一阶段", evaluation_content)
        self.assertIn("研究与执行差异", evaluation_content)
        self.assertIn("name=\"timeframe_profiles.4h.trend_window\"", features_content)
        self.assertIn("name=\"timeframe_profiles.4h.rsi_period\"", features_content)
        self.assertIn("name=\"timeframe_profiles.4h.roc_period\"", features_content)
        self.assertIn("name=\"timeframe_profiles.4h.cci_period\"", features_content)
        self.assertIn("name=\"timeframe_profiles.4h.stoch_period\"", features_content)
        self.assertIn("name=\"timeframe_profiles.1h.breakout_lookback\"", features_content)
        self.assertIn("name=\"timeframe_profiles.1h.rsi_period\"", features_content)
        self.assertIn("name=\"timeframe_profiles.1h.roc_period\"", features_content)
        self.assertIn("name=\"timeframe_profiles.1h.cci_period\"", features_content)
        self.assertIn("name=\"timeframe_profiles.1h.stoch_period\"", features_content)
        self.assertIn("name=\"cost_model\"", backtest_content)
        self.assertIn("name=\"dry_run_min_net_return_pct\"", backtest_content)
        self.assertIn("name=\"dry_run_min_sharpe\"", backtest_content)
        self.assertIn("name=\"dry_run_max_drawdown_pct\"", backtest_content)
        self.assertIn("name=\"dry_run_max_loss_streak\"", backtest_content)
        self.assertIn("name=\"dry_run_min_win_rate\"", backtest_content)
        self.assertIn("name=\"dry_run_max_turnover\"", backtest_content)
        self.assertIn("name=\"dry_run_min_sample_count\"", backtest_content)
        self.assertIn("name=\"live_min_win_rate\"", backtest_content)
        self.assertIn("name=\"live_max_turnover\"", backtest_content)
        self.assertIn("name=\"live_min_sample_count\"", backtest_content)
        self.assertIn("name=\"strict_rule_min_ema20_gap_pct\"", backtest_content)
        self.assertIn("name=\"strict_rule_min_ema55_gap_pct\"", backtest_content)
        self.assertIn("name=\"strict_rule_max_atr_pct\"", backtest_content)
        self.assertIn("name=\"strict_rule_min_volume_ratio\"", backtest_content)
        self.assertIn("name=\"enable_rule_gate\"", backtest_content)
        self.assertIn("name=\"enable_validation_gate\"", backtest_content)
        self.assertIn("name=\"enable_backtest_gate\"", backtest_content)
        self.assertIn("name=\"enable_consistency_gate\"", backtest_content)
        self.assertIn("name=\"enable_live_gate\"", backtest_content)
        self.assertIn("按类别看当前启用情况", features_content)
        self.assertIn("name=\"enable_rule_gate\"", evaluation_content)
        self.assertIn("name=\"enable_validation_gate\"", evaluation_content)
        self.assertIn("name=\"enable_backtest_gate\"", evaluation_content)
        self.assertIn("name=\"enable_consistency_gate\"", evaluation_content)
        self.assertIn("name=\"enable_live_gate\"", evaluation_content)
        self.assertIn("name=\"dry_run_min_win_rate\"", evaluation_content)
        self.assertIn("name=\"dry_run_max_turnover\"", evaluation_content)
        self.assertIn("name=\"dry_run_min_sample_count\"", evaluation_content)
        self.assertIn("name=\"validation_min_sample_count\"", evaluation_content)
        self.assertIn("name=\"validation_min_avg_future_return_pct\"", evaluation_content)
        self.assertIn("name=\"consistency_max_validation_backtest_return_gap_pct\"", evaluation_content)
        self.assertIn("name=\"consistency_max_training_validation_positive_rate_gap\"", evaluation_content)
        self.assertIn("name=\"consistency_max_training_validation_return_gap_pct\"", evaluation_content)
        self.assertIn("name=\"rule_min_ema20_gap_pct\"", evaluation_content)
        self.assertIn("name=\"rule_min_ema55_gap_pct\"", evaluation_content)
        self.assertIn("name=\"rule_max_atr_pct\"", evaluation_content)
        self.assertIn("name=\"rule_min_volume_ratio\"", evaluation_content)
        self.assertIn("name=\"strict_rule_min_ema20_gap_pct\"", evaluation_content)
        self.assertIn("name=\"strict_rule_min_ema55_gap_pct\"", evaluation_content)
        self.assertIn("name=\"strict_rule_max_atr_pct\"", evaluation_content)
        self.assertIn("name=\"strict_rule_min_volume_ratio\"", evaluation_content)
        self.assertIn("实验对比与复盘窗口", evaluation_content)
        self.assertIn("name=\"review_limit\"", evaluation_content)
        self.assertIn("name=\"comparison_run_limit\"", evaluation_content)
        self.assertIn("实验对比窗口", evaluation_content)
        self.assertIn("最近训练实验快照", evaluation_content)
        self.assertIn("最近推理实验快照", evaluation_content)
        self.assertIn("更值得进入 dry-run", evaluation_content)
        self.assertIn("严格规则", backtest_content)
        self.assertIn("门控开关", backtest_content)
        self.assertIn("分组摘要", features_content)

    def test_tasks_page_highlights_takeover_and_recovery_guidance(self) -> None:
        content = (WEB_APP / "tasks" / "page.tsx").read_text(encoding="utf-8")

        self.assertIn("长期运行与人工接管", content)
        self.assertIn("当前阻塞", content)
        self.assertIn("接管建议", content)
        self.assertIn("恢复步骤", content)
        self.assertIn("告警摘要", content)
        self.assertIn("长期运行窗口", content)
        self.assertIn("今日轮次", content)
        self.assertIn("冷却剩余", content)
        self.assertIn("连续失败", content)
        self.assertIn("升级级别", content)
        self.assertIn("同步新鲜度", content)
        self.assertIn("最后成功时间", content)
        self.assertIn("自动化运行参数", content)
        self.assertIn("长时间接管阈值", content)
        self.assertIn("活跃告警窗口", content)
        self.assertIn("活跃错误", content)
        self.assertIn("最近复盘记录", content)
        self.assertIn("这里最多显示最近", content)
        self.assertIn("现在先处理什么", content)
        self.assertIn("调度什么时候继续", content)
        self.assertIn("人工接管后怎么恢复", content)

    def test_evaluation_page_explains_research_vs_execution_alignment(self) -> None:
        content = (WEB_APP / "evaluation" / "page.tsx").read_text(encoding="utf-8")

        self.assertIn("研究结果 vs 执行结果", content)
        self.assertIn("对齐结论", content)
        self.assertIn("执行现状", content)
        self.assertIn("差异说明", content)
        self.assertIn("建议动作", content)
        self.assertIn("执行对齐明细", content)
        self.assertIn("这一轮更值得推进什么", content)
        self.assertIn("先推荐谁", content)
        self.assertIn("先淘汰谁", content)
        self.assertIn("研究和执行差几步", content)
        self.assertIn("最近订单标的", content)
        self.assertIn("最近持仓标的", content)
        self.assertIn("实验对齐概况", content)
        self.assertIn("训练模型", content)
        self.assertIn("推理模型", content)
        self.assertIn("训练数据快照", content)
        self.assertIn("推理数据快照", content)
        self.assertIn("当前研究结果仍然基于这页右上角的最新门槛", content)
        self.assertIn("最近复盘记录", content)
        self.assertIn("最近训练实验", content)
        self.assertIn("最近推理实验", content)
        self.assertIn("去任务页看自动化", content)
        self.assertIn("为什么推荐", content)
        self.assertIn("为什么淘汰", content)
        self.assertIn("研究和执行差在哪里", content)
        self.assertIn("推荐摘要", content)
        self.assertIn("淘汰摘要", content)
        self.assertIn("差异摘要", content)

    def test_strategies_page_surfaces_manual_takeover_risk_state(self) -> None:
        content = (WEB_APP / "strategies" / "page.tsx").read_text(encoding="utf-8")

        self.assertIn("当前自动化状态", content)
        self.assertIn("当前已人工接管", content)
        self.assertIn("去任务页处理接管与恢复", content)

    def test_evaluation_page_mentions_alignment_explanation_sections(self) -> None:
        content = (WEB_APP / "evaluation" / "page.tsx").read_text(encoding="utf-8")

        self.assertIn("研究结果 vs 执行结果", content)
        self.assertIn("对齐解释", content)
        self.assertIn("最近执行摘要", content)


if __name__ == "__main__":
    unittest.main()

"""研究到执行仲裁服务测试。

这个文件负责验证研究推荐、执行状态和运行窗口会被压成统一仲裁结论。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.automation_workflow_service import AutomationWorkflowService  # noqa: E402
from services.api.app.services.research_execution_arbitration_service import (  # noqa: E402
    ResearchExecutionArbitrationService,
)


class ResearchExecutionArbitrationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._service = ResearchExecutionArbitrationService()

    @staticmethod
    def _evaluation_workspace(
        *,
        symbol: str = "ETHUSDT",
        stage: str = "dry_run",
        next_action: str = "go_dry_run",
        reason: str = "候选已经通过当前研究门控。",
        difference_summary: str = "研究侧推荐 ETHUSDT，但执行侧还没完全对齐。",
        difference_reasons: list[str] | None = None,
        latest_sync_status: str = "succeeded",
    ) -> dict[str, object]:
        return {
            "best_experiment": {
                "symbol": symbol,
                "recommended_stage": stage,
                "next_action": next_action,
                "reason": reason,
                "score": "0.88",
            },
            "recommendation_explanation": {
                "headline": f"{symbol} 当前值得继续推进",
                "detail": reason,
            },
            "elimination_explanation": {
                "headline": "当前没有主要淘汰项",
                "detail": "这一轮暂时没有额外淘汰说明。",
            },
            "stage_decision_summary": {
                "why_recommended": reason,
                "why_blocked": "当前没有额外淘汰说明。",
                "execution_gap": difference_summary,
                "next_step": next_action,
            },
            "alignment_details": {
                "research_symbol": symbol,
                "research_action": next_action,
                "alignment_state": "研究和执行暂未对齐",
                "runtime_mode": "dry-run",
                "latest_sync_status": latest_sync_status,
                "difference_summary": difference_summary,
                "difference_severity": "medium",
                "difference_reasons": difference_reasons or ["执行侧还没有最新对齐结果"],
                "next_step": "先补执行同步或 dry-run，再回来复核。",
            },
        }

    @staticmethod
    def _automation_status(
        *,
        mode: str = "auto_dry_run",
        manual_takeover: bool = False,
        paused: bool = False,
        blocked_reason: str = "",
        runtime_action: str = "run_next_cycle",
        latest_sync_status: str = "succeeded",
        execution_state: str = "dry-run",
        recovery_action: str = "healthy",
    ) -> dict[str, object]:
        return {
            "state": {
                "mode": mode,
                "manual_takeover": manual_takeover,
                "paused": paused,
                "paused_reason": "manual_takeover" if manual_takeover else "",
            },
            "runtime_window": {
                "blocked_reason": blocked_reason,
                "next_action": runtime_action,
                "ready_for_cycle": blocked_reason == "",
                "cooldown_remaining_minutes": 15 if blocked_reason == "cooldown_active" else 0,
                "story": {
                    "headline": "当前已经可以继续下一轮" if blocked_reason == "" else "当前仍在等待",
                    "why_not_resume": "当前还有阻塞。",
                },
            },
            "resume_status": {
                "waiting_for": "none" if blocked_reason == "" else blocked_reason,
                "resume_needed": blocked_reason in {"manual_takeover_active", "paused_waiting_review"},
                "resume_ready": False,
                "continue_after_resume": False,
                "cannot_resume_reason": "当前还有阻塞。" if blocked_reason else "",
            },
            "execution_health": {
                "runtime_mode": "dry-run",
                "latest_sync_status": latest_sync_status,
                "recovery_action": recovery_action,
                "execution_state": {
                    "state": execution_state,
                    "detail": "执行链状态正常",
                },
            },
            "active_blockers": [],
            "operator_actions": [],
            "control_actions": [],
        }

    def test_returns_wait_sync_when_research_is_ready_but_execution_not_aligned(self) -> None:
        decision = self._service.build_decision(
            evaluation_workspace=self._evaluation_workspace(
                next_action="go_dry_run",
                difference_summary="研究侧推荐 ETHUSDT，但执行侧还没完全对齐。",
                difference_reasons=["同步失败", "最近订单仍是 BTCUSDT"],
                latest_sync_status="failed",
            ),
            automation_status=self._automation_status(
                latest_sync_status="failed",
                recovery_action="retry_sync",
            ),
        )

        self.assertEqual(decision["status"], "wait_sync")
        self.assertEqual(decision["symbol"], "ETHUSDT")
        self.assertEqual(decision["recommended_stage"], "dry_run")
        self.assertEqual(decision["suggested_action"]["action"], "review_sync")
        self.assertTrue(decision["blocking_items"])

    def test_returns_continue_research_when_execution_is_present_but_research_is_not_ready(self) -> None:
        decision = self._service.build_decision(
            evaluation_workspace=self._evaluation_workspace(
                stage="research",
                next_action="continue_research",
                reason="当前候选还没稳定通过研究门控。",
                difference_summary="研究结果还没准备好，先别推进执行。",
                difference_reasons=["当前还没有研究候选，先补研究结果。"],
            ),
            automation_status=self._automation_status(
                mode="auto_live",
                latest_sync_status="succeeded",
                execution_state="live",
            ),
        )

        self.assertEqual(decision["status"], "continue_research")
        self.assertEqual(decision["suggested_action"]["target_page"], "/research")
        self.assertIn("研究", decision["headline"])
        self.assertTrue(decision["blocking_items"])

    def test_returns_manual_takeover_when_takeover_is_active(self) -> None:
        decision = self._service.build_decision(
            evaluation_workspace=self._evaluation_workspace(next_action="go_live", stage="live"),
            automation_status=self._automation_status(
                mode="auto_live",
                manual_takeover=True,
                paused=True,
                blocked_reason="manual_takeover_active",
                runtime_action="manual_takeover",
            ),
        )

        self.assertEqual(decision["status"], "manual_takeover")
        self.assertEqual(decision["suggested_action"]["target_page"], "/tasks")
        self.assertIn("人工接管", decision["headline"])
        self.assertTrue(decision["blocking_items"])

    def test_returns_cooldown_when_runtime_window_is_waiting(self) -> None:
        decision = self._service.build_decision(
            evaluation_workspace=self._evaluation_workspace(next_action="go_dry_run"),
            automation_status=self._automation_status(
                blocked_reason="cooldown_active",
                runtime_action="wait_cooldown",
            ),
        )

        self.assertEqual(decision["status"], "cooldown")
        self.assertEqual(decision["suggested_action"]["action"], "wait_cooldown")
        self.assertIn("冷却", decision["headline"])
        self.assertTrue(decision["blocking_items"])

    def test_returns_manual_mode_when_runtime_is_still_manual(self) -> None:
        decision = self._service.build_decision(
            evaluation_workspace=self._evaluation_workspace(next_action="go_dry_run"),
            automation_status=self._automation_status(
                mode="manual",
                blocked_reason="manual_mode",
                runtime_action="manual_review",
                execution_state="manual",
            ),
        )

        self.assertEqual(decision["status"], "manual_mode")
        self.assertEqual(decision["suggested_action"]["target_page"], "/tasks")
        self.assertIn("手动模式", decision["headline"])
        self.assertTrue(decision["blocking_items"])

    def test_returns_wait_window_when_daily_limit_is_reached(self) -> None:
        decision = self._service.build_decision(
            evaluation_workspace=self._evaluation_workspace(next_action="go_dry_run"),
            automation_status=self._automation_status(
                blocked_reason="daily_limit_reached",
                runtime_action="wait_next_window",
            ),
        )

        self.assertEqual(decision["status"], "wait_window")
        self.assertEqual(decision["suggested_action"]["action"], "wait_next_window")
        self.assertTrue(decision["blocking_items"])

    def test_returns_go_live_when_live_stage_is_ready(self) -> None:
        decision = self._service.build_decision(
            evaluation_workspace=self._evaluation_workspace(
                stage="live",
                next_action="go_live",
                reason="当前候选已经满足 live 准入条件。",
                difference_summary="研究标的、最近订单和最近持仓已经对上",
                difference_reasons=["当前没有明显差异"],
            ),
            automation_status=self._automation_status(
                mode="auto_live",
                latest_sync_status="succeeded",
                execution_state="live",
            ),
        )

        self.assertEqual(decision["status"], "go_live")
        self.assertEqual(decision["suggested_action"]["action"], "enter_live")
        self.assertEqual(decision["recommended_stage"], "live")

    def test_normalizes_stage_and_execution_state_variants(self) -> None:
        decision = self._service.build_decision(
            evaluation_workspace=self._evaluation_workspace(
                stage=" DRY-RUN ",
                next_action=" GO_DRY_RUN ",
                reason="当前候选已经满足 dry-run 准入条件。",
                difference_summary="研究标的、最近订单和最近持仓已经对上",
                difference_reasons=["当前没有明显差异"],
            ),
            automation_status=self._automation_status(
                latest_sync_status="succeeded",
                execution_state=" DRY-RUN ",
            ),
        )

        self.assertEqual(decision["status"], "go_dry_run")
        self.assertEqual(decision["recommended_stage"], "dry_run")

    def test_returns_safe_fallback_when_evaluation_workspace_is_unavailable(self) -> None:
        def _raise_workspace_error() -> dict[str, object]:
            raise RuntimeError("workspace unavailable")

        service = ResearchExecutionArbitrationService(evaluation_reader=_raise_workspace_error)

        decision = service.build_decision(
            automation_status=self._automation_status(),
        )

        self.assertEqual(decision["status"], "continue_research")
        self.assertEqual(decision["symbol"], "")
        self.assertEqual(decision["suggested_action"]["target_page"], "/research")
        self.assertTrue(decision["blocking_items"])

    def test_automation_workflow_status_exposes_arbitration_payload(self) -> None:
        scheduler = mock.Mock()
        scheduler.get_health_summary.return_value = {}
        automation = mock.Mock()
        automation.get_status.return_value = {
            "state": {
                "mode": "auto_dry_run",
                "paused": False,
                "manual_takeover": False,
                "daily_summary": {"cycle_count": 0},
                "last_cycle": {},
            },
            "automation_config": {"long_run_seconds": 300, "alert_cleanup_minutes": 15},
            "execution_policy": {"status": "ready"},
            "daily_summary": {"cycle_count": 0},
        }
        automation.build_health_summary.return_value = {
            "resume_checklist": [],
            "active_blockers": [],
            "operator_actions": [],
            "control_actions": [],
            "takeover_summary": {},
            "alert_summary": {},
        }
        reviewer = mock.Mock()
        reviewer.build_report.return_value = {"overview": {}}
        syncer = mock.Mock()
        syncer.get_execution_health_summary.return_value = {
            "runtime_mode": "dry-run",
            "latest_sync_status": "succeeded",
            "execution_state": {"state": "manual"},
            "recovery_action": "healthy",
        }
        arbiter = mock.Mock()
        arbiter.build_decision.return_value = {
            "status": "go_dry_run",
            "headline": "当前可以进入 dry-run",
            "detail": "研究和执行条件已经具备。",
            "symbol": "ETHUSDT",
            "recommended_stage": "dry_run",
            "research_action": "go_dry_run",
            "reason_items": ["研究推荐已经就绪"],
            "blocking_items": [],
            "suggested_action": {
                "action": "enter_dry_run",
                "label": "去策略页确认 dry-run",
                "target_page": "/strategies",
            },
            "inputs": {"mode": "auto_dry_run"},
        }

        workflow = AutomationWorkflowService(
            scheduler=scheduler,
            automation=automation,
            reviewer=reviewer,
            syncer=syncer,
            arbiter=arbiter,
        )

        status = workflow.get_status()

        self.assertIn("arbitration", status)
        self.assertEqual(status["arbitration"]["status"], "go_dry_run")
        self.assertEqual(status["arbitration"]["suggested_action"]["target_page"], "/strategies")
        arbiter.build_decision.assert_called_once()

    def test_automation_workflow_status_falls_back_when_arbiter_raises(self) -> None:
        scheduler = mock.Mock()
        scheduler.get_health_summary.return_value = {}
        automation = mock.Mock()
        automation.get_status.return_value = {
            "state": {
                "mode": "auto_dry_run",
                "paused": False,
                "manual_takeover": False,
                "daily_summary": {"cycle_count": 0},
                "last_cycle": {},
            },
            "automation_config": {"long_run_seconds": 300, "alert_cleanup_minutes": 15},
            "execution_policy": {"status": "ready"},
            "daily_summary": {"cycle_count": 0},
        }
        automation.build_health_summary.return_value = {
            "resume_checklist": [],
            "active_blockers": [],
            "operator_actions": [],
            "control_actions": [],
            "takeover_summary": {},
            "alert_summary": {},
        }
        reviewer = mock.Mock()
        reviewer.build_report.return_value = {"overview": {}}
        syncer = mock.Mock()
        syncer.get_execution_health_summary.return_value = {
            "runtime_mode": "dry-run",
            "latest_sync_status": "succeeded",
            "execution_state": {"state": "manual"},
            "recovery_action": "healthy",
        }
        arbiter = mock.Mock()
        arbiter.build_decision.side_effect = RuntimeError("arbiter unavailable")

        workflow = AutomationWorkflowService(
            scheduler=scheduler,
            automation=automation,
            reviewer=reviewer,
            syncer=syncer,
            arbiter=arbiter,
        )

        status = workflow.get_status()

        self.assertIn("arbitration", status)
        self.assertEqual(status["arbitration"]["status"], "continue_research")
        self.assertEqual(status["arbitration"]["suggested_action"]["target_page"], "/research")


if __name__ == "__main__":
    unittest.main()

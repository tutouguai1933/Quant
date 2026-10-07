"""验证自动化 ML 等待模型不派单、不报警，以及历史展示保持真实风险和原文。"""
from __future__ import annotations

import json
from unittest import mock

from services.api.app.services.automation_workflow_service import AutomationWorkflowService
from services.api.app.services.automation_cycle_history_service import AutomationCycleHistoryService
from services.api.tests import test_automation_service as fixtures


WAITING_DETAIL = "尚无合格生产模型，继续研究并等待下一轮验证。"
LEGACY_MESSAGE = "模型使用旧评估，需按新协议验证"


def _workflow(monkeypatch, mode):
    """只执行真实工作流分支，所有任务、状态与执行器均为无副作用测试桩。"""
    automation = mock.Mock()
    automation.get_state.return_value = {
        "mode": mode, "paused": False, "armed_symbol": "", "manual_takeover": False,
        "daily_summary": {"cycle_count": 0}, "last_cycle": {},
    }
    automation.build_health_summary.return_value = {"run_health": {}}
    scheduler = fixtures._FakeScheduler()
    dispatcher = mock.Mock()
    monkeypatch.setattr("services.api.app.services.automation_workflow_service.CycleLock", lambda: mock.Mock(acquire=mock.Mock(return_value=True)))
    workflow = AutomationWorkflowService(
        scheduler=scheduler, automation=automation, dispatcher=dispatcher,
        research=mock.Mock(), signals=mock.Mock(), arbiter=mock.Mock(),
        reviewer=fixtures._FakeReviewer(), syncer=fixtures._FakeSyncService(runtime_mode="dry-run"),
    )
    monkeypatch.setattr(workflow, "_get_operations_config", lambda: {"review_limit": 10, "auto_pause_on_error": True})
    monkeypatch.setattr(workflow, "_check_and_prepare_retrain", lambda **kwargs: {"should_retrain": False})
    monkeypatch.setattr(workflow, "_should_skip_training", lambda **kwargs: (False, ""))
    monkeypatch.setattr(workflow, "_build_priority_queue_payload", lambda **kwargs: {
        "items": [], "summary": {"model_waiting": True, "ready_count": 0,
                                   "detail": WAITING_DETAIL, "strategy_family": "automation_ml"},
    })
    return workflow, automation, scheduler, dispatcher


def test_model_waiting_cycle_keeps_research_running_without_dispatch_or_alerts(monkeypatch):
    """dry-run/live 都应等待合格模型，不能推荐 RSI 策略ID或触发交易与暂停。"""
    for mode in ("auto_dry_run", "auto_live"):
        workflow, automation, scheduler, dispatcher = _workflow(monkeypatch, mode)
        result = workflow.run_cycle(source="openclaw")
        assert result["status"] == "waiting"
        assert result["failure_reason"] == "awaiting_model"
        assert result["next_action"] == "continue_research"
        assert result["message"] == WAITING_DETAIL
        assert result["recommended_symbol"] == ""
        assert result["recommended_strategy_id"] == 0
        assert result["strategy_family"] == "automation_ml"
        assert result["source"] == "openclaw"
        assert result["dispatch"] is None
        assert [name for name, _ in scheduler.named_calls] == ["research_train", "research_infer", "signal_output", "review"]
        dispatcher.dispatch_latest_signal.assert_not_called()
        automation.record_alert.assert_not_called()
        automation.pause.assert_not_called()
        automation.manual_takeover.assert_not_called()
        automation.arm_symbol.assert_not_called()
        automation.record_cycle.assert_called_once()


def test_new_awaiting_model_history_is_waiting_model_with_ml_family(tmp_path):
    """新等待记录正确归属自动化ML，原始状态不伪装成派单失败。"""
    service = AutomationCycleHistoryService(state_path=tmp_path / "history.json")
    service.record_cycle({"status": "waiting", "failure_reason": "awaiting_model",
                          "mode": "auto_dry_run", "source": "openclaw",
                          "strategy_family": "automation_ml", "recommended_symbol": "",
                          "message": WAITING_DETAIL, "next_action": "continue_research"})
    record = service.get_history()[0]
    assert record["display_status"] == "waiting_model"
    assert record["source"] == "openclaw"
    assert record["strategy_family"] == "automation_ml"
    assert record["message"] == WAITING_DETAIL
    assert record["failure_reason"] == "awaiting_model"
    assert record["recommended_symbol"] == ""
    assert service.get_summary()["blocked_count"] == 0
    assert service.get_summary()["failed_count"] == 0


def _legacy_history(tmp_path, record):
    """将旧格式写入临时文件，返回原始字节用于确认读时转换不改写历史。"""
    path = tmp_path / "history.json"
    path.write_text(json.dumps({"records": [record]}, ensure_ascii=False), encoding="utf-8")
    return path, path.read_bytes(), AutomationCycleHistoryService(state_path=path)


def test_legacy_global_model_block_is_displayed_as_waiting_without_rewriting_original(tmp_path):
    """旧全局模型阻断只规范展示字段，保留原始状态、消息和文件。"""
    original = {"recorded_at": "2026-10-07T17:15:15+00:00", "status": "waiting",
                "display_status": "blocked", "failure_reason": "candidate_blocked",
                "recommended_symbol": "ORDIUSDT", "message": LEGACY_MESSAGE,
                "candidates": [{"symbol": "ORDIUSDT", "dry_run_gate_status": "blocked",
                                "dry_run_gate_reasons": [LEGACY_MESSAGE, "研究信号不能执行"]}]}
    path, original_bytes, service = _legacy_history(tmp_path, original)
    record = service.get_history()[0]
    assert record["display_status"] == "waiting_model"
    assert "等待" in record["display_message"]
    assert record["message"] == original["message"]
    assert record["status"] == original["status"]
    assert record["failure_reason"] == original["failure_reason"]
    assert record["recommended_symbol"] == original["recommended_symbol"]
    assert record["strategy_family"] == "automation_ml"
    assert record.get("source", "") == ""
    assert service.get_summary()["blocked_count"] == 0
    assert path.read_bytes() == original_bytes


def test_real_risk_block_is_not_reclassified_as_model_waiting(tmp_path):
    """真实风险原因优先；即使附带模型文字也不能被转成普通模型等待。"""
    message = "风险预算不足；" + LEGACY_MESSAGE
    # 旧记录可能只有统一candidate_blocked；具体gate中的风险原因仍必须优先。
    for failure_reason in ("risk_blocked", "candidate_blocked"):
        original = {"recorded_at": "2026-10-07T17:15:15+00:00", "status": "waiting",
                    "display_status": "blocked", "failure_reason": failure_reason,
                    "recommended_symbol": "BTCUSDT", "message": message,
                    "strategy_family": "rsi", "source": "rsi",
                    "candidates": [{"symbol": "BTCUSDT", "dry_run_gate_status": "blocked",
                                    "dry_run_gate_reasons": ["risk_blocked", LEGACY_MESSAGE]}]}
        path, original_bytes, service = _legacy_history(tmp_path, original)
        record = service.get_history()[0]
        assert record["display_status"] == "blocked"
        assert record.get("display_message", message) == message
        assert record["message"] == message
        assert record["strategy_family"] == "rsi"
        assert record["source"] == "rsi"
        assert service.get_summary()["blocked_count"] == 1
        assert path.read_bytes() == original_bytes


def test_ai_history_with_real_risk_reason_keeps_blocked_status():
    """AI候选同时含模型和真实风控原因时，不能把风险掩盖为单纯等待。"""
    from services.api.app.services.automation_cycle_history_service import AutomationCycleHistoryService
    record = {"status":"waiting", "display_status":"blocked", "failure_reason":"candidate_blocked",
        "strategy_family":"automation_ml", "message":"模型使用旧评估，需按新协议验证",
        "candidates":[{"dry_run_gate_reasons":["模型使用旧评估，需按新协议验证","risk_blocked：风险预算不足"]}]}
    result=AutomationCycleHistoryService._present_record(record)
    assert result["display_status"]=="blocked"
    assert "display_message" not in result

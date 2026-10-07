"""全局AI模型未准入应等待模型，不伪装成单币被淘汰。"""
import pytest
from services.api.app.services.candidate_priority_service import CandidatePriorityService

SCOPE = {"status": "ready", "candidate_symbols": ["ORDIUSDT", "BTCUSDT"], "live_allowed_symbols": ["ORDIUSDT", "BTCUSDT"]}


def report(admission=False):
    """构造已有单币许可但全局模型未合格的隔离报告。"""
    return {"model_admission": {"passed": admission, "reasons": ["尚无通过新评估的生产模型"]},
            "candidates": [{"symbol": "ORDIUSDT", "next_action": "enter_live", "allowed_to_live": True,
                            "allowed_to_dry_run": True, "forced_for_validation": True,
                            "dry_run_gate": {"status": "passed"}, "live_gate": {"status": "passed"}}]}


def test_explicit_global_model_failure_overrides_coin_permissions():
    """全球模型失败覆盖live、dry-run和强制研究许可。"""
    queue = CandidatePriorityService().build_priority_queue(report=report(), candidate_scope=SCOPE)
    row = queue["items"][0]
    assert row["queue_status"] == "waiting_model"
    assert not row["allowed_to_live"] and not row["allowed_to_dry_run"] and not row["forced_for_validation"]
    assert row["next_action"] == "continue_research"
    assert row["recommended_stage"] == "research"
    assert "等待合格AI模型" in queue["summary"]["detail"]
    assert "尚无通过新评估的生产模型" in queue["summary"]["detail"]
    assert queue["summary"]["waiting_model_count"] == 1
    assert queue["summary"]["blocked_count"] == queue["summary"]["ready_count"] == 0
    assert queue["summary"]["active_symbol"] == ""


@pytest.mark.parametrize("mode", ["manual", "auto_dry_run", "auto_live"])
def test_dispatch_waits_for_model_without_active_coin(mode):
    """每种运行模式都等待合格模型，而非报告单币candidate_blocked。"""
    service = CandidatePriorityService()
    queue = service.build_priority_queue(report=report(), candidate_scope=SCOPE)
    dispatch = service.build_dispatch_queue(priority_queue=queue, mode=mode, armed_symbol="ORDIUSDT")
    assert dispatch["items"][0]["dispatch_status"] == "waiting"
    assert dispatch["items"][0]["dispatch_code"] == "awaiting_model"
    assert dispatch["summary"]["active_symbol"] == ""
    assert dispatch["summary"]["waiting_model_count"] == 1
    assert dispatch["summary"]["blocked_count"] == dispatch["summary"]["ready_count"] == 0
    assert "等待合格AI模型" in dispatch["summary"]["detail"]


def test_missing_admission_keeps_legacy_blocked_behavior():
    """缺模型准入字段不擅自改成等待，更不能为旧阻断候选放行。"""
    payload = report()
    payload.pop("model_admission")
    payload["candidates"][0].update(allowed_to_live=False, allowed_to_dry_run=False, next_action="continue_research")
    service = CandidatePriorityService()
    queue = service.build_priority_queue(report=payload, candidate_scope=SCOPE)
    assert queue["items"][0]["queue_status"] == "blocked"
    assert queue["summary"]["waiting_model_count"] == 0
    dispatch = service.build_dispatch_queue(priority_queue=queue, mode="auto_live", armed_symbol="")
    assert dispatch["items"][0]["dispatch_code"] == "candidate_blocked"


def test_passed_model_does_not_bypass_candidate_scope():
    """模型合格时仍保留原候选池与live范围门禁。"""
    queue = CandidatePriorityService().build_priority_queue(report=report(True), candidate_scope={"status": "ready", "candidate_symbols": ["BTCUSDT"], "live_allowed_symbols": ["BTCUSDT"]})
    assert queue["items"][0]["queue_status"] == "blocked"
    assert "候选池" in queue["summary"]["detail"]


def test_empty_failed_model_report_still_has_global_waiting_detail():
    """无单币候选时仍说明等待全局模型，不能报告某个币被阻断。"""
    payload = report()
    payload["candidates"] = []
    service = CandidatePriorityService()
    queue = service.build_priority_queue(report=payload, candidate_scope=SCOPE)
    dispatch = service.build_dispatch_queue(priority_queue=queue, mode="auto_live", armed_symbol="")
    assert "等待合格AI模型" in dispatch["summary"]["detail"]
    assert dispatch["summary"]["dispatch_status"] == "waiting"
    assert dispatch["summary"]["dispatch_code"] == "awaiting_model"
    assert dispatch["summary"]["active_symbol"] == ""

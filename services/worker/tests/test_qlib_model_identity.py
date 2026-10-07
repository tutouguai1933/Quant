"""验证研究候选使用实际预测模型的准入说明，不继承旧生产版本的原因。"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services.worker.qlib_config import load_qlib_config
from services.worker.qlib_runner import QlibRunner


def fixture(tmp_path):
    """准备新协议研究模型及旧生产指针，不拟合或加载模型。"""
    runner = QlibRunner(config=load_qlib_config(env={"QUANT_QLIB_RUNTIME_ROOT":str(tmp_path)}))
    path=tmp_path/"latest.txt"
    record=SimpleNamespace(version_id="new-staging", stage="staging", model_path=path,
        metrics={"val_auc":.52,"val_f1":0}, training_context={
            "evaluation_version":"ml_price_replay_v2","evaluation_available":True,
            "input_protocol":runner._model_input_protocol(), "prediction_semantics":"return_above_threshold_probability"})
    payload={"model_version":"training-artifact","metrics":{"registry_version_id":"new-staging","model_path":str(path)}}
    return runner,record,payload


def test_research_reason_belongs_to_actual_new_model(tmp_path):
    """已按新协议训练但未合格的模型不应被描述为仍在使用旧评估。"""
    runner,record,payload=fixture(tmp_path)
    old={"passed":False,"model_version":"old-prod","reasons":["模型使用旧评估，需按新协议验证"]}
    with patch("services.worker.model_registry.get_model_registry") as registry:
        registry.return_value.get_model.return_value=record
        admission=runner._resolve_research_admission(payload,rejected_production=old)
    assert admission["passed"] is False
    assert admission["stage"]=="staging"
    assert admission["model_version"]=="new-staging"
    assert not any("旧评估" in reason for reason in admission["reasons"])
    assert any("验证质量" in reason for reason in admission["reasons"])
    assert admission["rejected_production"]["model_version"]=="old-prod"


def test_good_staging_is_never_promoted_by_explanation_fix(tmp_path):
    """研究模型即使指标良好仍需正式晋升，不能被本次修复放行。"""
    runner,record,payload=fixture(tmp_path)
    record.metrics={"val_auc":.8,"val_f1":.7}
    with patch("services.worker.model_registry.get_model_registry") as registry:
        registry.return_value.get_model.return_value=record
        admission=runner._resolve_research_admission(payload,rejected_production={"passed":False,"reasons":[]})
        registry.return_value.promote.assert_not_called()
    assert not admission["passed"]
    assert "模型未晋升生产" in admission["reasons"]


def test_unregistered_research_model_is_explicitly_unavailable(tmp_path):
    """注册失败也不能借旧生产版本身份产生执行候选。"""
    runner,_,payload=fixture(tmp_path)
    with patch("services.worker.model_registry.get_model_registry") as registry:
        registry.return_value.get_model.return_value=None
        admission=runner._resolve_research_admission(payload,rejected_production={"passed":False,"reasons":["旧生产"]})
    assert not admission["passed"]
    assert admission["model_version"]=="new-staging"
    assert any("未登记" in reason for reason in admission["reasons"])

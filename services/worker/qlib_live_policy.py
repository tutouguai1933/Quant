"""自动化 ML 策略的实时行情与执行准入；不参与 RSI 自然入场。"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from services.worker.qlib_features import build_feature_rows

EVALUATION_VERSION = "ml_price_replay_v2"
UPSIDE_PROBABILITY = "return_above_threshold_probability"
ML_ENTRY_TAG_PREFIX = "quant-ml:"


@dataclass(frozen=True)
class LivePolicy:
    """统一配置模型质量与信号过期限制。"""
    min_auc: float = .55
    promotion_improvement: float = .01
    max_feature_age_bars: int = 2
    max_prediction_age_seconds: int = 3600


def load_live_policy() -> LivePolicy:
    """读取独立于 RSI 参数的自动化模型准入配置。"""
    policy = LivePolicy(
        min_auc=float(os.getenv("QUANT_QLIB_MODEL_MIN_AUC", ".55")),
        promotion_improvement=float(os.getenv("QUANT_QLIB_PROMOTION_MIN_IMPROVEMENT", ".01")),
        max_feature_age_bars=int(os.getenv("QUANT_QLIB_FEATURE_MAX_AGE_BARS", "2")),
        max_prediction_age_seconds=int(os.getenv("QUANT_QLIB_PREDICTION_MAX_AGE_SECONDS", "3600")),
    )
    if not (.5 < policy.min_auc <= 1) or not math.isfinite(policy.promotion_improvement) or policy.promotion_improvement < 0 or min(policy.max_feature_age_bars, policy.max_prediction_age_seconds) <= 0:
        raise ValueError("自动化模型准入配置无效")
    return policy


def hide_legacy_evaluation(artifact):
    """旧评估仅保留原始历史文件，读取结果不再展示无效绩效或放行旧候选。"""
    if not isinstance(artifact, dict):
        return artifact
    result = dict(artifact)
    legacy = False
    backtest = artifact.get("backtest")
    if isinstance(backtest, dict) and backtest.get("evaluation_version") != EVALUATION_VERSION:
        result["backtest"] = {**backtest, "evaluation_status": "unavailable", "unavailable_reason": "旧回测包含未来信息，需使用新评估协议重新验证",
                              "metrics": {}, "series": {"performance": []}}
        legacy = True
    if "signals" in artifact and "model_admission" not in artifact:
        candidates = dict(artifact.get("candidates") or {})
        items = [{**item, "allowed_to_live": False, "allowed_to_dry_run": False, "forced_for_validation": False,
                  "next_action": "continue_research", "dry_run_gate": {"status": "blocked", "reasons": ["旧结果缺少生产准入"]},
                  "live_gate": {"status": "blocked", "reasons": ["旧结果缺少生产准入"]}} for item in candidates.get("items", [])]
        result["candidates"] = {**candidates, "items": items,
                                "summary": {"candidate_count": len(items), "ready_count": 0, "live_ready_count": 0, "blocked_count": len(items)}}
        legacy = True
    if legacy:
        result["experiment_report"] = {}
        result["warnings"] = [*list(artifact.get("warnings") or []), "旧评估不可用于策略收益或交易准入"]
    return result


def latest_closed_feature(*, symbol, candles, config, now, policy=None):
    """仅以当前可见的已收盘行情计算特征，不建立未来标签。"""
    policy = policy or load_live_policy()
    now_ms = int(now.timestamp() * 1000)
    unique = {}
    for row in candles:
        try:
            start, end = int(row["open_time"]), int(row["close_time"])
        except (KeyError, TypeError, ValueError):
            continue
        if start <= end <= now_ms:
            unique[start] = row
    closed = [unique[t] for t in sorted(unique)]
    if len(closed) < 55:
        raise ValueError(f"{symbol} 已收盘特征历史不足")
    interval = int(closed[-1]["close_time"]) - int(closed[-1]["open_time"]) + 1
    if interval <= 0 or now_ms - int(closed[-1]["close_time"]) > interval * policy.max_feature_age_bars:
        raise ValueError(f"{symbol} 行情已过期")
    rows = build_feature_rows(
        symbol, closed, missing_policy=config.missing_policy,
        outlier_policy=config.outlier_policy, normalization_policy=config.normalization_policy,
        timeframe_profiles=config.timeframe_profiles,
    )
    if not rows:
        raise ValueError(f"{symbol} 没有可用实时特征")
    latest = rows[-1]
    feature_ms = int(latest["generated_at"])
    if now_ms - feature_ms > interval * policy.max_feature_age_bars:
        raise ValueError(f"{symbol} 有效特征已过期")
    asof = datetime.fromtimestamp(feature_ms / 1000, timezone.utc)
    expires = min(asof + timedelta(milliseconds=interval * policy.max_feature_age_bars), now + timedelta(seconds=policy.max_prediction_age_seconds))
    return latest, {"feature_asof": asof.isoformat(), "expires_at": expires.isoformat(), "feature_timeframe_ms": interval}


def production_admission(record, *, policy=None):
    """旧评估或未晋升模型仅供研究，不允许产生执行信号。"""
    policy = policy or load_live_policy()
    reasons = []
    if record is None:
        return {"passed": False, "reasons": ["没有合格生产模型"], "stage": "research", "model_version": ""}
    context = dict(record.training_context or {})
    auc = float(record.metrics.get("val_auc") or 0)
    if record.stage != "production":
        reasons.append("模型未晋升生产")
    if context.get("evaluation_version") != EVALUATION_VERSION:
        reasons.append("模型使用旧评估，需按新协议验证")
    if not context.get("evaluation_available"):
        reasons.append("模型缺少可用价格回放评估")
    if not isinstance(context.get("input_protocol"), dict) or not context["input_protocol"]:
        reasons.append("模型缺少训练输入协议")
    elif context["input_protocol"].get("model_mode") != "binary":
        reasons.append("排序分数不能作为上涨概率交易")
    if not math.isfinite(auc) or auc < policy.min_auc:
        reasons.append("模型验证质量不足")
    if float(record.metrics.get("val_f1") or 0) <= 0:
        reasons.append("模型验证未识别有效正样本")
    return {"passed": not reasons, "reasons": reasons, "stage": record.stage, "model_version": record.version_id,
            "evaluation_version": context.get("evaluation_version"), "prediction_semantics": context.get("prediction_semantics", UPSIDE_PROBABILITY)}


def inference_execution_guard(inference, *, symbol=None, now=None, opening_short=False, reducing_position=False, verify_current_production=False):
    """执行前再次校验推理准入和实际行情时间，禁止过期及错误做空语义。"""
    now = now or datetime.now(timezone.utc)
    admission = dict(inference.get("model_admission") or {})
    reasons = [] if reducing_position else list(admission.get("reasons") or [])
    if not reducing_position and (admission.get("passed") is not True or admission.get("stage") != "production" or admission.get("evaluation_version") != EVALUATION_VERSION):
        reasons.append("自动化模型尚未通过生产准入")
    if verify_current_production and not reducing_position:
        from services.worker.model_registry import get_model_registry
        try:
            record = get_model_registry().get_production_model()
            current = production_admission(record)
            if not current["passed"] or current["model_version"] != admission.get("model_version"):
                reasons.append("当前生产模型已变化或失效，需重新推理")
        except Exception as exc:
            reasons.append(f"无法确认当前生产模型: {exc}")
    signals = [s for s in inference.get("signals", []) if not symbol or str(s.get("symbol", "")).replace("/", "").split(":")[0] == symbol.replace("/", "").split(":")[0]]
    if not signals:
        reasons.append("没有可用实时信号")
    for signal in signals:
        try:
            asof = datetime.fromisoformat(str(signal["feature_asof"]).replace("Z", "+00:00"))
            expires = datetime.fromisoformat(str(signal["expires_at"]).replace("Z", "+00:00"))
            if asof > now or expires <= now or not asof.tzinfo or not expires.tzinfo:
                reasons.append("信号行情未来或已过期")
        except (KeyError, ValueError, TypeError):
            reasons.append("信号缺少有效行情时间")
        if not reducing_position and signal.get("model_version") != admission.get("model_version"):
            reasons.append("信号与生产模型版本不一致")
        if not reducing_position and signal.get("executable") is not True:
            reasons.append("研究信号不能执行")
        if opening_short and signal.get("prediction_semantics") != "downside_probability":
            reasons.append("上涨超过阈值的概率不能作为做空概率")
    return {"passed": not reasons, "reasons": list(dict.fromkeys(reasons))}

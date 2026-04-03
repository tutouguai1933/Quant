"""Qlib 统一实验对比摘要。

这个文件负责把训练、推理、候选和实验摘要收成一份稳定结果。
"""

from __future__ import annotations


def build_experiment_report(
    *,
    latest_training: dict[str, object] | None,
    latest_inference: dict[str, object] | None,
    candidates: dict[str, object] | None,
) -> dict[str, object]:
    """统一整理研究实验对比摘要。"""

    latest_training_payload = dict(latest_training or {})
    latest_inference_payload = dict(latest_inference or {})
    candidate_payload = dict(candidates or {})
    candidate_items = list(candidate_payload.get("items") or [])
    inference_summary = dict(latest_inference_payload.get("summary") or {})
    overview = {
        "candidate_count": len(candidate_items),
        "ready_count": sum(1 for item in candidate_items if bool(item.get("allowed_to_dry_run"))),
        "signal_count": max(len(list(latest_inference_payload.get("signals") or [])), _parse_int(inference_summary.get("signal_count"))),
    }
    return {
        "overview": overview,
        "latest_training": latest_training_payload,
        "latest_inference": latest_inference_payload,
        "candidates": candidate_items,
        "experiments": {
            "training": _build_experiment_entry(latest_training_payload),
            "inference": _build_experiment_entry(latest_inference_payload),
        },
    }


def _build_experiment_entry(payload: dict[str, object]) -> dict[str, object]:
    """把单次实验结果整理成统一摘要。"""

    return {
        "run_id": str(payload.get("run_id", "")),
        "status": str(payload.get("status", "unavailable")),
        "generated_at": str(payload.get("generated_at", "")),
        "model_version": str(payload.get("model_version", "")),
        "signal_count": max(
            len(list(payload.get("signals") or [])),
            _parse_int(dict(payload.get("summary") or {}).get("signal_count")),
        ),
    }


def _parse_int(value: object) -> int:
    """把输入转成整数。"""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

"""评估与实验中心聚合服务。

这个文件负责把研究报告里的评估摘要、淘汰原因和实验账本整理成前端可见结构。
"""

from __future__ import annotations

from services.api.app.services.research_service import research_service
from services.api.app.services.validation_workflow_service import validation_workflow_service
from services.api.app.services.workbench_config_service import workbench_config_service


class EvaluationWorkspaceService:
    """聚合评估与实验中心上下文。"""

    def __init__(self, *, report_reader: object | None = None, controls_builder=None, review_reader: object | None = None) -> None:
        self._report_reader = report_reader or research_service
        self._controls_builder = controls_builder or workbench_config_service.build_workspace_controls
        self._review_reader = review_reader or validation_workflow_service

    def get_workspace(self) -> dict[str, object]:
        """返回评估与实验中心统一模型。"""

        controls = self._controls_builder()
        review_limit = self._resolve_review_limit(controls)
        report = self._read_factory_report()
        leaderboard = self._build_leaderboard(report)
        evaluation = dict(report.get("evaluation") or {})
        reviews = dict(report.get("reviews") or {})
        overview = dict(report.get("overview") or {})
        recent_runs = list((report.get("experiments") or {}).get("recent_runs") or [])
        review_report = self._read_validation_review(limit=review_limit)
        execution_alignment = dict(review_report.get("execution_comparison") or {})
        validation_reviews = dict(review_report.get("reviews") or {})
        configured_thresholds = dict((controls.get("config") or {}).get("thresholds") or {})

        status = str(report.get("status", "unavailable") or "unavailable")
        if evaluation or leaderboard or reviews:
            status = "ready"

        return {
            "status": status,
            "backend": str(report.get("backend", "qlib-fallback") or "qlib-fallback"),
            "config_alignment": dict(report.get("config_alignment") or {}),
            "overview": {
                "recommended_symbol": str(overview.get("recommended_symbol", "")),
                "recommended_action": str(overview.get("recommended_action", "")),
                "candidate_count": int(overview.get("candidate_count", 0) or 0),
            },
            "controls": {
                "dry_run_min_score": str(configured_thresholds.get("dry_run_min_score", "")),
                "dry_run_min_positive_rate": str(configured_thresholds.get("dry_run_min_positive_rate", "")),
                "dry_run_min_net_return_pct": str(configured_thresholds.get("dry_run_min_net_return_pct", "")),
                "dry_run_min_sharpe": str(configured_thresholds.get("dry_run_min_sharpe", "")),
                "dry_run_max_drawdown_pct": str(configured_thresholds.get("dry_run_max_drawdown_pct", "")),
                "dry_run_max_loss_streak": str(configured_thresholds.get("dry_run_max_loss_streak", "")),
                "dry_run_min_win_rate": str(configured_thresholds.get("dry_run_min_win_rate", "0.5")),
                "dry_run_max_turnover": str(configured_thresholds.get("dry_run_max_turnover", "0.6")),
                "dry_run_min_sample_count": str(configured_thresholds.get("dry_run_min_sample_count", "20")),
                "validation_min_sample_count": str(configured_thresholds.get("validation_min_sample_count", "12")),
                "live_min_score": str(configured_thresholds.get("live_min_score", "")),
                "live_min_positive_rate": str(configured_thresholds.get("live_min_positive_rate", "")),
                "live_min_net_return_pct": str(configured_thresholds.get("live_min_net_return_pct", "")),
                "live_min_win_rate": str(configured_thresholds.get("live_min_win_rate", "0.55")),
                "live_max_turnover": str(configured_thresholds.get("live_max_turnover", "0.45")),
                "live_min_sample_count": str(configured_thresholds.get("live_min_sample_count", "24")),
            },
            "evaluation": evaluation,
            "reviews": {
                **reviews,
                **{key: dict(value or {}) for key, value in validation_reviews.items()},
            },
            "leaderboard": leaderboard,
            "recent_runs": [dict(item) for item in recent_runs if isinstance(item, dict)],
            "experiment_comparison": self._build_experiment_comparison(report),
            "gate_matrix": self._build_gate_matrix(report),
            "run_deltas": self._build_run_deltas(report),
            "comparison_summary": self._build_comparison_summary(
                report=report,
                validation_reviews=validation_reviews,
                execution_alignment=execution_alignment,
            ),
            "execution_alignment": execution_alignment,
            "alignment_details": self._build_alignment_details(
                overview=overview,
                execution_alignment=execution_alignment,
            ),
        }

    def _read_factory_report(self) -> dict[str, object]:
        """读取统一研究报告。"""

        reader = getattr(self._report_reader, "get_factory_report", None)
        if callable(reader):
            payload = reader()
            if isinstance(payload, dict):
                return payload
        return {"status": "unavailable", "backend": "qlib-fallback"}

    def _read_validation_review(self, *, limit: int) -> dict[str, object]:
        """读取统一复盘摘要。"""

        reader = getattr(self._review_reader, "build_report", None)
        if callable(reader):
            payload = reader(limit=limit)
            if isinstance(payload, dict):
                return payload
        return {}

    @staticmethod
    def _resolve_review_limit(controls: dict[str, object]) -> int:
        """从统一工作台配置中取复盘展示窗口。"""

        operations = dict((controls.get("config") or {}).get("operations") or {})
        try:
            value = int(str(operations.get("review_limit", "10") or "10"))
        except (TypeError, ValueError):
            return 10
        return max(value, 1)

    @staticmethod
    def _build_leaderboard(report: dict[str, object]) -> list[dict[str, object]]:
        """把实验排行整理成可直接展示推荐原因和淘汰原因的结构。"""

        rows: list[dict[str, object]] = []
        for item in list(report.get("leaderboard") or []):
            if not isinstance(item, dict):
                continue
            row = dict(item)
            failure_reasons = [
                str(reason).strip()
                for reason in list(row.get("failure_reasons") or [])
                if str(reason).strip()
            ]
            elimination_reason = EvaluationWorkspaceService._resolve_elimination_reason(row=row, failure_reasons=failure_reasons)
            row["failure_reasons"] = failure_reasons
            row["recommendation_reason"] = str(row.get("recommendation_reason", "")).strip()
            row["elimination_reason"] = elimination_reason
            rows.append(row)
        return rows

    @staticmethod
    def _resolve_elimination_reason(*, row: dict[str, object], failure_reasons: list[str]) -> str:
        """统一淘汰原因展示口径。"""

        if failure_reasons:
            return " / ".join(failure_reasons)
        dry_run_gate = dict(row.get("dry_run_gate") or {})
        dry_reasons = [str(reason).strip() for reason in list(dry_run_gate.get("reasons") or []) if str(reason).strip()]
        if dry_reasons:
            return " / ".join(dry_reasons)
        live_gate = dict(row.get("live_gate") or {})
        live_reasons = [str(reason).strip() for reason in list(live_gate.get("reasons") or []) if str(reason).strip()]
        if live_reasons:
            return " / ".join(live_reasons)
        return "已通过"

    @staticmethod
    def _build_experiment_comparison(report: dict[str, object]) -> list[dict[str, object]]:
        """把训练、推理和最近运行压成统一对照表。"""

        experiments = dict(report.get("experiments") or {})
        training = dict(experiments.get("training") or report.get("latest_training") or {})
        inference = dict(experiments.get("inference") or report.get("latest_inference") or {})
        recent_runs = [dict(item) for item in list(experiments.get("recent_runs") or []) if isinstance(item, dict)]
        rows: list[dict[str, object]] = []
        if training:
            rows.append(
                {
                    "run_type": "training",
                    "run_id": str(training.get("run_id", "")),
                    "status": str(training.get("status", "")),
                    "model_version": str(training.get("model_version", "")),
                    "dataset_snapshot_id": str(training.get("dataset_snapshot_id", "")),
                    "signal_count": str(training.get("signal_count", "")),
                }
            )
        if inference:
            rows.append(
                {
                    "run_type": "inference",
                    "run_id": str(inference.get("run_id", "")),
                    "status": str(inference.get("status", "")),
                    "model_version": str(inference.get("model_version", "")),
                    "dataset_snapshot_id": str(inference.get("dataset_snapshot_id", "")),
                    "signal_count": str(inference.get("signal_count", "")),
                }
            )
        for item in recent_runs:
            if not training and str(item.get("run_type", "")) == "training":
                rows.append(
                    {
                        "run_type": "training",
                        "run_id": str(item.get("run_id", "")),
                        "status": str(item.get("status", "")),
                        "model_version": str(item.get("model_version", "")),
                        "dataset_snapshot_id": str(dict(item.get("dataset_snapshot") or {}).get("snapshot_id", "")),
                        "signal_count": str(item.get("signal_count", "")),
                    }
                )
                continue
            if not inference and str(item.get("run_type", "")) == "inference":
                rows.append(
                    {
                        "run_type": "inference",
                        "run_id": str(item.get("run_id", "")),
                        "status": str(item.get("status", "")),
                        "model_version": str(item.get("model_version", "")),
                        "dataset_snapshot_id": str(dict(item.get("dataset_snapshot") or {}).get("snapshot_id", "")),
                        "signal_count": str(item.get("signal_count", "")),
                    }
                )
                continue
            if str(item.get("run_type", "")) in {"training", "inference"}:
                continue
            rows.append(
                {
                    "run_type": str(item.get("run_type", "")),
                    "run_id": str(item.get("run_id", "")),
                    "status": str(item.get("status", "")),
                    "model_version": str(item.get("model_version", "")),
                    "dataset_snapshot_id": str(dict(item.get("dataset_snapshot") or {}).get("snapshot_id", "")),
                    "signal_count": "",
                }
            )
        return rows

    @staticmethod
    def _build_gate_matrix(report: dict[str, object]) -> list[dict[str, object]]:
        """把候选在各个门控的状态整理成表格。"""

        rows: list[dict[str, object]] = []
        for item in list(report.get("candidates") or []):
            if not isinstance(item, dict):
                continue
            rule_gate = dict(item.get("rule_gate") or {})
            validation_gate = dict(item.get("research_validation_gate") or {})
            backtest_gate = dict(item.get("backtest_gate") or {})
            consistency_gate = dict(item.get("consistency_gate") or {})
            blocking_gate, primary_reason = EvaluationWorkspaceService._resolve_blocking_gate(
                rule_gate=rule_gate,
                validation_gate=validation_gate,
                backtest_gate=backtest_gate,
                consistency_gate=consistency_gate,
                dry_run_gate=dict(item.get("dry_run_gate") or {}),
            )
            rows.append(
                {
                    "symbol": str(item.get("symbol", "")),
                    "allowed_to_dry_run": bool(item.get("allowed_to_dry_run")),
                    "allowed_to_live": bool(item.get("allowed_to_live")),
                    "blocking_gate": blocking_gate,
                    "primary_reason": primary_reason,
                    "rule_gate": EvaluationWorkspaceService._format_gate_status(rule_gate),
                    "validation_gate": EvaluationWorkspaceService._format_gate_status(validation_gate),
                    "backtest_gate": EvaluationWorkspaceService._format_gate_status(backtest_gate),
                    "consistency_gate": EvaluationWorkspaceService._format_gate_status(consistency_gate),
                }
            )
        return rows

    @staticmethod
    def _build_comparison_summary(
        *,
        report: dict[str, object],
        validation_reviews: dict[str, object],
        execution_alignment: dict[str, object],
    ) -> dict[str, object]:
        """把训练、推理、配置和执行的一致性压成摘要。"""

        experiments = dict(report.get("experiments") or {})
        training = dict(experiments.get("training") or report.get("latest_training") or {})
        inference = dict(experiments.get("inference") or report.get("latest_inference") or {})
        config_alignment = dict(report.get("config_alignment") or {})
        research_review = dict(validation_reviews.get("research") or report.get("reviews", {}).get("research") or {})
        training_model = str(training.get("model_version", ""))
        inference_model = str(inference.get("model_version", ""))
        training_snapshot = str(training.get("dataset_snapshot_id", ""))
        inference_snapshot = str(inference.get("dataset_snapshot_id", ""))
        model_aligned = bool(training_model and inference_model and training_model == inference_model)
        dataset_aligned = bool(training_snapshot and inference_snapshot and training_snapshot == inference_snapshot)

        note_parts = [
            f"配置对齐：{str(config_alignment.get('status', 'unavailable')) or 'unavailable'}",
            f"研究复盘：{str(research_review.get('result', 'n/a')) or 'n/a'}",
            f"执行对齐：{str(execution_alignment.get('status', 'n/a')) or 'n/a'}",
        ]

        return {
            "training_run_id": str(training.get("run_id", "")),
            "inference_run_id": str(inference.get("run_id", "")),
            "training_status": str(training.get("status", "")),
            "inference_status": str(inference.get("status", "")),
            "config_alignment_status": str(config_alignment.get("status", "unavailable") or "unavailable"),
            "execution_alignment_status": str(execution_alignment.get("status", "unavailable") or "unavailable"),
            "review_result": str(research_review.get("result", "") or ""),
            "next_action": str(research_review.get("next_action", report.get("overview", {}).get("recommended_action", "")) or ""),
            "model_aligned": model_aligned,
            "dataset_aligned": dataset_aligned,
            "note": " / ".join(note_parts),
        }

    @staticmethod
    def _build_run_deltas(report: dict[str, object]) -> list[dict[str, object]]:
        """比较最近两轮训练和推理的主要差异。"""

        experiments = dict(report.get("experiments") or {})
        recent_runs = [dict(item) for item in list(experiments.get("recent_runs") or []) if isinstance(item, dict)]
        latest_by_type = {
            "training": dict(experiments.get("training") or report.get("latest_training") or {}),
            "inference": dict(experiments.get("inference") or report.get("latest_inference") or {}),
        }
        rows: list[dict[str, object]] = []
        for run_type in ("training", "inference"):
            current = EvaluationWorkspaceService._merge_run_with_recent(
                latest_by_type.get(run_type) or {},
                recent_runs=recent_runs,
                run_type=run_type,
            )
            if not current:
                continue
            previous = EvaluationWorkspaceService._find_previous_run(
                recent_runs,
                run_type=run_type,
                current_run_id=str(current.get("run_id", "")),
            )
            if not previous:
                continue
            current_backtest = dict((current.get("backtest") or {}).get("metrics") or current.get("backtest") or {})
            previous_backtest = dict((previous.get("backtest") or {}).get("metrics") or previous.get("backtest") or {})
            current_snapshot = str(dict(current.get("dataset_snapshot") or {}).get("snapshot_id") or current.get("dataset_snapshot_id", ""))
            previous_snapshot = str(dict(previous.get("dataset_snapshot") or {}).get("snapshot_id") or previous.get("dataset_snapshot_id", ""))
            model_changed = str(current.get("model_version", "")) != str(previous.get("model_version", ""))
            dataset_changed = current_snapshot != previous_snapshot
            changed_field_payload = EvaluationWorkspaceService._resolve_changed_fields(
                current=current,
                previous=previous,
            )
            rows.append(
                {
                    "run_type": run_type,
                    "current_run_id": str(current.get("run_id", "")),
                    "previous_run_id": str(previous.get("run_id", "")),
                    "model_changed": "是" if model_changed else "否",
                    "dataset_changed": "是" if dataset_changed else "否",
                    "signal_count_delta": EvaluationWorkspaceService._format_delta(
                        current.get("signal_count", dict(current.get("summary") or {}).get("signal_count", "")),
                        previous.get("signal_count", ""),
                    ),
                    "net_return_delta": EvaluationWorkspaceService._format_delta(
                        current_backtest.get("net_return_pct", ""),
                        previous_backtest.get("net_return_pct", ""),
                    ),
                    "sharpe_delta": EvaluationWorkspaceService._format_delta(
                        current_backtest.get("sharpe", ""),
                        previous_backtest.get("sharpe", ""),
                    ),
                    "win_rate_delta": EvaluationWorkspaceService._format_delta(
                        current_backtest.get("win_rate", ""),
                        previous_backtest.get("win_rate", ""),
                    ),
                    "changed_fields": list(changed_field_payload.get("fields") or []),
                    "changed_fields_status": str(changed_field_payload.get("status", "ready") or "ready"),
                    "changed_fields_note": str(changed_field_payload.get("note", "") or ""),
                    "note": EvaluationWorkspaceService._build_delta_note(
                        run_type=run_type,
                        model_changed=model_changed,
                        dataset_changed=dataset_changed,
                    ),
                }
            )
        return rows

    @staticmethod
    def _resolve_changed_fields(*, current: dict[str, object], previous: dict[str, object]) -> dict[str, object]:
        """列出最近两轮最主要的配置变化。"""

        current_context = dict(current.get("training_context") or current.get("inference_context") or {})
        previous_context = dict(previous.get("training_context") or previous.get("inference_context") or {})
        if not current_context or not previous_context:
            return {
                "fields": [],
                "status": "unavailable",
                "note": "当前实验账本缺少配置快照，暂时无法比较最近两轮配置变化。",
            }
        current_parameters = dict(current_context.get("parameters") or current_context.get("input_summary") or {})
        previous_parameters = dict(previous_context.get("parameters") or previous_context.get("input_summary") or {})
        watched_fields = (
            "research_template",
            "model_key",
            "label_mode",
            "holding_window_min_days",
            "holding_window_max_days",
            "sample_limit",
            "lookback_days",
            "window_mode",
            "start_date",
            "end_date",
            "missing_policy",
            "outlier_policy",
            "normalization_policy",
            "backtest_fee_bps",
            "backtest_slippage_bps",
        )
        changed = []
        for field in watched_fields:
            if str(current_parameters.get(field, "")) != str(previous_parameters.get(field, "")):
                changed.append(field)
        return {
            "fields": changed,
            "status": "ready",
            "note": "",
        }

    @staticmethod
    def _build_alignment_details(
        *,
        overview: dict[str, object],
        execution_alignment: dict[str, object],
    ) -> dict[str, str]:
        """把研究和执行的最近标的对齐成更直白的明细。"""

        execution = dict(execution_alignment.get("execution") or {})
        orders = [dict(item) for item in list(execution.get("orders") or []) if isinstance(item, dict)]
        positions = [dict(item) for item in list(execution.get("positions") or []) if isinstance(item, dict)]
        research_symbol = str(
            execution_alignment.get("symbol")
            or overview.get("recommended_symbol")
            or ""
        )
        last_order_symbol = str(orders[0].get("symbol", "")) if orders else ""
        last_position_symbol = str(positions[0].get("symbol", "")) if positions else ""
        status = str(execution_alignment.get("status", "") or "unavailable")
        if status == "matched":
            alignment_state = "研究和执行已对齐"
        elif status == "waiting":
            alignment_state = "研究已生成，等待执行收口"
        elif status == "unavailable":
            alignment_state = "当前还没有执行对齐结果"
        else:
            alignment_state = "研究和执行暂未对齐"
        return {
            "research_symbol": research_symbol,
            "last_order_symbol": last_order_symbol,
            "last_position_symbol": last_position_symbol,
            "alignment_state": alignment_state,
        }

    @staticmethod
    def _find_previous_run(recent_runs: list[dict[str, object]], *, run_type: str, current_run_id: str) -> dict[str, object]:
        """找到同类型的上一轮运行。"""

        for item in recent_runs:
            if str(item.get("run_type", "")) != run_type:
                continue
            if current_run_id and str(item.get("run_id", "")) == current_run_id:
                continue
            return dict(item)
        return {}

    @staticmethod
    def _merge_run_with_recent(current: dict[str, object], *, recent_runs: list[dict[str, object]], run_type: str) -> dict[str, object]:
        """当前轮缺少上下文时，用实验账本里的同轮记录补齐。"""

        current_run = dict(current or {})
        if not current_run:
            return {}
        if current_run.get("training_context") or current_run.get("inference_context"):
            return current_run
        current_run_id = str(current_run.get("run_id", ""))
        for item in recent_runs:
            if str(item.get("run_type", "")) != run_type:
                continue
            if current_run_id and str(item.get("run_id", "")) != current_run_id:
                continue
            merged = dict(item)
            merged.update(current_run)
            if item.get("training_context") and not current_run.get("training_context"):
                merged["training_context"] = dict(item.get("training_context") or {})
            if item.get("inference_context") and not current_run.get("inference_context"):
                merged["inference_context"] = dict(item.get("inference_context") or {})
            if item.get("backtest") and not current_run.get("backtest"):
                merged["backtest"] = dict(item.get("backtest") or {})
            if item.get("dataset_snapshot") and not current_run.get("dataset_snapshot"):
                merged["dataset_snapshot"] = dict(item.get("dataset_snapshot") or {})
            return merged
        return current_run

    @staticmethod
    def _format_delta(current: object, previous: object) -> str:
        """把当前值与上一轮差值格式化成稳定字符串。"""

        try:
            current_value = float(str(current or "0"))
            previous_value = float(str(previous or "0"))
        except ValueError:
            return "n/a"
        return f"{current_value - previous_value:+.4f}"

    @staticmethod
    def _build_delta_note(*, run_type: str, model_changed: bool, dataset_changed: bool) -> str:
        """生成最近两轮对比说明。"""

        prefix = "训练对比" if run_type == "training" else "推理对比"
        notes: list[str] = []
        if model_changed:
            notes.append("模型已切换")
        if dataset_changed:
            notes.append("数据快照已变化")
        if not notes:
            notes.append("沿用上一轮模型和数据")
        return f"{prefix}：{'，'.join(notes)}"

    @staticmethod
    def _resolve_blocking_gate(
        *,
        rule_gate: dict[str, object],
        validation_gate: dict[str, object],
        backtest_gate: dict[str, object],
        consistency_gate: dict[str, object],
        dry_run_gate: dict[str, object],
    ) -> tuple[str, str]:
        """找出候选当前最主要卡住的门。"""

        ordered_gates = [
            ("rule_gate", rule_gate),
            ("validation_gate", validation_gate),
            ("backtest_gate", backtest_gate),
            ("consistency_gate", consistency_gate),
        ]
        for gate_name, gate_payload in ordered_gates:
            if EvaluationWorkspaceService._gate_passed(gate_payload):
                continue
            reasons = [str(reason).strip() for reason in list(gate_payload.get("reasons") or []) if str(reason).strip()]
            return gate_name, " / ".join(reasons) if reasons else "未通过"
        dry_run_reasons = [str(reason).strip() for reason in list(dry_run_gate.get("reasons") or []) if str(reason).strip()]
        if dry_run_reasons:
            return "dry_run_gate", " / ".join(dry_run_reasons)
        return "passed", "已通过"

    @staticmethod
    def _format_gate_status(gate: dict[str, object]) -> str:
        """统一门控状态文案。"""

        if not gate:
            return "n/a"
        return "通过" if EvaluationWorkspaceService._gate_passed(gate) else "拦下"

    @staticmethod
    def _gate_passed(gate: dict[str, object]) -> bool:
        """判断单个门控是否通过。"""

        if not gate:
            return False
        return bool(gate.get("passed"))


evaluation_workspace_service = EvaluationWorkspaceService()

"""评估与实验中心聚合服务。

这个文件负责把研究报告里的评估摘要、淘汰原因和实验账本整理成前端可见结构。
"""

from __future__ import annotations

from services.api.app.services.research_service import research_service
from services.api.app.services.validation_workflow_service import validation_workflow_service
from services.api.app.services.workbench_config_service import (
    _build_automation_preset_catalog,
    _build_operations_preset_catalog,
    _describe_catalog_item,
    workbench_config_service,
)


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
        comparison_run_limit = self._resolve_comparison_run_limit(controls)
        report = self._read_factory_report()
        evaluation = dict(report.get("evaluation") or {})
        reviews = dict(report.get("reviews") or {})
        overview = dict(report.get("overview") or {})
        recent_runs = list((report.get("experiments") or {}).get("recent_runs") or [])
        review_report = self._read_validation_review(limit=review_limit)
        recent_review_tasks = [dict(item) for item in list(review_report.get("recent_tasks") or []) if isinstance(item, dict)]
        execution_alignment = dict(review_report.get("execution_comparison") or {})
        validation_reviews = dict(review_report.get("reviews") or {})
        configured_thresholds = dict((controls.get("config") or {}).get("thresholds") or {})
        configured_operations = dict((controls.get("config") or {}).get("operations") or {})
        configured_automation = dict((controls.get("config") or {}).get("automation") or {})
        configured_research = dict((controls.get("config") or {}).get("research") or {})
        candidate_scope = workbench_config_service.build_candidate_scope_contract(dict(controls.get("config") or {}))
        option_catalogs = dict(controls.get("options") or {})
        gate_matrix = self._build_gate_matrix(report)
        current_research_template = self._resolve_current_research_template(
            report=report,
            configured_research=configured_research,
        )
        leaderboard = self._build_leaderboard(
            report,
            gate_matrix=gate_matrix,
            current_research_template=current_research_template,
            option_catalogs=option_catalogs,
        )
        best_experiment = self._build_best_experiment(
            leaderboard=leaderboard,
            gate_matrix=gate_matrix,
            overview=overview,
            research_reviews=reviews,
            validation_reviews=validation_reviews,
            candidate_scope=candidate_scope,
        )
        best_stage_candidates = self._build_best_stage_candidates(
            leaderboard=leaderboard,
            gate_matrix=gate_matrix,
            overview=overview,
            validation_reviews=validation_reviews,
            candidate_scope=candidate_scope,
        )
        recommendation_explanation = self._build_recommendation_explanation(
            leaderboard=leaderboard,
            gate_matrix=gate_matrix,
            best_experiment=best_experiment,
            review_result=str(dict(reviews.get("research") or {}).get("result", "") or ""),
        )
        elimination_explanation = self._build_elimination_explanation(
            leaderboard=leaderboard,
            gate_matrix=gate_matrix,
        )
        alignment_details = self._build_alignment_details(
            overview=overview,
            execution_alignment=execution_alignment,
        )
        alignment_actions = self._build_alignment_actions(execution_alignment=execution_alignment)
        alignment_story = self._build_alignment_story(
            alignment_details=alignment_details,
            alignment_actions=alignment_actions,
        )
        stage_decision_summary = self._build_stage_decision_summary(
            best_experiment=best_experiment,
            recommendation_explanation=recommendation_explanation,
            elimination_explanation=elimination_explanation,
            alignment_details=alignment_details,
        )
        decision_board = self._build_decision_board(
            best_experiment=best_experiment,
            best_stage_candidates=best_stage_candidates,
            recommendation_explanation=recommendation_explanation,
            elimination_explanation=elimination_explanation,
            alignment_story=alignment_story,
        )

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
            "candidate_scope": candidate_scope,
            "selection_story": self._build_selection_story(
                option_catalogs=option_catalogs,
                thresholds=configured_thresholds,
                config_alignment=dict(report.get("config_alignment") or {}),
            ),
            "threshold_catalog": self._build_threshold_catalog(
                option_catalogs=option_catalogs,
                thresholds=configured_thresholds,
                config_alignment=dict(report.get("config_alignment") or {}),
            ),
            "controls": {
                "threshold_preset_key": str(configured_thresholds.get("threshold_preset_key", "standard_gate") or "standard_gate"),
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
                "validation_min_avg_future_return_pct": str(configured_thresholds.get("validation_min_avg_future_return_pct", "-0.1")),
                "consistency_max_validation_backtest_return_gap_pct": str(configured_thresholds.get("consistency_max_validation_backtest_return_gap_pct", "1.5")),
                "consistency_max_training_validation_positive_rate_gap": str(configured_thresholds.get("consistency_max_training_validation_positive_rate_gap", "0.2")),
                "consistency_max_training_validation_return_gap_pct": str(configured_thresholds.get("consistency_max_training_validation_return_gap_pct", "1.5")),
                "rule_min_ema20_gap_pct": str(configured_thresholds.get("rule_min_ema20_gap_pct", "0")),
                "rule_min_ema55_gap_pct": str(configured_thresholds.get("rule_min_ema55_gap_pct", "0")),
                "rule_max_atr_pct": str(configured_thresholds.get("rule_max_atr_pct", "5")),
                "rule_min_volume_ratio": str(configured_thresholds.get("rule_min_volume_ratio", "1")),
                "strict_rule_min_ema20_gap_pct": str(configured_thresholds.get("strict_rule_min_ema20_gap_pct", "1.2")),
                "strict_rule_min_ema55_gap_pct": str(configured_thresholds.get("strict_rule_min_ema55_gap_pct", "1.8")),
                "strict_rule_max_atr_pct": str(configured_thresholds.get("strict_rule_max_atr_pct", "4.5")),
                "strict_rule_min_volume_ratio": str(configured_thresholds.get("strict_rule_min_volume_ratio", "1.05")),
                "enable_rule_gate": bool(configured_thresholds.get("enable_rule_gate", True)),
                "enable_validation_gate": bool(configured_thresholds.get("enable_validation_gate", True)),
                "enable_backtest_gate": bool(configured_thresholds.get("enable_backtest_gate", True)),
                "enable_consistency_gate": bool(configured_thresholds.get("enable_consistency_gate", True)),
                "enable_live_gate": bool(configured_thresholds.get("enable_live_gate", True)),
                "live_min_score": str(configured_thresholds.get("live_min_score", "")),
                "live_min_positive_rate": str(configured_thresholds.get("live_min_positive_rate", "")),
                "live_min_net_return_pct": str(configured_thresholds.get("live_min_net_return_pct", "")),
                "live_min_win_rate": str(configured_thresholds.get("live_min_win_rate", "0.55")),
                "live_max_turnover": str(configured_thresholds.get("live_max_turnover", "0.45")),
                "live_min_sample_count": str(configured_thresholds.get("live_min_sample_count", "24")),
                "available_threshold_presets": [str(item) for item in list((controls.get("options") or {}).get("threshold_presets") or [])],
                "threshold_preset_catalog": [dict(item) for item in list((controls.get("options") or {}).get("threshold_preset_catalog") or []) if isinstance(item, dict)],
            },
            "operations": {
                "operations_preset_key": str(configured_operations.get("operations_preset_key", "balanced_guard")),
                "operations_preset_detail": _describe_catalog_item(
                    _build_operations_preset_catalog(),
                    key=str(configured_operations.get("operations_preset_key", "balanced_guard")),
                    title="长期运行预设",
                ),
                "review_limit": str(configured_operations.get("review_limit", "10")),
                "comparison_run_limit": str(configured_operations.get("comparison_run_limit", "5")),
                "cycle_cooldown_minutes": str(configured_operations.get("cycle_cooldown_minutes", "15")),
                "max_daily_cycle_count": str(configured_operations.get("max_daily_cycle_count", "8")),
                "automation_preset_key": str(configured_automation.get("automation_preset_key", "balanced_runtime")),
                "automation_preset_detail": _describe_catalog_item(
                    _build_automation_preset_catalog(),
                    key=str(configured_automation.get("automation_preset_key", "balanced_runtime")),
                    title="自动化运行预设",
                ),
            },
            "evaluation": evaluation,
            "reviews": {
                **reviews,
                **{key: dict(value or {}) for key, value in validation_reviews.items()},
            },
            "recent_review_tasks": recent_review_tasks,
            "leaderboard": leaderboard,
            "best_experiment": best_experiment,
            "best_stage_candidates": best_stage_candidates,
            "decision_board": decision_board,
            "recommendation_explanation": recommendation_explanation,
            "elimination_explanation": elimination_explanation,
            "recent_runs": [dict(item) for item in recent_runs if isinstance(item, dict)][:comparison_run_limit],
            "recent_training_runs": self._build_recent_run_history(report=report, run_type="training", limit=comparison_run_limit),
            "recent_inference_runs": self._build_recent_run_history(report=report, run_type="inference", limit=comparison_run_limit),
            "experiment_comparison": self._build_experiment_comparison(report, limit=comparison_run_limit),
            "gate_matrix": gate_matrix,
            "workflow_alignment_timeline": self._build_workflow_alignment_timeline(review_report),
            "run_deltas": self._build_run_deltas(report, limit=comparison_run_limit),
            "delta_overview": self._build_delta_overview(report),
            "comparison_summary": self._build_comparison_summary(
                report=report,
                validation_reviews=validation_reviews,
                execution_alignment=execution_alignment,
            ),
            "execution_alignment": execution_alignment,
            "alignment_metric_rows": self._build_alignment_metric_rows(
                best_experiment=best_experiment,
                best_stage_candidates=best_stage_candidates,
                execution_alignment=execution_alignment,
                validation_reviews=validation_reviews,
            ),
            "alignment_details": alignment_details,
            "alignment_story": alignment_story,
            "alignment_gaps": self._build_alignment_gaps(
                overview=overview,
                execution_alignment=execution_alignment,
            ),
            "alignment_actions": alignment_actions,
            "stage_decision_summary": stage_decision_summary,
        }

    @staticmethod
    def _resolve_catalog_item(
        catalog: list[dict[str, object]],
        *,
        key: str,
        fallback_label: str,
    ) -> dict[str, str]:
        """从目录里找出当前选中的说明项。"""

        for item in catalog:
            if str(item.get("key", "")).strip() == key:
                return {
                    "key": key,
                    "label": str(item.get("label", fallback_label) or fallback_label),
                    "fit": str(item.get("fit", "当前没有适用场景说明") or "当前没有适用场景说明"),
                    "detail": str(item.get("detail", "当前没有额外说明") or "当前没有额外说明"),
                }
        return {
            "key": key,
            "label": fallback_label,
            "fit": "当前没有适用场景说明",
            "detail": "当前没有额外说明",
        }

    def _build_selection_story(
        self,
        *,
        option_catalogs: dict[str, object],
        thresholds: dict[str, object],
        config_alignment: dict[str, object],
    ) -> dict[str, object]:
        """把当前准入预设和四层门槛压成一屏说明。"""

        threshold_preset = self._resolve_catalog_item(
            [dict(item) for item in list(option_catalogs.get("threshold_preset_catalog") or []) if isinstance(item, dict)],
            key=str(thresholds.get("threshold_preset_key", "standard_gate") or "standard_gate"),
            fallback_label=str(thresholds.get("threshold_preset_key", "standard_gate") or "standard_gate"),
        )
        alignment_status = str(config_alignment.get("status", "unavailable") or "unavailable")
        alignment_note = str(config_alignment.get("note", "") or "").strip()
        if not alignment_note:
            alignment_note = self._build_alignment_note(alignment_status)
        return {
            "headline": threshold_preset["label"],
            "detail": (
                f"dry-run 分数 ≥ {thresholds.get('dry_run_min_score', '0.55')} / "
                f"验证样本 ≥ {thresholds.get('validation_min_sample_count', '12')} / "
                f"live 分数 ≥ {thresholds.get('live_min_score', '0.65')}"
            ),
            "alignment_status": alignment_status,
            "alignment_note": alignment_note,
            "threshold_preset": threshold_preset,
            "dry_run_summary": self._build_dry_run_summary(thresholds),
            "validation_summary": self._build_validation_summary(thresholds),
            "consistency_summary": self._build_consistency_summary(thresholds),
            "live_summary": self._build_live_summary(thresholds),
            "gate_summary": self._build_gate_summary(thresholds),
        }

    def _build_threshold_catalog(
        self,
        *,
        option_catalogs: dict[str, object],
        thresholds: dict[str, object],
        config_alignment: dict[str, object],
    ) -> list[dict[str, str]]:
        """把准入门槛整理成稳定目录。"""

        threshold_preset = self._resolve_catalog_item(
            [dict(item) for item in list(option_catalogs.get("threshold_preset_catalog") or []) if isinstance(item, dict)],
            key=str(thresholds.get("threshold_preset_key", "standard_gate") or "standard_gate"),
            fallback_label=str(thresholds.get("threshold_preset_key", "standard_gate") or "standard_gate"),
        )
        alignment_status = str(config_alignment.get("status", "unavailable") or "unavailable")
        alignment_note = str(config_alignment.get("note", "") or "").strip() or self._build_alignment_note(alignment_status)
        return [
            {
                "key": "threshold_preset",
                "label": "准入预设",
                "current": threshold_preset["label"],
                "effect": "先统一切换一整套放行口径，再决定要不要细调单个门槛。",
                "detail": threshold_preset["detail"],
            },
            {
                "key": "dry_run_gate",
                "label": "dry-run 门槛",
                "current": self._build_dry_run_summary(thresholds),
                "effect": "决定候选能不能先进入 dry-run 观察，而不是继续停在研究阶段。",
                "detail": alignment_note,
            },
            {
                "key": "validation_gate",
                "label": "验证门槛",
                "current": self._build_validation_summary(thresholds),
                "effect": "要求样本外验证先站住，避免只在训练段里好看。",
                "detail": "验证门主要看样本量和平均未来收益，不够就先别放到后面阶段。",
            },
            {
                "key": "rule_gate",
                "label": "规则过滤",
                "current": self._build_rule_summary(thresholds),
                "effect": "先筛掉趋势不够强、波动过大或量能不足的候选。",
                "detail": self._build_strict_rule_summary(thresholds),
            },
            {
                "key": "consistency_gate",
                "label": "一致性门槛",
                "current": self._build_consistency_summary(thresholds),
                "effect": "避免训练、验证和回测差得太远，结果看起来稳但换窗口就走样。",
                "detail": "一致性门主要限制训练/验证/回测之间的收益和正收益比例漂移。",
            },
            {
                "key": "live_gate",
                "label": "live 门槛",
                "current": self._build_live_summary(thresholds),
                "effect": "只有更稳的候选才允许继续进入小额 live。",
                "detail": "live 门默认比 dry-run 更严格，先保守验证真实执行风险。",
            },
            {
                "key": "gate_switches",
                "label": "门控开关",
                "current": self._build_gate_summary(thresholds),
                "effect": "方便快速判断到底是哪一层在拦住候选。",
                "detail": "这些开关更适合临时排查，不适合长期关闭后直接放行。",
            },
        ]

    @staticmethod
    def _build_alignment_note(status: str) -> str:
        """生成当前结果和配置是否对齐的说明。"""

        if status == "aligned":
            return "当前研究结果仍然基于这页右上角的最新门槛。"
        if status == "stale":
            return "检测到评估门槛和研究结果之间可能存在漂移，请先重跑研究或重新核对。"
        return "评估系统还没拿到配置快照，暂时无法确认当前门槛是否已经生效。"

    @staticmethod
    def _build_dry_run_summary(thresholds: dict[str, object]) -> str:
        """压缩 dry-run 门槛摘要。"""

        return (
            f"分数 ≥ {thresholds.get('dry_run_min_score', '0.55')} / "
            f"净收益 ≥ {thresholds.get('dry_run_min_net_return_pct', '0')}% / "
            f"Sharpe ≥ {thresholds.get('dry_run_min_sharpe', '0.5')} / "
            f"样本 ≥ {thresholds.get('dry_run_min_sample_count', '20')}"
        )

    @staticmethod
    def _build_validation_summary(thresholds: dict[str, object]) -> str:
        """压缩验证门槛摘要。"""

        return (
            f"样本 ≥ {thresholds.get('validation_min_sample_count', '12')} / "
            f"平均未来收益 ≥ {thresholds.get('validation_min_avg_future_return_pct', '-0.1')}%"
        )

    @staticmethod
    def _build_rule_summary(thresholds: dict[str, object]) -> str:
        """压缩规则门摘要。"""

        return (
            f"EMA20 ≥ {thresholds.get('rule_min_ema20_gap_pct', '0')}% / "
            f"EMA55 ≥ {thresholds.get('rule_min_ema55_gap_pct', '0')}% / "
            f"ATR ≤ {thresholds.get('rule_max_atr_pct', '5')}% / "
            f"量比 ≥ {thresholds.get('rule_min_volume_ratio', '1')}"
        )

    @staticmethod
    def _build_strict_rule_summary(thresholds: dict[str, object]) -> str:
        """压缩严格规则模板摘要。"""

        return (
            f"严格模板：EMA20 ≥ {thresholds.get('strict_rule_min_ema20_gap_pct', '1.2')}% / "
            f"EMA55 ≥ {thresholds.get('strict_rule_min_ema55_gap_pct', '1.8')}% / "
            f"ATR ≤ {thresholds.get('strict_rule_max_atr_pct', '4.5')}% / "
            f"量比 ≥ {thresholds.get('strict_rule_min_volume_ratio', '1.05')}"
        )

    @staticmethod
    def _build_consistency_summary(thresholds: dict[str, object]) -> str:
        """压缩一致性门槛摘要。"""

        return (
            f"验证/回测收益差 ≤ {thresholds.get('consistency_max_validation_backtest_return_gap_pct', '1.5')}% / "
            f"训练/验证正收益比例差 ≤ {thresholds.get('consistency_max_training_validation_positive_rate_gap', '0.2')} / "
            f"训练/验证收益差 ≤ {thresholds.get('consistency_max_training_validation_return_gap_pct', '1.5')}%"
        )

    @staticmethod
    def _build_live_summary(thresholds: dict[str, object]) -> str:
        """压缩 live 门槛摘要。"""

        return (
            f"分数 ≥ {thresholds.get('live_min_score', '0.65')} / "
            f"净收益 ≥ {thresholds.get('live_min_net_return_pct', '0.20')}% / "
            f"胜率 ≥ {thresholds.get('live_min_win_rate', '0.55')} / "
            f"样本 ≥ {thresholds.get('live_min_sample_count', '24')}"
        )

    @staticmethod
    def _build_gate_summary(thresholds: dict[str, object]) -> str:
        """压缩五个门控开关摘要。"""

        gates = [
            ("规则门", bool(thresholds.get("enable_rule_gate", True))),
            ("验证门", bool(thresholds.get("enable_validation_gate", True))),
            ("回测门", bool(thresholds.get("enable_backtest_gate", True))),
            ("一致性门", bool(thresholds.get("enable_consistency_gate", True))),
            ("live 门", bool(thresholds.get("enable_live_gate", True))),
        ]
        return " / ".join(f"{label}{'开启' if enabled else '关闭'}" for label, enabled in gates)

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
    def _resolve_comparison_run_limit(controls: dict[str, object]) -> int:
        """从统一工作台配置中取实验对比窗口。"""

        operations = dict((controls.get("config") or {}).get("operations") or {})
        try:
            value = int(str(operations.get("comparison_run_limit", "5") or "5"))
        except (TypeError, ValueError):
            return 5
        return max(value, 1)

    @staticmethod
    def _build_leaderboard(
        report: dict[str, object],
        *,
        gate_matrix: list[dict[str, object]],
        current_research_template: str,
        option_catalogs: dict[str, object],
    ) -> list[dict[str, object]]:
        """把实验排行整理成可直接展示推荐原因和淘汰原因的结构。"""

        candidate_by_symbol = {
            str(item.get("symbol", "")).strip(): dict(item)
            for item in list(report.get("candidates") or [])
            if isinstance(item, dict) and str(item.get("symbol", "")).strip()
        }
        rows: list[dict[str, object]] = []
        for item in list(report.get("leaderboard") or []):
            if not isinstance(item, dict):
                continue
            row = dict(item)
            symbol = str(row.get("symbol", "")).strip()
            gate_row = EvaluationWorkspaceService._find_gate_row(gate_matrix=gate_matrix, symbol=symbol)
            candidate = candidate_by_symbol.get(symbol, {})
            failure_reasons = [
                str(reason).strip()
                for reason in list(row.get("failure_reasons") or [])
                if str(reason).strip()
            ]
            elimination_reason = EvaluationWorkspaceService._resolve_elimination_reason(row=row, failure_reasons=failure_reasons)
            row["failure_reasons"] = failure_reasons
            row["recommendation_reason"] = str(row.get("recommendation_reason", "")).strip()
            row["elimination_reason"] = elimination_reason
            template_fit = EvaluationWorkspaceService._build_template_fit_story(
                symbol=symbol or "当前候选",
                current_research_template=current_research_template,
                option_catalogs=option_catalogs,
                gate_row=gate_row,
                next_action=str(row.get("next_action", "")).strip(),
                raw_reason=str(row.get("recommendation_reason", "") or elimination_reason),
                strategy_template=str(candidate.get("strategy_template", "") or row.get("strategy_template", "")).strip(),
            )
            row["research_template"] = current_research_template
            row["template_fit_status"] = str(template_fit.get("status", "unavailable"))
            row["template_fit_headline"] = str(template_fit.get("headline", "当前还没有模板适配结论"))
            row["template_fit_detail"] = str(template_fit.get("detail", "当前还没有模板适配说明"))
            rows.append(row)
        return rows

    @staticmethod
    def _build_best_experiment(
        *,
        leaderboard: list[dict[str, object]],
        gate_matrix: list[dict[str, object]],
        overview: dict[str, object],
        research_reviews: dict[str, object],
        validation_reviews: dict[str, object],
        candidate_scope: dict[str, object],
    ) -> dict[str, object]:
        """提炼当前最值得继续推进的一轮实验。"""

        top = dict(leaderboard[0] or {}) if leaderboard else {}
        research_review = dict(research_reviews.get("research") or {})
        validation_review = dict(validation_reviews.get("validation") or {})
        symbol = str(top.get("symbol", "") or overview.get("recommended_symbol", "")).strip()
        next_action = str(
            top.get("next_action", "")
            or research_review.get("next_action", "")
            or overview.get("recommended_action", "")
        ).strip()
        gate_row = EvaluationWorkspaceService._find_gate_row(gate_matrix=gate_matrix, symbol=symbol)
        requested_stage = EvaluationWorkspaceService._resolve_requested_stage(next_action=next_action, symbol=symbol)
        recommended_stage = EvaluationWorkspaceService._resolve_recommended_stage(
            next_action=next_action,
            symbol=symbol,
            candidate_scope=candidate_scope,
            gate_row=gate_row,
        )
        normalized_next_action = EvaluationWorkspaceService._normalize_next_action_for_stage(
            stage=recommended_stage,
            next_action=next_action,
        )
        reason = str(
            top.get("recommendation_reason", "")
            or top.get("review_result", "")
            or research_review.get("result", "")
            or validation_review.get("result", "")
        ).strip()
        if not reason:
            reason = "当前还没有足够结果判断哪一轮更适合继续推进。"
        score = str(top.get("score", "")).strip()
        recommendation_story = EvaluationWorkspaceService._build_recommendation_story(
            symbol=symbol or "当前候选",
            stage=recommended_stage,
            score=score,
            next_action=normalized_next_action,
            raw_reason=reason,
            review_result=str(research_review.get("result", "") or validation_review.get("result", "") or ""),
            gate_row=gate_row,
            scope_reason=(
                EvaluationWorkspaceService._build_candidate_scope_block_reason(
                    candidate_scope=candidate_scope,
                    stage=requested_stage,
                    symbol=symbol,
                )
                if requested_stage != recommended_stage
                else ""
            ),
        )
        return {
            "symbol": symbol,
            "recommended_stage": recommended_stage,
            "next_action": normalized_next_action
            or (
                "go_live"
                if recommended_stage == "live"
                else "go_dry_run"
                if recommended_stage == "dry_run"
                else "continue_research"
            ),
            "reason": str(recommendation_story.get("detail", "")).strip() or reason,
            "score": score,
        }

    @staticmethod
    def _build_recommendation_explanation(
        *,
        leaderboard: list[dict[str, object]],
        gate_matrix: list[dict[str, object]],
        best_experiment: dict[str, object],
        review_result: str,
    ) -> dict[str, object]:
        """把推荐理由整理成前端可直接显示的解释摘要。"""

        top = dict(leaderboard[0] or {}) if leaderboard else {}
        symbol = str(best_experiment.get("symbol", "") or top.get("symbol", "")).strip() or "当前候选"
        stage = str(best_experiment.get("recommended_stage", "dry_run") or "dry_run")
        score = str(best_experiment.get("score", "") or top.get("score", "")).strip() or "n/a"
        action = str(best_experiment.get("next_action", "") or top.get("next_action", "")).strip() or "continue_research"
        raw_reason = str(top.get("recommendation_reason", "")).strip()
        story = EvaluationWorkspaceService._build_recommendation_story(
            symbol=symbol,
            stage=stage,
            score=score,
            next_action=action,
            raw_reason=raw_reason,
            review_result=review_result,
            gate_row=EvaluationWorkspaceService._find_gate_row(gate_matrix=gate_matrix, symbol=symbol),
        )
        story["template_fit"] = {
            "status": str(top.get("template_fit_status", "unavailable") or "unavailable"),
            "template_key": str(top.get("research_template", "") or ""),
            "headline": str(top.get("template_fit_headline", "当前还没有模板适配结论") or "当前还没有模板适配结论"),
            "detail": str(top.get("template_fit_detail", "当前还没有模板适配说明") or "当前还没有模板适配说明"),
        }
        return story

    @staticmethod
    def _build_best_stage_candidates(
        *,
        leaderboard: list[dict[str, object]],
        gate_matrix: list[dict[str, object]],
        overview: dict[str, object],
        validation_reviews: dict[str, object],
        candidate_scope: dict[str, object],
    ) -> dict[str, dict[str, str]]:
        """按阶段提炼最值得继续推进的候选。"""

        gate_by_symbol = {
            str(item.get("symbol", "")).strip(): dict(item)
            for item in gate_matrix
            if str(item.get("symbol", "")).strip()
        }
        research_review = dict(validation_reviews.get("research") or {})

        def build_stage_candidate(stage: str, *, allow_key: str) -> dict[str, str]:
            for item in leaderboard:
                symbol = str(item.get("symbol", "")).strip()
                gate = gate_by_symbol.get(symbol, {})
                if not gate:
                    continue
                if not bool(gate.get(allow_key)):
                    continue
                if not EvaluationWorkspaceService._candidate_scope_allows_stage(
                    candidate_scope=candidate_scope,
                    stage=stage,
                    symbol=symbol,
                    gate_row=gate,
                ):
                    continue
                score = str(item.get("score", "")).strip() or "n/a"
                next_action = str(item.get("next_action", "")).strip() or ("go_live" if stage == "live" else "enter_dry_run")
                default_reason = (
                    f"{symbol or '当前候选'} 当前更值得进入 {'live' if stage == 'live' else 'dry-run'}。"
                )
                reason = str(item.get("recommendation_reason", "")).strip() or default_reason
                return {
                    "symbol": symbol or "当前候选",
                    "stage": stage,
                    "score": score,
                    "next_action": next_action,
                    "reason": reason,
                }
            fallback_symbol = str(overview.get("recommended_symbol", "")).strip() or "当前还没有候选"
            fallback_action = str(research_review.get("next_action", "") or overview.get("recommended_action", "")).strip()
            scope_reason = EvaluationWorkspaceService._build_candidate_scope_block_reason(
                candidate_scope=candidate_scope,
                stage=stage,
                symbol=fallback_symbol,
            )
            return {
                "symbol": fallback_symbol,
                "stage": stage,
                "score": "n/a",
                "next_action": "continue_research" if scope_reason else fallback_action or "continue_research",
                "reason": scope_reason or f"当前还没有候选明确满足 {'live' if stage == 'live' else 'dry-run'} 放行条件。",
            }

        return {
            "dry_run": build_stage_candidate("dry_run", allow_key="allowed_to_dry_run"),
            "live": build_stage_candidate("live", allow_key="allowed_to_live"),
        }

    @staticmethod
    def _build_elimination_explanation(
        *,
        leaderboard: list[dict[str, object]],
        gate_matrix: list[dict[str, object]],
    ) -> dict[str, object]:
        """把淘汰原因压成一段更直白的说明。"""

        blocked_rows = [dict(item) for item in leaderboard if str(item.get("elimination_reason", "已通过")) != "已通过"]
        if not blocked_rows:
            return {
                "headline": "当前没有明显淘汰项",
                "detail": "这一轮候选要么已通过，要么还没有生成足够多的阻断记录。",
                "top_reason": "当前没有主要淘汰原因",
                "primary_symbol": "",
                "primary_gate": "",
                "next_step": "继续保持当前门槛，等下一轮候选进入评估。",
                "evidence": [],
            }
        top_row = blocked_rows[0]
        symbol = str(top_row.get("symbol", "")).strip() or "当前候选"
        gate_row = EvaluationWorkspaceService._find_gate_row(gate_matrix=gate_matrix, symbol=symbol)
        primary_gate = str(gate_row.get("blocking_gate", "")).strip() or "unknown"
        top_reason = EvaluationWorkspaceService._format_reason_text(str(top_row.get("elimination_reason", "")).strip()) or "当前没有主要淘汰原因"
        gate_label = EvaluationWorkspaceService._format_gate_name(primary_gate)
        next_step = EvaluationWorkspaceService._build_gate_fix_action(primary_gate=primary_gate)
        return {
            "headline": f"{symbol} 当前主要卡在{gate_label}",
            "detail": f"{symbol} 目前被 {gate_label} 拦下，主要原因是 {top_reason}，先处理这个卡点，再决定要不要继续放量。",
            "top_reason": top_reason,
            "primary_symbol": symbol,
            "primary_gate": primary_gate,
            "next_step": next_step,
            "template_fit": {
                "status": str(top_row.get("template_fit_status", "unavailable") or "unavailable"),
                "template_key": str(top_row.get("research_template", "") or ""),
                "headline": str(top_row.get("template_fit_headline", "当前还没有模板适配结论") or "当前还没有模板适配结论"),
                "detail": str(top_row.get("template_fit_detail", "当前还没有模板适配说明") or "当前还没有模板适配说明"),
            },
            "evidence": [
                f"当前被拦下 {len(blocked_rows)} 个候选",
                f"最靠前候选：{symbol} / {gate_label}",
                f"主要原因：{top_reason}",
                f"修复方向：{next_step}",
            ],
        }

    @staticmethod
    def _build_alignment_story(
        *,
        alignment_details: dict[str, object],
        alignment_actions: list[dict[str, object]],
    ) -> dict[str, str]:
        """把研究和执行之间的差异压成一句结论。"""

        reasons = [str(item) for item in list(alignment_details.get("difference_reasons") or []) if str(item).strip()]
        first_action = dict(alignment_actions[0] or {}) if alignment_actions else {}
        summary = str(alignment_details.get("difference_summary", "") or "当前还没有足够结果可对齐")
        research_symbol = str(alignment_details.get("research_symbol", "")).strip()
        last_order_symbol = str(alignment_details.get("last_order_symbol", "")).strip()
        last_position_symbol = str(alignment_details.get("last_position_symbol", "")).strip()
        headline = (
            f"研究侧推荐 {research_symbol}，执行侧还没完全对齐"
            if research_symbol and reasons != ["当前没有明显差异"]
            else summary
        )
        detail = " / ".join(
            EvaluationWorkspaceService._format_alignment_reason(item)
            for item in reasons[:4]
        ) if reasons else "当前没有明显差异。"
        if reasons == ["当前没有明显差异"]:
            detail = "研究侧推荐、最近订单和最近持仓目前一致。"
        return {
            "headline": headline,
            "detail": detail,
            "evidence": [
                f"研究侧：{research_symbol or '当前还没有推荐标的'}",
                f"执行侧最近订单：{last_order_symbol or '当前没有订单'}",
                f"执行侧最近持仓：{last_position_symbol or '当前没有持仓'}",
                f"主要卡点：{detail}",
            ] if reasons != ["当前没有明显差异"] else [headline],
            "next_step": str(alignment_details.get("next_step", "") or first_action.get("detail", "") or "先继续观察。"),
        }

    @staticmethod
    def _build_alignment_metric_rows(
        *,
        best_experiment: dict[str, object],
        best_stage_candidates: dict[str, dict[str, str]],
        execution_alignment: dict[str, object],
        validation_reviews: dict[str, object],
    ) -> list[dict[str, str]]:
        """把研究、回测和执行放到一张对照表里。"""

        execution = dict(execution_alignment.get("execution") or {})
        backtest = dict(execution_alignment.get("backtest") or {})
        research_review = dict(validation_reviews.get("research") or {})
        dry_candidate = dict(best_stage_candidates.get("dry_run") or {})
        live_candidate = dict(best_stage_candidates.get("live") or {})
        research_symbol = str(best_experiment.get("symbol", "")).strip() or "当前候选"
        research_action = str(best_experiment.get("next_action", "")).strip() or "continue_research"
        research_result = str(research_review.get("result", "")).strip() or "未生成"
        runtime_mode = str(execution.get("runtime_mode", "")).strip() or "unknown"
        latest_sync_status = str(execution.get("latest_sync_status", "")).strip() or "unknown"
        matched_order_count = str(execution.get("matched_order_count", "0"))
        matched_position_count = str(execution.get("matched_position_count", "0"))
        backtest_net_return = str(backtest.get("net_return_pct", "")).strip() or "n/a"
        backtest_sharpe = str(backtest.get("sharpe", "")).strip() or "n/a"
        backtest_win_rate = str(backtest.get("win_rate", "")).strip() or "n/a"

        return [
            {
                "metric": "研究结论",
                "research": f"{research_symbol} / {research_action} / {research_result}",
                "backtest": "先看这一轮候选在回测里有没有稳定通过。",
                "execution": f"{runtime_mode} / 同步 {latest_sync_status}",
                "impact": "先确认研究推荐和执行状态是不是还在同一轮。",
            },
            {
                "metric": "阶段候选",
                "research": f"dry-run：{str(dry_candidate.get('symbol', 'n/a'))} / {str(dry_candidate.get('reason', ''))}",
                "backtest": f"live：{str(live_candidate.get('symbol', 'n/a'))} / {str(live_candidate.get('reason', ''))}",
                "execution": (
                    f"下一步 {EvaluationWorkspaceService._format_stage_label(str(best_experiment.get('recommended_stage', 'research')))}"
                    f" / {str(best_experiment.get('next_action', 'continue_research'))}"
                ),
                "impact": "先分清现在更适合继续 dry-run，还是已经够格进入 live。",
            },
            {
                "metric": "回测结论",
                "research": f"净收益 {backtest_net_return}",
                "backtest": f"Sharpe {backtest_sharpe} / 胜率 {backtest_win_rate}",
                "execution": f"订单 {matched_order_count} / 持仓 {matched_position_count}",
                "impact": "这里直接对照回测表现和执行落地有没有明显落差。",
            },
        ]

    @staticmethod
    def _build_stage_decision_summary(
        *,
        best_experiment: dict[str, object],
        recommendation_explanation: dict[str, object],
        elimination_explanation: dict[str, object],
        alignment_details: dict[str, object],
    ) -> dict[str, str]:
        """把“为什么推荐 / 为什么淘汰 / 和执行差在哪”压成直白摘要。"""

        symbol = str(best_experiment.get("symbol", "")).strip() or "当前候选"
        stage = str(best_experiment.get("recommended_stage", "research") or "research")
        stage_label = EvaluationWorkspaceService._format_stage_label(stage)
        return {
            "headline": (
                f"{symbol} 现在更适合先继续研究"
                if stage == "research"
                else f"{symbol} 现在更适合进入 {stage_label}"
            ),
            "why_recommended": str(recommendation_explanation.get("detail", "")).strip() or "当前还没有足够理由说明为什么推荐。",
            "why_blocked": str(elimination_explanation.get("detail", "")).strip() or "当前没有额外淘汰说明。",
            "execution_gap": str(alignment_details.get("difference_summary", "")).strip() or "当前还没有研究与执行差异摘要。",
            "template_fit": str(
                dict(recommendation_explanation.get("template_fit") or {}).get("detail", "")
                or dict(elimination_explanation.get("template_fit") or {}).get("detail", "")
                or "当前还没有模板适配说明。"
            ).strip(),
            "next_step": str(best_experiment.get("next_action", "")).strip() or "continue_research",
        }

    @staticmethod
    def _resolve_current_research_template(
        *,
        report: dict[str, object],
        configured_research: dict[str, object],
    ) -> str:
        """优先读取当前配置，再回退到最近产物。"""

        configured_template = str(configured_research.get("research_template", "") or "").strip()
        if configured_template:
            return configured_template
        latest_training = dict(report.get("latest_training") or {})
        training_context = dict(latest_training.get("training_context") or {})
        training_parameters = dict(training_context.get("parameters") or {})
        latest_inference = dict(report.get("latest_inference") or {})
        inference_context = dict(latest_inference.get("inference_context") or {})
        input_summary = dict(inference_context.get("input_summary") or {})
        return str(
            latest_inference.get("research_template")
            or input_summary.get("research_template")
            or latest_training.get("research_template")
            or training_parameters.get("research_template")
            or "single_asset_timing"
        ).strip()

    @staticmethod
    def _build_template_fit_story(
        *,
        symbol: str,
        current_research_template: str,
        option_catalogs: dict[str, object],
        gate_row: dict[str, object],
        next_action: str,
        raw_reason: str,
        strategy_template: str,
    ) -> dict[str, str]:
        """把候选和当前研究模板的关系翻译成一段直白说明。"""

        template_catalog = [
            dict(item)
            for item in list(option_catalogs.get("research_template_catalog") or [])
            if isinstance(item, dict)
        ]
        template_key = str(current_research_template or "single_asset_timing").strip() or "single_asset_timing"
        template_item = EvaluationWorkspaceService._resolve_catalog_item(
            template_catalog,
            key=template_key,
            fallback_label=template_key,
        )
        allowed_to_dry_run = bool(gate_row.get("allowed_to_dry_run"))
        allowed_to_live = bool(gate_row.get("allowed_to_live"))
        primary_reason = str(gate_row.get("primary_reason", "")).strip()
        cleaned_reason = EvaluationWorkspaceService._format_reason_text(raw_reason)
        stage = EvaluationWorkspaceService._resolve_requested_stage(next_action=next_action, symbol=symbol)
        detail_parts: list[str] = []
        if template_key == "single_asset_timing_strict":
            if allowed_to_live or stage == "live":
                headline = f"{symbol} 更适合 {template_item['label']}"
                status = "matched"
                detail_parts.append(f"当前模板是 {template_item['label']}，更强调趋势、量能和波动一致性，这只币已经够格继续往更严格阶段推进")
            elif allowed_to_dry_run:
                headline = f"{symbol} 先按 {template_item['label']} 继续观察"
                status = "guarded"
                detail_parts.append(f"当前模板是 {template_item['label']}，这只币已经过了 dry-run 门，但还没同时满足更严格的放量条件")
            else:
                headline = f"{symbol} 暂时不适合 {template_item['label']}"
                status = "blocked"
                detail_parts.append(f"当前模板是 {template_item['label']}，这只币还没满足更强调一致性的筛选要求")
        else:
            if allowed_to_dry_run:
                headline = f"{symbol} 更适合 {template_item['label']}"
                status = "matched"
                detail_parts.append(f"当前模板是 {template_item['label']}，更适合先抓趋势和动量，这只币已经过了 dry-run 门")
            else:
                headline = f"{symbol} 暂时不适合 {template_item['label']}"
                status = "blocked"
                detail_parts.append(f"当前模板是 {template_item['label']}，会先用更宽一点的择时口径筛候选，但这只币暂时还没过 dry-run 门")
        if strategy_template:
            detail_parts.append(f"当前会承接到 {strategy_template} 这套执行模板")
        if primary_reason and primary_reason != "已通过":
            detail_parts.append(f"主要卡点是 {primary_reason}")
        elif cleaned_reason and cleaned_reason not in {"候选已就绪"}:
            detail_parts.append(f"研究侧判断是 {cleaned_reason}")
        return {
            "status": status,
            "headline": headline,
            "detail": "；".join(detail_parts) + "。",
        }

    @staticmethod
    def _build_decision_board(
        *,
        best_experiment: dict[str, object],
        best_stage_candidates: dict[str, dict[str, str]],
        recommendation_explanation: dict[str, object],
        elimination_explanation: dict[str, object],
        alignment_story: dict[str, object],
    ) -> dict[str, object]:
        """把 dry-run / live 的推进判断收成统一决策入口。"""

        primary_stage = str(best_experiment.get("recommended_stage", "research") or "research")
        primary_symbol = str(best_experiment.get("symbol", "")).strip()
        next_action = str(best_experiment.get("next_action", "")).strip() or "continue_research"
        if not primary_symbol or primary_stage == "research":
            primary_stage = "research"
        if primary_stage == "live":
            headline = f"现在先把 {primary_symbol or '当前候选'} 推进到 live"
            summary = str(recommendation_explanation.get("detail", "")).strip() or "当前已经够格进入 live。"
        elif primary_stage == "dry_run" and primary_symbol:
            headline = f"现在先把 {primary_symbol} 推进到 dry-run"
            summary = str(recommendation_explanation.get("detail", "")).strip() or "当前更适合先进入 dry-run。"
        else:
            primary_stage = "research"
            headline = "现在先补研究结果，再决定推进哪一层"
            summary = "当前还没有足够候选可以进入 dry-run 或 live。"

        dry_candidate = dict(best_stage_candidates.get("dry_run") or {})
        live_candidate = dict(best_stage_candidates.get("live") or {})

        return {
            "headline": headline,
            "summary": summary,
            "primary_stage": primary_stage,
            "next_action": next_action,
            "cards": [
                EvaluationWorkspaceService._build_decision_card(
                    stage="dry_run",
                    candidate=dry_candidate,
                    primary_stage=primary_stage,
                    recommendation_explanation=recommendation_explanation,
                    elimination_explanation=elimination_explanation,
                    alignment_story=alignment_story,
                ),
                EvaluationWorkspaceService._build_decision_card(
                    stage="live",
                    candidate=live_candidate,
                    primary_stage=primary_stage,
                    recommendation_explanation=recommendation_explanation,
                    elimination_explanation=elimination_explanation,
                    alignment_story=alignment_story,
                ),
            ],
        }

    @staticmethod
    def _build_decision_card(
        *,
        stage: str,
        candidate: dict[str, str],
        primary_stage: str,
        recommendation_explanation: dict[str, object],
        elimination_explanation: dict[str, object],
        alignment_story: dict[str, object],
    ) -> dict[str, str]:
        """给 dry-run / live 各生成一张稳定决策卡。"""

        stage_label = "live" if stage == "live" else "dry-run"
        symbol = str(candidate.get("symbol", "")).strip() or "当前还没有候选"
        reason = str(candidate.get("reason", "")).strip() or f"当前还没有候选明确满足 {stage_label} 放行条件。"
        next_step = str(candidate.get("next_action", "")).strip() or "continue_research"

        if primary_stage == "research":
            decision = "暂时还不能推进"
            decision_reason = "当前还没有足够研究结果，先补训练、推理和评估。"
        elif stage == primary_stage:
            decision = "现在值得推进"
            decision_reason = str(recommendation_explanation.get("detail", "")).strip() or reason
        elif stage == "live":
            decision = "暂时不优先"
            decision_reason = "当前流程仍先看 dry-run 复盘，不直接放到 live。"
        else:
            decision = "当前不是第一优先"
            decision_reason = str(alignment_story.get("detail", "")).strip() or reason

        return {
            "stage": stage,
            "symbol": symbol,
            "decision": decision,
            "reason": decision_reason,
            "blocking": str(elimination_explanation.get("detail", "")).strip() if stage != primary_stage else str(candidate.get("reason", "")).strip() or str(elimination_explanation.get("detail", "")).strip(),
            "next_step": next_step,
            "readiness": "ready" if stage == primary_stage and primary_stage != "research" else "waiting",
        }

    @staticmethod
    def _find_gate_row(*, gate_matrix: list[dict[str, object]], symbol: str) -> dict[str, object]:
        """按标的查找当前候选的门控摘要。"""

        target = str(symbol or "").strip()
        if not target:
            return {}
        for item in gate_matrix:
            if str(item.get("symbol", "")).strip() == target:
                return dict(item)
        return {}

    @staticmethod
    def _build_recommendation_story(
        *,
        symbol: str,
        stage: str,
        score: str,
        next_action: str,
        raw_reason: str,
        review_result: str,
        gate_row: dict[str, object],
        scope_reason: str = "",
    ) -> dict[str, object]:
        """把推荐理由压成稳定的人话结论。"""

        target = EvaluationWorkspaceService._format_stage_label(stage)
        dry_run_status = "通过" if bool(gate_row.get("allowed_to_dry_run")) else "拦下"
        live_status = str(gate_row.get("live_gate", "n/a") or "n/a")
        primary_reason = str(gate_row.get("primary_reason", "")).strip()
        if stage == "research":
            detail_parts = [f"{symbol} 当前综合排序第一，但还不能直接推进到 dry-run 或 live"]
        else:
            detail_parts = [f"{symbol} 当前综合排序第一，更适合先进入 {target}"]

        if stage == "research":
            if primary_reason and primary_reason != "已通过":
                detail_parts.append(f"当前主要卡点是 {primary_reason}")
            else:
                detail_parts.append("当前还需要先补训练、推理或复盘")
        elif dry_run_status == "通过" and live_status == "通过" and stage != "live":
            detail_parts.append("虽然 live 门也已通过，但当前流程仍先进入 dry-run，再决定是否继续放到 live")
        elif dry_run_status == "通过" and live_status == "通过":
            detail_parts.append("dry-run 和 live 门都已通过，可以直接继续推进 live")
        elif dry_run_status == "通过":
            if primary_reason and primary_reason != "已通过":
                detail_parts.append(f"dry-run 门已通过，但 live 门还没放行，当前主要卡点是 {primary_reason}")
            else:
                detail_parts.append("dry-run 门已通过，但 live 门还没放行，先进入 dry-run 继续观察")
        else:
            if primary_reason and primary_reason != "已通过":
                detail_parts.append(f"当前还没过 dry-run 门，主要卡点是 {primary_reason}")
            else:
                detail_parts.append("当前还没过 dry-run 门，先继续研究")

        cleaned_reason = EvaluationWorkspaceService._format_reason_text(raw_reason)
        if cleaned_reason and cleaned_reason not in {"候选已就绪"}:
            detail_parts.append(f"当前信号侧判断是：{cleaned_reason}")
        if scope_reason:
            detail_parts.append(scope_reason)

        gate_summary = f"dry-run 门：{dry_run_status}；live 门：{live_status}"
        if live_status != "通过" and primary_reason and primary_reason != "已通过":
            gate_summary = f"{gate_summary}（当前卡点：{primary_reason}）"
        if scope_reason:
            gate_summary = f"{gate_summary}；范围契约：{scope_reason}"

        return {
            "headline": (
                f"{symbol} 当前先继续研究"
                if stage == "research"
                else f"{symbol} 当前优先进入 {target}"
            ),
            "detail": "；".join(detail_parts) + "。",
            "evidence": [
                f"分数 {score or 'n/a'} / 当前综合排序第一",
                gate_summary,
                f"研究复盘：{EvaluationWorkspaceService._format_review_summary(review_result=review_result, next_action=next_action)}",
            ],
        }

    @staticmethod
    def _resolve_requested_stage(*, next_action: str, symbol: str) -> str:
        """按下一步动作判断当前更适合停在哪一层。"""

        if not symbol.strip():
            return "research"
        action = str(next_action).strip().lower()
        if action in {"go_live", "enter_live"}:
            return "live"
        if action in {"go_dry_run", "enter_dry_run"}:
            return "dry_run"
        return "research"

    @staticmethod
    def _resolve_recommended_stage(
        *,
        next_action: str,
        symbol: str,
        candidate_scope: dict[str, object],
        gate_row: dict[str, object],
    ) -> str:
        """结合统一范围契约和门控结果，判断当前更适合停在哪一层。"""

        requested_stage = EvaluationWorkspaceService._resolve_requested_stage(next_action=next_action, symbol=symbol)
        if requested_stage == "live":
            if EvaluationWorkspaceService._candidate_scope_allows_stage(
                candidate_scope=candidate_scope,
                stage="live",
                symbol=symbol,
                gate_row=gate_row,
            ):
                return "live"
            if EvaluationWorkspaceService._candidate_scope_allows_stage(
                candidate_scope=candidate_scope,
                stage="dry_run",
                symbol=symbol,
                gate_row=gate_row,
            ):
                return "dry_run"
            return "research"
        if requested_stage == "dry_run":
            if EvaluationWorkspaceService._candidate_scope_allows_stage(
                candidate_scope=candidate_scope,
                stage="dry_run",
                symbol=symbol,
                gate_row=gate_row,
            ):
                return "dry_run"
            return "research"
        return "research"

    @staticmethod
    def _normalize_next_action_for_stage(*, stage: str, next_action: str) -> str:
        """把动作和最终推荐阶段对齐。"""

        action = str(next_action).strip()
        if stage == "live":
            return action if action in {"go_live", "enter_live"} else "go_live"
        if stage == "dry_run":
            return action if action in {"go_dry_run", "enter_dry_run"} else "go_dry_run"
        return action if action in {"run_training", "run_inference", "wait_live", "continue_research"} else "continue_research"

    @staticmethod
    def _candidate_scope_allows_stage(
        *,
        candidate_scope: dict[str, object],
        stage: str,
        symbol: str,
        gate_row: dict[str, object],
    ) -> bool:
        """判断统一范围契约是否允许当前标的进入目标阶段。"""

        target_symbol = str(symbol or "").strip()
        if not target_symbol:
            return False
        status = str(candidate_scope.get("status", "candidate_pool_missing") or "candidate_pool_missing")
        candidate_symbols = {
            str(item).strip()
            for item in list(candidate_scope.get("candidate_symbols") or [])
            if str(item).strip()
        }
        live_symbols = {
            str(item).strip()
            for item in list(candidate_scope.get("live_allowed_symbols") or [])
            if str(item).strip()
        }
        if stage == "live":
            return (
                status == "ready"
                and target_symbol in candidate_symbols
                and target_symbol in live_symbols
                and bool(gate_row.get("allowed_to_live"))
            )
        return (
            status != "candidate_pool_missing"
            and target_symbol in candidate_symbols
            and bool(gate_row.get("allowed_to_dry_run"))
        )

    @staticmethod
    def _build_candidate_scope_block_reason(
        *,
        candidate_scope: dict[str, object],
        stage: str,
        symbol: str,
    ) -> str:
        """把范围契约导致的阻断翻译成直白说明。"""

        target_symbol = str(symbol or "").strip()
        status = str(candidate_scope.get("status", "candidate_pool_missing") or "candidate_pool_missing")
        candidate_symbols = {
            str(item).strip()
            for item in list(candidate_scope.get("candidate_symbols") or [])
            if str(item).strip()
        }
        live_symbols = {
            str(item).strip()
            for item in list(candidate_scope.get("live_allowed_symbols") or [])
            if str(item).strip()
        }
        removed_symbols = [
            str(item).strip()
            for item in list(candidate_scope.get("live_removed_symbols") or [])
            if str(item).strip()
        ]
        if stage == "live":
            if status == "candidate_pool_missing":
                return "当前还没有统一候选池，先把研究 / dry-run 候选池固定下来。"
            if status == "live_subset_missing":
                return "当前 live 子集还没放行，先决定哪些币允许继续进入 live。"
            if status == "live_subset_out_of_scope":
                removed_summary = " / ".join(removed_symbols) if removed_symbols else "原 live 子集"
                return f"当前 live 子集已经和候选池脱节，先把 {removed_summary} 收回到当前候选池内。"
            if target_symbol and target_symbol not in live_symbols:
                return f"{target_symbol} 当前不在 live 子集内，先留在 dry-run 继续观察。"
        if stage == "dry_run":
            if status == "candidate_pool_missing":
                return "当前还没有统一候选池，先在数据工作台选好研究 / dry-run 候选池。"
            if target_symbol and target_symbol not in candidate_symbols:
                return f"{target_symbol} 当前不在统一候选池内，先回到数据工作台调整候选范围。"
        return ""

    @staticmethod
    def _format_stage_label(stage: str) -> str:
        """把内部阶段键翻译成人话。"""

        if stage == "live":
            return "live"
        if stage == "dry_run":
            return "dry-run"
        return "继续研究"

    @staticmethod
    def _format_review_summary(*, review_result: str, next_action: str) -> str:
        """把研究复盘结果翻译成前端可读说明。"""

        result_label_map = {
            "candidate_ready": "候选已就绪",
            "candidate_blocked": "候选暂未通过",
            "training_missing": "训练结果缺失",
            "inference_missing": "推理结果缺失",
            "waiting": "当前仍在等待",
            "succeeded": "当前已完成",
            "failed": "当前已失败",
        }
        action_label_map = {
            "enter_dry_run": "先进入 dry-run",
            "go_dry_run": "先进入 dry-run",
            "go_live": "准备进入 live",
            "enter_live": "准备进入 live",
            "continue_research": "先继续研究",
            "run_training": "先跑训练",
            "run_inference": "先补推理",
            "wait_live": "继续等待 live",
        }
        result_label = result_label_map.get(str(review_result).strip(), str(review_result).strip() or "当前还没有复盘结论")
        action_label = action_label_map.get(str(next_action).strip(), str(next_action).strip() or "继续观察")
        if result_label and action_label:
            return f"{result_label}，{action_label}"
        return result_label or action_label or "当前还没有复盘结论"

    @staticmethod
    def _format_reason_text(value: str) -> str:
        """把内部原因码翻译成页面可读文本。"""

        mapping = {
            "candidate_ready": "候选已就绪",
            "candidate_blocked": "候选暂未通过",
            "training_missing": "训练结果缺失",
            "inference_missing": "推理结果缺失",
            "sample_count_too_low": "样本数不足",
            "validation_score_too_low": "验证分数不足",
            "score_below_live_floor": "live 分数不足",
            "live_threshold_not_met": "live 门槛未满足",
            "waiting": "当前仍在等待",
            "failed": "当前已失败",
        }
        text = str(value or "").strip()
        return mapping.get(text, text)

    @staticmethod
    def _format_gate_name(value: str) -> str:
        """把门控字段翻译成页面可读名称。"""

        mapping = {
            "rule_gate": "规则门",
            "validation_gate": "验证门",
            "backtest_gate": "回测门",
            "consistency_gate": "一致性门",
            "dry_run_gate": "dry-run 门",
            "live_gate": "live 门",
            "passed": "已通过",
            "unknown": "当前门控",
        }
        text = str(value or "").strip()
        return mapping.get(text, text or "当前门控")

    @staticmethod
    def _build_gate_fix_action(*, primary_gate: str) -> str:
        """按主要卡点给出一句修复方向。"""

        mapping = {
            "rule_gate": "先补趋势、量能或波动过滤，再重跑研究。",
            "validation_gate": "先补验证样本量或样本外收益，再决定要不要继续推进。",
            "backtest_gate": "先回看回测收益、回撤和成本模型，再决定要不要继续放行。",
            "consistency_gate": "先缩小训练/验证/回测之间的漂移，再继续推进。",
            "dry_run_gate": "先让候选满足 dry-run 门，再考虑进入观察阶段。",
            "live_gate": "先补 live 门要求，再考虑进入小额 live。",
        }
        return mapping.get(str(primary_gate).strip(), "先补主要卡点，再决定要不要继续推进。")

    @staticmethod
    def _format_alignment_reason(value: str) -> str:
        """把研究/执行差异翻译成统一口径。"""

        text = str(value or "").strip()
        if text.startswith("最近订单仍是 "):
            return f"执行侧最近订单仍是 {text.removeprefix('最近订单仍是 ')}"
        if text.startswith("最近持仓仍是 "):
            return f"执行侧最近持仓仍是 {text.removeprefix('最近持仓仍是 ')}"
        if text == "同步失败":
            return "执行同步失败"
        if text == "当前仍在手动模式，需要人工确认":
            return "当前仍在手动模式，需要人工确认"
        if text == "当前没有明显差异":
            return "研究和执行当前没有明显差异"
        return text

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
    def _build_experiment_comparison(report: dict[str, object], *, limit: int) -> list[dict[str, object]]:
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
        return rows[:limit]

    @staticmethod
    def _build_recent_run_history(*, report: dict[str, object], run_type: str, limit: int) -> list[dict[str, object]]:
        """按训练或推理拆出最近运行历史。"""

        experiments = dict(report.get("experiments") or {})
        recent_runs = [dict(item) for item in list(experiments.get("recent_runs") or []) if isinstance(item, dict)]
        rows: list[dict[str, object]] = []
        for item in recent_runs:
            if str(item.get("run_type", "")) != run_type:
                continue
            backtest = dict((item.get("backtest") or {}).get("metrics") or item.get("backtest") or {})
            context = dict(item.get("training_context") or item.get("inference_context") or {})
            parameters = dict(context.get("parameters") or context.get("input_summary") or {})
            rows.append(
                {
                    "run_id": str(item.get("run_id", "")),
                    "status": str(item.get("status", "")),
                    "model_version": str(item.get("model_version", "")),
                    "dataset_snapshot_id": str(
                        dict(item.get("dataset_snapshot") or {}).get("snapshot_id", "")
                        or item.get("dataset_snapshot_id", "")
                    ),
                    "signal_count": str(item.get("signal_count", dict(item.get("summary") or {}).get("signal_count", ""))),
                    "net_return_pct": str(backtest.get("net_return_pct", "")),
                    "sharpe": str(backtest.get("sharpe", "")),
                    "win_rate": str(backtest.get("win_rate", "")),
                    "holding_window": str(
                        context.get("holding_window")
                        or parameters.get("holding_window_label", "")
                    ),
                    "research_preset_key": str(parameters.get("research_preset_key", "")),
                    "research_template": str(parameters.get("research_template", "")),
                    "model_key": str(parameters.get("model_key", "")),
                    "label_preset_key": str(parameters.get("label_preset_key", "")),
                    "label_mode": str(parameters.get("label_mode", "")),
                    "label_trigger_basis": str(parameters.get("label_trigger_basis", "")),
                    "window_mode": str(parameters.get("window_mode", "")),
                    "force_validation_top_candidate": "是"
                    if bool(parameters.get("force_validation_top_candidate", False))
                    else "否",
                }
            )
        return rows[:limit]

    @staticmethod
    def _build_workflow_alignment_timeline(review_report: dict[str, object]) -> list[dict[str, object]]:
        """把研究到执行的最近一轮关键节点压成时间线。"""

        recent_tasks = [dict(item) for item in list(review_report.get("recent_tasks") or []) if isinstance(item, dict)]
        rows: list[dict[str, object]] = []
        label_map = {
            "research_train": "研究训练",
            "research_infer": "研究推理",
            "signal_output": "信号输出",
            "sync": "执行同步",
            "review": "统一复盘",
        }
        for task_type in ("research_train", "research_infer", "signal_output", "sync", "review"):
            latest = next((item for item in recent_tasks if str(item.get("task_type", "")) == task_type), None)
            if not latest:
                rows.append(
                    {
                        "task_type": task_type,
                        "label": label_map.get(task_type, task_type),
                        "status": "waiting",
                        "requested_at": "",
                        "finished_at": "",
                        "detail": "当前还没有这一段记录",
                    }
                )
                continue
            rows.append(
                {
                    "task_type": task_type,
                    "label": label_map.get(task_type, task_type),
                    "status": str(latest.get("status", "waiting") or "waiting"),
                    "requested_at": str(latest.get("requested_at", "") or ""),
                    "finished_at": str(latest.get("finished_at", "") or ""),
                    "detail": str(latest.get("result_summary", "") or latest.get("error_message", "") or "当前没有额外说明"),
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
            dry_run_gate = dict(item.get("dry_run_gate") or {})
            live_gate = dict(item.get("live_gate") or {})
            blocking_gate, primary_reason = EvaluationWorkspaceService._resolve_blocking_gate(
                rule_gate=rule_gate,
                validation_gate=validation_gate,
                backtest_gate=backtest_gate,
                consistency_gate=consistency_gate,
                dry_run_gate=dry_run_gate,
                live_gate=live_gate,
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
                    "live_gate": EvaluationWorkspaceService._format_gate_status(live_gate),
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

        experiment_alignment_note = EvaluationWorkspaceService._build_experiment_alignment_note(
            training_present=bool(training),
            inference_present=bool(inference),
            training_model=training_model,
            inference_model=inference_model,
            training_snapshot=training_snapshot,
            inference_snapshot=inference_snapshot,
            model_aligned=model_aligned,
            dataset_aligned=dataset_aligned,
        )

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
            "training_model_version": training_model,
            "inference_model_version": inference_model,
            "training_dataset_snapshot": training_snapshot,
            "inference_dataset_snapshot": inference_snapshot,
            "experiment_alignment_note": experiment_alignment_note,
        }

    @staticmethod
    def _build_run_deltas(report: dict[str, object], *, limit: int = 5) -> list[dict[str, object]]:
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
                    "comparison_readiness": EvaluationWorkspaceService._resolve_comparison_readiness(
                        changed_field_payload=changed_field_payload,
                        model_changed=model_changed,
                        dataset_changed=dataset_changed,
                    ),
                    "comparison_reason": EvaluationWorkspaceService._build_comparison_reason(
                        model_changed=model_changed,
                        dataset_changed=dataset_changed,
                        changed_field_payload=changed_field_payload,
                    ),
                    "change_summary": EvaluationWorkspaceService._build_change_summary(
                        model_changed=model_changed,
                        dataset_changed=dataset_changed,
                        changed_fields=list(changed_field_payload.get("fields") or []),
                    ),
                    "note": EvaluationWorkspaceService._build_delta_note(
                        run_type=run_type,
                        model_changed=model_changed,
                        dataset_changed=dataset_changed,
                    ),
                }
            )
        return rows[:limit]

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
            "research_preset_key",
            "label_preset_key",
            "research_template",
            "model_key",
            "label_mode",
            "label_trigger_basis",
            "holding_window_label",
            "force_validation_top_candidate",
            "holding_window_min_days",
            "holding_window_max_days",
            "train_split_ratio",
            "validation_split_ratio",
            "test_split_ratio",
            "signal_confidence_floor",
            "trend_weight",
            "momentum_weight",
            "volume_weight",
            "oscillator_weight",
            "volatility_weight",
            "strict_penalty_weight",
            "primary_factors",
            "auxiliary_factors",
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
            "backtest_cost_model",
            "dry_run_min_score",
            "dry_run_min_positive_rate",
            "dry_run_min_net_return_pct",
            "dry_run_min_sharpe",
            "dry_run_max_drawdown_pct",
            "dry_run_max_loss_streak",
            "dry_run_min_win_rate",
            "dry_run_max_turnover",
            "dry_run_min_sample_count",
            "validation_min_sample_count",
            "enable_rule_gate",
            "enable_validation_gate",
            "enable_backtest_gate",
            "enable_consistency_gate",
            "enable_live_gate",
            "live_min_score",
            "live_min_positive_rate",
            "live_min_net_return_pct",
            "live_min_win_rate",
            "live_max_turnover",
            "live_min_sample_count",
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
    def _resolve_comparison_readiness(
        *,
        changed_field_payload: dict[str, object],
        model_changed: bool,
        dataset_changed: bool,
    ) -> str:
        """说明最近两轮对比当前是否完整。"""

        if str(changed_field_payload.get("status", "ready") or "ready") == "unavailable":
            return "unavailable"
        fields = list(changed_field_payload.get("fields") or [])
        return "limited" if model_changed or dataset_changed or bool(fields) else "ready"

    @staticmethod
    def _build_comparison_reason(
        *,
        model_changed: bool,
        dataset_changed: bool,
        changed_field_payload: dict[str, object],
    ) -> str:
        """生成最近两轮对比的口头原因。"""

        if str(changed_field_payload.get("status", "ready") or "ready") == "unavailable":
            return str(changed_field_payload.get("note", "") or "当前实验账本缺少配置快照，暂时无法比较。")
        reasons: list[str] = []
        fields = EvaluationWorkspaceService._format_changed_field_labels(
            list(changed_field_payload.get("fields") or []),
        )
        if model_changed and dataset_changed:
            reasons.append("模型版本和数据快照都变了，本轮收益变化不能直接归因。")
        elif model_changed:
            reasons.append("模型版本已切换，这更像换方案，不是同模型复测。")
        elif dataset_changed:
            reasons.append("数据快照已变化，这更像换样本，不是同样本复测。")
        if fields:
            reasons.append(f"关键配置也变了：{' / '.join(fields)}")
        if not reasons:
            return "模型、数据和关键配置都没变，可以直接看结果差异。"
        return "；".join(reasons)

    @staticmethod
    def _build_change_summary(
        *,
        model_changed: bool,
        dataset_changed: bool,
        changed_fields: list[object],
    ) -> str:
        """把最主要的变化压成一行摘要。"""

        summary: list[str] = []
        if model_changed:
            summary.append("模型版本")
        if dataset_changed:
            summary.append("数据快照")
        fields = EvaluationWorkspaceService._format_changed_field_labels(changed_fields)
        if fields:
            summary.extend(fields[:3])
            if len(fields) > 3:
                summary.append(f"另外还有 {len(fields) - 3} 项配置变化")
        if not summary:
            summary.append("主要结果沿用上一轮口径")
        return " / ".join(summary)

    @staticmethod
    def _format_changed_field_labels(changed_fields: list[object]) -> list[str]:
        """把内部字段名转成前端能直接读懂的中文。"""

        label_map = {
            "research_preset_key": "研究预设",
            "label_preset_key": "标签预设",
            "research_template": "研究模板",
            "model_key": "模型选择",
            "label_mode": "标签口径",
            "label_trigger_basis": "标签触发口径",
            "holding_window_label": "持有窗口",
            "force_validation_top_candidate": "强制验证当前最优候选",
            "holding_window_min_days": "最短持有天数",
            "holding_window_max_days": "最长持有天数",
            "train_split_ratio": "训练比例",
            "validation_split_ratio": "验证比例",
            "test_split_ratio": "测试比例",
            "signal_confidence_floor": "最低置信度",
            "trend_weight": "趋势权重",
            "momentum_weight": "动量权重",
            "volume_weight": "量能权重",
            "oscillator_weight": "震荡权重",
            "volatility_weight": "波动权重",
            "strict_penalty_weight": "严格模板惩罚权重",
            "primary_factors": "主判断因子",
            "auxiliary_factors": "辅助因子",
            "sample_limit": "样本长度",
            "lookback_days": "回看天数",
            "window_mode": "窗口模式",
            "start_date": "固定日期范围",
            "end_date": "固定日期范围",
            "missing_policy": "缺失处理",
            "outlier_policy": "去极值",
            "normalization_policy": "标准化",
            "backtest_fee_bps": "回测手续费",
            "backtest_slippage_bps": "回测滑点",
            "backtest_cost_model": "成本模型",
            "dry_run_min_score": "dry-run 最低分数",
            "dry_run_min_positive_rate": "dry-run 最低正收益比例",
            "dry_run_min_net_return_pct": "dry-run 最低净收益",
            "dry_run_min_sharpe": "dry-run 最低 Sharpe",
            "dry_run_max_drawdown_pct": "dry-run 最大回撤",
            "dry_run_max_loss_streak": "dry-run 最大连续亏损段",
            "dry_run_min_win_rate": "dry-run 最低胜率",
            "dry_run_max_turnover": "dry-run 最高换手",
            "dry_run_min_sample_count": "dry-run 最低样本数",
            "validation_min_sample_count": "验证最少样本数",
            "validation_min_avg_future_return_pct": "验证最低未来收益",
            "consistency_max_validation_backtest_return_gap_pct": "验证与回测最大收益差",
            "consistency_max_training_validation_positive_rate_gap": "训练与验证最大正收益比例差",
            "consistency_max_training_validation_return_gap_pct": "训练与验证最大收益差",
            "rule_min_ema20_gap_pct": "规则门最小 EMA20 偏离",
            "rule_min_ema55_gap_pct": "规则门最小 EMA55 偏离",
            "rule_max_atr_pct": "规则门最大 ATR 波动",
            "rule_min_volume_ratio": "规则门最小量能比",
            "strict_rule_min_ema20_gap_pct": "严格模板最小 EMA20 偏离",
            "strict_rule_min_ema55_gap_pct": "严格模板最小 EMA55 偏离",
            "strict_rule_max_atr_pct": "严格模板最大 ATR 波动",
            "strict_rule_min_volume_ratio": "严格模板最小量能比",
            "enable_rule_gate": "规则门开关",
            "enable_validation_gate": "验证门开关",
            "enable_backtest_gate": "回测门开关",
            "enable_consistency_gate": "一致性门开关",
            "enable_live_gate": "live 门开关",
            "live_min_score": "live 最低分数",
            "live_min_positive_rate": "live 最低正收益比例",
            "live_min_net_return_pct": "live 最低净收益",
            "live_min_win_rate": "live 最低胜率",
            "live_max_turnover": "live 最高换手",
            "live_min_sample_count": "live 最低样本数",
        }
        labels: list[str] = []
        for item in changed_fields:
            field = str(item).strip()
            if not field:
                continue
            label = label_map.get(field, field)
            if label in labels:
                continue
            labels.append(label)
        return labels

    @staticmethod
    def _build_delta_overview(report: dict[str, object]) -> dict[str, object]:
        """把最近两轮对比压成一张概况卡。"""

        rows = EvaluationWorkspaceService._build_run_deltas(report)
        if not rows:
            return {
                "status": "unavailable",
                "headline": "当前还没有足够的实验账本",
                "detail": "至少要有两轮同类型训练或推理，系统才会给出最近两轮变化焦点。",
            }
        current = dict(rows[0])
        return {
            "status": str(current.get("comparison_readiness", "ready") or "ready"),
            "headline": f"当前先看：{str(current.get('change_summary', '') or '当前没有变化摘要')}",
            "detail": str(current.get("comparison_reason", "") or "当前没有变化说明"),
            "note": str(current.get("note", "") or "当前没有补充说明"),
        }

    @staticmethod
    def _build_alignment_details(
        *,
        overview: dict[str, object],
        execution_alignment: dict[str, object],
    ) -> dict[str, object]:
        """把研究和执行的最近标的对齐成更直白的明细。"""

        execution = dict(execution_alignment.get("execution") or {})
        orders = [dict(item) for item in list(execution.get("orders") or []) if isinstance(item, dict)]
        positions = [dict(item) for item in list(execution.get("positions") or []) if isinstance(item, dict)]
        research_symbol = str(
            execution_alignment.get("symbol")
            or overview.get("recommended_symbol")
            or ""
        )
        research_action = str(
            execution_alignment.get("recommended_action")
            or overview.get("recommended_action")
            or ""
        )
        last_order_symbol = str(orders[0].get("symbol", "")) if orders else ""
        last_position_symbol = str(positions[0].get("symbol", "")) if positions else ""
        latest_sync_status = str(execution.get("latest_sync_status", "") or "unknown")
        runtime_mode = str(execution.get("runtime_mode", "") or "unknown")
        status = str(execution_alignment.get("status", "") or "unavailable")
        if status == "matched":
            alignment_state = "研究和执行已对齐"
        elif status == "waiting_research":
            alignment_state = "研究已生成，等待执行收口"
        elif status == "unavailable":
            alignment_state = "当前还没有执行对齐结果"
        else:
            alignment_state = "研究和执行暂未对齐"
        if not research_symbol and status == "unavailable":
            return {
                "research_symbol": research_symbol,
                "research_action": research_action,
                "last_order_symbol": last_order_symbol,
                "last_position_symbol": last_position_symbol,
                "alignment_state": alignment_state,
                "runtime_mode": runtime_mode,
                "latest_sync_status": latest_sync_status,
                "difference_summary": "当前还没有足够结果可对齐",
                "difference_severity": "unknown",
                "difference_reasons": ["当前还没有研究候选，先补研究结果。"],
                "next_step": "先补研究结果、执行同步或 dry-run，再回来复核。",
            }
        if status == "unavailable":
            return {
                "research_symbol": research_symbol,
                "research_action": research_action,
                "last_order_symbol": last_order_symbol,
                "last_position_symbol": last_position_symbol,
                "alignment_state": alignment_state,
                "runtime_mode": runtime_mode,
                "latest_sync_status": latest_sync_status,
                "difference_summary": "当前执行侧还没有可对齐结果",
                "difference_severity": "unknown",
                "difference_reasons": ["执行侧还没有最新对齐结果，先补执行同步或 dry-run。"],
                "next_step": "先补执行同步或 dry-run，再回来复核。",
            }
        difference_reasons: list[str] = []
        if research_symbol and last_order_symbol and research_symbol != last_order_symbol:
            difference_reasons.append(f"最近订单仍是 {last_order_symbol}")
        if research_symbol and last_position_symbol and research_symbol != last_position_symbol:
            difference_reasons.append(f"最近持仓仍是 {last_position_symbol}")
        if latest_sync_status == "failed":
            difference_reasons.append("同步失败")
        if runtime_mode == "manual" and research_action == "enter_dry_run":
            difference_reasons.append("当前仍在手动模式，需要人工确认")
        if not difference_reasons:
            difference_reasons.append("当前没有明显差异")
        if difference_reasons == ["当前没有明显差异"]:
            difference_summary = "研究标的、最近订单和最近持仓已经对上"
            difference_severity = "low"
            next_step = "继续观察 dry-run 或小额 live 的复盘结果。"
        elif status == "waiting_research":
            difference_summary = f"研究侧推荐 {research_symbol or 'n/a'}，但执行侧还没进入同一轮"
            difference_severity = "medium"
            next_step = "先回到研究、回测和评估链补强候选，再决定是否放行。"
        else:
            difference_summary = (
                f"研究侧推荐 {research_symbol or 'n/a'}，但执行侧还没完全对齐。"
            )
            difference_severity = "high" if latest_sync_status == "failed" else "medium"
            next_step = "先恢复同步，再确认是否真的把研究候选派发到执行侧。"
        return {
            "research_symbol": research_symbol,
            "research_action": research_action,
            "last_order_symbol": last_order_symbol,
            "last_position_symbol": last_position_symbol,
            "alignment_state": alignment_state,
            "runtime_mode": runtime_mode,
            "latest_sync_status": latest_sync_status,
            "difference_summary": difference_summary,
            "difference_severity": difference_severity,
            "difference_reasons": difference_reasons,
            "next_step": next_step,
        }

    @staticmethod
    def _build_alignment_gaps(
        *,
        overview: dict[str, object],
        execution_alignment: dict[str, object],
    ) -> list[dict[str, str]]:
        """列出研究和执行当前差在哪。"""

        details = EvaluationWorkspaceService._build_alignment_details(
            overview=overview,
            execution_alignment=execution_alignment,
        )
        reasons = list(details.get("difference_reasons") or [])
        if reasons == ["当前没有明显差异"]:
            return []
        return [
            {
                "label": f"差异 {index + 1}",
                "detail": str(item),
                "severity": str(details.get("difference_severity", "low")),
            }
            for index, item in enumerate(reasons)
        ]

    @staticmethod
    def _build_alignment_actions(*, execution_alignment: dict[str, object]) -> list[dict[str, str]]:
        """给评估页一组更直观的下一步动作。"""

        status = str(execution_alignment.get("status", "") or "unavailable")
        if status == "matched":
            return [
                {"label": "继续保持研究和执行同一轮", "detail": "当前研究和执行已经对齐，先继续看 dry-run 或 live 的复盘。"},
                {"label": "回到任务页看自动化", "detail": "确认自动化模式和长期运行参数是否需要调整。"},
            ]
        if status == "attention_required":
            return [
                {"label": "先恢复同步", "detail": "执行结果没有完全收口前，不要继续放大验证范围。"},
                {"label": "再回到策略页确认派发", "detail": "同步恢复后，再核对这轮研究候选是否真的进入执行。"},
            ]
        if status == "no_execution":
            return [
                {"label": "先去策略页确认派发", "detail": "研究已有候选，但执行侧还没有动作。"},
                {"label": "回到任务页确认是否被人工暂停", "detail": "人工接管或 Kill Switch 都会让执行停在研究之前。"},
            ]
        return [
            {"label": "继续研究", "detail": "先补训练、推理和评估结果，再决定是否进入 dry-run。"},
        ]

    @staticmethod
    def _build_experiment_alignment_note(
        *,
        training_present: bool,
        inference_present: bool,
        training_model: str,
        inference_model: str,
        training_snapshot: str,
        inference_snapshot: str,
        model_aligned: bool,
        dataset_aligned: bool,
    ) -> str:
        """生成实验对比的口头说明。"""

        if not training_present and not inference_present:
            return "当前还没有训练或推理记录，先跑实验再来看对比。"

        details: list[str] = []
        if training_present or inference_present:
            details.append(f"训练模型 {training_model or 'n/a'} / 推理模型 {inference_model or 'n/a'}")
            details.append(f"训练数据 {training_snapshot or 'n/a'} / 推理数据 {inference_snapshot or 'n/a'}")
        if training_present and inference_present:
            details.append(
                f"模型{'一致' if model_aligned else '不一致'} / 数据{'一致' if dataset_aligned else '不一致'}"
            )
        if not training_present:
            details.append("尚未生成训练结果")
        if not inference_present:
            details.append("尚未生成推理结果")
        return "；".join(details)

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
        live_gate: dict[str, object],
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
        if not EvaluationWorkspaceService._gate_passed(dry_run_gate):
            dry_run_reasons = [str(reason).strip() for reason in list(dry_run_gate.get("reasons") or []) if str(reason).strip()]
            return "dry_run_gate", " / ".join(dry_run_reasons) if dry_run_reasons else "未通过"
        if live_gate and not EvaluationWorkspaceService._gate_passed(live_gate):
            live_reasons = [str(reason).strip() for reason in list(live_gate.get("reasons") or []) if str(reason).strip()]
            return "live_gate", " / ".join(live_reasons) if live_reasons else "未通过"
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
        if "passed" in gate:
            return bool(gate.get("passed"))
        status = str(gate.get("status", "") or "").strip().lower()
        if status:
            return status == "passed"
        return not [str(reason).strip() for reason in list(gate.get("reasons") or []) if str(reason).strip()]


evaluation_workspace_service = EvaluationWorkspaceService()

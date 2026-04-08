"""策略研究工作台聚合服务。

这个文件负责把研究报告里的模板、标签、窗口和实验参数整理成前端工作台结构。
"""

from __future__ import annotations

from services.api.app.services.research_service import research_service
from services.api.app.services.workbench_config_service import workbench_config_service


class ResearchWorkspaceService:
    """聚合当前研究上下文。"""

    def __init__(self, *, report_reader: object | None = None, controls_builder=None) -> None:
        self._report_reader = report_reader or research_service
        self._controls_builder = controls_builder or workbench_config_service.build_workspace_controls

    def get_workspace(self) -> dict[str, object]:
        """返回策略研究工作台统一模型。"""

        report = self._read_factory_report()
        latest_training = dict(report.get("latest_training") or {})
        latest_inference = dict(report.get("latest_inference") or {})
        overview = dict(report.get("overview") or {})
        training_context = dict(latest_training.get("training_context") or {})
        sample_window = dict(training_context.get("sample_window") or {})
        parameters = dict(training_context.get("parameters") or {})
        controls = self._controls_builder()
        configured_data = dict((controls.get("config") or {}).get("data") or {})
        configured_features = dict((controls.get("config") or {}).get("features") or {})
        configured_research = dict((controls.get("config") or {}).get("research") or {})
        configured_thresholds = dict((controls.get("config") or {}).get("thresholds") or {})
        min_days = int(configured_research.get("min_holding_days", 1) or 1)
        max_days = int(configured_research.get("max_holding_days", 3) or 3)
        label_target_pct = str(configured_research.get("label_target_pct", "1"))
        label_stop_pct = str(configured_research.get("label_stop_pct", "-1"))
        label_mode = str(configured_research.get("label_mode", "earliest_hit") or "earliest_hit")
        label_trigger_basis = str(configured_research.get("label_trigger_basis", "close") or "close")
        strategy_templates = sorted(
            {
                str(item.get("strategy_template", "")).strip()
                for item in list(report.get("candidates") or [])
                if isinstance(item, dict) and str(item.get("strategy_template", "")).strip()
            }
        )

        status = str(report.get("status", "unavailable") or "unavailable")
        if latest_training or latest_inference or strategy_templates:
            status = "ready"

        return {
            "status": status,
            "backend": str(report.get("backend", "qlib-fallback") or "qlib-fallback"),
            "config_alignment": dict(report.get("config_alignment") or {}),
            "overview": {
                "holding_window": str(training_context.get("holding_window", "")),
                "candidate_count": int(overview.get("candidate_count", 0) or 0),
                "recommended_symbol": str(overview.get("recommended_symbol", "")),
                "recommended_action": str(overview.get("recommended_action", "")),
            },
            "strategy_templates": strategy_templates,
            "labeling": {
                "label_columns": [str(item) for item in list(latest_training.get("label_columns") or [])],
                "label_mode": label_mode,
                "definition": self._build_label_definition(
                    label_mode=label_mode,
                    label_trigger_basis=label_trigger_basis,
                    min_days=min_days,
                    max_days=max_days,
                    label_target_pct=label_target_pct,
                    label_stop_pct=label_stop_pct,
                ),
            },
            "sample_window": {
                name: dict(value or {})
                for name, value in sample_window.items()
            },
            "model": {
                "model_version": str(
                    latest_inference.get("model_version")
                    or latest_training.get("model_version")
                    or ""
                ),
                "backend": str(report.get("backend", "qlib-fallback") or "qlib-fallback"),
            },
            "controls": {
                "research_template": str(configured_research.get("research_template", "")),
                "model_key": str(configured_research.get("model_key", "")),
                "label_mode": label_mode,
                "label_trigger_basis": label_trigger_basis,
                "holding_window_label": str(configured_research.get("holding_window_label", "")),
                "force_validation_top_candidate": bool(
                    configured_research.get("force_validation_top_candidate", False)
                ),
                "min_holding_days": int(configured_research.get("min_holding_days", 1) or 1),
                "max_holding_days": int(configured_research.get("max_holding_days", 3) or 3),
                "label_target_pct": str(configured_research.get("label_target_pct", "")),
                "label_stop_pct": str(configured_research.get("label_stop_pct", "")),
                "train_split_ratio": str(configured_research.get("train_split_ratio", "0.6")),
                "validation_split_ratio": str(configured_research.get("validation_split_ratio", "0.2")),
                "test_split_ratio": str(configured_research.get("test_split_ratio", "0.2")),
                "signal_confidence_floor": str(configured_research.get("signal_confidence_floor", "0.55")),
                "trend_weight": str(configured_research.get("trend_weight", "1.3")),
                "momentum_weight": str(configured_research.get("momentum_weight", "1")),
                "volume_weight": str(configured_research.get("volume_weight", "1.1")),
                "oscillator_weight": str(configured_research.get("oscillator_weight", "0.7")),
                "volatility_weight": str(configured_research.get("volatility_weight", "0.9")),
                "strict_penalty_weight": str(configured_research.get("strict_penalty_weight", "1")),
                "available_models": [str(item) for item in list((controls.get("options") or {}).get("models") or [])],
                "available_research_templates": [str(item) for item in list((controls.get("options") or {}).get("research_templates") or [])],
                "available_label_modes": [str(item) for item in list((controls.get("options") or {}).get("label_modes") or [])],
                "available_label_trigger_bases": [str(item) for item in list((controls.get("options") or {}).get("label_trigger_bases") or [])],
                "available_holding_windows": [str(item) for item in list((controls.get("options") or {}).get("holding_windows") or [])],
            },
            "parameters": {
                str(name): str(value)
                for name, value in parameters.items()
            },
            "selectors": {
                "symbols": [str(item) for item in list(training_context.get("symbols") or [])],
                "timeframes": [str(item) for item in list(training_context.get("timeframes") or [])],
            },
            "readiness": self._build_readiness(
                configured_data=configured_data,
                latest_training=latest_training,
                latest_inference=latest_inference,
                config_alignment=dict(report.get("config_alignment") or {}),
            ),
            "execution_preview": self._build_execution_preview(
                configured_data=configured_data,
                configured_features=configured_features,
                configured_research=configured_research,
                configured_thresholds=configured_thresholds,
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

    @staticmethod
    def _build_label_definition(
        *,
        label_mode: str,
        label_trigger_basis: str,
        min_days: int,
        max_days: int,
        label_target_pct: str,
        label_stop_pct: str,
    ) -> str:
        """生成更直白的标签说明。"""

        trigger_detail = "按收盘价判断" if label_trigger_basis == "close" else "按高低点命中判断"
        if label_mode == "close_only":
            return f"未来 {min_days}-{max_days} 天窗口结束时，{trigger_detail}；窗口结束达到 +{label_target_pct}% 记 buy，低于 {label_stop_pct}% 记 sell，其余记 watch。"
        return f"未来 {min_days}-{max_days} 天内，{trigger_detail}；最早达到 +{label_target_pct}% 记 buy，最早达到 {label_stop_pct}% 记 sell，其余记 watch。"

    @staticmethod
    def _build_readiness(
        *,
        configured_data: dict[str, object],
        latest_training: dict[str, object],
        latest_inference: dict[str, object],
        config_alignment: dict[str, object],
    ) -> dict[str, object]:
        """整理研究工作台当前是否能继续推进。"""

        selected_symbols = [str(item) for item in list(configured_data.get("selected_symbols") or []) if str(item).strip()]
        timeframes = [str(item) for item in list(configured_data.get("timeframes") or []) if str(item).strip()]
        blocking_reasons: list[str] = []
        if not selected_symbols:
            blocking_reasons.append("还没有选择研究标的")
        if not timeframes:
            blocking_reasons.append("还没有选择研究周期")
        train_ready = not blocking_reasons
        config_status = str(config_alignment.get("status", "unavailable") or "unavailable")
        if config_status not in {"aligned", "ready", "fresh"}:
            infer_ready = False
            infer_reason = str(config_alignment.get("note", "当前结果和配置还没有对齐") or "当前结果和配置还没有对齐")
        elif latest_training:
            infer_ready = True
            infer_reason = "当前已有训练结果，可以继续推理和进入评估。"
        else:
            infer_ready = False
            infer_reason = "当前还没有训练结果，先运行研究训练。"
        if not train_ready:
            next_step = "先补齐数据范围，再运行研究训练。"
        elif not latest_training:
            next_step = "先运行研究训练，生成训练窗口和实验参数。"
        elif not latest_inference:
            next_step = "继续运行研究推理，把候选和研究报告补齐。"
        elif not infer_ready:
            next_step = "先重新跑一轮训练和推理，让结果和当前配置重新对齐。"
        else:
            next_step = "当前研究已准备好，可以进入评估、dry-run 或继续比较实验。"
        return {
            "train_ready": train_ready,
            "infer_ready": infer_ready,
            "blocking_reasons": blocking_reasons,
            "infer_reason": infer_reason,
            "next_step": next_step,
        }

    @staticmethod
    def _build_execution_preview(
        *,
        configured_data: dict[str, object],
        configured_features: dict[str, object],
        configured_research: dict[str, object],
        configured_thresholds: dict[str, object],
    ) -> dict[str, str]:
        """把当前研究配置会怎样影响后续执行讲清楚。"""

        selected_symbols = [str(item) for item in list(configured_data.get("selected_symbols") or []) if str(item).strip()]
        timeframes = [str(item) for item in list(configured_data.get("timeframes") or []) if str(item).strip()]
        primary_factors = [str(item) for item in list(configured_features.get("primary_factors") or []) if str(item).strip()]
        auxiliary_factors = [str(item) for item in list(configured_features.get("auxiliary_factors") or []) if str(item).strip()]
        return {
            "data_scope": f"{' / '.join(selected_symbols) or '未选择标的'} · {' / '.join(timeframes) or '未选择周期'} · 最近 {configured_data.get('lookback_days', 30)} 天 / {configured_data.get('sample_limit', 120)} 根样本",
            "factor_mix": f"主判断 {len(primary_factors)} 个 / 辅助确认 {len(auxiliary_factors)} 个",
            "label_scope": f"{configured_research.get('label_mode', 'earliest_hit')} / {configured_research.get('label_trigger_basis', 'close')} · {configured_research.get('min_holding_days', 1)}-{configured_research.get('max_holding_days', 3)} 天 · 目标 {configured_research.get('label_target_pct', '1')}% / 止损 {configured_research.get('label_stop_pct', '-1')}%",
            "dry_run_gate": f"score ≥ {configured_thresholds.get('dry_run_min_score', '0.55')} / 净收益 ≥ {configured_thresholds.get('dry_run_min_net_return_pct', '0')}% / Sharpe ≥ {configured_thresholds.get('dry_run_min_sharpe', '0.5')}",
            "live_gate": f"score ≥ {configured_thresholds.get('live_min_score', '0.65')} / 净收益 ≥ {configured_thresholds.get('live_min_net_return_pct', '0.20')}% / 胜率 ≥ {configured_thresholds.get('live_min_win_rate', '0.55')}",
            "validation_policy": "当前最优候选会被强制送去验证"
            if bool(configured_research.get("force_validation_top_candidate", False))
            else "候选按统一门控自然筛选后再进入验证",
        }


research_workspace_service = ResearchWorkspaceService()

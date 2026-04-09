"""回测工作台聚合服务。

这个文件负责把研究报告里的回测摘要、成本假设和候选对比整理成前端可见结构。
"""

from __future__ import annotations

from services.api.app.services.research_service import research_service
from services.api.app.services.workbench_config_service import workbench_config_service


class BacktestWorkspaceService:
    """聚合当前回测上下文。"""

    def __init__(self, *, report_reader: object | None = None, controls_builder=None) -> None:
        self._report_reader = report_reader or research_service
        self._controls_builder = controls_builder or workbench_config_service.build_workspace_controls

    def get_workspace(self) -> dict[str, object]:
        """返回回测工作台统一模型。"""

        report = self._read_factory_report()
        latest_training = dict(report.get("latest_training") or {})
        training_context = dict(latest_training.get("training_context") or {})
        training_backtest = dict(latest_training.get("backtest") or {})
        assumptions = dict(training_backtest.get("assumptions") or {})
        metrics = dict(training_backtest.get("metrics") or {})
        validation = dict(latest_training.get("validation") or {})
        controls = self._controls_builder()
        configured_backtest = dict((controls.get("config") or {}).get("backtest") or {})
        configured_thresholds = dict((controls.get("config") or {}).get("thresholds") or {})
        option_catalogs = dict(controls.get("options") or {})
        backtest_preset_key = str(configured_backtest.get("backtest_preset_key", "realistic_standard") or "realistic_standard")
        configured_fee_bps = str(configured_backtest.get("fee_bps", "10") or "10")
        configured_slippage_bps = str(configured_backtest.get("slippage_bps", "5") or "5")
        configured_cost_model = str(configured_backtest.get("cost_model", "round_trip_basis_points") or "round_trip_basis_points")
        result_fee_bps = str(assumptions.get("fee_bps", configured_fee_bps) or configured_fee_bps)
        result_slippage_bps = str(assumptions.get("slippage_bps", configured_slippage_bps) or configured_slippage_bps)
        result_cost_model = str(assumptions.get("cost_model", configured_cost_model) or configured_cost_model)
        leaderboard = [
            {
                "symbol": str(item.get("symbol", "")),
                "strategy_template": str(item.get("strategy_template", "")),
                "backtest": dict(item.get("backtest") or {}),
            }
            for item in list(report.get("leaderboard") or [])
            if isinstance(item, dict)
        ]

        status = str(report.get("status", "unavailable") or "unavailable")
        if training_backtest or leaderboard:
            status = "ready"

        return {
            "status": status,
            "backend": str(report.get("backend", "qlib-fallback") or "qlib-fallback"),
            "overview": {
                "holding_window": str(training_context.get("holding_window", "")),
                "candidate_count": len(leaderboard),
                "recommended_symbol": str((report.get("overview") or {}).get("recommended_symbol", "")),
            },
            "assumptions": {
                str(name): str(value)
                for name, value in assumptions.items()
            },
            "controls": {
                "backtest_preset_key": backtest_preset_key,
                "fee_bps": configured_fee_bps,
                "slippage_bps": configured_slippage_bps,
                "cost_model": configured_cost_model,
                "available_cost_models": [str(item) for item in list((controls.get("options") or {}).get("backtest_cost_models") or [])],
                "cost_model_catalog": [dict(item) for item in list((controls.get("options") or {}).get("cost_model_catalog") or []) if isinstance(item, dict)],
                "available_backtest_presets": [str(item) for item in list((controls.get("options") or {}).get("backtest_presets") or [])],
                "backtest_preset_catalog": [dict(item) for item in list((controls.get("options") or {}).get("backtest_preset_catalog") or []) if isinstance(item, dict)],
                "dry_run_min_score": str(configured_thresholds.get("dry_run_min_score", "0.55")),
                "dry_run_min_positive_rate": str(configured_thresholds.get("dry_run_min_positive_rate", "0.45")),
                "dry_run_min_net_return_pct": str(configured_thresholds.get("dry_run_min_net_return_pct", "0")),
                "dry_run_min_sharpe": str(configured_thresholds.get("dry_run_min_sharpe", "0.5")),
                "dry_run_max_drawdown_pct": str(configured_thresholds.get("dry_run_max_drawdown_pct", "15")),
                "dry_run_max_loss_streak": str(configured_thresholds.get("dry_run_max_loss_streak", "3")),
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
                "live_min_score": str(configured_thresholds.get("live_min_score", "0.65")),
                "live_min_positive_rate": str(configured_thresholds.get("live_min_positive_rate", "0.50")),
                "live_min_net_return_pct": str(configured_thresholds.get("live_min_net_return_pct", "0.20")),
                "enable_rule_gate": bool(configured_thresholds.get("enable_rule_gate", True)),
                "enable_validation_gate": bool(configured_thresholds.get("enable_validation_gate", True)),
                "enable_backtest_gate": bool(configured_thresholds.get("enable_backtest_gate", True)),
                "enable_consistency_gate": bool(configured_thresholds.get("enable_consistency_gate", True)),
                "enable_live_gate": bool(configured_thresholds.get("enable_live_gate", True)),
                "live_min_win_rate": str(configured_thresholds.get("live_min_win_rate", "0.55")),
                "live_max_turnover": str(configured_thresholds.get("live_max_turnover", "0.45")),
                "live_min_sample_count": str(configured_thresholds.get("live_min_sample_count", "24")),
            },
            "training_backtest": {
                "metrics": {
                    str(name): str(value)
                    for name, value in metrics.items()
                }
            },
            "stage_assessment": self._build_stage_assessment(
                metrics=metrics,
                validation=validation,
                sample_window=dict(training_context.get("sample_window") or {}),
                thresholds=configured_thresholds,
            ),
            "selection_story": self._build_selection_story(
                option_catalogs=option_catalogs,
                backtest_preset_key=backtest_preset_key,
                configured_fee_bps=configured_fee_bps,
                configured_slippage_bps=configured_slippage_bps,
                configured_cost_model=configured_cost_model,
                result_fee_bps=result_fee_bps,
                result_slippage_bps=result_slippage_bps,
                result_cost_model=result_cost_model,
                thresholds=configured_thresholds,
            ),
            "cost_filter_catalog": self._build_cost_filter_catalog(
                option_catalogs=option_catalogs,
                backtest_preset_key=backtest_preset_key,
                configured_fee_bps=configured_fee_bps,
                configured_slippage_bps=configured_slippage_bps,
                configured_cost_model=configured_cost_model,
                result_fee_bps=result_fee_bps,
                result_slippage_bps=result_slippage_bps,
                result_cost_model=result_cost_model,
                thresholds=configured_thresholds,
            ),
            "leaderboard": [
                {
                    "symbol": item["symbol"],
                    "strategy_template": item["strategy_template"],
                    "backtest": {
                        str(name): str(value)
                        for name, value in dict(item.get("backtest") or {}).items()
                    },
                }
                for item in leaderboard
            ],
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
        backtest_preset_key: str,
        configured_fee_bps: str,
        configured_slippage_bps: str,
        configured_cost_model: str,
        result_fee_bps: str,
        result_slippage_bps: str,
        result_cost_model: str,
        thresholds: dict[str, object],
    ) -> dict[str, object]:
        """把当前回测 preset、成本口径和过滤条件压成一屏说明。"""

        backtest_preset = self._resolve_catalog_item(
            [dict(item) for item in list(option_catalogs.get("backtest_preset_catalog") or []) if isinstance(item, dict)],
            key=backtest_preset_key,
            fallback_label=backtest_preset_key,
        )
        result_cost_model_item = self._resolve_catalog_item(
            [dict(item) for item in list(option_catalogs.get("cost_model_catalog") or []) if isinstance(item, dict)],
            key=result_cost_model,
            fallback_label=result_cost_model,
        )
        configured_cost_model_item = self._resolve_catalog_item(
            [dict(item) for item in list(option_catalogs.get("cost_model_catalog") or []) if isinstance(item, dict)],
            key=configured_cost_model,
            fallback_label=configured_cost_model,
        )
        alignment_status, alignment_note = self._build_cost_alignment_note(
            configured_fee_bps=configured_fee_bps,
            configured_slippage_bps=configured_slippage_bps,
            configured_cost_model_item=configured_cost_model_item,
            result_fee_bps=result_fee_bps,
            result_slippage_bps=result_slippage_bps,
            result_cost_model_item=result_cost_model_item,
        )
        return {
            "headline": f"{backtest_preset['label']} / {result_cost_model_item['label']}",
            "detail": (
                f"手续费 {result_fee_bps} bps / 滑点 {result_slippage_bps} bps / "
                f"dry-run 净收益 ≥ {thresholds.get('dry_run_min_net_return_pct', '0')}% / "
                f"最大回撤 ≤ {thresholds.get('dry_run_max_drawdown_pct', '15')}%"
            ),
            "alignment_status": alignment_status,
            "alignment_note": alignment_note,
            "backtest_preset": backtest_preset,
            "cost_model": result_cost_model_item,
            "configured_cost_model": configured_cost_model_item,
            "filter_summary": self._build_rule_filter_summary(thresholds),
            "gate_summary": self._build_gate_summary(thresholds),
        }

    def _build_cost_filter_catalog(
        self,
        *,
        option_catalogs: dict[str, object],
        backtest_preset_key: str,
        configured_fee_bps: str,
        configured_slippage_bps: str,
        configured_cost_model: str,
        result_fee_bps: str,
        result_slippage_bps: str,
        result_cost_model: str,
        thresholds: dict[str, object],
    ) -> list[dict[str, str]]:
        """把成本和过滤参数整理成稳定目录。"""

        backtest_preset = self._resolve_catalog_item(
            [dict(item) for item in list(option_catalogs.get("backtest_preset_catalog") or []) if isinstance(item, dict)],
            key=backtest_preset_key,
            fallback_label=backtest_preset_key,
        )
        result_cost_model_item = self._resolve_catalog_item(
            [dict(item) for item in list(option_catalogs.get("cost_model_catalog") or []) if isinstance(item, dict)],
            key=result_cost_model,
            fallback_label=result_cost_model,
        )
        configured_cost_model_item = self._resolve_catalog_item(
            [dict(item) for item in list(option_catalogs.get("cost_model_catalog") or []) if isinstance(item, dict)],
            key=configured_cost_model,
            fallback_label=configured_cost_model,
        )
        alignment_status, alignment_note = self._build_cost_alignment_note(
            configured_fee_bps=configured_fee_bps,
            configured_slippage_bps=configured_slippage_bps,
            configured_cost_model_item=configured_cost_model_item,
            result_fee_bps=result_fee_bps,
            result_slippage_bps=result_slippage_bps,
            result_cost_model_item=result_cost_model_item,
        )
        return [
            {
                "key": "cost_model",
                "label": "成本模型",
                "current": result_cost_model_item["label"],
                "effect": "决定净收益是按双边、单边还是零成本基线来扣减。",
                "detail": alignment_note if alignment_status == "stale" else result_cost_model_item["detail"],
            },
            {
                "key": "cost_inputs",
                "label": "成本输入",
                "current": f"手续费 {result_fee_bps} bps / 滑点 {result_slippage_bps} bps",
                "effect": "动作越频繁，这两项越容易直接吃掉毛收益。",
                "detail": (
                    f"已保存配置：手续费 {configured_fee_bps} bps / 滑点 {configured_slippage_bps} bps / "
                    f"{configured_cost_model_item['label']}，需重跑后才会体现在结果里。"
                    if alignment_status == "stale"
                    else f"当前回测预设：{backtest_preset['label']} / {backtest_preset['detail']}"
                ),
            },
            {
                "key": "rule_filters",
                "label": "规则过滤",
                "current": self._build_rule_filter_summary(thresholds),
                "effect": "先筛掉趋势不够强、波动过大或量能不足的候选。",
                "detail": (
                    f"严格模板：EMA20 ≥ {thresholds.get('strict_rule_min_ema20_gap_pct', '1.2')}% / "
                    f"EMA55 ≥ {thresholds.get('strict_rule_min_ema55_gap_pct', '1.8')}% / "
                    f"ATR ≤ {thresholds.get('strict_rule_max_atr_pct', '4.5')}% / "
                    f"量比 ≥ {thresholds.get('strict_rule_min_volume_ratio', '1.05')}"
                ),
            },
            {
                "key": "consistency_filters",
                "label": "一致性过滤",
                "current": (
                    f"验证/回测收益差 ≤ {thresholds.get('consistency_max_validation_backtest_return_gap_pct', '1.5')}% / "
                    f"训练/验证正收益比例差 ≤ {thresholds.get('consistency_max_training_validation_positive_rate_gap', '0.2')} / "
                    f"训练/验证收益差 ≤ {thresholds.get('consistency_max_training_validation_return_gap_pct', '1.5')}%"
                ),
                "effect": "避免只在单段样本里好看，换一个窗口就明显走样。",
                "detail": (
                    f"验证样本数 ≥ {thresholds.get('validation_min_sample_count', '12')} / "
                    f"验证平均未来收益 ≥ {thresholds.get('validation_min_avg_future_return_pct', '-0.1')}%"
                ),
            },
            {
                "key": "gate_switches",
                "label": "门控开关",
                "current": self._build_gate_summary(thresholds),
                "effect": "方便快速判断到底是哪一层在拦住候选。",
                "detail": "这些开关更适合临时排查，不适合长期关闭后直接放行到 dry-run 或 live。",
            },
        ]

    @staticmethod
    def _build_cost_alignment_note(
        *,
        configured_fee_bps: str,
        configured_slippage_bps: str,
        configured_cost_model_item: dict[str, str],
        result_fee_bps: str,
        result_slippage_bps: str,
        result_cost_model_item: dict[str, str],
    ) -> tuple[str, str]:
        """说明当前页面配置和本轮回测结果是否已经对齐。"""

        is_stale = (
            configured_fee_bps != result_fee_bps
            or configured_slippage_bps != result_slippage_bps
            or configured_cost_model_item["key"] != result_cost_model_item["key"]
        )
        if is_stale:
            return (
                "stale",
                f"本轮结果按手续费 {result_fee_bps} bps / 滑点 {result_slippage_bps} bps / "
                f"{result_cost_model_item['label']} 计算；已保存新回测配置，重跑训练后才会生效。",
            )
        return (
            "aligned",
            f"本轮结果与当前回测配置已对齐：手续费 {result_fee_bps} bps / "
            f"滑点 {result_slippage_bps} bps / {result_cost_model_item['label']}。",
        )

    @staticmethod
    def _build_rule_filter_summary(thresholds: dict[str, object]) -> str:
        """把规则过滤压成一行摘要。"""

        return (
            f"EMA20 ≥ {thresholds.get('rule_min_ema20_gap_pct', '0')}% / "
            f"EMA55 ≥ {thresholds.get('rule_min_ema55_gap_pct', '0')}% / "
            f"ATR ≤ {thresholds.get('rule_max_atr_pct', '5')}% / "
            f"量比 ≥ {thresholds.get('rule_min_volume_ratio', '1')}"
        )

    @staticmethod
    def _build_gate_summary(thresholds: dict[str, object]) -> str:
        """把五个门控开关压成一行说明。"""

        gates = [
            ("规则门", bool(thresholds.get("enable_rule_gate", True))),
            ("验证门", bool(thresholds.get("enable_validation_gate", True))),
            ("回测门", bool(thresholds.get("enable_backtest_gate", True))),
            ("一致性门", bool(thresholds.get("enable_consistency_gate", True))),
            ("live 门", bool(thresholds.get("enable_live_gate", True))),
        ]
        return " / ".join(f"{label}{'开启' if enabled else '关闭'}" for label, enabled in gates)

    @staticmethod
    def _build_stage_assessment(
        *,
        metrics: dict[str, object],
        validation: dict[str, object],
        sample_window: dict[str, object],
        thresholds: dict[str, object],
    ) -> list[dict[str, str]]:
        """把 dry-run、验证和 live 三层门槛压成可读摘要。"""

        validation_window = dict(sample_window.get("validation") or {})
        validation_count = int(validation_window.get("count", 0) or 0)
        validation_avg = str(validation.get("avg_future_return_pct", "") or "")
        return [
            {
                "stage": "dry-run",
                "headline": "先看这轮回测够不够进入 dry-run",
                "focus": (
                    f"score ≥ {thresholds.get('dry_run_min_score', '0.55')} / "
                    f"净收益 ≥ {thresholds.get('dry_run_min_net_return_pct', '0')}% / "
                    f"Sharpe ≥ {thresholds.get('dry_run_min_sharpe', '0.5')}"
                ),
                "current": (
                    f"当前净收益 {metrics.get('net_return_pct', 'n/a')} / "
                    f"Sharpe {metrics.get('sharpe', 'n/a')} / "
                    f"胜率 {metrics.get('win_rate', 'n/a')}"
                ),
            },
            {
                "stage": "validation",
                "headline": "再看样本外验证有没有站住",
                "focus": (
                    f"样本数 ≥ {thresholds.get('validation_min_sample_count', '12')} / "
                    f"平均未来收益 ≥ {thresholds.get('validation_min_avg_future_return_pct', '-0.1')}%"
                ),
                "current": (
                    f"当前验证样本 {validation_count} / "
                    f"平均未来收益 {validation_avg or 'n/a'}"
                ),
            },
            {
                "stage": "live",
                "headline": "最后才看是否值得放行到 live",
                "focus": (
                    f"score ≥ {thresholds.get('live_min_score', '0.65')} / "
                    f"净收益 ≥ {thresholds.get('live_min_net_return_pct', '0.20')}% / "
                    f"胜率 ≥ {thresholds.get('live_min_win_rate', '0.55')}"
                ),
                "current": (
                    f"当前净收益 {metrics.get('net_return_pct', 'n/a')} / "
                    f"胜率 {metrics.get('win_rate', 'n/a')} / "
                    f"换手 {metrics.get('turnover', 'n/a')}"
                ),
            },
        ]


backtest_workspace_service = BacktestWorkspaceService()

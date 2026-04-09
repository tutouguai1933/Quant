"""特征工作台聚合服务。

这个文件负责把研究层里的因子协议整理成前端可直接展示的特征工作台结构。
"""

from __future__ import annotations

from copy import deepcopy

from services.api.app.services.research_service import research_service
from services.api.app.services.workbench_config_service import workbench_config_service
from services.worker.qlib_features import FEATURE_PROTOCOL


class FeatureWorkspaceService:
    """聚合因子协议、分类、角色和周期参数。"""

    def __init__(
        self,
        *,
        research_reader: object | None = None,
        controls_builder=None,
    ) -> None:
        self._research_reader = research_reader or research_service
        self._controls_builder = controls_builder or workbench_config_service.build_workspace_controls

    def get_workspace(self) -> dict[str, object]:
        """返回特征工作台统一模型。"""

        report = self._read_factory_report()
        report_factor_protocol = dict(report.get("factor_protocol") or {})
        factor_protocol = report_factor_protocol or deepcopy(FEATURE_PROTOCOL)
        factors = list(factor_protocol.get("factors") or [])
        latest_training = dict(report.get("latest_training") or {})
        training_context = dict(latest_training.get("training_context") or {})
        controls = self._controls_builder()
        configured_features = dict((controls.get("config") or {}).get("features") or {})
        configured_research = dict((controls.get("config") or {}).get("research") or {})
        option_catalogs = dict(controls.get("options") or {})
        categories = {
            str(name): [str(item) for item in list(items or [])]
            for name, items in dict(factor_protocol.get("categories") or {}).items()
        }
        configured_timeframe_profiles = {
            str(interval): dict(profile or {})
            for interval, profile in dict(configured_features.get("timeframe_profiles") or {}).items()
        }

        status = str(report.get("status", "unavailable") or "unavailable")
        if report_factor_protocol and factors:
            status = "ready"
        elif status != "ready":
            status = "unavailable"

        primary = list((factor_protocol.get("roles") or {}).get("primary") or [])
        auxiliary = list((factor_protocol.get("roles") or {}).get("auxiliary") or [])

        return {
            "status": status,
            "backend": str(report.get("backend", "qlib-fallback") or "qlib-fallback"),
            "overview": {
                "feature_version": str(
                    training_context.get("feature_version")
                    or factor_protocol.get("version")
                    or ""
                ),
                "factor_count": len(factors),
                "primary_count": len(primary),
                "auxiliary_count": len(auxiliary),
                "holding_window": str(training_context.get("holding_window", "")),
            },
            "categories": categories,
            "roles": {
                "primary": [str(item) for item in primary],
                "auxiliary": [str(item) for item in auxiliary],
            },
            "controls": {
                "feature_preset_key": str(configured_features.get("feature_preset_key", "balanced_default") or "balanced_default"),
                "primary_factors": [str(item) for item in list(configured_features.get("primary_factors") or [])],
                "auxiliary_factors": [str(item) for item in list(configured_features.get("auxiliary_factors") or [])],
                "missing_policy": str(configured_features.get("missing_policy", "neutral_fill") or "neutral_fill"),
                "outlier_policy": str(configured_features.get("outlier_policy", "clip") or "clip"),
                "normalization_policy": str(configured_features.get("normalization_policy", "fixed_4dp") or "fixed_4dp"),
                "signal_confidence_floor": str(configured_research.get("signal_confidence_floor", "0.55") or "0.55"),
                "trend_weight": str(configured_research.get("trend_weight", "1.3") or "1.3"),
                "momentum_weight": str(configured_research.get("momentum_weight", "1") or "1"),
                "volume_weight": str(configured_research.get("volume_weight", "1.1") or "1.1"),
                "oscillator_weight": str(configured_research.get("oscillator_weight", "0.7") or "0.7"),
                "volatility_weight": str(configured_research.get("volatility_weight", "0.9") or "0.9"),
                "strict_penalty_weight": str(configured_research.get("strict_penalty_weight", "1") or "1"),
                "timeframe_profiles": {
                    str(interval): dict(profile or {})
                    for interval, profile in configured_timeframe_profiles.items()
                },
                "available_primary_factors": [str(item) for item in list((controls.get("options") or {}).get("primary_factors") or [])],
                "available_auxiliary_factors": [str(item) for item in list((controls.get("options") or {}).get("auxiliary_factors") or [])],
                "available_missing_policies": [str(item) for item in list((controls.get("options") or {}).get("missing_policies") or [])],
                "available_outlier_policies": [str(item) for item in list((controls.get("options") or {}).get("outlier_policies") or [])],
                "available_normalization_policies": [str(item) for item in list((controls.get("options") or {}).get("normalization_policies") or [])],
                "available_feature_presets": [str(item) for item in list((controls.get("options") or {}).get("feature_presets") or [])],
                "feature_preset_catalog": [dict(item) for item in list((controls.get("options") or {}).get("feature_preset_catalog") or []) if isinstance(item, dict)],
            },
            "preprocessing": {
                "missing_policy": str((factor_protocol.get("preprocessing") or {}).get("missing_policy", "")),
                "outlier_policy": str((factor_protocol.get("preprocessing") or {}).get("outlier_policy", "")),
                "normalization_policy": str((factor_protocol.get("preprocessing") or {}).get("normalization_policy", "")),
            },
            "timeframe_profiles": {
                str(interval): dict(profile or {})
                for interval, profile in dict(factor_protocol.get("timeframe_profiles") or {}).items()
            },
            "factors": [
                {
                    "name": str(item.get("name", "")),
                    "category": str(item.get("category", "")),
                    "role": str(item.get("role", "")),
                    "description": str(item.get("description", "")),
                }
                for item in factors
                if isinstance(item, dict)
            ],
            "selection_matrix": self._build_selection_matrix(factors=factors, configured_features=configured_features),
            "category_catalog": self._build_category_catalog(categories=categories, configured_features=configured_features),
            "selection_story": self._build_selection_story(
                option_catalogs=option_catalogs,
                feature_preset_key=str(configured_features.get("feature_preset_key", "balanced_default") or "balanced_default"),
                configured_features=configured_features,
                timeframe_profiles=configured_timeframe_profiles,
            ),
        }

    def _read_factory_report(self) -> dict[str, object]:
        """读取统一研究报告。"""

        reader = getattr(self._research_reader, "get_factory_report", None)
        if callable(reader):
            payload = reader()
            if isinstance(payload, dict):
                return payload
        return {"status": "unavailable", "backend": "qlib-fallback"}

    @staticmethod
    def _build_selection_matrix(*, factors: list[object], configured_features: dict[str, object]) -> list[dict[str, str]]:
        """把协议角色和当前勾选角色整理成一张明细表。"""

        primary = {str(item).strip() for item in list(configured_features.get("primary_factors") or []) if str(item).strip()}
        auxiliary = {str(item).strip() for item in list(configured_features.get("auxiliary_factors") or []) if str(item).strip()}
        rows: list[dict[str, str]] = []
        for item in factors:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            current_role = "未启用"
            if name in primary:
                current_role = "主判断"
            elif name in auxiliary:
                current_role = "辅助确认"
            rows.append(
                {
                    "name": name,
                    "category": str(item.get("category", "")).strip() or "未分类",
                    "protocol_role": str(item.get("role", "")).strip() or "未定义",
                    "current_role": current_role,
                    "description": str(item.get("description", "")).strip() or "当前没有说明",
                }
            )
        return rows

    @staticmethod
    def _resolve_catalog_item(
        catalog: list[dict[str, object]],
        *,
        key: str,
        fallback_label: str,
    ) -> dict[str, str]:
        """从目录里找当前选中的说明项。"""

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

    @staticmethod
    def _describe_feature_category(category: str) -> dict[str, str]:
        """按因子类别给出统一说明。"""

        normalized = category.lower()
        if "trend" in normalized or "趋势" in category:
            return {
                "label": "趋势类因子",
                "weight_entry": "研究页 trend_weight",
                "effect": "更偏判断顺趋势能不能继续拿。",
                "detail": "重点看均线偏离、趋势斜率和突破延续，适合先判断是不是仍在主趋势里。",
            }
        if "momentum" in normalized or "动量" in category:
            return {
                "label": "动量类因子",
                "weight_entry": "研究页 momentum_weight",
                "effect": "更偏判断走势是不是在加速。",
                "detail": "重点看涨跌速度和短期推进，适合先判断这段走势有没有继续冲的动力。",
            }
        if "volume" in normalized or "量" in category:
            return {
                "label": "量能类因子",
                "weight_entry": "研究页 volume_weight",
                "effect": "更偏确认量价是不是同步。",
                "detail": "重点看成交量放大和量价配合，适合确认突破是不是有真实买卖支持。",
            }
        if "osc" in normalized or "oscillator" in normalized or "震荡" in category:
            return {
                "label": "震荡类因子",
                "weight_entry": "研究页 oscillator_weight",
                "effect": "更偏提醒什么时候不要追。",
                "detail": "重点看超买超卖和回摆位置，适合过滤追高或过度回撤的时段。",
            }
        if "vol" in normalized or "波动" in category:
            return {
                "label": "波动类因子",
                "weight_entry": "研究页 volatility_weight",
                "effect": "更偏控制波动和风险折扣。",
                "detail": "重点看波动幅度和风险压力，适合在进 dry-run 或 live 前先压掉过度波动。",
            }
        return {
            "label": "通用因子",
            "weight_entry": "研究页统一评分",
            "effect": "当前先按统一评分承接。",
            "detail": "这类因子暂时没有单独权重入口，会先按统一评分逻辑参与研究判断。",
        }

    @classmethod
    def _build_category_catalog(
        cls,
        *,
        categories: dict[str, list[str]],
        configured_features: dict[str, object],
    ) -> list[dict[str, object]]:
        """把因子类别、当前启用比例和研究影响整理成目录。"""

        primary = {str(item).strip() for item in list(configured_features.get("primary_factors") or []) if str(item).strip()}
        auxiliary = {str(item).strip() for item in list(configured_features.get("auxiliary_factors") or []) if str(item).strip()}
        rows: list[dict[str, object]] = []
        for category, items in categories.items():
            description = cls._describe_feature_category(category)
            primary_count = sum(1 for item in items if item in primary)
            auxiliary_count = sum(1 for item in items if item in auxiliary)
            rows.append(
                {
                    "key": category,
                    "label": description["label"],
                    "weight_entry": description["weight_entry"],
                    "effect": description["effect"],
                    "detail": description["detail"],
                    "factor_count": len(items),
                    "primary_count": primary_count,
                    "auxiliary_count": auxiliary_count,
                    "current_mix": f"{primary_count} 主判断 / {auxiliary_count} 辅助 / {len(items)} 总计",
                }
            )
        return rows

    def _build_selection_story(
        self,
        *,
        option_catalogs: dict[str, object],
        feature_preset_key: str,
        configured_features: dict[str, object],
        timeframe_profiles: dict[str, dict[str, object]],
    ) -> dict[str, object]:
        """把当前因子组合和预处理口径压成一屏说明。"""

        primary_factors = [str(item) for item in list(configured_features.get("primary_factors") or []) if str(item).strip()]
        auxiliary_factors = [str(item) for item in list(configured_features.get("auxiliary_factors") or []) if str(item).strip()]
        feature_preset = self._resolve_catalog_item(
            [dict(item) for item in list(option_catalogs.get("feature_preset_catalog") or []) if isinstance(item, dict)],
            key=feature_preset_key,
            fallback_label=feature_preset_key,
        )
        missing_policy = str(configured_features.get("missing_policy", "neutral_fill") or "neutral_fill")
        outlier_policy = str(configured_features.get("outlier_policy", "clip") or "clip")
        normalization_policy = str(configured_features.get("normalization_policy", "fixed_4dp") or "fixed_4dp")
        timeframe_summary = self._build_timeframe_summary(timeframe_profiles)
        return {
            "headline": f"{feature_preset['label']} / 主判断 {len(primary_factors)} 个 / 辅助确认 {len(auxiliary_factors)} 个",
            "detail": f"缺失 {missing_policy} / 去极值 {outlier_policy} / 标准化 {normalization_policy}；{timeframe_summary}",
            "feature_preset": feature_preset,
            "preprocessing": {
                "headline": f"缺失 {missing_policy} / 去极值 {outlier_policy} / 标准化 {normalization_policy}",
                "detail": "这些规则会在下一轮训练和推理前先处理坏行、极端值和尺度差异，直接影响因子是否稳定。",
            },
            "timeframe_summary": timeframe_summary,
        }

    @staticmethod
    def _build_timeframe_summary(timeframe_profiles: dict[str, dict[str, object]]) -> str:
        """把周期参数压成一行摘要。"""

        parts: list[str] = []
        for interval, profile in timeframe_profiles.items():
            if not profile:
                continue
            summary = ", ".join(f"{name}={value}" for name, value in profile.items())
            parts.append(f"{interval}: {summary}")
        if not parts:
            return "当前还没有周期参数。"
        return "周期参数 " + " / ".join(parts)


feature_workspace_service = FeatureWorkspaceService()

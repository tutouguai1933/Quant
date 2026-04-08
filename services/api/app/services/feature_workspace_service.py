"""特征工作台聚合服务。

这个文件负责把研究层里的因子协议整理成前端可直接展示的特征工作台结构。
"""

from __future__ import annotations

from services.api.app.services.research_service import research_service
from services.api.app.services.workbench_config_service import workbench_config_service


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
        factor_protocol = dict(report.get("factor_protocol") or {})
        factors = list(factor_protocol.get("factors") or [])
        latest_training = dict(report.get("latest_training") or {})
        training_context = dict(latest_training.get("training_context") or {})
        controls = self._controls_builder()
        configured_features = dict((controls.get("config") or {}).get("features") or {})

        status = str(report.get("status", "unavailable") or "unavailable")
        if factors:
            status = "ready"
        else:
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
            "categories": {
                str(name): [str(item) for item in list(items or [])]
                for name, items in dict(factor_protocol.get("categories") or {}).items()
            },
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
                "timeframe_profiles": {
                    str(interval): dict(profile or {})
                    for interval, profile in dict(configured_features.get("timeframe_profiles") or {}).items()
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
        }

    def _read_factory_report(self) -> dict[str, object]:
        """读取统一研究报告。"""

        reader = getattr(self._research_reader, "get_factory_report", None)
        if callable(reader):
            payload = reader()
            if isinstance(payload, dict):
                return payload
        return {"status": "unavailable", "backend": "qlib-fallback"}


feature_workspace_service = FeatureWorkspaceService()

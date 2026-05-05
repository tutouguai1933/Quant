"""特征工作台聚合服务。

这个文件负责把研究层里的因子协议整理成前端可直接展示的特征工作台结构。
"""

from __future__ import annotations

from copy import deepcopy

from services.api.app.services.research_service import research_service
from services.api.app.services.terminal_view_helpers import (
    build_terminal_page,
    metric_card,
    terminal_state,
)
from services.api.app.services.terminal_series_service import terminal_series_service
from services.api.app.services.workbench_config_service import workbench_config_service
from services.worker.qlib_features import FEATURE_PROTOCOL


# 因子详情字典：包含常见因子的完整描述信息
FACTOR_DETAILS = {
    # ========== 趋势类因子 ==========
    "ema20_gap_pct": {
        "formula": "(close - ema(close, 20)) / ema(close, 20)",
        "why_effective": "衡量价格相对20日均线的偏离程度，偏离越大说明趋势越强或回调越深",
        "how_to_use": "方向=+1（正值做多）。正偏离>3%时可顺势做多，回归均线附近可减仓",
        "pitfalls": "震荡行情中频繁发出假信号，需要配合波动率过滤",
        "recommended_with": "rsi_14, vol_20",
    },
    "trend_slope_20": {
        "formula": "linear_regression_slope(close, 20) / close",
        "why_effective": "量化价格线性趋势的斜率，正值表示上升趋势，负值表示下降趋势",
        "how_to_use": "方向=+1。斜率>0且持续放大时可持有，斜率转负时应离场",
        "pitfalls": "对突发跳空敏感，需要配合成交量确认",
        "recommended_with": "ema20_gap_pct, volume_ratio",
    },
    "breakout_20": {
        "formula": "close / max(high, 20) - 1",
        "why_effective": "检测价格是否突破20日高点，突破往往预示趋势延续",
        "how_to_use": "方向=+1。突破时买入，回踩确认加仓",
        "pitfalls": "假突破频繁，需要放量配合",
        "recommended_with": "volume_ratio, mom_20",
    },
    # ========== 动量类因子 ==========
    "mom_20": {
        "formula": "close / close_20 - 1",
        "why_effective": "衡量过去20根K线的价格变化幅度，正值表示上涨动量",
        "how_to_use": "方向=+1，动量越大越可能延续",
        "pitfalls": "震荡市里动量信号会频繁失效",
        "recommended_with": "vol_20, rsi_14",
    },
    "roc_10": {
        "formula": "(close - close_10) / close_10 * 100",
        "why_effective": "变化率指标，衡量短期价格变化速度",
        "how_to_use": "方向=+1。ROC>0且加速时持有，减速时观望",
        "pitfalls": "短期波动噪音大，需要平滑处理",
        "recommended_with": "mom_20, ema20_gap_pct",
    },
    "momentum_score": {
        "formula": "rank(mom_5, mom_10, mom_20)",
        "why_effective": "综合多周期动量排名，平滑单一周期噪音",
        "how_to_use": "方向=+1。排名前20%时做多，后20%时做空",
        "pitfalls": "滞后于价格反转",
        "recommended_with": "trend_slope_20, rsi_14",
    },
    # ========== 震荡类因子 ==========
    "rsi_14": {
        "formula": "RSI(close, 14)",
        "why_effective": "衡量过去14根K线涨跌力量对比，>70 过热，<30 超卖",
        "how_to_use": "方向=-1（低值做多）。RSI<30 时做多，RSI>50 时卖出",
        "pitfalls": "趋势币种可以长期保持 RSI > 80",
        "recommended_with": "ema20_gap_pct, vol_20",
    },
    "rsi_7": {
        "formula": "RSI(close, 7)",
        "why_effective": "更敏感的超买超卖指标，适合短线交易",
        "how_to_use": "方向=-1。RSI<25 时做多，RSI>75 时卖出",
        "pitfalls": "假信号比RSI_14多，需要配合趋势过滤",
        "recommended_with": "rsi_14, trend_slope_20",
    },
    "kdj_k": {
        "formula": "KDJ_K(close, high, low, 9, 3, 3)",
        "why_effective": "随机指标K值，反映价格相对高低位置",
        "how_to_use": "方向=-1。K<20 时做多，K>80 时卖出",
        "pitfalls": "横盘震荡时信号密集，容易过度交易",
        "recommended_with": "rsi_14, volume_ratio",
    },
    "cci_20": {
        "formula": "CCI(close, 20)",
        "why_effective": "商品通道指标，衡量价格偏离统计平均的程度",
        "how_to_use": "方向=-1。CCI<-100 超卖做多，CCI>+100 超买卖出",
        "pitfalls": "在强趋势中会持续超买/超卖",
        "recommended_with": "rsi_14, bollinger_width",
    },
    "willr_14": {
        "formula": "Williams %R(close, high, low, 14)",
        "why_effective": "威廉指标，衡量收盘价在近期高低点范围的位置",
        "how_to_use": "方向=-1。%R<-80 超卖做多，%R>-20 超买卖出",
        "pitfalls": "与RSI类似，趋势行情中会长期极端",
        "recommended_with": "rsi_14, mom_20",
    },
    # ========== 波动率类因子 ==========
    "vol_20": {
        "formula": "std(return, 20) * sqrt(252)",
        "why_effective": "年化波动率，量化价格波动程度",
        "how_to_use": "方向=-1。低波动时买入，高波动时减仓",
        "pitfalls": "极端行情时波动率会飙升导致误判",
        "recommended_with": "rsi_14, bollinger_width",
    },
    "vol_ratio_5_20": {
        "formula": "std(return, 5) / std(return, 20)",
        "why_effective": "短期/长期波动率比值，检测波动率突变",
        "how_to_use": "方向=-1。比值>2时波动加剧应减仓",
        "pitfalls": "波动率骤升后可能持续高企",
        "recommended_with": "vol_20, atr_ratio",
    },
    "atr_ratio": {
        "formula": "ATR(14) / close",
        "why_effective": "真实波幅占比，衡量日内波动相对价格的比例",
        "how_to_use": "方向=-1。比例<2%时波动小可持有，>5%时风险大",
        "pitfalls": "不同币种基准差异大，需要标准化",
        "recommended_with": "vol_20, bollinger_width",
    },
    "bollinger_width": {
        "formula": "(upper_band - lower_band) / middle_band",
        "why_effective": "布林带宽度，量化价格波动区间",
        "how_to_use": "方向=-1。宽度收窄时可能突破，宽度放大时波动大",
        "pitfalls": "收窄后方向不确定，需要成交量确认",
        "recommended_with": "vol_20, volume_ratio",
    },
    # ========== 量能类因子 ==========
    "volume_ratio": {
        "formula": "volume / sma(volume, 20)",
        "why_effective": "当前成交量与20日均量比，放量往往伴随趋势",
        "how_to_use": "方向=+1。放量>1.5倍时关注，缩量<0.5时观望",
        "pitfalls": "放量下跌也是放量，需要配合价格方向",
        "recommended_with": "mom_20, obv_signal",
    },
    "obv_signal": {
        "formula": "OBV / sma(OBV, 20) - 1",
        "why_effective": "能量潮指标偏离，检测量价背离",
        "how_to_use": "方向=+1。OBV上升且价格横盘时可能突破",
        "pitfalls": "对分红、拆股敏感，需要调整",
        "recommended_with": "volume_ratio, rsi_14",
    },
    "vwap_gap": {
        "formula": "(close - VWAP) / VWAP",
        "why_effective": "价格相对成交量加权均价偏离，机构交易参考",
        "how_to_use": "方向=+1。正偏离可顺势，负偏离可能反弹",
        "pitfalls": "日内指标，日线级别效果减弱",
        "recommended_with": "volume_ratio, ema20_gap_pct",
    },
    "volume_spike": {
        "formula": "volume / max(volume, 20)",
        "why_effective": "成交量相对近期峰值比例，检测异常放量",
        "how_to_use": "方向=+1。放量突破时买入，缩量回归时卖出",
        "pitfalls": "异常放量可能是恐慌抛售",
        "recommended_with": "breakout_20, mom_20",
    },
    # ========== 均线偏离类因子 ==========
    "ma5_gap": {
        "formula": "(close - ma(close, 5)) / ma(close, 5)",
        "why_effective": "短期均线偏离，捕捉短期回调机会",
        "how_to_use": "方向=-1。偏离<-2%时可能反弹",
        "pitfalls": "强趋势中偏离会持续扩大",
        "recommended_with": "ema20_gap_pct, rsi_14",
    },
    "ma60_gap": {
        "formula": "(close - ma(close, 60)) / ma(close, 60)",
        "why_effective": "长期均线偏离，衡量中期趋势强度",
        "how_to_use": "方向=+1。正偏离持有，负偏离观望",
        "pitfalls": "滞后性强，不适合短线",
        "recommended_with": "trend_slope_20, vol_20",
    },
    "ma_cross_signal": {
        "formula": "ma(close, 5) > ma(close, 20) ? 1 : -1",
        "why_effective": "均线金叉死叉信号，经典趋势判断",
        "how_to_use": "方向=+1。金叉买入，死叉卖出",
        "pitfalls": "震荡市频繁交叉，假信号多",
        "recommended_with": "ema20_gap_pct, volume_ratio",
    },
    # ========== 形态类因子 ==========
    "higher_high": {
        "formula": "high > max(high[1:10])",
        "why_effective": "检测是否创新高，上升趋势特征",
        "how_to_use": "方向=+1。创新高时持有，连续新高后注意回调",
        "pitfalls": "假突破需要放量确认",
        "recommended_with": "breakout_20, volume_ratio",
    },
    "lower_low": {
        "formula": "low < min(low[1:10])",
        "why_effective": "检测是否创新低，下降趋势特征",
        "how_to_use": "方向=-1。新低后可能反弹",
        "pitfalls": "下降趋势中会持续新低",
        "recommended_with": "rsi_14, cci_20",
    },
    "gap_pct": {
        "formula": "(open - close[-1]) / close[-1]",
        "why_effective": "跳空缺口幅度，反映市场情绪突变",
        "how_to_use": "方向=+1。向上跳空>2%可能加速，向下跳空谨慎",
        "pitfalls": "缺口可能回补，不宜追涨",
        "recommended_with": "volume_ratio, mom_20",
    },
}


def get_factor_detail(factor_name: str) -> dict[str, str]:
    """获取因子详情，未定义的因子返回默认值。

    Args:
        factor_name: 因子名称

    Returns:
        包含 formula, why_effective, how_to_use, pitfalls, recommended_with 的字典
    """
    detail = FACTOR_DETAILS.get(factor_name, {})
    return {
        "formula": detail.get("formula", "暂无公式说明"),
        "why_effective": detail.get("why_effective", "暂无有效性说明"),
        "how_to_use": detail.get("how_to_use", "暂无使用说明"),
        "pitfalls": detail.get("pitfalls", "暂无注意事项"),
        "recommended_with": detail.get("recommended_with", "暂无推荐搭配"),
    }


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

        protocol_primary = list((factor_protocol.get("roles") or {}).get("primary") or [])
        protocol_auxiliary = list((factor_protocol.get("roles") or {}).get("auxiliary") or [])

        configured_primary_factors = [
            str(item).strip()
            for item in list(configured_features.get("primary_factors") or [])
            if str(item).strip()
        ]
        configured_auxiliary_factors = [
            str(item).strip()
            for item in list(configured_features.get("auxiliary_factors") or [])
            if str(item).strip()
        ]

        category_insights = self._build_category_insights(
            categories=categories,
            configured_primary_factors=configured_primary_factors,
            configured_auxiliary_factors=configured_auxiliary_factors,
            configured_research=configured_research,
        )
        timeframe_summary = self._build_timeframe_summary(configured_timeframe_profiles)
        effectiveness_summary = self._build_effectiveness_summary(
            category_insights=category_insights,
            configured_primary_factors=configured_primary_factors,
            configured_auxiliary_factors=configured_auxiliary_factors,
            configured_research=configured_research,
            configured_features=configured_features,
            timeframe_summary=timeframe_summary,
        )
        redundancy_summary = self._build_redundancy_summary(
            categories=categories,
            configured_factors=configured_primary_factors + configured_auxiliary_factors,
            category_insights=category_insights,
        )
        score_story = self._build_score_story(
            configured_research=configured_research,
            category_insights=category_insights,
            configured_primary_factors=configured_primary_factors,
            configured_auxiliary_factors=configured_auxiliary_factors,
        )

        # 构建 terminal 视图
        terminal = self._build_terminal_view(
            report=report,
            overview={
                "factor_count": len(factors),
                "primary_count": len(protocol_primary),
                "auxiliary_count": len(protocol_auxiliary),
                "feature_version": str(
                    training_context.get("feature_version")
                    or factor_protocol.get("version")
                    or "v1"
                ),
                "category_count": len(categories),
                "enabled_count": len(configured_primary_factors) + len(configured_auxiliary_factors),
            },
            effectiveness_summary=effectiveness_summary,
            factors=[
                {
                    "name": str(item.get("name", "")),
                    "category": str(item.get("category", "")),
                    "role": str(item.get("role", "")),
                    "description": str(item.get("description", "")),
                    **get_factor_detail(str(item.get("name", ""))),
                }
                for item in factors
                if isinstance(item, dict)
            ],
            redundancy_summary=redundancy_summary,
            categories=categories,
            selection_matrix=self._build_selection_matrix(factors=factors, configured_features=configured_features),
        )

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
                "primary_count": len(protocol_primary),
                "auxiliary_count": len(protocol_auxiliary),
                "holding_window": str(training_context.get("holding_window", "")),
            },
            "categories": categories,
            "roles": {
                "primary": [str(item) for item in protocol_primary],
                "auxiliary": [str(item) for item in protocol_auxiliary],
            },
            "controls": {
                "feature_preset_key": str(configured_features.get("feature_preset_key", "balanced_default") or "balanced_default"),
                "primary_factors": list(configured_primary_factors),
                "auxiliary_factors": list(configured_auxiliary_factors),
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
                    **get_factor_detail(str(item.get("name", ""))),
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
            "effectiveness_summary": effectiveness_summary,
            "redundancy_summary": redundancy_summary,
            "score_story": score_story,
            "terminal": terminal,
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

    def _build_category_insights(
        self,
        *,
        categories: dict[str, list[str]],
        configured_primary_factors: list[str],
        configured_auxiliary_factors: list[str],
        configured_research: dict[str, object],
    ) -> dict[str, object]:
        """统计每个类别的启用情况，作为摘要的辅助数据。"""

        configured_primary_set = {item for item in configured_primary_factors}
        configured_auxiliary_set = {item for item in configured_auxiliary_factors}
        configured_all = configured_primary_set | configured_auxiliary_set
        rows: list[dict[str, object]] = []
        by_category: dict[str, dict[str, object]] = {}
        total_primary = 0
        total_auxiliary = 0
        total_enabled = 0
        for category, factors in categories.items():
            canonical_category = str(category).strip()
            if not canonical_category:
                continue
            description = self._describe_feature_category(canonical_category)
            normalized_name = canonical_category.lower()
            primary_count = sum(1 for item in factors if str(item).strip() in configured_primary_set)
            auxiliary_count = sum(1 for item in factors if str(item).strip() in configured_auxiliary_set)
            enabled_factors = [str(item).strip() for item in factors if str(item).strip() in configured_all]
            total = primary_count + auxiliary_count
            total_primary += primary_count
            total_auxiliary += auxiliary_count
            total_enabled += total
            row = {
                "category": canonical_category,
                "label": description["label"],
                "weight_entry": description["weight_entry"],
                "detail": description["detail"],
                "primary_count": primary_count,
                "auxiliary_count": auxiliary_count,
                "total_enabled": total,
                "enabled_factors": enabled_factors,
            }
            rows.append(row)
            by_category[normalized_name] = {
                "label": description["label"],
                "weight_entry": description["weight_entry"],
                "detail": description["detail"],
                "primary_count": primary_count,
                "auxiliary_count": auxiliary_count,
                "total_enabled": total,
                "enabled_factors": enabled_factors,
            }
        return {
            "rows": rows,
            "by_category": by_category,
            "primary_total": total_primary,
            "auxiliary_total": total_auxiliary,
            "total_enabled": total_enabled,
        }

    def _build_effectiveness_summary(
        self,
        *,
        category_insights: dict[str, object],
        configured_primary_factors: list[str],
        configured_auxiliary_factors: list[str],
        configured_research: dict[str, object],
        configured_features: dict[str, object],
        timeframe_summary: str,
    ) -> dict[str, object]:
        """构建有效性摘要，突出主力因子分布与信号稳定性。"""

        category_rows = list(category_insights.get("rows") or [])
        total_enabled = category_insights.get("total_enabled", 0)
        top_category_row = max(category_rows, key=lambda row: row.get("total_enabled", 0), default=None)
        top_category_label = top_category_row["label"] if top_category_row else "暂无主导类别"
        signal_confidence_floor = str(configured_research.get("signal_confidence_floor", "0.55") or "0.55")
        primary_count = len(configured_primary_factors)
        auxiliary_count = len(configured_auxiliary_factors)
        headline = f"{primary_count} 主 + {auxiliary_count} 辅 / 已启用 {total_enabled} 个因子"
        detail = f"首轮观察 {configured_features.get('feature_preset_key', 'balanced_default')} 设置 / {timeframe_summary}"
        ic_story = f"{top_category_label} 贡献领先，当前权重入口 {top_category_row.get('weight_entry', '研究页统一评分')} 控制其评分。"
        bucket_story = f"{len([row for row in category_rows if row.get('total_enabled')])} 类因子都参与了判断，{top_category_label} 保持主导。"
        stability_story = f"信心底线 {signal_confidence_floor}，保持混合候选（{primary_count} 主 {auxiliary_count} 辅）的稳定性。"
        category_rows_output: list[dict[str, object]] = []
        for row in category_rows:
            category_rows_output.append(
                {
                    "category": row.get("category", "默认"),
                    "headline": f"{row.get('label', row.get('category', ''))} {row.get('primary_count', 0)} 主 / {row.get('auxiliary_count', 0)} 辅 / {row.get('total_enabled', 0)} 启用",
                    "detail": row.get("detail", "暂无说明"),
                    "weight_entry": row.get("weight_entry", "研究页统一评分"),
                }
            )
        if not category_rows_output:
            category_rows_output.append(
                {
                    "category": "未分类",
                    "headline": "当前未启用任何因子",
                    "detail": "请在配置里启用主判断或辅助判断因子以获得更多摘要。",
                    "weight_entry": "研究页统一评分",
                }
            )
        return {
            "headline": headline,
            "detail": detail,
            "top_category": top_category_label,
            "ic_story": ic_story,
            "bucket_story": bucket_story,
            "stability_story": stability_story,
            "category_rows": category_rows_output,
        }

    def _build_redundancy_summary(
        self,
        *,
        categories: dict[str, list[str]],
        configured_factors: list[str],
        category_insights: dict[str, object],
    ) -> dict[str, object]:
        """建立冗余摘要，显化趋势 / 动量 / 震荡 / 波动的重合情况。"""

        by_category = category_insights.get("by_category", {})
        configured_set = {str(item).strip() for item in configured_factors}
        target_pairs: list[tuple[str, str]] = [
            ("trend", "momentum"),
            ("oscillator", "volatility"),
        ]
        overlap_groups: list[dict[str, object]] = []
        for a, b in target_pairs:
            info_a = by_category.get(a, {})
            info_b = by_category.get(b, {})
            factors = list({*info_a.get("enabled_factors", []), *info_b.get("enabled_factors", [])})
            label = f"{info_a.get('label', a.title())} / {info_b.get('label', b.title())} 重合".strip()
            detail = (
                f"{label} 包含 {len(factors)} 个启用因子：{', '.join(factors)}"
                if factors
                else f"{label} 当前尚未激活因子，冗余可控。"
            )
            overlap_groups.append({
                "label": label,
                "detail": detail,
                "factors": factors,
            })
        volume_info = by_category.get("volume", {})
        volume_factors = volume_info.get("enabled_factors", [])
        volume_detail = (
            f"量能类因子 {', '.join(volume_factors)} 被激活，冗余较低。"
            if volume_factors
            else "当前未启用量能类因子，无法识别重复。"
        )
        overlap_groups.append(
            {
                "label": volume_info.get("label", "量能类因子"),
                "detail": volume_detail,
                "factors": volume_factors,
            }
        )
        headline = f"已检视 {len(overlap_groups)} 组重合趋势"
        detail = f"{sum(len(group.get('factors', [])) for group in overlap_groups)} 个因子参与 冗余/差异 校验。"
        next_step = (
            f"优先检查 {overlap_groups[0]['label']} 的因子组合，若冗余过高可从配置中删减。"
            if overlap_groups
            else "暂无重合因子，继续保持配置。"
        )
        return {
            "headline": headline,
            "detail": detail,
            "next_step": next_step,
            "overlap_groups": overlap_groups,
        }

    def _build_score_story(
        self,
        *,
        configured_research: dict[str, object],
        category_insights: dict[str, object],
        configured_primary_factors: list[str],
        configured_auxiliary_factors: list[str],
    ) -> dict[str, object]:
        """汇总多因子打分、当前权重和混合程度。"""

        weight_map: list[tuple[str, str, str]] = [
            ("trend_weight", "trend", "趋势"),
            ("momentum_weight", "momentum", "动量"),
            ("volume_weight", "volume", "量能"),
            ("oscillator_weight", "oscillator", "震荡"),
            ("volatility_weight", "volatility", "波动"),
        ]
        contributors: list[dict[str, object]] = []
        total_weight = 0.0
        by_category = category_insights.get("by_category", {})
        for key, category_key, label in weight_map:
            raw_value = str(configured_research.get(key, "1") or "1")
            numeric = self._parse_decimal(raw_value)
            total_weight += numeric
            category_info = by_category.get(category_key, {})
            descriptor = (
                f"当前有 {category_info.get('total_enabled', 0)} 个启用因子。"
                if category_info
                else "暂无启用因子。"
            )
            contributors.append(
                {
                    "label": label,
                    "weight": raw_value,
                    "description": f"研究页 {label} 权重 {raw_value}，{descriptor}",
                }
            )
        signal_confidence_floor = str(configured_research.get("signal_confidence_floor", "0.55") or "0.55")
        headline = f"研究权重总和 {total_weight:.1f}" if total_weight else "研究权重待配置"
        detail = f"信心底线 {signal_confidence_floor}；已按主/辅混合 ({len(configured_primary_factors)} 主 / {len(configured_auxiliary_factors)} 辅) 构建候选。"
        candidate_explanation = (
            f"主判断 {len(configured_primary_factors)} 个因子和辅助 {len(configured_auxiliary_factors)} 个因子共同构成打分篮子。"
        )
        return {
            "headline": headline,
            "detail": detail,
            "candidate_explanation": candidate_explanation,
            "contributors": contributors,
        }

    @staticmethod
    def _parse_decimal(value: str) -> float:
        """Safely parse a numeric string to float, defaulting to 1.0."""

        try:
            return float(value)
        except (ValueError, TypeError):
            return 1.0

    def _build_terminal_view(
        self,
        *,
        report: dict[str, object],
        overview: dict[str, object],
        effectiveness_summary: dict[str, object],
        factors: list[dict[str, str]],
        redundancy_summary: dict[str, object],
        categories: dict[str, list[str]],
        selection_matrix: list[dict[str, str]],
    ) -> dict[str, object]:
        """构建终端视图，包含因子研究和因子知识库两个子视图。"""

        # 构建顶层页面信息
        page = build_terminal_page(
            route="/features",
            breadcrumb="数据与知识 / 因子研究",
            title="因子研究",
            subtitle="因子 IC、分组收益与冗余检查",
        )

        # 构建 research 视图
        research = self._build_terminal_research(
            report=report,
            overview=overview,
            effectiveness_summary=effectiveness_summary,
            factors=factors,
            redundancy_summary=redundancy_summary,
        )

        # 构建 knowledge 视图
        knowledge = self._build_terminal_knowledge(
            overview=overview,
            categories=categories,
            factors=factors,
            selection_matrix=selection_matrix,
        )

        return {
            "page": page,
            "research": research,
            "knowledge": knowledge,
        }

    def _build_terminal_research(
        self,
        *,
        report: dict[str, object],
        overview: dict[str, object],
        effectiveness_summary: dict[str, object],
        factors: list[dict[str, str]],
        redundancy_summary: dict[str, object],
    ) -> dict[str, object]:
        """构建因子研究终端视图。"""

        # 指标卡：从 overview 和 effectiveness_summary 提取
        metrics = [
            metric_card("factor_count", "因子数量", overview.get("factor_count", 0), format="integer"),
            metric_card("primary_count", "主因子", overview.get("primary_count", 0), format="integer"),
            metric_card("auxiliary_count", "辅助因子", overview.get("auxiliary_count", 0), format="integer"),
            metric_card("mean_ic", "平均 IC", "0", format="decimal"),
            metric_card("icir", "ICIR", "0", format="decimal"),
            metric_card("effective_factor_count", "有效因子", overview.get("enabled_count", 0), format="integer"),
        ]

        # 图表：使用 terminal_series_service
        ic_series = terminal_series_service.build_factor_ic_series(report)
        cumulative_ic = terminal_series_service.build_factor_ic_series(report)  # 同一数据源，前端区分
        quantile_nav = terminal_series_service.build_factor_quantile_nav(report)

        charts = {
            "ic_series": ic_series,
            "cumulative_ic": cumulative_ic,
            "quantile_nav": quantile_nav,
        }

        # 表格：从 factors 和 redundancy_summary 构造
        factor_rows = [
            {
                "name": factor.get("name", ""),
                "category": factor.get("category", ""),
                "role": factor.get("role", ""),
                "ic": "0.00",
                "rank_ic": "0.00",
            }
            for factor in factors
        ]

        # 冗余表格
        redundancy_rows = []
        overlap_groups = list(redundancy_summary.get("overlap_groups") or [])
        for group in overlap_groups:
            redundancy_rows.append({
                "label": group.get("label", ""),
                "factor_count": len(group.get("factors", [])),
                "detail": group.get("detail", ""),
            })

        # 相关性表格（暂为空）
        correlation_rows: list[dict[str, object]] = []

        tables = {
            "factor_rows": factor_rows,
            "correlation_rows": correlation_rows,
            "redundancy_rows": redundancy_rows,
        }

        return {
            "metrics": metrics,
            "charts": charts,
            "tables": tables,
        }

    def _build_terminal_knowledge(
        self,
        *,
        overview: dict[str, object],
        categories: dict[str, list[str]],
        factors: list[dict[str, str]],
        selection_matrix: list[dict[str, str]],
    ) -> dict[str, object]:
        """构建因子知识库终端视图。"""

        # 指标卡
        metrics = [
            metric_card("factor_count", "因子总数", overview.get("factor_count", 0), format="integer"),
            metric_card("category_count", "分类数量", overview.get("category_count", 0), format="integer"),
            metric_card("enabled_count", "已启用", overview.get("enabled_count", 0), format="integer"),
            metric_card("feature_version", "协议版本", overview.get("feature_version", "v1"), format="text"),
        ]

        # 筛选器：从 categories 构造
        filters = [
            {"key": category, "label": category, "count": len(items)}
            for category, items in categories.items()
        ]

        # 因子卡片：从 factors 和 selection_matrix 构造
        factor_cards = []
        selection_map = {row.get("name", ""): row for row in selection_matrix}
        for factor in factors:
            name = factor.get("name", "")
            selection_info = selection_map.get(name, {})
            detail = get_factor_detail(name)
            factor_cards.append({
                "name": name,
                "category": factor.get("category", ""),
                "role": factor.get("role", ""),
                "current_role": selection_info.get("current_role", "未启用"),
                "description": factor.get("description", ""),
                "formula": detail.get("formula", "暂无公式说明"),
                "why_effective": detail.get("why_effective", "暂无有效性说明"),
                "how_to_use": detail.get("how_to_use", "暂无使用说明"),
                "pitfalls": detail.get("pitfalls", "暂无注意事项"),
                "recommended_with": detail.get("recommended_with", "暂无推荐搭配"),
            })

        # 因子详情：包含完整的因子信息
        factor_details = [
            {
                "name": factor.get("name", ""),
                "category": factor.get("category", ""),
                "role": factor.get("role", ""),
                "description": factor.get("description", ""),
                **get_factor_detail(factor.get("name", "")),
            }
            for factor in factors
        ]

        return {
            "metrics": metrics,
            "filters": filters,
            "factor_cards": factor_cards,
            "factor_details": factor_details,
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

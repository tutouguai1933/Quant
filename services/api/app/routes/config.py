"""配置中心 API 路由。

提供配置查询、更新、历史追踪和验证接口。
"""

from __future__ import annotations

from typing import Any

from services.api.app.services.config_center_service import (
    config_center_service,
    detect_environment,
    get_config,
    get_config_section_values,
    is_sensitive_key,
    mask_sensitive_value,
)
from services.api.app.services.auth_service import auth_service


try:
    from fastapi import APIRouter, Body, Header, Query
except ImportError:
    class APIRouter:  # pragma: no cover - lightweight local fallback
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def get(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

        def post(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

        def delete(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

        def put(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    def Body(default=None):  # pragma: no cover - lightweight local fallback
        return default

    def Query(default=None, **kwargs):  # pragma: no cover - lightweight local fallback
        return default

    def Header(default: str = "") -> str:  # pragma: no cover - fallback stub
        return default


router = APIRouter(prefix="/api/v1/config", tags=["config"])


def _success(data: dict[str, Any] | list[Any], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """成功响应格式。"""
    return {"data": data, "error": None, "meta": meta or {}}


def _error(code: str, message: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """错误响应格式。"""
    return {"data": None, "error": {"code": code, "message": message}, "meta": meta or {}}


def _unauthorized() -> dict[str, Any]:
    """未授权响应格式。"""
    return {
        "data": None,
        "error": {"code": "unauthorized", "message": "authentication required"},
        "meta": {"source": "config-center"},
    }


@router.get("")
def get_all_config(include_secrets: bool = Query(False, description="是否包含敏感信息")) -> dict[str, Any]:
    """获取所有配置。

    合并 api.env 和 JSON 配置文件，按分组组织返回。

    Args:
        include_secrets: 是否包含敏感信息（默认脱敏）

    Returns:
        所有配置信息
    """
    try:
        config = config_center_service.get_all_config(include_secrets=include_secrets)
        return _success(config, {"source": "config-center", "action": "get_all"})
    except Exception as e:
        return _error("config_error", f"获取配置失败: {e}", {"source": "config-center"})


@router.get("/schema")
def get_config_schema() -> dict[str, Any]:
    """获取配置模式定义。

    返回配置分组、来源文件和敏感字段定义。

    Returns:
        配置模式定义
    """
    try:
        schema = config_center_service.get_config_schema()
        return _success(schema, {"source": "config-center", "action": "get_schema"})
    except Exception as e:
        return _error("schema_error", f"获取配置模式失败: {e}", {"source": "config-center"})


@router.get("/sections/{section}")
def get_config_section(
    section: str,
    include_secrets: bool = Query(False, description="是否包含敏感信息"),
) -> dict[str, Any]:
    """获取特定配置段。

    Args:
        section: 配置段名称 (network/trading/risk/alert/research/auth/binance)
        include_secrets: 是否包含敏感信息

    Returns:
        配置段内容
    """
    try:
        config = config_center_service.get_config_section(
            section=section,
            include_secrets=include_secrets,
        )
        return _success(config, {"source": "config-center", "action": "get_section"})
    except ValueError as e:
        return _error("invalid_section", str(e), {"source": "config-center"})
    except Exception as e:
        return _error("config_error", f"获取配置段失败: {e}", {"source": "config-center"})


@router.get("/history")
def get_config_history(
    key: str | None = Query(None, description="过滤特定配置键"),
    action: str | None = Query(None, description="过滤操作类型 (create/update/delete)"),
    limit: int = Query(100, ge=1, le=500, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
) -> dict[str, Any]:
    """获取配置变更历史。

    Args:
        key: 过滤特定配置键
        action: 过滤操作类型
        limit: 返回数量限制
        offset: 偏移量

    Returns:
        配置变更历史记录
    """
    try:
        history = config_center_service.get_config_history(
            key=key,
            action=action,
            limit=limit,
            offset=offset,
        )
        return _success(history, {"source": "config-center", "action": "get_history"})
    except Exception as e:
        return _error("history_error", f"获取配置历史失败: {e}", {"source": "config-center"})


@router.get("/validate")
def validate_config() -> dict[str, Any]:
    """验证配置完整性。

    检查必需配置项是否存在、值是否有效。

    Returns:
        验证结果，包含缺失和无效配置项
    """
    try:
        result = config_center_service.validate_config()
        return _success(result, {"source": "config-center", "action": "validate"})
    except Exception as e:
        return _error("validation_error", f"配置验证失败: {e}", {"source": "config-center"})


@router.post("/update")
def update_config(
    payload: dict[str, Any] | None = Body(None),
    key: str = "",
    value: str = "",
    operator: str = "system",
    comment: str = "",
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """更新单个配置项。

    需要管理员权限。

    Args:
        payload: 请求体，可包含 key, value, operator, comment
        key: 配置键名
        value: 新值
        operator: 操作者
        comment: 变更说明
        token: 认证令牌
        authorization: Bearer 认证头

    Returns:
        更新结果
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    request = payload if isinstance(payload, dict) else {}
    resolved_key = str(request.get("key", key))
    resolved_value = str(request.get("value", value))
    resolved_operator = str(request.get("operator", operator))
    resolved_comment = str(request.get("comment", comment))

    if not resolved_key:
        return _error("invalid_request", "缺少配置键名", {"source": "config-center"})

    try:
        result = config_center_service.update_config(
            key=resolved_key,
            value=resolved_value,
            operator=resolved_operator,
            comment=resolved_comment,
        )
        return _success(result, {"source": "config-center", "action": "update"})
    except ValueError as e:
        return _error("invalid_config", str(e), {"source": "config-center"})
    except Exception as e:
        return _error("update_error", f"更新配置失败: {e}", {"source": "config-center"})


@router.post("/batch-update")
def batch_update_config(
    payload: dict[str, Any] | None = Body(None),
    updates: dict[str, str] | None = None,
    operator: str = "system",
    comment: str = "",
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """批量更新配置项。

    需要管理员权限。

    Args:
        payload: 请求体，可包含 updates, operator, comment
        updates: 配置键值对
        operator: 操作者
        comment: 变更说明
        token: 认证令牌
        authorization: Bearer 认证头

    Returns:
        批量更新结果
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    request = payload if isinstance(payload, dict) else {}
    resolved_updates = request.get("updates", updates) or {}
    resolved_operator = str(request.get("operator", operator))
    resolved_comment = str(request.get("comment", comment))

    if not resolved_updates:
        return _error("invalid_request", "缺少配置更新内容", {"source": "config-center"})

    try:
        result = config_center_service.batch_update_config(
            updates=resolved_updates,
            operator=resolved_operator,
            comment=resolved_comment,
        )
        return _success(result, {"source": "config-center", "action": "batch_update"})
    except Exception as e:
        return _error("batch_update_error", f"批量更新配置失败: {e}", {"source": "config-center"})


@router.delete("/{key}")
def delete_config(
    key: str,
    operator: str = Query("system", description="操作者"),
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """删除配置项。

    需要管理员权限。

    Args:
        key: 配置键名
        operator: 操作者
        token: 认证令牌
        authorization: Bearer 认证头

    Returns:
        删除结果
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    try:
        result = config_center_service.delete_config(key=key, operator=operator)
        return _success(result, {"source": "config-center", "action": "delete"})
    except ValueError as e:
        return _error("config_not_found", str(e), {"source": "config-center"})
    except Exception as e:
        return _error("delete_error", f"删除配置失败: {e}", {"source": "config-center"})


@router.post("/reload")
def reload_config(
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """重新加载配置。

    需要管理员权限。配置更新后需要重启服务才能生效。

    Args:
        token: 认证令牌
        authorization: Bearer 认证头

    Returns:
        重载结果
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    try:
        result = config_center_service.reload_config()
        return _success(result, {"source": "config-center", "action": "reload"})
    except Exception as e:
        return _error("reload_error", f"重载配置失败: {e}", {"source": "config-center"})


# ========== 交易对白名单管理 API ==========


@router.get("/pairs")
def get_pair_whitelist() -> dict[str, Any]:
    """获取交易对白名单配置。

    Returns:
        交易对白名单配置信息，包含：
        - whitelist: 白名单列表
        - blacklist: 黑名单列表
        - max_pairs: 最大交易对数量
        - stake_per_pair: 仓位分配策略
        - volatility_params: 各币种波动率参数
        - effective_whitelist: 实际生效的白名单（排除黑名单后）
    """
    try:
        result = config_center_service.get_pair_whitelist()
        return _success(result, {"source": "config-center", "action": "get_pairs"})
    except Exception as e:
        return _error("pairs_error", f"获取交易对配置失败: {e}", {"source": "config-center"})


@router.put("/pairs")
def update_pair_whitelist(
    payload: dict[str, Any] | None = Body(None),
    whitelist: list[str] | None = None,
    blacklist: list[str] | None = None,
    max_pairs: int | None = None,
    stake_per_pair: str | None = None,
    operator: str = "system",
    comment: str = "",
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """更新交易对白名单配置。

    需要管理员权限。

    Args:
        payload: 请求体
        whitelist: 新的白名单列表，例如 ["BTC/USDT", "ETH/USDT", "DOGE/USDT"]
        blacklist: 新的黑名单列表
        max_pairs: 最大交易对数量（默认5）
        stake_per_pair: 仓位分配策略（equal/volatility/score）
        operator: 操作者
        comment: 变更说明
        token: 认证令牌
        authorization: Bearer 认证头

    Returns:
        更新结果和当前配置
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    request = payload if isinstance(payload, dict) else {}

    resolved_whitelist = request.get("whitelist", whitelist)
    resolved_blacklist = request.get("blacklist", blacklist)
    resolved_max_pairs = request.get("max_pairs", max_pairs)
    resolved_stake_per_pair = request.get("stake_per_pair", stake_per_pair)
    resolved_operator = str(request.get("operator", operator))
    resolved_comment = str(request.get("comment", comment))

    try:
        result = config_center_service.update_pair_whitelist(
            whitelist=resolved_whitelist,
            blacklist=resolved_blacklist,
            max_pairs=resolved_max_pairs,
            stake_per_pair=resolved_stake_per_pair,
            operator=resolved_operator,
            comment=resolved_comment,
        )
        return _success(result, {"source": "config-center", "action": "update_pairs"})
    except Exception as e:
        return _error("pairs_update_error", f"更新交易对配置失败: {e}", {"source": "config-center"})


@router.get("/pairs/validate")
def validate_pair_whitelist() -> dict[str, Any]:
    """验证交易对白名单配置。

    Returns:
        验证结果，包含：
        - valid: 是否有效
        - errors: 错误列表
        - warnings: 警告列表
        - pairs_status: 各交易对的状态详情
    """
    try:
        result = config_center_service.validate_pair_whitelist()
        return _success(result, {"source": "config-center", "action": "validate_pairs"})
    except Exception as e:
        return _error("pairs_validation_error", f"验证交易对配置失败: {e}", {"source": "config-center"})


@router.get("/pairs/{pair}/volatility")
def get_pair_volatility_params(pair: str) -> dict[str, Any]:
    """获取特定交易对的波动率参数。

    Args:
        pair: 交易对名称（如 BTC/USDT 或 BTCUSDT）

    Returns:
        该交易对的波动率参数配置：
        - volatility_multiplier: 波动率乘数
        - stop_loss_multiplier: 止损乘数
        - position_multiplier: 仓位乘数
    """
    try:
        result = config_center_service.get_pair_volatility_params(pair)
        return _success(result, {"source": "config-center", "action": "get_pair_volatility"})
    except Exception as e:
        return _error("pair_volatility_error", f"获取交易对波动率参数失败: {e}", {"source": "config-center"})


# ========== 统一配置访问接口 ==========


@router.get("/environment")
def get_environment() -> dict[str, Any]:
    """获取当前运行环境信息。

    Returns:
        环境信息：
        - environment: "server" 或 "local"
        - is_docker: 是否在 Docker 容器中
        - runtime_mode: 当前运行模式
    """
    try:
        env = detect_environment()
        runtime_mode = get_config("QUANT_RUNTIME_MODE", "dry-run", as_type="str")
        return _success({
            "environment": env,
            "is_docker": env == "server",
            "runtime_mode": runtime_mode,
        }, {"source": "config-center", "action": "get_environment"})
    except Exception as e:
        return _error("environment_error", f"获取环境信息失败: {e}", {"source": "config-center"})


@router.get("/value/{key}")
def get_config_value(
    key: str,
    default: str = Query("", description="默认值"),
    as_type: str = Query("str", description="返回类型 (str/int/float/decimal/bool/list)"),
    include_secrets: bool = Query(False, description="是否包含敏感信息"),
) -> dict[str, Any]:
    """获取单个配置项的值。

    Args:
        key: 配置键名（如 QUANT_STRATEGY_MIN_ENTRY_SCORE）
        default: 默认值（可选）
        as_type: 返回类型 (str/int/float/decimal/bool/list)
        include_secrets: 是否包含敏感信息（敏感信息默认脱敏）

    Returns:
        配置值
    """
    try:
        value = get_config(key, default if default else None, as_type=as_type)

        # 敏感信息脱敏
        if not include_secrets and is_sensitive_key(key):
            value = mask_sensitive_value(key, str(value) if value else None)

        return _success({
            "key": key,
            "value": value,
            "type": as_type,
            "is_sensitive": is_sensitive_key(key),
        }, {"source": "config-center", "action": "get_value"})
    except Exception as e:
        return _error("value_error", f"获取配置值失败: {e}", {"source": "config-center"})


@router.get("/section/{section}/values")
def get_section_values(
    section: str,
    include_secrets: bool = Query(False, description="是否包含敏感信息"),
) -> dict[str, Any]:
    """获取配置段的全部值（已自动解析类型）。

    Args:
        section: 配置段名称（如 strategy, vpn, risk 等）
        include_secrets: 是否包含敏感信息

    Returns:
        配置段的全部键值对
    """
    try:
        values = get_config_section_values(section)

        # 敏感信息脱敏
        if not include_secrets:
            for key in values:
                if is_sensitive_key(key) and values[key]:
                    values[key] = "***REDACTED***"

        return _success({
            "section": section,
            "values": values,
        }, {"source": "config-center", "action": "get_section_values"})
    except ValueError as e:
        return _error("invalid_section", str(e), {"source": "config-center"})
    except Exception as e:
        return _error("section_error", f"获取配置段值失败: {e}", {"source": "config-center"})
"""配置中心 API 路由。

提供配置查询、更新、历史追踪和验证接口。
"""

from __future__ import annotations

from typing import Any

from services.api.app.services.config_center_service import config_center_service


try:
    from fastapi import APIRouter, Body, Query
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

    def Body(default=None):  # pragma: no cover - lightweight local fallback
        return default

    def Query(default=None, **kwargs):  # pragma: no cover - lightweight local fallback
        return default


router = APIRouter(prefix="/api/v1/config", tags=["config"])


def _success(data: dict[str, Any] | list[Any], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """成功响应格式。"""
    return {"data": data, "error": None, "meta": meta or {}}


def _error(code: str, message: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """错误响应格式。"""
    return {"data": None, "error": {"code": code, "message": message}, "meta": meta or {}}


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
) -> dict[str, Any]:
    """更新单个配置项。

    需要管理员权限。

    Args:
        payload: 请求体，可包含 key, value, operator, comment
        key: 配置键名
        value: 新值
        operator: 操作者
        comment: 变更说明

    Returns:
        更新结果
    """
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
) -> dict[str, Any]:
    """批量更新配置项。

    需要管理员权限。

    Args:
        payload: 请求体，可包含 updates, operator, comment
        updates: 配置键值对
        operator: 操作者
        comment: 变更说明

    Returns:
        批量更新结果
    """
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
) -> dict[str, Any]:
    """删除配置项。

    需要管理员权限。

    Args:
        key: 配置键名
        operator: 操作者

    Returns:
        删除结果
    """
    try:
        result = config_center_service.delete_config(key=key, operator=operator)
        return _success(result, {"source": "config-center", "action": "delete"})
    except ValueError as e:
        return _error("config_not_found", str(e), {"source": "config-center"})
    except Exception as e:
        return _error("delete_error", f"删除配置失败: {e}", {"source": "config-center"})


@router.post("/reload")
def reload_config() -> dict[str, Any]:
    """重新加载配置。

    注意：配置更新后需要重启服务才能生效。

    Returns:
        重载结果
    """
    try:
        result = config_center_service.reload_config()
        return _success(result, {"source": "config-center", "action": "reload"})
    except Exception as e:
        return _error("reload_error", f"重载配置失败: {e}", {"source": "config-center"})
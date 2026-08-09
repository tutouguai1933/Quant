"""路由公共响应助手。

全站统一使用 {"data", "error", "meta"} envelope 结构，
这里提供 _success / _error / _error_with_code / _unauthorized 的公共实现，
避免各路由文件重复定义。

- _success: 成功响应
- _error: health 风格错误响应（message 在前）
- _error_with_code: exchange/config 风格错误响应（code 在前），仅签名兼容旧调用
- _unauthorized: 未认证响应
"""

from __future__ import annotations

from typing import Any


def _success(data: Any, meta: dict | None = None) -> dict:
    """统一成功响应 envelope。"""
    return {"data": data, "error": None, "meta": meta or {}}


def _error(message: str, code: str = "INTERNAL_ERROR", meta: dict | None = None) -> dict:
    """统一错误响应 envelope（message 在前，参考 health.py 的签名）。"""
    return {"data": None, "error": {"message": message, "code": code}, "meta": meta or {}}


def _error_with_code(code: str, message: str, meta: dict | None = None) -> dict:
    """统一错误响应 envelope（code 在前，兼容 exchange/config 旧调用签名）。"""
    return {"data": None, "error": {"code": code, "message": message}, "meta": meta or {}}


def _unauthorized() -> dict:
    """统一未认证响应 envelope。"""
    return {
        "data": None,
        "error": {"code": "unauthorized", "message": "authentication required"},
        "meta": {"source": "control-plane-api"},
    }

"""通用重试和降级工具。"""

from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable, TypeVar
from urllib.error import HTTPError, URLError

T = TypeVar("T")


def with_retry_and_fallback(
    max_retries: int = 3,
    base_delay: float = 0.5,
    timeout_errors: tuple[type[Exception], ...] = (TimeoutError, URLError, OSError),
    fallback_value: Any = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """为函数添加重试和降级逻辑的装饰器。

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟时间（秒），使用指数退避
        timeout_errors: 需要重试的异常类型
        fallback_value: 降级返回值（如果是 callable 则调用它）
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except timeout_errors as exc:
                    last_exception = exc
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)
                    continue
                except HTTPError as exc:
                    if exc.code >= 500:
                        last_exception = exc
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            time.sleep(delay)
                        continue
                    raise

            if callable(fallback_value):
                return fallback_value(last_exception)
            return fallback_value

        return wrapper
    return decorator


def create_unavailable_response(error: Exception | None = None) -> dict[str, object]:
    """创建服务不可用的降级响应。"""

    error_code = "connection_failed"
    message = "服务暂时不可用，请稍后重试"

    if error is not None:
        if isinstance(error, TimeoutError):
            error_code = "timeout"
            message = "连接超时，请检查网络或稍后重试"
        elif isinstance(error, URLError):
            error_code = "connection_failed"
            message = f"无法连接到服务: {getattr(error, 'reason', '未知错误')}"
        elif isinstance(error, HTTPError):
            error_code = "server_error"
            message = f"服务器错误 ({error.code})"

    return {
        "status": "unavailable",
        "error_code": error_code,
        "message": message,
    }

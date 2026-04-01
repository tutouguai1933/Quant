"""单管理员鉴权服务。

这个文件负责最小会话管理，只服务第一阶段控制平面，不扩展为多用户系统。
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from hmac import compare_digest


def utc_now() -> datetime:
    """返回当前 UTC 时间。"""

    return datetime.now(timezone.utc)


class AuthService:
    """提供单管理员登录、会话查询和登出能力。"""

    def __init__(self) -> None:
        self._admin_username = os.getenv("QUANT_ADMIN_USERNAME", "admin")
        self._admin_password = os.getenv("QUANT_ADMIN_PASSWORD", "1933")
        self._session_ttl_seconds = int(os.getenv("QUANT_SESSION_TTL_SECONDS", "28800"))
        self._sessions: dict[str, dict[str, object]] = {}

    def login(self, username: str, password: str) -> dict[str, object]:
        """校验管理员账号并创建会话。"""

        if not self._is_valid_credentials(username, password):
            raise ValueError("invalid credentials")

        token = secrets.token_urlsafe(24)
        issued_at = utc_now()
        session = {
            "token": token,
            "username": self._admin_username,
            "scope": "control_plane",
            "status": "active",
            "issued_at": issued_at.isoformat(),
            "expires_at": (issued_at + timedelta(seconds=self._session_ttl_seconds)).isoformat(),
        }
        self._sessions[token] = session
        return dict(session)

    def get_session(self, token: str) -> dict[str, object] | None:
        """返回有效会话。"""

        session = self._sessions.get(token)
        if session is None:
            return None

        expires_at = datetime.fromisoformat(str(session["expires_at"]))
        if expires_at <= utc_now():
            self._sessions.pop(token, None)
            return None
        return dict(session)

    def logout(self, token: str) -> dict[str, object] | None:
        """撤销会话。"""

        session = self._sessions.pop(token, None)
        if session is None:
            return None
        return {
            "token": token,
            "username": session["username"],
            "scope": session["scope"],
            "status": "revoked",
            "revoked_at": utc_now().isoformat(),
        }

    def require_control_plane_access(self, token: str) -> dict[str, object]:
        """要求必须带有效控制平面令牌。"""

        session = self.get_session(token)
        if session is None or session.get("scope") != "control_plane":
            raise PermissionError("authentication required")
        return session

    def resolve_access_token(self, token: str = "", authorization: str = "") -> str:
        """从查询参数或 Bearer 头中提取令牌。"""

        token_value = token if isinstance(token, str) else ""
        authorization_value = authorization if isinstance(authorization, str) else ""
        if token_value:
            return token_value
        prefix = "Bearer "
        if authorization_value.startswith(prefix):
            return authorization_value[len(prefix) :].strip()
        return ""

    def get_login_model(self) -> dict[str, object]:
        """返回登录页需要的最小展示模型。"""

        return {
            "default_username": self._admin_username,
            "session_mode": "单管理员 + 本地会话令牌",
            "protected_pages": ["Strategies", "Tasks", "Risk"],
            "notes": [
                "仅保留单管理员入口",
                "登录后通过会话令牌访问控制平面",
                "当前阶段不扩展多用户与角色权限",
            ],
        }

    def _is_valid_credentials(self, username: str, password: str) -> bool:
        """校验账号密码。"""

        return compare_digest(username, self._admin_username) and compare_digest(password, self._admin_password)


auth_service = AuthService()

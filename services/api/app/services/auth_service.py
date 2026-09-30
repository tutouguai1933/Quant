"""单管理员鉴权服务。

这个文件负责最小会话管理，只服务第一阶段控制平面，不扩展为多用户系统。
"""

from __future__ import annotations

import os
import hashlib
import json
import logging
import tempfile
import threading
from pathlib import Path
import secrets
from datetime import datetime, timedelta, timezone
from hmac import compare_digest


logger = logging.getLogger(__name__)


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
        self._lock = threading.RLock()
        configured_path = os.getenv("QUANT_SESSION_STATE_PATH", "").strip()
        self._session_path = Path(configured_path) if configured_path else None
        # 管理员凭据变更后使旧会话失效；文件权限仅允许容器用户读取。
        self._account_fingerprint = hashlib.sha256(
            f"{self._admin_username}\0{self._admin_password}".encode("utf-8")
        ).hexdigest()
        self._restore_sessions()

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
        with self._lock:
            self._prune_expired_sessions()
            self._sessions[self._token_digest(token)] = session
            self._save_sessions()
        return dict(session)

    def get_session(self, token: str) -> dict[str, object] | None:
        """返回有效会话。"""

        with self._lock:
            session = self._sessions.get(self._token_digest(token))
            if session is None:
                return None
            expires_at = datetime.fromisoformat(str(session["expires_at"]))
            if expires_at <= utc_now():
                self._sessions.pop(self._token_digest(token), None)
                self._save_sessions()
                return None
            return {**session, "token": token}

    def logout(self, token: str) -> dict[str, object] | None:
        """撤销会话。"""

        with self._lock:
            session = self._sessions.pop(self._token_digest(token), None)
            if session is not None:
                self._save_sessions()
        if session is None:
            return None
        return {
            "token": token,
            "username": session["username"],
            "scope": session["scope"],
            "status": "revoked",
            "revoked_at": utc_now().isoformat(),
        }

    @staticmethod
    def _token_digest(token: str) -> str:
        """只持久化令牌摘要，运行文件不能直接作为Bearer令牌使用。"""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _prune_expired_sessions(self) -> None:
        """清理过期记录，控制长时间运行时的会话数量。"""
        now = utc_now()
        self._sessions = {
            key: session for key, session in self._sessions.items()
            if datetime.fromisoformat(str(session["expires_at"])) > now
        }

    def _restore_sessions(self) -> None:
        """从挂载运行目录恢复有效登录，损坏时拒绝恢复并显式记日志。"""
        if self._session_path is None:
            return
        try:
            payload = json.loads(self._session_path.read_text(encoding="utf-8"))
            if payload.get("account_fingerprint") != self._account_fingerprint:
                return
            sessions = payload["sessions"]
            if not isinstance(sessions, dict):
                raise ValueError("会话记录格式无效")
            self._sessions = sessions
            self._prune_expired_sessions()
        except FileNotFoundError:
            return
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            self._sessions = {}
            logger.exception("会话文件无法读取，需要重新登录")

    def _save_sessions(self) -> None:
        """原子保存会话到私有文件，API重建时沿用挂载卷中的登录记录。"""
        if self._session_path is None:
            return
        self._session_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_path = tempfile.mkstemp(
            prefix=f".{self._session_path.name}.", dir=self._session_path.parent,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                payload = {
                    "version": 1,
                    "account_fingerprint": self._account_fingerprint,
                    "sessions": {
                        key: {field: value for field, value in session.items() if field != "token"}
                        for key, session in self._sessions.items()
                    },
                }
                json.dump(payload, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, self._session_path)
        except OSError:
            logger.exception("会话文件保存失败，本次登录无法保证跨重启保留")
            raise

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

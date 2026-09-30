"""验证会话跨API重启保留，登出、过期和更改密码仍能使会话失效。"""

import json
import os
import stat
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from services.api.app.services.auth_service import AuthService


class AuthPersistenceTests(unittest.TestCase):
    """使用临时目录，避免触碰用户实际会话。"""

    def setUp(self):
        """配置独立会话文件和测试管理员。"""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "sessions.json"
        env = patch.dict(os.environ, {
            "QUANT_SESSION_STATE_PATH": str(self.path),
            "QUANT_ADMIN_USERNAME": "tester", "QUANT_ADMIN_PASSWORD": "private-test-password",
        })
        env.start()
        self.addCleanup(env.stop)

    def test_session_survives_recreating_service(self):
        """重启后使用旧令牌依然能通过控制面校验。"""
        first = AuthService()
        session = first.login("tester", "private-test-password")
        second = AuthService()
        self.assertEqual(second.get_session(session["token"]), session)
        self.assertEqual(second.require_control_plane_access(session["token"]), session)

    def test_logout_remains_revoked_after_restart(self):
        """登出撤销必须持久化，重启不能恢复已撤销登录。"""
        first = AuthService()
        session = first.login("tester", "private-test-password")
        second = AuthService()
        self.assertIsNotNone(second.logout(session["token"]))
        self.assertIsNone(AuthService().get_session(session["token"]))

    def test_persistent_file_does_not_contain_bearer_token(self):
        """文件只保存令牌摘要，权限限制为当前用户可读写。"""
        token = AuthService().login("tester", "private-test-password")["token"]
        self.assertTrue(self.path.exists(), "会话文件未创建")
        self.assertNotIn(token, self.path.read_text(encoding="utf-8"))
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_expired_session_is_not_restored(self):
        """重启只恢复仍在有效期内的会话。"""
        with patch("services.api.app.services.auth_service.utc_now",
                   return_value=datetime.now(timezone.utc) - timedelta(days=10)):
            session = AuthService().login("tester", "private-test-password")
        self.assertIsNone(AuthService().get_session(session["token"]))

    def test_password_change_invalidates_stored_sessions(self):
        """更换管理员密码后，旧会话不能继续使用。"""
        session = AuthService().login("tester", "private-test-password")
        with patch.dict(os.environ, {"QUANT_ADMIN_PASSWORD": "changed-password"}):
            self.assertIsNone(AuthService().get_session(session["token"]))

    def test_corrupted_file_fails_closed_with_visible_log(self):
        """损坏文件应显式记日志并要求重新登录，不接受未知令牌。"""
        self.path.write_text("bad-json", encoding="utf-8")
        with self.assertLogs("services.api.app.services.auth_service", level="ERROR"):
            service = AuthService()
        self.assertIsNone(service.get_session("unknown"))

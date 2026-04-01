from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.routes.auth import get_login_model, get_session, login, logout  # noqa: E402
from services.api.app.services.auth_service import auth_service  # noqa: E402


class AuthFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        auth_service.__init__()

    def test_login_creates_single_admin_session(self) -> None:
        response = login(username="admin", password="1933")

        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["item"]["username"], "admin")
        self.assertTrue(response["data"]["item"]["token"])

    def test_invalid_login_is_rejected(self) -> None:
        response = login(username="admin", password="wrong-password")

        self.assertEqual(response["error"]["code"], "invalid_credentials")

    def test_login_accepts_json_style_payload(self) -> None:
        response = login(payload={"username": "admin", "password": "1933"})

        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["item"]["username"], "admin")

    def test_session_and_logout_follow_same_token(self) -> None:
        logged_in = login(username="admin", password="1933")
        token = logged_in["data"]["item"]["token"]

        current = get_session(token=token)
        revoked = logout(token=token)
        missing = get_session(token=token)

        self.assertIsNone(current["error"])
        self.assertEqual(current["data"]["item"]["scope"], "control_plane")
        self.assertIsNone(revoked["error"])
        self.assertEqual(revoked["data"]["item"]["status"], "revoked")
        self.assertEqual(missing["error"]["code"], "session_not_found")

    def test_login_model_comes_from_auth_service(self) -> None:
        response = get_login_model()

        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["item"]["default_username"], "admin")
        self.assertIn("Strategies", response["data"]["item"]["protected_pages"])


if __name__ == "__main__":
    unittest.main()

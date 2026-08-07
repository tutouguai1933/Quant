"""自动恢复服务单元测试。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.auto_recovery_service import (  # noqa: E402
    AutoRecoveryService,
    RecoveryAction,
    RecoveryConfig,
    RecoveryStatus,
)


class AutoRecoveryServiceTests(unittest.TestCase):
    """AutoRecoveryService 单元测试。"""

    def test_attempt_recovery_restarts_container_and_records(self) -> None:
        """attempt_recovery 成功重启容器并记录 SUCCESS（回归：dataclass 缺 status 默认值）。"""
        service = AutoRecoveryService(RecoveryConfig())
        with mock.patch.object(service, "_run_docker_command", return_value=(True, "restarted")):
            record = service.attempt_recovery("quant-freqtrade")

        self.assertEqual(record.status, RecoveryStatus.SUCCESS)
        self.assertEqual(record.action, RecoveryAction.RESTART_CONTAINER)
        self.assertEqual(record.service_name, "quant-freqtrade")
        self.assertEqual(len(service._recovery_history), 1)

    def test_attempt_recovery_failed_records_error(self) -> None:
        """docker restart 失败时记录 FAILED 并累计尝试次数。"""
        service = AutoRecoveryService(RecoveryConfig())
        with mock.patch.object(service, "_run_docker_command", return_value=(False, "docker error")):
            record = service.attempt_recovery("quant-freqtrade")

        self.assertEqual(record.status, RecoveryStatus.FAILED)
        self.assertIn("docker error", record.error or "")
        self.assertEqual(service._recovery_attempts["quant-freqtrade"], 1)

    def test_attempt_recovery_cooldown_skips(self) -> None:
        """冷却期内重复尝试返回 COOLING 不重启。"""
        service = AutoRecoveryService(RecoveryConfig())
        with mock.patch.object(service, "_run_docker_command", return_value=(True, "restarted")):
            service.attempt_recovery("quant-freqtrade")
        with mock.patch.object(service, "_run_docker_command") as mock_docker:
            record = service.attempt_recovery("quant-freqtrade")

        self.assertEqual(record.status, RecoveryStatus.COOLING)
        mock_docker.assert_not_called()

    def test_attempt_recovery_max_attempts_skips(self) -> None:
        """达到最大尝试次数后返回 SKIPPED 不重启。"""
        service = AutoRecoveryService(RecoveryConfig())
        with mock.patch.object(service, "_run_docker_command", return_value=(False, "docker error")):
            for _ in range(service._config.max_recovery_attempts):
                service.attempt_recovery("quant-freqtrade")
        with mock.patch.object(service, "_run_docker_command") as mock_docker:
            record = service.attempt_recovery("quant-freqtrade")

        self.assertEqual(record.status, RecoveryStatus.SKIPPED)
        mock_docker.assert_not_called()

    def test_attempt_recovery_unknown_service_skipped(self) -> None:
        """不在允许列表的服务返回 SKIPPED。"""
        service = AutoRecoveryService(RecoveryConfig())
        record = service.attempt_recovery("not-a-service")
        self.assertEqual(record.status, RecoveryStatus.SKIPPED)

    def test_check_service_health_unhealthy(self) -> None:
        """容器 unhealthy 时检测为不健康（触发恢复的依据）。"""
        service = AutoRecoveryService(RecoveryConfig())
        with mock.patch.object(
            service,
            "_run_docker_command",
            side_effect=[
                (True, "running|abc123"),
                (True, "unhealthy"),
            ],
        ):
            health = service.check_service_health("quant-freqtrade")

        self.assertFalse(health["healthy"])
        self.assertEqual(health["health"], "unhealthy")


if __name__ == "__main__":
    unittest.main()

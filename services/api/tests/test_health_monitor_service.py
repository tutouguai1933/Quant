"""Tests for health_monitor_service."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from services.api.app.services.health_monitor_service import (
    HealthMonitorService,
    MonitorConfig,
    ContainerInfo,
    ContainerStatus,
    HealthStatus,
    health_monitor_service,
)


class TestMonitorConfig:
    """Test MonitorConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = MonitorConfig()
        assert config.enabled is True
        assert config.interval_seconds == 60
        assert config.alert_on_unhealthy is True
        assert config.alert_on_exit is True
        assert "quant-api" in config.monitored_containers
        assert "quant-web" in config.monitored_containers
        assert "quant-freqtrade" in config.monitored_containers
        assert "quant-mihomo" in config.monitored_containers
        assert "quant-openclaw" in config.monitored_containers

    def test_custom_config(self):
        """Test custom configuration values."""
        config = MonitorConfig(
            enabled=False,
            interval_seconds=30,
            alert_on_unhealthy=False,
            monitored_containers=["custom-container"],
        )
        assert config.enabled is False
        assert config.interval_seconds == 30
        assert config.alert_on_unhealthy is False
        assert config.monitored_containers == ["custom-container"]


class TestContainerStatus:
    """Test ContainerStatus enum."""

    def test_status_values(self):
        """Test container status enum values."""
        assert ContainerStatus.RUNNING.value == "running"
        assert ContainerStatus.EXITED.value == "exited"
        assert ContainerStatus.PAUSED.value == "paused"
        assert ContainerStatus.RESTARTING.value == "restarting"
        assert ContainerStatus.DEAD.value == "dead"
        assert ContainerStatus.UNKNOWN.value == "unknown"


class TestHealthStatus:
    """Test HealthStatus enum."""

    def test_health_values(self):
        """Test health status enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.STARTING.value == "starting"
        assert HealthStatus.NONE.value == "none"


class TestHealthMonitorService:
    """Test HealthMonitorService."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        service = HealthMonitorService()
        assert service.config.enabled is True
        assert service.is_monitoring is False

    def test_init_custom_config(self):
        """Test initialization with custom config."""
        config = MonitorConfig(interval_seconds=120)
        service = HealthMonitorService(config=config)
        assert service.config.interval_seconds == 120

    @patch("subprocess.run")
    def test_check_container_health_running_healthy(self, mock_run):
        """Test checking a running and healthy container."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "running|healthy|abc123def456|quant-api:latest"
        mock_run.return_value = mock_result

        service = HealthMonitorService()
        info = service.check_container_health("quant-api")

        assert info.name == "quant-api"
        assert info.status == ContainerStatus.RUNNING
        assert info.health == HealthStatus.HEALTHY
        assert info.container_id == "abc123def456"
        assert info.image == "quant-api:latest"
        assert info.error == ""

    @patch("subprocess.run")
    def test_check_container_health_running_no_health_check(self, mock_run):
        """Test checking a running container with no health check."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "running||abc123def456|quant-api:latest"
        mock_run.return_value = mock_result

        service = HealthMonitorService()
        info = service.check_container_health("quant-api")

        assert info.name == "quant-api"
        assert info.status == ContainerStatus.RUNNING
        assert info.health == HealthStatus.NONE
        assert info.error == ""

    @patch("subprocess.run")
    def test_check_container_health_unhealthy(self, mock_run):
        """Test checking an unhealthy container."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "running|unhealthy|abc123def456|quant-api:latest"
        mock_run.return_value = mock_result

        service = HealthMonitorService()
        info = service.check_container_health("quant-api")

        assert info.name == "quant-api"
        assert info.status == ContainerStatus.RUNNING
        assert info.health == HealthStatus.UNHEALTHY

    @patch("subprocess.run")
    def test_check_container_health_exited(self, mock_run):
        """Test checking an exited container."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "exited||abc123def456|quant-api:latest"
        mock_run.return_value = mock_result

        service = HealthMonitorService()
        info = service.check_container_health("quant-api")

        assert info.name == "quant-api"
        assert info.status == ContainerStatus.EXITED
        assert info.health == HealthStatus.NONE

    @patch("subprocess.run")
    def test_check_container_health_not_found(self, mock_run):
        """Test checking a non-existent container."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: No such container: unknown-container"
        mock_run.return_value = mock_result

        service = HealthMonitorService()
        info = service.check_container_health("unknown-container")

        assert info.name == "unknown-container"
        assert info.status == ContainerStatus.UNKNOWN
        assert info.health == HealthStatus.NONE
        assert "No such container" in info.error

    @patch("subprocess.run")
    def test_check_all_services(self, mock_run):
        """Test checking all services."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "running|healthy|abc123|image:latest"
        mock_run.return_value = mock_result

        service = HealthMonitorService()
        result = service.check_all_services()

        assert "checked_at" in result
        assert "all_healthy" in result
        assert "containers" in result
        assert "summary" in result
        assert result["summary"]["total"] == 5
        assert result["summary"]["running"] == 5
        assert result["summary"]["unhealthy"] == 0

    def test_get_cached_status_empty(self):
        """Test getting cached status when empty."""
        service = HealthMonitorService()
        result = service.get_cached_status()

        assert "checked_at" in result
        assert result["containers"] == {}
        assert result["summary"]["total"] == 5
        assert result["monitoring_active"] is False

    def test_start_monitoring_no_event_loop(self):
        """Test start monitoring without running event loop."""
        service = HealthMonitorService()
        result = service.start_monitoring()

        # Should fail since no event loop is running in test
        assert result is False
        assert service.is_monitoring is False

    def test_stop_monitoring(self):
        """Test stopping monitoring."""
        service = HealthMonitorService()
        service._running = True
        service.stop_monitoring()

        assert service.is_monitoring is False


class TestGlobalInstance:
    """Test global health_monitor_service instance."""

    def test_global_instance_exists(self):
        """Test that global instance exists."""
        assert health_monitor_service is not None
        assert isinstance(health_monitor_service, HealthMonitorService)

    def test_global_instance_config(self):
        """Test global instance configuration."""
        assert health_monitor_service.config.enabled is True
        assert len(health_monitor_service.config.monitored_containers) == 5
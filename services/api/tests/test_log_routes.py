"""Tests for log management endpoints."""

from __future__ import annotations

import pytest

from fastapi.testclient import TestClient

from services.api.app.main import app


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


class TestLogRoutes:
    """Tests for log management API routes."""

    def test_logs_status_returns_success(self, client: TestClient) -> None:
        """日志状态端点返回成功响应。"""
        response = client.get("/api/v1/logs/status")
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is None
        assert "data" in data
        assert "total_size_mb" in data["data"]
        assert "directories" in data["data"]

    def test_logs_check_returns_success(self, client: TestClient) -> None:
        """日志检查端点返回成功响应。"""
        response = client.get("/api/v1/logs/check")
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is None
        assert "data" in data
        assert "current_total_mb" in data["data"]
        assert "threshold_mb" in data["data"]
        assert "needs_cleanup" in data["data"]
        assert "recommendation" in data["data"]

    def test_logs_check_with_custom_threshold(self, client: TestClient) -> None:
        """日志检查端点支持自定义阈值。"""
        response = client.get("/api/v1/logs/check?max_size_mb=10.0")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["threshold_mb"] == 10.0

    def test_logs_config_returns_success(self, client: TestClient) -> None:
        """日志配置端点返回成功响应。"""
        response = client.get("/api/v1/logs/config")
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is None
        assert "data" in data
        assert "max_bytes_mb" in data["data"]
        assert "backup_count" in data["data"]
        # 验证配置值
        assert data["data"]["max_bytes_mb"] == 10.0
        assert data["data"]["backup_count"] == 5

    def test_logs_cleanup_with_valid_days(self, client: TestClient) -> None:
        """日志清理端点接受有效天数参数。"""
        response = client.post("/api/v1/logs/cleanup?days_to_keep=30")
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is None
        assert "data" in data
        assert "status" in data["data"]
        assert data["data"]["days_to_keep"] == 30

    def test_logs_cleanup_rejects_invalid_days_too_small(self, client: TestClient) -> None:
        """日志清理端点拒绝小于1的天数。"""
        response = client.post("/api/v1/logs/cleanup?days_to_keep=0")
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is not None
        assert "INVALID_DAYS" in data["error"]["code"]

    def test_logs_cleanup_rejects_invalid_days_too_large(self, client: TestClient) -> None:
        """日志清理端点拒绝大于365的天数。"""
        response = client.post("/api/v1/logs/cleanup?days_to_keep=400")
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is not None
        assert "INVALID_DAYS" in data["error"]["code"]
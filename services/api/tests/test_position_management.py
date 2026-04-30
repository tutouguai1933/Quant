"""Tests for position_management_service."""

from __future__ import annotations

import json
import pytest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch, MagicMock

from services.api.app.services.position_management_service import (
    PositionManagementService,
    PositionConfig,
    PositionSuggestion,
    DrawdownState,
    PositionSummary,
    PositionStatus,
    RiskLevel,
    position_management_service,
    _parse_decimal,
)


class TestPositionConfig:
    """Test PositionConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PositionConfig()
        assert config.max_drawdown_pct == Decimal("15")
        assert config.position_risk_pct == Decimal("2")
        assert config.max_position_count == 4
        assert config.base_capital == Decimal("10000")
        assert config.kelly_enabled is False
        assert config.kelly_fraction == Decimal("0.5")
        assert config.trading_paused_on_drawdown is True
        assert config.drawdown_alert_threshold == Decimal("10")

    def test_custom_config(self):
        """Test custom configuration values."""
        config = PositionConfig(
            max_drawdown_pct=Decimal("20"),
            position_risk_pct=Decimal("3"),
            max_position_count=5,
            base_capital=Decimal("50000"),
            kelly_enabled=True,
        )
        assert config.max_drawdown_pct == Decimal("20")
        assert config.position_risk_pct == Decimal("3")
        assert config.max_position_count == 5
        assert config.base_capital == Decimal("50000")
        assert config.kelly_enabled is True

    def test_from_json_file_exists(self, tmp_path):
        """Test loading config from JSON file."""
        config_file = tmp_path / "position_config.json"
        config_data = {
            "max_drawdown_pct": 18,
            "position_risk_pct": 2.5,
            "max_position_count": 3,
            "base_capital": 20000,
            "kelly_enabled": True,
            "kelly_fraction": 0.25,
            "risk_levels": {
                "low": {"multiplier": 0.8, "max_positions": 3},
                "medium": {"multiplier": 0.5, "max_positions": 2},
            },
        }
        config_file.write_text(json.dumps(config_data))

        config = PositionConfig.from_json(config_file)
        assert config.max_drawdown_pct == Decimal("18")
        assert config.position_risk_pct == Decimal("2.5")
        assert config.max_position_count == 3
        assert config.base_capital == Decimal("20000")
        assert config.kelly_enabled is True
        assert config.kelly_fraction == Decimal("0.25")
        assert "low" in config.risk_levels
        assert "medium" in config.risk_levels

    def test_from_json_file_not_found(self):
        """Test loading config when file not found."""
        config = PositionConfig.from_json("/nonexistent/path/config.json")
        # Should return defaults
        assert config.max_drawdown_pct == Decimal("15")
        assert config.position_risk_pct == Decimal("2")

    def test_from_json_invalid_json(self, tmp_path):
        """Test loading config with invalid JSON."""
        config_file = tmp_path / "invalid_config.json"
        config_file.write_text("not valid json {{{")

        config = PositionConfig.from_json(config_file)
        # Should return defaults
        assert config.max_drawdown_pct == Decimal("15")


class TestParseDecimal:
    """Test _parse_decimal helper."""

    def test_parse_valid_decimal(self):
        """Test parsing valid decimal."""
        result = _parse_decimal("123.45", "test")
        assert result == Decimal("123.45")

    def test_parse_none_returns_default(self):
        """Test parsing None returns default."""
        result = _parse_decimal(None, Decimal("10"))
        assert result == Decimal("10")

    def test_parse_default(self):
        """Test parsing with default."""
        result = _parse_decimal("invalid", Decimal("10"))
        assert result == Decimal("10")

    def test_parse_int(self):
        """Test parsing integer."""
        result = _parse_decimal(42, Decimal("0"))
        assert result == Decimal("42")


class TestPositionSuggestion:
    """Test PositionSuggestion dataclass."""

    def test_to_dict(self):
        """Test to_dict serialization."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        suggestion = PositionSuggestion(
            symbol="BTCUSDT",
            suggested_size=Decimal("0.1"),
            risk_amount=Decimal("200"),
            position_pct=Decimal("2"),
            method="fixed_ratio",
            reason="Test reason",
            stop_loss_price=Decimal("95000"),
            entry_price=Decimal("100000"),
            calculated_at=now,
        )

        result = suggestion.to_dict()
        assert result["symbol"] == "BTCUSDT"
        assert result["method"] == "fixed_ratio"
        assert result["reason"] == "Test reason"
        assert "suggested_size" in result
        assert "risk_amount" in result
        assert "position_pct" in result


class TestDrawdownState:
    """Test DrawdownState dataclass."""

    def test_to_dict(self):
        """Test to_dict serialization."""
        state = DrawdownState(
            current_drawdown_pct=Decimal("5.5"),
            peak_capital=Decimal("10000"),
            current_capital=Decimal("9450"),
            triggered=False,
            trading_paused=False,
        )

        result = state.to_dict()
        assert result["current_drawdown_pct"] == "5.50"
        assert result["peak_capital"] == "10000.00"
        assert result["current_capital"] == "9450.00"
        assert result["triggered"] is False
        assert result["trading_paused"] is False


class TestPositionSummary:
    """Test PositionSummary dataclass."""

    def test_to_dict(self):
        """Test to_dict serialization."""
        drawdown = DrawdownState(current_drawdown_pct=Decimal("0"))
        summary = PositionSummary(
            status=PositionStatus.NORMAL,
            current_positions=2,
            max_positions=4,
            available_slots=2,
            total_capital=Decimal("10000"),
            used_capital=Decimal("5000"),
            available_capital=Decimal("5000"),
            drawdown_state=drawdown,
            risk_level=RiskLevel.LOW,
            can_open_new=True,
            reason="Normal operation",
        )

        result = summary.to_dict()
        assert result["status"] == "normal"
        assert result["current_positions"] == 2
        assert result["max_positions"] == 4
        assert result["risk_level"] == "low"
        assert result["can_open_new"] is True


class TestPositionManagementService:
    """Test PositionManagementService."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        service = PositionManagementService()
        assert service._config.max_drawdown_pct == Decimal("15")
        assert service._drawdown_state.peak_capital == Decimal("10000")

    def test_init_custom_config(self):
        """Test initialization with custom config."""
        config = PositionConfig(
            max_drawdown_pct=Decimal("20"),
            base_capital=Decimal("50000"),
        )
        service = PositionManagementService(config=config)
        assert service._config.max_drawdown_pct == Decimal("20")
        assert service._drawdown_state.peak_capital == Decimal("50000")

    def test_get_position_status_normal(self):
        """Test get_position_status in normal state."""
        service = PositionManagementService()
        status = service.get_position_status()

        assert status.status == PositionStatus.NORMAL
        assert status.current_positions == 0
        assert status.can_open_new is True
        assert status.risk_level == RiskLevel.LOW

    def test_get_position_status_with_positions(self):
        """Test get_position_status with existing positions."""
        config = PositionConfig(base_capital=Decimal("20000"))
        service = PositionManagementService(config=config)
        service.add_position("BTCUSDT", Decimal("0.05"), Decimal("50000"))
        service.add_position("ETHUSDT", Decimal("1"), Decimal("3000"))

        status = service.get_position_status()
        assert status.current_positions == 2
        assert status.available_slots == 2

    def test_calculate_position_fixed_ratio_no_prices(self):
        """Test calculate_position with fixed ratio, no prices."""
        service = PositionManagementService()
        suggestion = service.calculate_position("BTCUSDT")

        assert suggestion.symbol == "BTCUSDT"
        assert suggestion.method == "fixed_ratio"
        assert suggestion.suggested_size == Decimal("0")

    def test_calculate_position_fixed_ratio_with_prices(self):
        """Test calculate_position with entry and stop loss prices."""
        service = PositionManagementService()
        suggestion = service.calculate_position(
            symbol="BTCUSDT",
            entry_price=Decimal("100000"),
            stop_loss_price=Decimal("95000"),
            method="fixed_ratio",
        )

        # Risk amount = 10000 * 2% = 200
        # Risk per unit = 100000 - 95000 = 5000
        # Position size = 200 / 5000 = 0.04 BTC
        assert suggestion.symbol == "BTCUSDT"
        assert suggestion.suggested_size == Decimal("0.04")
        assert suggestion.risk_amount == Decimal("200")

    def test_calculate_position_kelly_disabled(self):
        """Test calculate_position with Kelly method disabled."""
        config = PositionConfig(kelly_enabled=False)
        service = PositionManagementService(config=config)

        suggestion = service.calculate_position(
            symbol="BTCUSDT",
            entry_price=Decimal("100000"),
            method="kelly",
        )

        # Should fallback to fixed_ratio
        assert suggestion.method == "fixed_ratio"

    def test_calculate_position_kelly_enabled(self):
        """Test calculate_position with Kelly method enabled."""
        config = PositionConfig(kelly_enabled=True, kelly_fraction=Decimal("0.5"))
        service = PositionManagementService(config=config)

        # Add some trade history
        service.record_trade_result("BTCUSDT", Decimal("100"))
        service.record_trade_result("BTCUSDT", Decimal("-50"))
        service.record_trade_result("ETHUSDT", Decimal("80"))

        suggestion = service.calculate_position(
            symbol="BTCUSDT",
            entry_price=Decimal("100000"),
            method="kelly",
        )

        assert suggestion.symbol == "BTCUSDT"
        # Kelly should produce some result
        assert suggestion.position_pct > Decimal("0")

    def test_get_drawdown_status_no_drawdown(self):
        """Test get_drawdown_status with no drawdown."""
        service = PositionManagementService()
        state = service.get_drawdown_status()

        assert state.current_drawdown_pct == Decimal("0")
        assert state.triggered is False
        assert state.trading_paused is False

    def test_get_drawdown_status_with_drawdown(self):
        """Test get_drawdown_status with drawdown."""
        service = PositionManagementService()
        service.update_capital(Decimal("9000"))  # 10% drawdown

        state = service.get_drawdown_status()
        assert state.current_drawdown_pct == Decimal("10")
        assert state.triggered is False  # Not reached 15%

    def test_update_capital_increases_peak(self):
        """Test update_capital increases peak."""
        service = PositionManagementService()
        result = service.update_capital(Decimal("12000"))

        assert service._drawdown_state.peak_capital == Decimal("12000")
        assert service._drawdown_state.current_capital == Decimal("12000")

    def test_update_capital_decreases_triggers_drawdown(self):
        """Test update_capital triggers drawdown limit."""
        config = PositionConfig(
            max_drawdown_pct=Decimal("15"),
            trading_paused_on_drawdown=True,
        )
        service = PositionManagementService(config=config)
        service.update_capital(Decimal("8500"))  # 15% drawdown from 10000

        assert service._drawdown_state.triggered is True
        assert service._drawdown_state.trading_paused is True

        status = service.get_position_status()
        assert status.status == PositionStatus.TRADING_PAUSED
        assert status.can_open_new is False

    def test_record_trade_result_win(self):
        """Test record_trade_result with win."""
        service = PositionManagementService()
        result = service.record_trade_result("BTCUSDT", Decimal("100"))

        assert result["win_count"] == 1
        assert result["loss_count"] == 0
        assert service._drawdown_state.current_capital == Decimal("10100")

    def test_record_trade_result_loss(self):
        """Test record_trade_result with loss."""
        service = PositionManagementService()
        result = service.record_trade_result("BTCUSDT", Decimal("-50"))

        assert result["win_count"] == 0
        assert result["loss_count"] == 1
        assert service._drawdown_state.current_capital == Decimal("9950")

    def test_add_position_success(self):
        """Test add_position success."""
        service = PositionManagementService()
        result = service.add_position(
            symbol="BTCUSDT",
            size=Decimal("0.1"),
            entry_price=Decimal("100000"),
        )

        assert result["success"] is True
        assert "BTCUSDT" in service._current_positions

    def test_add_position_max_count_reached(self):
        """Test add_position when max count reached."""
        config = PositionConfig(max_position_count=2, base_capital=Decimal("20000"))
        service = PositionManagementService(config=config)
        result1 = service.add_position("BTCUSDT", Decimal("0.05"), Decimal("50000"))
        assert result1["success"] is True
        result2 = service.add_position("ETHUSDT", Decimal("1"), Decimal("3000"))
        assert result2["success"] is True

        result3 = service.add_position("SOLUSDT", Decimal("10"), Decimal("100"))
        assert result3["success"] is False
        assert "Maximum" in result3["reason"] or "Insufficient" in result3["reason"]

    def test_add_position_drawdown_triggered(self):
        """Test add_position when drawdown triggered."""
        config = PositionConfig(
            max_drawdown_pct=Decimal("10"),
            trading_paused_on_drawdown=True,
        )
        service = PositionManagementService(config=config)
        service.update_capital(Decimal("9000"))  # 10% drawdown

        result = service.add_position("BTCUSDT", Decimal("0.1"), Decimal("100000"))
        assert result["success"] is False
        assert result["reason"] == "Drawdown limit triggered (10.00%), trading paused"

    def test_remove_position_success(self):
        """Test remove_position success."""
        service = PositionManagementService()
        service.add_position("BTCUSDT", Decimal("0.1"), Decimal("100000"))

        result = service.remove_position("BTCUSDT")
        assert result["success"] is True
        assert "BTCUSDT" not in service._current_positions

    def test_remove_position_not_found(self):
        """Test remove_position when not found."""
        service = PositionManagementService()
        result = service.remove_position("BTCUSDT")

        assert result["success"] is False
        assert "not found" in result["reason"]

    def test_reset_drawdown_trigger(self):
        """Test reset_drawdown_trigger."""
        config = PositionConfig(max_drawdown_pct=Decimal("10"))
        service = PositionManagementService(config=config)
        service.update_capital(Decimal("9000"))  # Trigger drawdown

        assert service._drawdown_state.triggered is True

        result = service.reset_drawdown_trigger()
        assert result["success"] is True
        assert service._drawdown_state.triggered is False
        assert service._drawdown_state.trading_paused is False

    def test_reset_drawdown_trigger_not_triggered(self):
        """Test reset_drawdown_trigger when not triggered."""
        service = PositionManagementService()
        result = service.reset_drawdown_trigger()

        assert result["success"] is False
        assert "not triggered" in result["reason"]

    def test_set_risk_level(self):
        """Test set_risk_level."""
        service = PositionManagementService()
        result = service.set_risk_level(RiskLevel.HIGH)

        assert result["success"] is True
        assert result["risk_level"] == "high"

    def test_get_trade_statistics(self):
        """Test get_trade_statistics."""
        service = PositionManagementService()
        service.record_trade_result("BTCUSDT", Decimal("100"))
        service.record_trade_result("ETHUSDT", Decimal("-50"))
        service.record_trade_result("SOLUSDT", Decimal("80"))

        stats = service.get_trade_statistics()
        assert stats["total_trades"] == 3
        assert stats["win_count"] == 2
        assert stats["loss_count"] == 1
        assert Decimal(stats["win_rate"]) > Decimal("0.5")

    def test_determine_risk_level_auto(self):
        """Test automatic risk level determination."""
        service = PositionManagementService()

        # Low drawdown -> LOW
        service.update_capital(Decimal("9800"))
        level = service._determine_risk_level()
        assert level == RiskLevel.LOW

        # Medium drawdown -> MEDIUM
        service.update_capital(Decimal("9500"))
        level = service._determine_risk_level()
        assert level == RiskLevel.MEDIUM

        # High drawdown -> HIGH
        service.update_capital(Decimal("8800"))
        level = service._determine_risk_level()
        assert level == RiskLevel.HIGH

    def test_calculate_used_capital(self):
        """Test _calculate_used_capital."""
        config = PositionConfig(base_capital=Decimal("20000"))
        service = PositionManagementService(config=config)
        result1 = service.add_position("BTCUSDT", Decimal("0.05"), Decimal("50000"))
        assert result1["success"] is True
        result2 = service.add_position("ETHUSDT", Decimal("2"), Decimal("3000"))
        assert result2["success"] is True

        used = service._calculate_used_capital()
        # 0.05 * 50000 + 2 * 3000 = 2500 + 6000 = 8500
        assert used == Decimal("8500")


class TestGlobalInstance:
    """Test global position_management_service instance."""

    def test_global_instance_exists(self):
        """Test that global instance exists."""
        assert position_management_service is not None
        assert isinstance(position_management_service, PositionManagementService)

    def test_global_instance_config(self):
        """Test global instance configuration."""
        assert position_management_service._config.max_drawdown_pct == Decimal("15")
        assert position_management_service._config.position_risk_pct == Decimal("2")


class TestRiskLevelEnum:
    """Test RiskLevel enum."""

    def test_risk_level_values(self):
        """Test risk level enum values."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"


class TestPositionStatusEnum:
    """Test PositionStatus enum."""

    def test_status_values(self):
        """Test position status enum values."""
        assert PositionStatus.NORMAL.value == "normal"
        assert PositionStatus.WARNING.value == "warning"
        assert PositionStatus.DRAWDOWN_LIMIT.value == "drawdown_limit"
        assert PositionStatus.TRADING_PAUSED.value == "trading_paused"
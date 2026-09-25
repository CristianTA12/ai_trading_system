"""Tests del Risk Manager."""

import pytest

from src.risk.risk_manager import RiskDecision, RiskManager


class TestRiskManager:
    """Tests para el Risk Manager."""

    def setup_method(self):
        """Setup para cada test."""
        self.rm = RiskManager()
        self.rm.update_state(
            daily_loss=0.0,
            drawdown=0.0,
            open_positions=0,
            leverage=0.0,
        )

    def test_approved_trade(self):
        """Trade con buena confianza y edge debe ser aprobado."""
        result = self.rm.evaluate(
            confidence=0.75,
            expected_return=0.005,
            estimated_costs=0.001,
            requested_size=100,
            capital=10000,
        )
        assert result.approved is True
        assert result.decision == RiskDecision.APPROVED

    def test_rejected_low_confidence(self):
        """Trade con baja confianza debe ser rechazado."""
        result = self.rm.evaluate(
            confidence=0.40,
            expected_return=0.005,
            estimated_costs=0.001,
            requested_size=100,
            capital=10000,
        )
        assert result.approved is False
        assert result.decision == RiskDecision.REJECTED_LOW_CONFIDENCE

    def test_rejected_no_edge(self):
        """Trade sin edge después de costes debe ser rechazado."""
        result = self.rm.evaluate(
            confidence=0.80,
            expected_return=0.001,
            estimated_costs=0.002,  # Costes > retorno
            requested_size=100,
            capital=10000,
        )
        assert result.approved is False
        assert result.decision == RiskDecision.REJECTED_NO_EDGE

    def test_rejected_daily_loss(self):
        """Trade cuando daily loss excede el máximo debe ser rechazado."""
        self.rm.update_state(
            daily_loss=0.03,  # 3% > max 2%
            drawdown=0.0,
            open_positions=0,
            leverage=0.0,
        )
        result = self.rm.evaluate(
            confidence=0.80,
            expected_return=0.005,
            estimated_costs=0.001,
            requested_size=100,
            capital=10000,
        )
        assert result.approved is False
        assert result.decision == RiskDecision.REJECTED_DAILY_LOSS

    def test_rejected_max_drawdown_triggers_kill_switch(self):
        """Drawdown excesivo debe activar kill switch."""
        self.rm.update_state(
            daily_loss=0.0,
            drawdown=0.15,  # 15% > max 10%
            open_positions=0,
            leverage=0.0,
        )
        result = self.rm.evaluate(
            confidence=0.80,
            expected_return=0.005,
            estimated_costs=0.001,
            requested_size=100,
            capital=10000,
        )
        assert result.approved is False
        assert result.decision == RiskDecision.REJECTED_MAX_DRAWDOWN
        assert self.rm._kill_switch is True

    def test_kill_switch_blocks_all(self):
        """Kill switch debe bloquear todas las operaciones."""
        self.rm.activate_kill_switch(reason="test")
        result = self.rm.evaluate(
            confidence=0.99,
            expected_return=0.01,
            estimated_costs=0.0001,
            requested_size=100,
            capital=10000,
        )
        assert result.approved is False
        assert result.decision == RiskDecision.REJECTED_KILL_SWITCH

    def test_rejected_max_positions(self):
        """Exceder posiciones abiertas debe ser rechazado."""
        self.rm.update_state(
            daily_loss=0.0,
            drawdown=0.0,
            open_positions=3,  # max = 3
            leverage=0.0,
        )
        result = self.rm.evaluate(
            confidence=0.80,
            expected_return=0.005,
            estimated_costs=0.001,
            requested_size=100,
            capital=10000,
        )
        assert result.approved is False
        assert result.decision == RiskDecision.REJECTED_MAX_POSITIONS

    def test_position_size_adjusted(self):
        """El tamaño de posición debe ajustarse al máximo permitido."""
        result = self.rm.evaluate(
            confidence=0.80,
            expected_return=0.005,
            estimated_costs=0.001,
            requested_size=5000,  # 50% del capital, max es 20%
            capital=10000,
        )
        assert result.approved is True
        assert result.adjusted_size is not None
        assert result.adjusted_size <= 10000 * 0.20  # max_position_size

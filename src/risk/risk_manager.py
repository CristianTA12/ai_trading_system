"""Risk Manager — Capa de seguridad independiente de los modelos.

El Risk Manager NO puede ser modificado por los modelos.
Opera de forma independiente para proteger el capital.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.config.settings import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RiskDecision(str, Enum):
    """Decisión del risk manager."""

    APPROVED = "approved"
    REJECTED_LOW_CONFIDENCE = "rejected_low_confidence"
    REJECTED_NO_EDGE = "rejected_no_edge"
    REJECTED_DAILY_LOSS = "rejected_daily_loss"
    REJECTED_MAX_DRAWDOWN = "rejected_max_drawdown"
    REJECTED_MAX_POSITIONS = "rejected_max_positions"
    REJECTED_MAX_LEVERAGE = "rejected_max_leverage"
    REJECTED_KILL_SWITCH = "rejected_kill_switch"


@dataclass
class RiskCheckResult:
    """Resultado de la evaluación del risk manager."""

    decision: RiskDecision
    approved: bool
    reason: str
    adjusted_size: float | None = None  # Tamaño ajustado si se reduce
    checks: dict | None = None  # Detalle de cada check


class RiskManager:
    """Risk Manager independiente.

    Evalúa si una operación debe ejecutarse basándose en:
    - Confianza del modelo
    - Edge esperado después de costes
    - Pérdida diaria acumulada
    - Drawdown actual
    - Número de posiciones abiertas
    - Apalancamiento
    - Kill switch manual

    PRINCIPIO: El Risk Manager no puede ser modificado por los modelos.
    """

    def __init__(self) -> None:
        self._kill_switch = False
        self._daily_loss = 0.0
        self._current_drawdown = 0.0
        self._open_positions = 0
        self._current_leverage = 0.0

        # Cargar parámetros de configuración
        self.max_risk_per_trade = settings.risk.max_risk_per_trade
        self.max_position_size = settings.risk.max_position_size
        self.max_daily_loss = settings.risk.max_daily_loss
        self.max_drawdown = settings.risk.max_drawdown
        self.max_leverage = settings.risk.max_leverage
        self.max_open_positions = settings.risk.max_open_positions
        self.min_confidence = settings.risk.min_confidence

        logger.info(
            "risk_manager_initialized",
            max_daily_loss=self.max_daily_loss,
            max_drawdown=self.max_drawdown,
            min_confidence=self.min_confidence,
        )

    def activate_kill_switch(self, reason: str = "manual") -> None:
        """Activar kill switch — para TODAS las operaciones."""
        self._kill_switch = True
        logger.critical("kill_switch_activated", reason=reason)

    def deactivate_kill_switch(self) -> None:
        """Desactivar kill switch (requiere intervención manual)."""
        self._kill_switch = False
        logger.warning("kill_switch_deactivated")

    def update_state(
        self,
        daily_loss: float,
        drawdown: float,
        open_positions: int,
        leverage: float,
    ) -> None:
        """Actualizar estado del risk manager con datos actuales."""
        self._daily_loss = daily_loss
        self._current_drawdown = drawdown
        self._open_positions = open_positions
        self._current_leverage = leverage

    def evaluate(
        self,
        confidence: float,
        expected_return: float,
        estimated_costs: float,
        requested_size: float,
        capital: float,
    ) -> RiskCheckResult:
        """Evaluar si una operación debe ejecutarse.

        Args:
            confidence: Confianza del modelo (0-1).
            expected_return: Retorno esperado (ej: 0.003 = 0.3%).
            estimated_costs: Costes estimados (fees + spread + slippage).
            requested_size: Tamaño de posición solicitado (en USD).
            capital: Capital total actual.

        Returns:
            RiskCheckResult con la decisión y detalles.
        """
        checks = {}

        # 1. Kill switch
        if self._kill_switch:
            return RiskCheckResult(
                decision=RiskDecision.REJECTED_KILL_SWITCH,
                approved=False,
                reason="Kill switch activado",
                checks={"kill_switch": True},
            )

        # 2. Confianza mínima
        checks["confidence"] = {
            "value": confidence,
            "threshold": self.min_confidence,
            "passed": confidence >= self.min_confidence,
        }
        if confidence < self.min_confidence:
            logger.info("risk_rejected_low_confidence", confidence=confidence)
            return RiskCheckResult(
                decision=RiskDecision.REJECTED_LOW_CONFIDENCE,
                approved=False,
                reason=f"Confianza {confidence:.2f} < mínimo {self.min_confidence}",
                checks=checks,
            )

        # 3. Edge después de costes
        edge = expected_return - estimated_costs
        checks["edge"] = {
            "expected_return": expected_return,
            "costs": estimated_costs,
            "edge": edge,
            "passed": edge > 0,
        }
        if edge <= 0:
            logger.info("risk_rejected_no_edge", edge=edge)
            return RiskCheckResult(
                decision=RiskDecision.REJECTED_NO_EDGE,
                approved=False,
                reason=f"Sin edge: retorno {expected_return:.4f} - costes {estimated_costs:.4f} = {edge:.4f}",
                checks=checks,
            )

        # 4. Pérdida diaria
        checks["daily_loss"] = {
            "current": self._daily_loss,
            "max": self.max_daily_loss,
            "passed": self._daily_loss < self.max_daily_loss,
        }
        if self._daily_loss >= self.max_daily_loss:
            logger.warning("risk_rejected_daily_loss", daily_loss=self._daily_loss)
            return RiskCheckResult(
                decision=RiskDecision.REJECTED_DAILY_LOSS,
                approved=False,
                reason=f"Pérdida diaria {self._daily_loss:.2%} >= máximo {self.max_daily_loss:.2%}",
                checks=checks,
            )

        # 5. Drawdown
        checks["drawdown"] = {
            "current": self._current_drawdown,
            "max": self.max_drawdown,
            "passed": self._current_drawdown < self.max_drawdown,
        }
        if self._current_drawdown >= self.max_drawdown:
            logger.critical("risk_rejected_max_drawdown", drawdown=self._current_drawdown)
            self.activate_kill_switch(reason="max_drawdown_reached")
            return RiskCheckResult(
                decision=RiskDecision.REJECTED_MAX_DRAWDOWN,
                approved=False,
                reason=f"Drawdown {self._current_drawdown:.2%} >= máximo {self.max_drawdown:.2%}. Kill switch activado.",
                checks=checks,
            )

        # 6. Posiciones abiertas
        checks["positions"] = {
            "current": self._open_positions,
            "max": self.max_open_positions,
            "passed": self._open_positions < self.max_open_positions,
        }
        if self._open_positions >= self.max_open_positions:
            return RiskCheckResult(
                decision=RiskDecision.REJECTED_MAX_POSITIONS,
                approved=False,
                reason=f"Posiciones abiertas {self._open_positions} >= máximo {self.max_open_positions}",
                checks=checks,
            )

        # 7. Ajustar tamaño si excede límites
        max_size = capital * self.max_position_size
        adjusted_size = min(requested_size, max_size)

        max_risk_size = capital * self.max_risk_per_trade
        adjusted_size = min(adjusted_size, max_risk_size / abs(expected_return) if expected_return != 0 else adjusted_size)

        checks["size"] = {
            "requested": requested_size,
            "adjusted": adjusted_size,
            "max_position": max_size,
        }

        # Aprobado
        logger.info(
            "risk_approved",
            confidence=confidence,
            edge=edge,
            size=adjusted_size,
        )
        return RiskCheckResult(
            decision=RiskDecision.APPROVED,
            approved=True,
            reason="Todos los checks pasados",
            adjusted_size=adjusted_size,
            checks=checks,
        )

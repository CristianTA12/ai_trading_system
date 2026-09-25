"""Logging estructurado para el sistema de trading.

Usa structlog para logs estructurados con contexto,
facilitando debugging y monitorización.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog


def setup_logging(log_level: str = "INFO", log_dir: Path | None = None) -> None:
    """Configurar logging estructurado para todo el sistema.

    Args:
        log_level: Nivel de log (DEBUG, INFO, WARNING, ERROR).
        log_dir: Directorio para archivos de log. Si es None, solo stdout.
    """
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.CallsiteParameterAdder(
            [
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
    ]

    # En desarrollo: output bonito en consola
    # En producción: JSON para procesamiento automático
    if sys.stderr.isatty():
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Obtener un logger con nombre para un módulo.

    Args:
        name: Nombre del módulo (típicamente __name__).

    Returns:
        Logger configurado con el nombre del módulo.
    """
    return structlog.get_logger(module=name)

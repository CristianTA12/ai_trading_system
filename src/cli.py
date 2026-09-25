"""CLI principal del sistema de trading."""

from __future__ import annotations

import json
from pathlib import Path

import click
import psycopg2

from src.data.downloaders.historical_downloader import (
    default_month,
    download_archive,
    load_month,
    validate_archive,
)
from src.utils.logging import setup_logging


@click.group()
@click.option("--log-level", default="INFO", help="Nivel de log (DEBUG, INFO, WARNING, ERROR)")
def main(log_level: str) -> None:
    """AI Trading System — CLI principal."""
    setup_logging(log_level=log_level)


@main.command()
def status() -> None:
    """Mostrar estado del sistema."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="AI Trading System — Status")
    table.add_column("Servicio", style="cyan")
    table.add_column("Estado", style="green")

    # TODO: Implementar checks reales de cada servicio
    services = [
        ("TimescaleDB", "⏳ Pending"),
        ("Redis", "⏳ Pending"),
        ("MLflow", "⏳ Pending"),
        ("Grafana", "⏳ Pending"),
        ("Ollama", "⏳ Pending"),
        ("WebSocket", "⏳ Pending"),
    ]

    for name, state in services:
        table.add_row(name, state)

    console.print(table)


@main.command()
@click.option(
    "--month", default=default_month, help="Mes completo YYYY-MM; por defecto, el anterior."
)
@click.option("--raw-dir", type=click.Path(path_type=Path, file_okay=False), default=None)
@click.option("--refresh", is_flag=True, help="Volver a descargar y verificar el archivo.")
def download_historical(month: str, raw_dir: Path | None, refresh: bool) -> None:
    """Descargar y validar BTC/USDT spot 1m (sin cargar la base de datos)."""
    try:
        path = download_archive(month, raw_dir, refresh)
        _, report = validate_archive(month, raw_dir)
        click.echo(f"Archivo: {path}")
        _show_report(report)
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc


def _show_report(report: dict) -> None:
    click.echo(json.dumps(report, indent=2))
    if not report["valid"]:
        raise click.ClickException("Datos rechazados; consulta el informe de calidad")


@main.command("validate-data")
@click.option("--month", default=default_month)
@click.option("--raw-dir", type=click.Path(path_type=Path, file_okay=False), default=None)
def validate_data(month: str, raw_dir: Path | None) -> None:
    """Validar checksum y calidad de un mes descargado; no accede a la red."""
    try:
        _, report = validate_archive(month, raw_dir)
        _show_report(report)
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc


@main.command("load-data")
@click.option("--month", default=default_month)
@click.option("--raw-dir", type=click.Path(path_type=Path, file_okay=False), default=None)
def load_data(month: str, raw_dir: Path | None) -> None:
    """Validar y cargar el mes local en TimescaleDB; repetible sin duplicados."""
    try:
        _show_report(load_month(month, raw_dir))
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    except psycopg2.Error as exc:
        raise click.ClickException("Error PostgreSQL: comprueba DATABASE_URL y make up") from exc


@main.command()
def paper_trade() -> None:
    """Iniciar paper trading."""
    click.echo("📄 Iniciando paper trading...")
    # TODO: Implementar en Fase 6
    click.echo("⚠️  No implementado todavía (Fase 6)")


@main.command("sync-history")
@click.option("--start", required=True, help="Primer mes YYYY-MM, incluido")
@click.option("--end", default=default_month, help="Último mes YYYY-MM, incluido")
@click.option("--raw-dir", type=click.Path(path_type=Path, file_okay=False), default=None)
@click.option("--allow-gaps", is_flag=True, help="Conservar huecos de origen, sin inventar velas")
@click.option(
    "--quarantine-duration-errors",
    is_flag=True,
    help="Excluir y registrar velas con duración incorrecta",
)
def sync_history_command(
    start: str, end: str, raw_dir: Path | None, allow_gaps: bool, quarantine_duration_errors: bool
) -> None:
    """Descargar, validar y cargar un rango de meses; repetir reanuda sin duplicados."""
    from src.data.downloaders.history import sync_history

    try:
        report = sync_history(
            start, end, raw_dir, allow_gaps, quarantine_duration_errors=quarantine_duration_errors
        )
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    if not report["complete"]:
        raise click.ClickException("Hay meses fallidos: consulta data/reports/history-*.json")
    click.echo(f"Histórico cargado: {len(report['months'])} meses")


@main.command()
def live_trade() -> None:
    """Iniciar trading real (¡CUIDADO!)."""
    if not click.confirm("⚠️  Esto usa dinero REAL. ¿Estás seguro?"):
        click.echo("Cancelado.")
        return
    click.echo("💰 Iniciando trading real...")
    # TODO: Implementar en Fase 15
    click.echo("⚠️  No implementado todavía (Fase 15)")


@main.command("build-features")
@click.option("--start", required=True, help="Primer mes YYYY-MM")
@click.option("--end", default=default_month)
@click.option("--output", type=click.Path(path_type=Path, file_okay=False), default=None)
@click.option("--train-end", default="2024-01-01", help="Fin exclusivo de entrenamiento, UTC")
@click.option("--validation-end", default="2025-01-01", help="Fin exclusivo de validación, UTC")
def build_features_command(
    start: str, end: str, output: Path | None, train_end: str, validation_end: str
) -> None:
    """Exportar velas 15m, variables causales, objetivos y particiones temporales."""
    from src.features.dataset import export_dataset

    try:
        report = export_dataset(start, end, output, train_end, validation_end)
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    except psycopg2.Error as exc:
        raise click.ClickException("Error PostgreSQL: comprueba DATABASE_URL y make up") from exc
    click.echo(json.dumps(report, indent=2))


@main.command()
def backtest() -> None:
    """Ejecutar backtest."""
    click.echo("📊 Ejecutando backtest...")
    # TODO: Implementar en Fase 3
    click.echo("⚠️  No implementado todavía (Fase 3)")


if __name__ == "__main__":
    main()

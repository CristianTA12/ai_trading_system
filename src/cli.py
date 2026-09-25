"""CLI principal del sistema de trading."""

from __future__ import annotations

import click

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
def download_historical() -> None:
    """Descargar datos históricos de Binance."""
    click.echo("📥 Descargando datos históricos...")
    # TODO: Implementar en Fase 1
    click.echo("⚠️  No implementado todavía (Fase 1)")


@main.command()
def paper_trade() -> None:
    """Iniciar paper trading."""
    click.echo("📄 Iniciando paper trading...")
    # TODO: Implementar en Fase 6
    click.echo("⚠️  No implementado todavía (Fase 6)")


@main.command()
def live_trade() -> None:
    """Iniciar trading real (¡CUIDADO!)."""
    if not click.confirm("⚠️  Esto usa dinero REAL. ¿Estás seguro?"):
        click.echo("Cancelado.")
        return
    click.echo("💰 Iniciando trading real...")
    # TODO: Implementar en Fase 15
    click.echo("⚠️  No implementado todavía (Fase 15)")


@main.command()
def backtest() -> None:
    """Ejecutar backtest."""
    click.echo("📊 Ejecutando backtest...")
    # TODO: Implementar en Fase 3
    click.echo("⚠️  No implementado todavía (Fase 3)")


if __name__ == "__main__":
    main()

"""Command-line entry point shared by benchmark and XGBoost experiments."""

from datetime import UTC, datetime
from pathlib import Path

import click
from dotenv import load_dotenv

from src.backtesting.engine import ExecutionConfig
from src.backtesting.experiment import run_experiment
from src.models.xgboost.classifier import ModelConfig

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)


def command(train_model: bool = False):
    @click.command()
    @click.option(
        "--dataset", type=click.Path(exists=True, file_okay=False, path_type=Path), required=True
    )
    @click.option("--output", type=click.Path(file_okay=False, path_type=Path))
    @click.option("--initial-capital", default=10000.0, show_default=True)
    @click.option("--position-fraction", default=1.0, show_default=True)
    @click.option("--maker-fee", default=0.0002, show_default=True)
    @click.option("--taker-fee", default=0.0004, show_default=True)
    @click.option("--slippage", default=0.0001, show_default=True)
    @click.option("--liquidity", type=click.Choice(["taker", "maker"]), default="taker")
    @click.option("--random-seeds", default=30, type=click.IntRange(min=2))
    @click.option("--threshold", default=0.0025, show_default=True)
    @click.option("--confidence", default=0.5, show_default=True)
    @click.option("--n-estimators", default=500, type=click.IntRange(min=1))
    @click.option("--tracking-uri", default="http://localhost:5000", envvar="MLFLOW_TRACKING_URI")
    @click.option("--experiment", default="spot-baseline-v1")
    @click.option("--no-mlflow", is_flag=True, help="Guardar solo resultados locales")
    def main(
        dataset,
        output,
        initial_capital,
        position_fraction,
        maker_fee,
        taker_fee,
        slippage,
        liquidity,
        random_seeds,
        threshold,
        confidence,
        n_estimators,
        tracking_uri,
        experiment,
        no_mlflow,
    ):
        output = output or ROOT / "data" / "experiments" / (
            ("xgboost-" if train_model else "benchmarks-")
            + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        )
        try:
            execution = ExecutionConfig(
                initial_capital, position_fraction, maker_fee, taker_fee, slippage, liquidity
            )
            model = (
                ModelConfig(threshold=threshold, confidence=confidence, n_estimators=n_estimators)
                if train_model
                else None
            )
            click.echo(f"Validación iniciada; resultados: {output}")
            report = run_experiment(
                dataset,
                output,
                execution,
                model,
                random_seeds,
                None if no_mlflow else tracking_uri,
                experiment,
            )
        except Exception as exc:
            raise click.ClickException(f"Experimento incompleto: {exc}. Consulta {output}") from exc
        for name, values in report["strategies"].items():
            click.echo(
                f"{name}: retorno={values['total_return']:.2%}, drawdown={values['max_drawdown']:.2%}, operaciones={values['trades']}"
            )
        if report.get("mlflow_run_id"):
            click.echo(f"MLflow run: {report['mlflow_run_id']}")
        click.echo("El conjunto test permanece reservado.")

    return main


main = command()

if __name__ == "__main__":
    main()

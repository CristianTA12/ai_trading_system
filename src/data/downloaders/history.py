"""Resumable monthly ingestion with a durable summary, without filling source gaps."""

import json
from pathlib import Path

import psycopg2

from src.config.settings import PROJECT_ROOT
from src.data.downloaders.historical_downloader import download_archive, load_month
from src.data.validators.data_quality_validator import month_bounds


def month_range(start: str, end: str) -> list[str]:
    first, _ = month_bounds(start)
    last, _ = month_bounds(end)
    if first > last:
        raise ValueError("El mes inicial debe ser anterior o igual al final")
    months = []
    while first <= last:
        months.append(first.strftime("%Y-%m"))
        _, first = month_bounds(months[-1])
    return months


def sync_history(
    start: str,
    end: str,
    raw_dir: Path | None = None,
    allow_gaps: bool = False,
    report_path: Path | None = None,
    exclude_truncated: bool = False,
) -> dict:
    months = month_range(start, end)
    if exclude_truncated and not allow_gaps:
        raise ValueError("--exclude-truncated requiere --allow-gaps")
    destination = report_path or PROJECT_ROOT / "data" / "reports" / f"history-{start}-{end}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "start": start,
        "end": end,
        "allow_gaps": allow_gaps,
        "exclude_truncated": exclude_truncated,
        "requested_months": len(months),
        "months": [],
        "complete": False,
    }
    for month in months:
        try:
            download_archive(month, raw_dir)
            result = load_month(
                month, raw_dir, allow_gaps=allow_gaps, exclude_truncated=exclude_truncated
            )
            result["status"] = "loaded"
            print(
                f"{month}: {result['rows']} velas, {result['missing_minutes']} huecos, "
                f"{result['written_rows']} escrituras",
                flush=True,
            )
        except (ValueError, OSError, psycopg2.Error) as exc:
            message = (
                "Error PostgreSQL; comprueba conexión/configuración"
                if isinstance(exc, psycopg2.Error)
                else str(exc)
            )
            result = {"month": month, "status": "failed", "error": message}
            print(f"{month}: ERROR {message}", flush=True)
        report["months"].append(result)
        report["complete"] = len(report["months"]) == len(months) and all(
            item["status"] == "loaded" for item in report["months"]
        )
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        temporary.replace(destination)
    return report

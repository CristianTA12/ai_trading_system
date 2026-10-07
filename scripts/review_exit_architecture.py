"""Attribute existing iteration-15 exits without simulating any alternative policy."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

SEEDS = (42, 123, 456, 789, 2026)
FOLDS = ("2022 H1", "2022 H2", "2023 H1", "2023 H2")


def exit_kind(reason, timestamp, predictions, gate):
    if reason != "signal":
        return f"execution_{reason}"
    if timestamp not in gate.index or not bool(gate.loc[timestamp]):
        return "gate_closed_or_missing"
    if timestamp not in predictions.index:
        return "prediction_missing"
    p = predictions.loc[timestamp, ["p_down", "p_neutral", "p_up"]].to_numpy(dtype=float)
    if not np.isfinite(p).all() or (p < 0).any() or not np.isclose(p.sum(), 1):
        raise ValueError("Invalid probabilities")
    klass = int(p.argmax())
    if klass == 0:
        return "down_argmax"
    if klass == 1:
        return "neutral_argmax"
    if p[2] < 0.5:
        return "up_below_confidence"
    raise ValueError("Signal exit while entry still eligible")


def review(source, output):
    source, output = source.resolve(), output.resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Diagnostic output must be separate from immutable source")
    output.mkdir(parents=True, exist_ok=False)
    hashes = {}

    def read(name):
        path = source / name
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        if path.suffix == ".parquet":
            return pd.read_parquet(path)
        return json.loads(path.read_text())

    recipe = read("protocol.json")
    assert not recipe["test_evaluated"] and not recipe["validation_2024_evaluated"]
    gate = read("regime.parquet").allow_long
    rows = []
    for seed in SEEDS:
        for fold in FOLDS:
            for arm, model in (("sp500_regime", "model_sp500"), ("v1_regime", "model_v1")):
                prefix = f"seed_{seed}/{fold}"
                pred = read(f"{prefix}/{model}/predictions.parquet")
                trades = read(f"{prefix}/{arm}/base/trades.parquet")
                targets = read(f"{prefix}/{arm}/targets.parquet").target_position
                assert pred.index.max() < pd.Timestamp("2024-01-01", tz="UTC")
                assert targets.index.max() < pd.Timestamp("2024-01-01", tz="UTC")
                for trade in trades.itertuples():
                    kind = exit_kind(trade.reason, trade.exit_time, pred, gate)
                    minutes = (trade.exit_time - trade.entry_time).total_seconds() / 60
                    if kind in {"neutral_argmax", "up_below_confidence", "down_argmax"}:
                        assert minutes >= 240
                    if trade.reason == "signal":
                        assert targets.loc[trade.exit_time] == 0
                        previous = targets.loc[targets.index < trade.exit_time]
                        assert len(previous) and previous.iloc[-1] == 1
                    rows.append(
                        {
                            "seed": seed,
                            "fold": fold,
                            "arm": arm,
                            "entry_time": trade.entry_time,
                            "exit_time": trade.exit_time,
                            "kind": kind,
                            "hold_minutes": minutes,
                        }
                    )
    exits = pd.DataFrame(rows)
    exits.to_csv(output / "exits.csv", index=False)
    counts = exits.groupby(["arm", "fold", "kind"]).size().rename("exits").reset_index()
    counts.to_csv(output / "counts.csv", index=False)
    aggregate = exits.groupby(["arm", "kind"]).size().unstack(fill_value=0)
    aggregate.to_csv(output / "aggregate.csv")
    for name, digest in hashes.items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == digest
    report = {
        "source": str(source),
        "exit_counts": aggregate.to_dict(orient="index"),
        "total_exits": len(exits),
        "source_sha256": hashes,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "new_backtests": 0,
        "models_trained": 0,
        "test_evaluated": False,
        "counterfactual_returns_computed": False,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(aggregate.to_string())
    print(counts.loc[counts.fold.eq("2023 H1")].to_string(index=False))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    review(args.source, args.output)

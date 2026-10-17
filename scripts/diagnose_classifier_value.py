"""Paired descriptive attribution from frozen iteration-13 artifacts only."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

FOLDS = ("2022 H1", "2022 H2", "2023 H1", "2023 H2")
SEEDS = (42, 123, 456, 789, 2026)


def attribution(model_gross, gate_gross, model_net, gate_net, selected, allowed):
    """Exact log-return attribution; exposure-normalized residual is not a strategy."""
    arrays = [np.asarray(x, dtype=float) for x in (model_gross, gate_gross, model_net, gate_net)]
    if any(np.any(x <= 0) for x in arrays) or len({len(x) for x in arrays}) != 1:
        raise ValueError("Aligned strictly positive equity curves required")
    selected, allowed = np.asarray(selected, bool), np.asarray(allowed, bool)
    if len(selected) != len(arrays[0]) - 1 or len(allowed) != len(selected):
        raise ValueError("One position per equity interval required")
    if np.any(selected & ~allowed):
        raise ValueError("Model exposure outside gate")
    mg, gg, mn, gn = (np.diff(np.log(x)) for x in arrays)
    gross_delta, net_delta = (mg - gg).sum(), (mn - gn).sum()
    extra_drag = (mg - mn).sum() - (gg - gn).sum()
    skipped = allowed & ~selected
    share = selected.sum() / allowed.sum() if allowed.any() else 0.0
    exposure_term = (share - 1) * gg.sum()
    timing_residual = mg.sum() - share * gg.sum()
    assert np.isclose(net_delta, gross_delta - extra_drag, atol=1e-12)
    assert np.isclose(gross_delta, exposure_term + timing_residual, atol=1e-12)
    return {
        "net_delta_log_pp": 100 * net_delta,
        "gross_delta_log_pp": 100 * gross_delta,
        "extra_cost_drag_log_pp": 100 * extra_drag,
        "reduced_exposure_log_pp": 100 * exposure_term,
        "timing_residual_log_pp": 100 * timing_residual,
        "model_share_of_gate_exposure": share,
        "model_exposure": float(selected.mean()),
        "gate_exposure": float(allowed.mean()),
        "gate_log_return_selected_bps_per_bar": float(gg[selected].mean() * 10000)
        if selected.any()
        else None,
        "gate_log_return_skipped_bps_per_bar": float(gg[skipped].mean() * 10000)
        if skipped.any()
        else None,
        "net_delta_when_skipped_log_pp": float((mn - gn)[skipped].sum() * 100),
        "net_delta_other_intervals_log_pp": float((mn - gn)[~skipped].sum() * 100),
    }


def run(source, output):
    source, output = source.resolve(), output.resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Output must be separate from source")
    output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads((source / "protocol.json").read_text())
    assert not protocol["test_evaluated"] and not protocol["validation_2024_evaluated"]
    hashes, covered = {}, []

    def read(name):
        path = source / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[name] = digest
        expected = protocol["artifact_sha256"].get(name)
        if expected:
            assert digest == expected, name
            covered.append(name)
        return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)

    table = read("comparison.csv")
    gate = read("regime.parquet").allow_long
    rows, benchmarks = [], []
    for fold in FOLDS:

        def metric(arm, scenario, seed=None, fold=fold):
            subset = table.loc[
                (table.fold == fold)
                & (table.arm == arm)
                & (table.scenario == scenario)
                & (table.seed.isna() if seed is None else table.seed.eq(seed))
            ]
            assert len(subset) == 1
            return subset.iloc[0]

        gate_path = f"benchmarks/{fold}/regime_only"
        gg = read(f"{gate_path}/gross/equity.parquet").equity
        gn = read(f"{gate_path}/base/equity.parquet").equity
        bh = read(f"benchmarks/{fold}/buy_hold/base/equity.parquet").equity
        assert gg.index.equals(gn.index) and gn.index.equals(bh.index)
        for arm in ("buy_hold", "regime_only"):
            m = metric(arm, "base")
            benchmarks.append(
                {
                    "fold": fold,
                    "arm": arm,
                    **{
                        key: m[key]
                        for key in ("total_return", "sharpe", "max_drawdown", "exposure", "trades")
                    },
                }
            )
        allowed = gate.reindex(gg.index[1:] - pd.Timedelta(minutes=15))
        assert allowed.notna().all()
        for seed in SEEDS:
            path = f"seed_{seed}/{fold}/four_hour_regime"
            mg = read(f"{path}/gross/equity.parquet").equity
            mn = read(f"{path}/base/equity.parquet").equity
            assert mg.index.equals(gg.index) and mn.index.equals(gg.index)
            targets = read(f"{path}/targets.parquet").target_position.reindex(
                gg.index[1:] - pd.Timedelta(minutes=15)
            )
            assert targets.notna().all()
            m, g = metric("four_hour_regime", "base", seed), metric("regime_only", "base")
            for equity, saved in (
                (mn, m.total_return),
                (gn, g.total_return),
                (bh, metric("buy_hold", "base").total_return),
            ):
                assert np.isclose(equity.iloc[-1] / equity.iloc[0] - 1, saved, atol=1e-12)
            assert np.isclose(targets.mean(), m.exposure)
            assert np.isclose(allowed.mean(), g.exposure)
            rows.append(
                {
                    "fold": fold,
                    "seed": seed,
                    "model_return": m.total_return,
                    "gate_return": g.total_return,
                    "model_sharpe": m.sharpe,
                    "gate_sharpe": g.sharpe,
                    "model_dd": m.max_drawdown,
                    "gate_dd": g.max_drawdown,
                    "model_trades": m.trades,
                    "gate_trades": g.trades,
                    **attribution(mg, gg, mn, gn, targets, allowed),
                }
            )
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "paired_attribution.csv", index=False)
    pd.DataFrame(benchmarks).to_csv(output / "benchmarks.csv", index=False)
    aggregate = []
    for seed in SEEDS:
        part = frame[frame.seed == seed]
        aggregate.append(
            {
                "seed": seed,
                "model_compound": float((1 + part.model_return).prod() - 1),
                "gate_compound": float((1 + part.gate_return).prod() - 1),
                **{
                    key: float(part[key].sum())
                    for key in (
                        "gross_delta_log_pp",
                        "net_delta_log_pp",
                        "extra_cost_drag_log_pp",
                        "reduced_exposure_log_pp",
                        "timing_residual_log_pp",
                    )
                },
            }
        )
    for name, digest in hashes.items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == digest
    summary = {
        "source": str(source),
        "models_trained": 0,
        "backtests_run": 0,
        "test_evaluated": False,
        "validation_2024_evaluated": False,
        "paired_comparisons": len(rows),
        "source_files_read": len(hashes),
        "files_matched_original_manifest": len(set(covered)),
        "by_seed": aggregate,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (output / "source_hashes.json").write_text(json.dumps(hashes, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    print(frame.groupby("fold").mean(numeric_only=True).to_string())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.source, args.output)

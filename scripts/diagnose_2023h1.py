"""Read-only iteration 13 diagnosis; write derived tables to a separate new directory.

Threshold comparisons describe labels, not alternative trained/traded strategies.
No access to the dataset, validation 2024 or reserved test partitions.
"""

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

SEEDS = (42, 123, 456, 789, 2026)
FOLDS = ("2022 H1", "2022 H2", "2023 H1", "2023 H2")
ARM = "four_hour_regime"


def daily_returns(equity):
    """Match compute_metrics UTC daily bins, including internal gap handling."""
    daily = equity.resample("1D", closed="right", label="right").last()
    daily = daily.loc[daily.first_valid_index() : daily.last_valid_index()].ffill()
    return daily.pct_change(fill_method=None).dropna()


def class_counts(returns, threshold):
    values = returns.dropna()
    return [
        int(values.lt(-threshold).sum()),
        int(values.abs().le(threshold).sum()),
        int(values.gt(threshold).sum()),
    ]


def jaccard(a, b):
    union = a | b
    return len(a & b) / len(union) if union else None


def replay(index, signal, gate):
    """Independent scalar replay, distinguishing redundant entries from deferred exits."""
    holding, entered = False, None
    counts = dict(
        raw_signals=int(signal.sum()),
        eligible_signals=0,
        entries=0,
        redundant_signals=0,
        deferred_exit_bars=0,
        forced_gate_exits=0,
    )
    targets, entries = [], []
    for timestamp in index:
        eligible = timestamp in signal.index and bool(gate.at[timestamp])
        enter = eligible and bool(signal.at[timestamp])
        counts["eligible_signals"] += int(enter)
        if not eligible:
            counts["forced_gate_exits"] += int(holding)
            holding = False
        elif holding:
            counts["redundant_signals"] += int(enter)
            if not enter:
                if timestamp - entered >= pd.Timedelta(hours=4):
                    holding = False
                else:
                    counts["deferred_exit_bars"] += 1
        elif enter:
            holding, entered = True, timestamp
            entries.append(timestamp)
            counts["entries"] += 1
        targets.append(int(holding))
    assert counts["eligible_signals"] == counts["entries"] + counts["redundant_signals"]
    return pd.Series(targets, index=index), entries, counts


def diagnose(source, output):
    source, output = source.resolve(), output.resolve()
    if output == source or source in output.parents or output in source.parents:
        raise ValueError("Diagnostic output must be separate from the source experiment")
    output.mkdir(parents=True, exist_ok=False)
    hashes = {}

    def read(name):
        path = source / name
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        if path.suffix == ".parquet":
            return pd.read_parquet(path)
        if path.suffix == ".csv":
            return pd.read_csv(path)
        return json.loads(path.read_text())

    protocol = read("protocol.json")
    assert not protocol["test_evaluated"] and not protocol["validation_2024_evaluated"]
    table = read("comparison.csv")
    verdict = read(f"{ARM}_verdict.json")
    gate = read("regime.parquet").allow_long
    summaries, label_rows, consistency, importance_rows = [], [], [], []
    predictions, positions, entries_by_seed, ranks = {}, {}, {}, {}
    bh = table.query("arm == 'buy_hold' and scenario == 'base' and fold == '2023 H1'").iloc[0]
    bh_equity = read("benchmarks/2023 H1/buy_hold/base/equity.parquet").equity
    bh_daily = daily_returns(bh_equity)
    assert np.isclose(np.sqrt(365) * bh_daily.mean() / bh_daily.std(), bh.sharpe)
    bh_bar_returns = bh_equity.pct_change(fill_method=None).iloc[1:]
    interval_gate = gate.reindex(bh_bar_returns.index - pd.Timedelta(minutes=15))
    assert interval_gate.notna().all()
    market = {
        "buy_hold_return": float(bh.total_return),
        "buy_hold_sharpe": float(bh.sharpe),
        "buy_hold_daily_mean": float(bh_daily.mean()),
        "buy_hold_daily_std": float(bh_daily.std()),
        "gate_open_fraction": float(interval_gate.mean()),
        "first_open": str(interval_gate[interval_gate].index.min()),
        "buy_hold_factor_open_intervals": float(
            (1 + bh_bar_returns.to_numpy()[interval_gate.to_numpy()]).prod()
        ),
        "buy_hold_factor_closed_intervals": float(
            (1 + bh_bar_returns.to_numpy()[~interval_gate.to_numpy()]).prod()
        ),
    }
    assert np.isclose(
        market["buy_hold_factor_open_intervals"] * market["buy_hold_factor_closed_intervals"],
        1 + bh.total_return,
    )
    for seed_result in verdict["seeds"]:
        for fold_result in seed_result["folds"]:
            consistency.append(
                {
                    "seed": seed_result["seed"],
                    "fold": fold_result["fold"],
                    "consistency_pass": fold_result["consistency_pass"],
                    "cash_exception": fold_result["cash_exception"],
                    **fold_result["detail"],
                }
            )
    for fold in FOLDS:
        train = read(f"folds/{fold}/train_rows.parquet")
        for seed in SEEDS:
            base = f"seed_{seed}/{fold}"
            pred = read(f"{base}/four_hour/predictions.parquet")
            classification = read(f"{base}/four_hour/classification.json")
            assert class_counts(train.return_4h, 0.01) == classification["train_class_counts"]
            assert (
                class_counts(pred.actual_return, 0.01) == classification["validation_class_counts"]
            )
            for split, values in (("train", train.return_4h), ("evaluation", pred.actual_return)):
                for threshold in (0.005, 0.0075, 0.01):
                    counts = class_counts(values, threshold)
                    n = sum(counts)
                    label_rows.append(
                        {
                            "seed": seed,
                            "fold": fold,
                            "split": split,
                            "threshold_bps": threshold * 10000,
                            "scored": n,
                            "missing": int(values.isna().sum()),
                            **dict(zip(("down", "neutral", "up"), counts, strict=True)),
                            "up_fraction": counts[2] / n,
                            **{
                                f"weight_{name}": n / (3 * count) if count else None
                                for name, count in zip(
                                    ("down", "neutral", "up"), counts, strict=True
                                )
                            },
                        }
                    )
            if fold != "2023 H1":
                continue
            targets = read(f"{base}/{ARM}/targets.parquet").target_position
            eq = read(f"{base}/{ARM}/base/equity.parquet")
            trades = read(f"{base}/{ARM}/base/trades.parquet")
            fills = read(f"{base}/{ARM}/base/fills.parquet")
            importance = (
                read(f"{base}/four_hour/feature_importance.csv").set_index("Unnamed: 0").importance
            )
            probs = pred[["p_down", "p_neutral", "p_up"]]
            signal = pd.Series(
                (probs.to_numpy().argmax(axis=1) == 2) & pred.p_up.ge(0.5), index=pred.index
            )
            reconstructed, entry_times, counts = replay(targets.index, signal, gate)
            np.testing.assert_array_equal(reconstructed, targets)
            assert entry_times == fills.loc[fills.side.eq("buy"), "time"].tolist()
            assert entry_times == trades.entry_time.tolist()
            row = table.loc[
                table.seed.eq(seed)
                & table.fold.eq(fold)
                & table.arm.eq(ARM)
                & table.scenario.eq("base")
            ].iloc[0]
            returns = daily_returns(eq.equity)
            assert np.isclose(np.sqrt(365) * returns.mean() / returns.std(), row.sharpe)
            assert np.isclose(targets.mean(), row.exposure)
            duration = (trades.exit_time - trades.entry_time).dt.total_seconds() / 60
            reentry = (
                trades.entry_time.reset_index(drop=True)
                - trades.exit_time.shift().reset_index(drop=True)
            ).dt.total_seconds() / 60
            cm = np.asarray(classification["confusion_matrix"])
            summary = {
                "seed": seed,
                **counts,
                **{
                    k: float(row[k])
                    for k in (
                        "total_return",
                        "sharpe",
                        "max_drawdown",
                        "exposure",
                        "mean_trade_bps",
                    )
                },
                "capture_ratio": float(row.total_return / bh.total_return),
                "daily_mean": float(returns.mean()),
                "daily_std": float(returns.std()),
                "daily_mean_at_bh_sharpe_fixed_std": float(
                    bh.sharpe * returns.std() / np.sqrt(365)
                ),
                "nonzero_return_days": int(returns.ne(0).sum()),
                "daily_observations": len(returns),
                "hold_median_minutes": float(duration.median()),
                "hold_max_minutes": float(duration.max()),
                "reentries_under_4h": int(reentry.lt(240).sum()),
                "reentry_min_minutes": float(reentry.min()),
                "up_precision_argmax": float(cm[2, 2] / cm[:, 2].sum()),
                "up_recall_argmax": float(cm[2, 2] / cm[2].sum()),
                "top5_pnl_fraction": float(trades.net_pnl.nlargest(5).sum() / trades.net_pnl.sum()),
            }
            summaries.append(summary)
            predictions[seed], positions[seed] = pred, set(targets[targets.eq(1)].index)
            entries_by_seed[seed], ranks[seed] = set(entry_times), importance
            for rank, (feature, value) in enumerate(
                importance.sort_values(ascending=False).items(), 1
            ):
                importance_rows.append(
                    dict(seed=seed, rank=rank, feature=feature, importance=value)
                )
    pairs = []
    for a, b in itertools.combinations(SEEDS, 2):
        assert predictions[a].index.equals(predictions[b].index)
        pairs.append(
            {
                "seed_a": a,
                "seed_b": b,
                "p_up_correlation": predictions[a].p_up.corr(predictions[b].p_up),
                "p_up_mean_absolute_difference": float(
                    (predictions[a].p_up - predictions[b].p_up).abs().mean()
                ),
                "argmax_agreement": float(
                    predictions[a].predicted_class.eq(predictions[b].predicted_class).mean()
                ),
                "entry_jaccard": jaccard(entries_by_seed[a], entries_by_seed[b]),
                "position_jaccard": jaccard(positions[a], positions[b]),
                "importance_rank_spearman": ranks[a].corr(ranks[b], method="spearman"),
                "importance_top5_jaccard": jaccard(
                    set(ranks[a].nlargest(5).index), set(ranks[b].nlargest(5).index)
                ),
            }
        )
    for name, rows in (
        ("summary", summaries),
        ("class_distribution", label_rows),
        ("consistency", consistency),
        ("feature_importance", importance_rows),
        ("seed_similarity", pairs),
    ):
        pd.DataFrame(rows).to_csv(output / f"{name}.csv", index=False)
    table.loc[table.fold.eq("2023 H1")].to_csv(output / "all_arms_2023h1.csv", index=False)
    (output / "market.json").write_text(json.dumps(market, indent=2) + "\n")
    for name, digest in hashes.items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == digest
    manifest = {
        "source": str(source),
        "source_sha256": hashes,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_unchanged": True,
        "models_trained": 0,
        "backtests_run": 0,
        "validation_2024_evaluated": False,
        "test_evaluated": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"market": market, "summary": summaries}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    diagnose(args.source, args.output)

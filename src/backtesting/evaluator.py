"""Automated evaluator for the risk-return-v1 prospective criterion.

Reads fold-level metrics (candidate and Buy & Hold), applies the six gates
defined in docs/risk-return-v1.yaml, and returns a structured verdict per
seed and overall.  Does NOT train models or run backtests — it receives
pre-computed results.

The evaluator is deterministic and stateless: given the same inputs it
always produces the same verdict.  It never modifies the criterion YAML.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

# ---------------------------------------------------------------------------
# Configuration loaded from the criterion YAML
# ---------------------------------------------------------------------------

CRITERION_PATH = Path(__file__).parent.parent.parent / "docs" / "risk-return-v1.yaml"

FOLDS = ("2022 H1", "2022 H2", "2023 H1", "2023 H2")
SEEDS = (42, 123, 456, 789, 2026)

# Loaded once at import; the YAML is the source of truth.
_CRITERION: dict[str, Any] | None = None


def _load_criterion() -> dict[str, Any]:
    global _CRITERION
    if _CRITERION is None:
        if not CRITERION_PATH.exists():
            raise FileNotFoundError(f"Criterio no encontrado: {CRITERION_PATH}")
        with open(CRITERION_PATH, encoding="utf-8") as f:
            _CRITERION = yaml.safe_load(f)["criterio_prospectivo"]
    return _CRITERION


def criterion_sha256() -> str:
    """SHA-256 of the criterion YAML file, for traceability."""
    return hashlib.sha256(CRITERION_PATH.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Per-fold input
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FoldResult:
    """Metrics for one fold, one scenario (base or stress), one strategy."""

    fold: str
    net_return: float  # As fraction, e.g. 0.05 = +5%
    max_drawdown: float  # Positive magnitude, e.g. 0.15 = 15%
    sharpe: float | None  # None → undefined (e.g. all-cash)
    equity_curve: pd.Series  # DatetimeIndex, values = equity
    n_trades: int  # Number of round-trip trades
    n_fills: int  # Number of fill events (buys + sells)
    is_cash: bool  # True iff zero positions/executions, constant equity


@dataclass(frozen=True)
class SeedInput:
    """All fold results for one seed, both scenarios."""

    seed: int
    candidate_base: dict[str, FoldResult]  # fold name → FoldResult
    candidate_stress: dict[str, FoldResult]  # fold name → FoldResult (2 bp slippage)
    buyhold_base: dict[str, FoldResult]  # fold name → FoldResult


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def validate_fold_result(fr: FoldResult, context: str = "") -> None:
    """Validate a FoldResult, raising ValueError on bad data.

    Checks:
    - fold name is one of the expected folds
    - net_return and max_drawdown are finite floats
    - sharpe, if not None, is finite
    - max_drawdown is non-negative
    - equity_curve is non-empty with all finite positive values
    - n_trades and n_fills are non-negative integers
    - is_cash consistency: if True, n_trades and n_fills must be 0,
      and equity must be constant (all values equal)
    """
    prefix = f"[{context}] " if context else ""

    # Fold name
    if fr.fold not in FOLDS:
        raise ValueError(f"{prefix}Fold desconocido: {fr.fold!r}; esperados: {FOLDS}")

    # Finite numerics
    if not np.isfinite(fr.net_return):
        raise ValueError(f"{prefix}net_return no finito: {fr.net_return}")
    if not np.isfinite(fr.max_drawdown):
        raise ValueError(f"{prefix}max_drawdown no finito: {fr.max_drawdown}")
    if fr.max_drawdown < 0:
        raise ValueError(f"{prefix}max_drawdown negativo: {fr.max_drawdown}")
    if fr.sharpe is not None and not np.isfinite(fr.sharpe):
        raise ValueError(f"{prefix}sharpe no finito: {fr.sharpe}")

    # Equity curve
    if fr.equity_curve.empty:
        raise ValueError(f"{prefix}equity_curve vacía")
    if not np.isfinite(fr.equity_curve.values).all():
        raise ValueError(f"{prefix}equity_curve contiene valores no finitos")
    if (fr.equity_curve.values <= 0).any():
        raise ValueError(f"{prefix}equity_curve contiene valores no positivos")

    # Counts
    if fr.n_trades < 0:
        raise ValueError(f"{prefix}n_trades negativo: {fr.n_trades}")
    if fr.n_fills < 0:
        raise ValueError(f"{prefix}n_fills negativo: {fr.n_fills}")

    # Cash consistency
    if fr.is_cash:
        if fr.n_trades != 0:
            raise ValueError(f"{prefix}is_cash=True pero n_trades={fr.n_trades}; debe ser 0")
        if fr.n_fills != 0:
            raise ValueError(f"{prefix}is_cash=True pero n_fills={fr.n_fills}; debe ser 0")
        equity_vals = fr.equity_curve.values
        if not (equity_vals == equity_vals[0]).all():
            raise ValueError(
                f"{prefix}is_cash=True pero equity no es constante: "
                f"min={equity_vals.min()}, max={equity_vals.max()}"
            )


def validate_seed_input(si: SeedInput) -> None:
    """Validate a SeedInput: correct folds and valid FoldResults.

    Checks:
    - seed is in the expected set
    - candidate_base, candidate_stress and buyhold_base each have exactly
      the 4 expected fold names
    - every FoldResult passes validate_fold_result
    - fold names inside FoldResults match their dict keys
    """
    expected = set(FOLDS)

    if si.seed not in SEEDS:
        raise ValueError(f"Semilla {si.seed} no está en las fijadas: {SEEDS}")

    for label, fold_dict in [
        ("candidate_base", si.candidate_base),
        ("candidate_stress", si.candidate_stress),
        ("buyhold_base", si.buyhold_base),
    ]:
        got = set(fold_dict.keys())
        if got != expected:
            missing = expected - got
            extra = got - expected
            raise ValueError(
                f"seed={si.seed} {label}: folds incorrectos. "
                f"Faltan: {missing or 'ninguno'}, sobran: {extra or 'ninguno'}"
            )
        for fold_name, fr in fold_dict.items():
            if fr.fold != fold_name:
                raise ValueError(
                    f"seed={si.seed} {label}: clave {fold_name!r} "
                    f"no coincide con fr.fold={fr.fold!r}"
                )
            validate_fold_result(fr, context=f"seed={si.seed} {label} {fold_name}")


# ---------------------------------------------------------------------------
# Gate evaluation
# ---------------------------------------------------------------------------


@dataclass
class FoldVerdict:
    fold: str
    consistency_sharpe: bool | None  # None when cash exception applies
    consistency_dd: bool | None  # None when cash exception applies
    consistency_pass: bool
    cash_exception: bool
    drawdown_pass: bool
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class SeedVerdict:
    seed: int
    profitability_pass: bool
    risk_pass: bool  # Per-fold AND concatenated
    consistency_pass: bool  # ≥3/4 folds
    friction_pass: bool
    all_pass: bool
    folds: list[FoldVerdict] = field(default_factory=list)
    compound_return_base: float = 0.0
    compound_return_stress: float = 0.0
    concat_max_drawdown: float = 0.0
    consistency_count: int = 0
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class OverallVerdict:
    passes: bool
    seeds_passing: int
    seeds_total: int
    min_seeds_required: int
    seeds: list[SeedVerdict] = field(default_factory=list)
    criterion_sha256: str = ""
    gate_historico: dict[str, Any] = field(default_factory=dict)


def _compound_return(fold_returns: list[float]) -> float:
    """Product of (1 + r_i) - 1."""
    result = 1.0
    for r in fold_returns:
        result *= 1.0 + r
    return result - 1.0


def _concatenate_equity(curves: list[pd.Series]) -> pd.Series:
    """Concatenate fold equity curves, scaling each by the previous final equity.

    Removes the duplicated initial point of each subsequent fold.
    Does not carry positions between folds.
    """
    if not curves:
        raise ValueError("No hay curvas para concatenar")

    parts: list[pd.Series] = [curves[0].copy()]
    for curve in curves[1:]:
        scale = parts[-1].iloc[-1] / curve.iloc[0]
        scaled = curve * scale
        # Remove duplicated first point (it equals the previous last point)
        parts.append(scaled.iloc[1:])

    return pd.concat(parts)


def _max_drawdown(equity: pd.Series) -> float:
    """Positive magnitude of the maximum drawdown."""
    running_max = equity.cummax()
    dd = 1.0 - equity / running_max
    return float(dd.max())


def evaluate_fold(
    candidate: FoldResult,
    buyhold: FoldResult,
    max_dd: float,
) -> FoldVerdict:
    """Evaluate consistency and risk for a single fold."""
    validate_fold_result(candidate, context=f"candidate {candidate.fold}")
    validate_fold_result(buyhold, context=f"buyhold {buyhold.fold}")

    # --- Cash exception ---
    cash_exception = False
    if candidate.is_cash and buyhold.net_return < 0:
        cash_exception = True

    # --- Drawdown gate (per fold) ---
    drawdown_pass = candidate.max_drawdown <= max_dd

    # --- Consistency ---
    if cash_exception:
        consistency_sharpe = None
        consistency_dd = None
        consistency_pass = True
    else:
        # Sharpe: candidate must be strictly greater than B&H
        if candidate.sharpe is None:
            # Undefined sharpe outside cash exception → fail
            consistency_sharpe = False
        elif buyhold.sharpe is None:
            # Undefined benchmark cannot establish strict superiority.
            consistency_sharpe = False
        else:
            consistency_sharpe = candidate.sharpe > buyhold.sharpe

        # Drawdown: candidate must be ≤ B&H
        consistency_dd = candidate.max_drawdown <= buyhold.max_drawdown

        consistency_pass = bool(consistency_sharpe and consistency_dd)

    return FoldVerdict(
        fold=candidate.fold,
        consistency_sharpe=consistency_sharpe,
        consistency_dd=consistency_dd,
        consistency_pass=consistency_pass,
        cash_exception=cash_exception,
        drawdown_pass=drawdown_pass,
        detail={
            "candidate_return": candidate.net_return,
            "candidate_sharpe": candidate.sharpe,
            "candidate_dd": candidate.max_drawdown,
            "buyhold_return": buyhold.net_return,
            "buyhold_sharpe": buyhold.sharpe,
            "buyhold_dd": buyhold.max_drawdown,
            "candidate_is_cash": candidate.is_cash,
            "candidate_trades": candidate.n_trades,
        },
    )


def evaluate_seed(seed_input: SeedInput) -> SeedVerdict:
    """Evaluate all six gates for a single seed."""
    validate_seed_input(seed_input)
    crit = _load_criterion()
    gates = crit["gates"]
    max_dd = gates["riesgo_absoluto"]["max_drawdown"]
    min_consistent = gates["consistencia"]["min_semestres"]

    # --- Per-fold evaluation ---
    fold_verdicts: list[FoldVerdict] = []
    base_returns: list[float] = []
    stress_returns: list[float] = []
    base_curves: list[pd.Series] = []
    all_dd_pass = True

    for fold_name in FOLDS:
        candidate = seed_input.candidate_base[fold_name]
        buyhold = seed_input.buyhold_base[fold_name]

        verdict = evaluate_fold(candidate, buyhold, max_dd)
        fold_verdicts.append(verdict)

        base_returns.append(candidate.net_return)
        base_curves.append(candidate.equity_curve)

        if not verdict.drawdown_pass:
            all_dd_pass = False

        # Stress returns
        stress_fold = seed_input.candidate_stress[fold_name]
        stress_returns.append(stress_fold.net_return)

    # --- Gate 1: Profitability ---
    compound_base = _compound_return(base_returns)
    profitability_pass = compound_base > 0

    # --- Gate 2: Risk (per-fold + concatenated) ---
    concat_equity = _concatenate_equity(base_curves)
    concat_dd = _max_drawdown(concat_equity)
    concat_dd_pass = concat_dd <= max_dd
    risk_pass = all_dd_pass and concat_dd_pass

    # --- Gate 3: Consistency (≥3/4 folds) ---
    consistency_count = sum(1 for v in fold_verdicts if v.consistency_pass)
    consistency_pass = consistency_count >= min_consistent

    # --- Gate 4: Friction stress ---
    compound_stress = _compound_return(stress_returns)
    friction_pass = compound_stress > 0

    # --- All gates ---
    all_pass = profitability_pass and risk_pass and consistency_pass and friction_pass

    return SeedVerdict(
        seed=seed_input.seed,
        profitability_pass=profitability_pass,
        risk_pass=risk_pass,
        consistency_pass=consistency_pass,
        friction_pass=friction_pass,
        all_pass=all_pass,
        folds=fold_verdicts,
        compound_return_base=compound_base,
        compound_return_stress=compound_stress,
        concat_max_drawdown=concat_dd,
        consistency_count=consistency_count,
        detail={
            "base_returns_by_fold": dict(zip(FOLDS, base_returns, strict=True)),
            "stress_returns_by_fold": dict(zip(FOLDS, stress_returns, strict=True)),
            "concat_dd": concat_dd,
        },
    )


def evaluate_all(seed_inputs: list[SeedInput]) -> OverallVerdict:
    """Evaluate the full criterion across all seeds.

    Args:
        seed_inputs: One SeedInput per seed, containing fold results for
            candidate (base + stress) and Buy & Hold (base).

    Returns:
        OverallVerdict with per-seed results and overall pass/fail.
    """
    crit = _load_criterion()
    min_seeds = crit["gates"]["estabilidad"]["min_semillas"]
    total_seeds = crit["gates"]["estabilidad"]["total_semillas"]

    # Validate input
    input_seeds = sorted(s.seed for s in seed_inputs)
    expected_seeds = sorted(SEEDS)
    if input_seeds != expected_seeds:
        raise ValueError(
            f"Semillas recibidas {input_seeds} no coinciden con las fijadas {expected_seeds}"
        )

    seed_verdicts = [evaluate_seed(si) for si in seed_inputs]
    seeds_passing = sum(1 for sv in seed_verdicts if sv.all_pass)

    # --- Gate histórico (referencia, no bloquea) ---
    # For each seed: count folds with strictly positive net return
    gate_historico: dict[str, Any] = {}
    for sv in seed_verdicts:
        positive_folds = sum(1 for fv in sv.folds if fv.detail.get("candidate_return", 0) > 0)
        gate_historico[f"seed_{sv.seed}"] = {
            "positive_folds": positive_folds,
            "passes_legacy_3_of_4": positive_folds >= 3,
        }

    return OverallVerdict(
        passes=seeds_passing >= min_seeds,
        seeds_passing=seeds_passing,
        seeds_total=total_seeds,
        min_seeds_required=min_seeds,
        seeds=seed_verdicts,
        criterion_sha256=criterion_sha256(),
        gate_historico=gate_historico,
    )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def verdict_to_dict(verdict: OverallVerdict) -> dict[str, Any]:
    """Convert an OverallVerdict to a JSON-serializable dict."""
    result: dict[str, Any] = {
        "passes": verdict.passes,
        "seeds_passing": verdict.seeds_passing,
        "seeds_total": verdict.seeds_total,
        "min_seeds_required": verdict.min_seeds_required,
        "criterion_sha256": verdict.criterion_sha256,
        "gate_historico": verdict.gate_historico,
        "seeds": [],
    }
    for sv in verdict.seeds:
        seed_dict: dict[str, Any] = {
            "seed": sv.seed,
            "all_pass": sv.all_pass,
            "profitability_pass": sv.profitability_pass,
            "risk_pass": sv.risk_pass,
            "consistency_pass": sv.consistency_pass,
            "friction_pass": sv.friction_pass,
            "compound_return_base": sv.compound_return_base,
            "compound_return_stress": sv.compound_return_stress,
            "concat_max_drawdown": sv.concat_max_drawdown,
            "consistency_count": sv.consistency_count,
            "detail": sv.detail,
            "folds": [],
        }
        for fv in sv.folds:
            fold_dict = {
                "fold": fv.fold,
                "consistency_pass": fv.consistency_pass,
                "cash_exception": fv.cash_exception,
                "drawdown_pass": fv.drawdown_pass,
                "detail": fv.detail,
            }
            if fv.consistency_sharpe is not None:
                fold_dict["consistency_sharpe"] = fv.consistency_sharpe
            if fv.consistency_dd is not None:
                fold_dict["consistency_dd"] = fv.consistency_dd
            seed_dict["folds"].append(fold_dict)
        result["seeds"].append(seed_dict)
    return result


def save_verdict(verdict: OverallVerdict, path: Path) -> None:
    """Save verdict as JSON with NaN-safe serialization."""
    data = verdict_to_dict(verdict)
    path.write_text(
        json.dumps(data, indent=2, allow_nan=False, default=str) + "\n",
        encoding="utf-8",
    )

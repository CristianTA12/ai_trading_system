"""Tests for the risk-return-v1 evaluator.

These tests verify the gate logic using synthetic fold results.
They do NOT depend on real model outputs or database access.
"""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from src.backtesting.evaluator import (
    FOLDS,
    SEEDS,
    FoldResult,
    SeedInput,
    _compound_return,
    _concatenate_equity,
    _max_drawdown,
    criterion_sha256,
    evaluate_all,
    evaluate_fold,
    evaluate_seed,
    save_verdict,
    validate_fold_result,
    validate_seed_input,
    verdict_to_dict,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _equity_curve(returns: list[float], start: float = 10_000.0) -> pd.Series:
    """Build a simple equity curve from a list of period returns."""
    values = [start]
    for r in returns:
        values.append(values[-1] * (1 + r))
    index = pd.date_range("2022-01-01", periods=len(values), freq="D", tz="UTC")
    return pd.Series(values, index=index, name="equity")


def _make_fold(
    fold: str,
    net_return: float,
    max_drawdown: float,
    sharpe: float | None,
    is_cash: bool = False,
    n_trades: int = 10,
) -> FoldResult:
    """Create a synthetic FoldResult."""
    eq = _equity_curve([net_return / 10] * 10, start=10_000.0)
    return FoldResult(
        fold=fold,
        net_return=net_return,
        max_drawdown=max_drawdown,
        sharpe=sharpe,
        equity_curve=eq,
        n_trades=0 if is_cash else n_trades,
        n_fills=0 if is_cash else n_trades * 2,
        is_cash=is_cash,
    )


def _make_seed_input(
    seed: int,
    candidate_specs: list[tuple[float, float, float | None, bool]],
    stress_specs: list[tuple[float, float, float | None, bool]] | None = None,
    buyhold_specs: list[tuple[float, float, float | None]] | None = None,
) -> SeedInput:
    """Build a SeedInput from compact specs.

    Each candidate/stress spec: (net_return, max_drawdown, sharpe, is_cash)
    Each buyhold spec: (net_return, max_drawdown, sharpe)
    """
    if stress_specs is None:
        # Default stress: same as base but slightly worse
        stress_specs = [
            (ret * 0.9 if ret > 0 else ret * 1.1, dd * 1.1, sh, cash)
            for ret, dd, sh, cash in candidate_specs
        ]

    if buyhold_specs is None:
        buyhold_specs = [
            (-0.57, 0.63, -2.0),
            (-0.17, 0.38, -0.4),
            (0.84, 0.22, 2.7),
            (0.39, 0.21, 1.9),
        ]

    candidate_base = {}
    candidate_stress = {}
    buyhold_base = {}

    for i, fold in enumerate(FOLDS):
        ret, dd, sh, cash = candidate_specs[i]
        candidate_base[fold] = _make_fold(fold, ret, dd, sh, is_cash=cash)

        sret, sdd, ssh, scash = stress_specs[i]
        candidate_stress[fold] = _make_fold(fold, sret, sdd, ssh, is_cash=scash)

        bret, bdd, bsh = buyhold_specs[i]
        buyhold_base[fold] = _make_fold(fold, bret, bdd, bsh)

    return SeedInput(
        seed=seed,
        candidate_base=candidate_base,
        candidate_stress=candidate_stress,
        buyhold_base=buyhold_base,
    )


# ---------------------------------------------------------------------------
# Tests: input validation
# ---------------------------------------------------------------------------


class TestValidateFoldResult:
    @staticmethod
    def _assert_rejected(fr, message):
        with pytest.raises(ValueError, match=message):
            validate_fold_result(fr)
        buyhold = _make_fold(fr.fold, -0.57, 0.63, -2.0)
        with pytest.raises(ValueError, match=message):
            evaluate_fold(fr, buyhold, max_dd=0.15)

    def test_nan_return_rejected(self):
        fr = _make_fold(FOLDS[0], 0.05, 0.02, 1.0)
        self._assert_rejected(replace(fr, net_return=float("nan")), "net_return no finito")

    def test_inf_drawdown_rejected(self):
        fr = _make_fold(FOLDS[0], 0.05, 0.02, 1.0)
        self._assert_rejected(replace(fr, max_drawdown=float("inf")), "max_drawdown no finito")

    def test_nan_sharpe_rejected(self):
        fr = _make_fold(FOLDS[0], 0.05, 0.02, 1.0)
        self._assert_rejected(replace(fr, sharpe=float("nan")), "sharpe no finito")

    def test_negative_drawdown_rejected(self):
        fr = _make_fold(FOLDS[0], 0.05, 0.02, 1.0)
        self._assert_rejected(replace(fr, max_drawdown=-0.05), "max_drawdown negativo")

    def test_empty_equity_rejected(self):
        fr = _make_fold(FOLDS[0], 0.05, 0.02, 1.0)
        self._assert_rejected(
            replace(fr, equity_curve=pd.Series([], dtype=float)), "equity_curve vacía"
        )

    def test_equity_with_nan_rejected(self):
        fr = _make_fold(FOLDS[0], 0.05, 0.02, 1.0)
        equity = fr.equity_curve.copy()
        equity.iloc[len(equity) // 2] = np.nan
        self._assert_rejected(
            replace(fr, equity_curve=equity), "equity_curve contiene valores no finitos"
        )

    def test_cash_with_trades_rejected(self):
        fr = _make_fold(FOLDS[0], 0.0, 0.0, None, is_cash=True)
        # Override after construction: the helper zeroes counts for cash.
        self._assert_rejected(replace(fr, n_trades=5), "is_cash=True pero n_trades=5")

    def test_cash_with_varying_equity_rejected(self):
        fr = _make_fold(FOLDS[0], 0.0, 0.0, None, is_cash=True)
        # Same initial/final equity, but an intra-fold drawdown: not cash.
        equity = _equity_curve([-0.10, 1 / 0.9 - 1])
        self._assert_rejected(
            replace(fr, equity_curve=equity), "is_cash=True pero equity no es constante"
        )


class TestValidateSeedInput:
    @staticmethod
    def _valid_input():
        return _make_seed_input(42, [(0.05, 0.02, 1.0, False)] * len(FOLDS))

    @staticmethod
    def _assert_rejected(si, message):
        with pytest.raises(ValueError, match=message):
            validate_seed_input(si)
        with pytest.raises(ValueError, match=message):
            evaluate_seed(si)

    @pytest.mark.parametrize("arm", ["candidate_base", "candidate_stress", "buyhold_base"])
    def test_missing_fold_rejected(self, arm):
        si = self._valid_input()
        del getattr(si, arm)[FOLDS[-1]]
        self._assert_rejected(si, rf"{arm}: folds incorrectos.*Faltan:.*2023 H2")

    @pytest.mark.parametrize("arm", ["candidate_base", "candidate_stress", "buyhold_base"])
    def test_extra_fold_rejected(self, arm):
        si = self._valid_input()
        getattr(si, arm)["2024 H1"] = _make_fold("2024 H1", 0.05, 0.02, 1.0)
        self._assert_rejected(si, rf"{arm}: folds incorrectos.*sobran:.*2024 H1")

    @pytest.mark.parametrize("arm", ["candidate_base", "candidate_stress", "buyhold_base"])
    def test_fold_name_mismatch_rejected(self, arm):
        si = self._valid_input()
        folds = getattr(si, arm)
        # Both names are valid; only the dictionary key/result pairing is invalid.
        folds[FOLDS[0]] = replace(folds[FOLDS[0]], fold=FOLDS[1])
        self._assert_rejected(si, rf"{arm}: clave .*no coincide con fr.fold")

    def test_wrong_seed_rejected(self):
        self._assert_rejected(
            replace(self._valid_input(), seed=999), "Semilla 999 no está en las fijadas"
        )


# ---------------------------------------------------------------------------
# Tests: compound return
# ---------------------------------------------------------------------------


class TestCompoundReturn:
    def test_positive(self):
        assert _compound_return([0.10, 0.05, -0.03, 0.08]) == pytest.approx(
            1.10 * 1.05 * 0.97 * 1.08 - 1
        )

    def test_zeros(self):
        assert _compound_return([0.0, 0.0, 0.0, 0.0]) == pytest.approx(0.0)

    def test_single_loss(self):
        assert _compound_return([-0.50]) == pytest.approx(-0.50)


# ---------------------------------------------------------------------------
# Tests: equity concatenation
# ---------------------------------------------------------------------------


class TestConcatenateEquity:
    def test_two_curves(self):
        c1 = _equity_curve([0.01, 0.02], start=10_000)
        c2 = _equity_curve([-0.01, 0.03], start=10_000)
        concat = _concatenate_equity([c1, c2])
        # c1 ends at 10_000 * 1.01 * 1.02 = 10302
        # c2 starts at 10_000, scale = 10302 / 10000 = 1.0302
        # c2 scaled: first point removed, rest scaled
        assert len(concat) == len(c1) + len(c2) - 1

    def test_single_curve(self):
        c1 = _equity_curve([0.05, -0.02])
        concat = _concatenate_equity([c1])
        assert len(concat) == len(c1)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            _concatenate_equity([])


# ---------------------------------------------------------------------------
# Tests: max drawdown
# ---------------------------------------------------------------------------


class TestMaxDrawdown:
    def test_no_drawdown(self):
        eq = pd.Series([100, 101, 102, 103])
        assert _max_drawdown(eq) == pytest.approx(0.0)

    def test_known_drawdown(self):
        eq = pd.Series([100, 110, 88, 95])
        # Peak=110, trough=88 → DD = 1 - 88/110 = 0.2
        assert _max_drawdown(eq) == pytest.approx(1 - 88 / 110)


# ---------------------------------------------------------------------------
# Tests: fold evaluation
# ---------------------------------------------------------------------------


class TestEvaluateFold:
    def test_undefined_benchmark_sharpe_fails(self):
        candidate = _make_fold("2023 H1", 0.1, 0.01, 1.0)
        buyhold = _make_fold("2023 H1", 0.0, 0.01, None)
        assert not evaluate_fold(candidate, buyhold, max_dd=0.15).consistency_pass

    def test_cash_rejects_small_equity_variation(self):
        candidate = _make_fold("2022 H1", 0.0, 0.0, None, is_cash=True)
        candidate.equity_curve.iloc[1] += 0.01
        with pytest.raises(ValueError, match="equity no es constante"):
            validate_fold_result(candidate)

    def test_cash_exception_bear_market(self):
        """Cash in a bear market passes consistency."""
        candidate = _make_fold("2022 H1", 0.0, 0.0, None, is_cash=True)
        buyhold = _make_fold("2022 H1", -0.57, 0.63, -2.0)
        verdict = evaluate_fold(candidate, buyhold, max_dd=0.15)
        assert verdict.consistency_pass is True
        assert verdict.cash_exception is True
        assert verdict.drawdown_pass is True

    def test_cash_no_exception_bull_market(self):
        """Cash in a bull market does NOT pass consistency."""
        candidate = _make_fold("2023 H1", 0.0, 0.0, None, is_cash=True)
        buyhold = _make_fold("2023 H1", 0.84, 0.22, 2.7)
        verdict = evaluate_fold(candidate, buyhold, max_dd=0.15)
        # B&H return > 0, so cash exception does not apply
        # But candidate is_cash=True and B&H > 0 → no exception
        assert verdict.cash_exception is False
        # Sharpe is None outside exception → fails
        assert verdict.consistency_pass is False

    def test_beats_buyhold(self):
        """Candidate with better Sharpe and lower DD passes."""
        candidate = _make_fold("2023 H2", 0.15, 0.10, 2.5)
        buyhold = _make_fold("2023 H2", 0.39, 0.21, 1.9)
        verdict = evaluate_fold(candidate, buyhold, max_dd=0.15)
        assert verdict.consistency_sharpe is True
        assert verdict.consistency_dd is True
        assert verdict.consistency_pass is True
        assert verdict.drawdown_pass is True

    def test_dd_exceeds_limit(self):
        """Drawdown above 15% fails risk gate."""
        candidate = _make_fold("2022 H1", -0.10, 0.20, -1.0)
        buyhold = _make_fold("2022 H1", -0.57, 0.63, -2.0)
        verdict = evaluate_fold(candidate, buyhold, max_dd=0.15)
        assert verdict.drawdown_pass is False

    def test_undefined_sharpe_outside_cash_fails(self):
        """Undefined Sharpe without cash exception → consistency fails."""
        candidate = _make_fold("2023 H1", 0.0, 0.01, None, is_cash=False, n_trades=5)
        buyhold = _make_fold("2023 H1", 0.84, 0.22, 2.7)
        verdict = evaluate_fold(candidate, buyhold, max_dd=0.15)
        assert verdict.consistency_pass is False


# ---------------------------------------------------------------------------
# Tests: seed evaluation
# ---------------------------------------------------------------------------


class TestEvaluateSeed:
    def test_all_gates_pass(self):
        """A seed that passes all gates."""
        si = _make_seed_input(
            seed=42,
            candidate_specs=[
                # 2022 H1: cash in bear → pass consistency, 0% DD
                (0.0, 0.0, None, True),
                # 2022 H2: cash in bear → pass consistency, 0% DD
                (0.0, 0.0, None, True),
                # 2023 H1: beats B&H Sharpe (3.0 > 2.7), lower DD (0.10 < 0.22)
                (0.30, 0.10, 3.0, False),
                # 2023 H2: beats B&H Sharpe (2.5 > 1.9), lower DD (0.08 < 0.21)
                (0.15, 0.08, 2.5, False),
            ],
        )
        verdict = evaluate_seed(si)
        assert verdict.profitability_pass is True
        assert verdict.risk_pass is True
        assert verdict.consistency_pass is True
        assert verdict.consistency_count == 4
        assert verdict.friction_pass is True
        assert verdict.all_pass is True

    def test_profitability_fails(self):
        """Compound return across folds is negative."""
        si = _make_seed_input(
            seed=42,
            candidate_specs=[
                (0.0, 0.0, None, True),
                (0.0, 0.0, None, True),
                (-0.30, 0.10, -1.0, False),  # Big loss
                (0.05, 0.05, 1.0, False),
            ],
        )
        verdict = evaluate_seed(si)
        assert verdict.profitability_pass is False
        assert verdict.all_pass is False

    def test_consistency_fails_only_two(self):
        """Only 2/4 folds pass consistency → fails."""
        si = _make_seed_input(
            seed=42,
            candidate_specs=[
                (0.0, 0.0, None, True),  # Cash in bear → pass
                (0.0, 0.0, None, True),  # Cash in bear → pass
                (0.10, 0.10, 1.0, False),  # Sharpe 1.0 < B&H 2.7 → fail
                (0.10, 0.08, 2.5, False),  # Sharpe 2.5 > B&H 1.9 → pass
            ],
        )
        verdict = evaluate_seed(si)
        assert verdict.consistency_count == 3
        assert verdict.consistency_pass is True  # 3/4 passes

    def test_risk_fails_high_dd(self):
        """One fold exceeds 15% DD → risk fails."""
        si = _make_seed_input(
            seed=42,
            candidate_specs=[
                (0.0, 0.0, None, True),
                (0.0, 0.0, None, True),
                (0.30, 0.20, 3.0, False),  # DD 20% > 15%
                (0.15, 0.08, 2.5, False),
            ],
        )
        verdict = evaluate_seed(si)
        assert verdict.risk_pass is False
        assert verdict.all_pass is False

    def test_friction_fails(self):
        """Stress scenario compound return is negative."""
        si = _make_seed_input(
            seed=42,
            candidate_specs=[
                (0.0, 0.0, None, True),
                (0.0, 0.0, None, True),
                (0.30, 0.10, 3.0, False),
                (0.15, 0.08, 2.5, False),
            ],
            stress_specs=[
                (0.0, 0.0, None, True),
                (0.0, 0.0, None, True),
                (-0.40, 0.15, -1.0, False),  # Stress wipes gains
                (-0.10, 0.10, -0.5, False),
            ],
        )
        verdict = evaluate_seed(si)
        assert verdict.friction_pass is False
        assert verdict.all_pass is False


# ---------------------------------------------------------------------------
# Tests: overall evaluation
# ---------------------------------------------------------------------------


class TestEvaluateAll:
    def _passing_specs(self):
        return [
            (0.0, 0.0, None, True),
            (0.0, 0.0, None, True),
            (0.30, 0.10, 3.0, False),
            (0.15, 0.08, 2.5, False),
        ]

    def _failing_specs(self):
        return [
            (-0.30, 0.12, -1.5, False),
            (-0.20, 0.14, -1.0, False),
            (0.10, 0.10, 1.0, False),  # Sharpe < B&H
            (0.05, 0.05, 0.5, False),  # Sharpe < B&H
        ]

    def test_4_of_5_pass(self):
        """4/5 seeds pass → overall passes."""
        inputs = [_make_seed_input(seed, self._passing_specs()) for seed in [42, 123, 456, 789]]
        inputs.append(_make_seed_input(2026, self._failing_specs()))
        verdict = evaluate_all(inputs)
        assert verdict.passes is True
        assert verdict.seeds_passing == 4

    def test_3_of_5_fail(self):
        """Only 2/5 seeds pass → overall fails."""
        inputs = [_make_seed_input(seed, self._passing_specs()) for seed in [42, 123]]
        inputs.extend(_make_seed_input(seed, self._failing_specs()) for seed in [456, 789, 2026])
        verdict = evaluate_all(inputs)
        assert verdict.passes is False
        assert verdict.seeds_passing == 2

    def test_wrong_seeds_raises(self):
        """Providing wrong seeds raises ValueError."""
        inputs = [_make_seed_input(seed, self._passing_specs()) for seed in [1, 2, 3, 4, 5]]
        with pytest.raises(ValueError, match="no coinciden"):
            evaluate_all(inputs)

    def test_criterion_sha256(self):
        """SHA-256 of criterion YAML is computed and stored."""
        inputs = [_make_seed_input(seed, self._passing_specs()) for seed in SEEDS]
        verdict = evaluate_all(inputs)
        assert len(verdict.criterion_sha256) == 64
        assert verdict.criterion_sha256 == criterion_sha256()

    def test_gate_historico_included(self):
        """Legacy gate (≥3/4 positive) is reported but doesn't block."""
        inputs = [_make_seed_input(seed, self._passing_specs()) for seed in SEEDS]
        verdict = evaluate_all(inputs)
        assert "seed_42" in verdict.gate_historico
        for info in verdict.gate_historico.values():
            assert "positive_folds" in info
            assert "passes_legacy_3_of_4" in info


# ---------------------------------------------------------------------------
# Tests: serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_verdict_to_dict(self):
        inputs = [
            _make_seed_input(
                seed,
                [
                    (0.0, 0.0, None, True),
                    (0.0, 0.0, None, True),
                    (0.30, 0.10, 3.0, False),
                    (0.15, 0.08, 2.5, False),
                ],
            )
            for seed in SEEDS
        ]
        verdict = evaluate_all(inputs)
        d = verdict_to_dict(verdict)
        assert isinstance(d, dict)
        assert d["passes"] is True
        assert len(d["seeds"]) == 5

    def test_save_verdict(self, tmp_path):
        inputs = [
            _make_seed_input(
                seed,
                [
                    (0.0, 0.0, None, True),
                    (0.0, 0.0, None, True),
                    (0.30, 0.10, 3.0, False),
                    (0.15, 0.08, 2.5, False),
                ],
            )
            for seed in SEEDS
        ]
        verdict = evaluate_all(inputs)
        path = tmp_path / "verdict.json"
        save_verdict(verdict, path)
        assert path.exists()
        import json

        data = json.loads(path.read_text())
        assert data["passes"] is True

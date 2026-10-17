import numpy as np
import pytest

from scripts.diagnose_classifier_value import attribution


def test_exact_cost_and_exposure_decomposition():
    gate = [100, 110, 121]
    model = [100, 110, 110]
    net_model = [100, 109, 108]
    net_gate = [100, 109, 120]
    result = attribution(model, gate, net_model, net_gate, [1, 0], [1, 1])
    assert result["model_share_of_gate_exposure"] == 0.5
    assert result["timing_residual_log_pp"] == pytest.approx(0)
    assert result["net_delta_log_pp"] == pytest.approx(100 * np.log(108 / 120))
    assert result["gross_delta_log_pp"] - result["extra_cost_drag_log_pp"] == pytest.approx(
        result["net_delta_log_pp"]
    )


def test_cash_fold_and_no_exposure_outside_gate():
    result = attribution([100, 100], [100, 100], [100, 100], [100, 100], [0], [0])
    assert result["net_delta_log_pp"] == result["timing_residual_log_pp"] == 0
    assert result["gate_log_return_selected_bps_per_bar"] is None
    with pytest.raises(ValueError, match="outside gate"):
        attribution([100, 100], [100, 100], [100, 100], [100, 100], [1], [0])

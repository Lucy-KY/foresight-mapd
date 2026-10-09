"""Integration check: with lam = mu = 0, M3-M5 must reproduce TP exactly.

Skipped until the simulator, TP and the reservation table exist.
"""

import pytest

from foresight.costs import (
    ForesightCost,
    SpatioTemporalCost,
    SpatioTemporalDirectionalCost,
)

ZERO_WEIGHT_MODELS = [
    lambda: ForesightCost(lam=0.0, window=5),
    lambda: SpatioTemporalCost(lam=0.0, delta=2),
    lambda: SpatioTemporalDirectionalCost(lam=0.0, delta=2, mu=0.0, delta_dir=2),
]


@pytest.mark.parametrize("make_model", ZERO_WEIGHT_MODELS)
def test_zero_weights_match_tp(make_model):
    pytest.skip("enable once Simulator, TokenPassing and ReservationTable are implemented")


def test_delta_zero_is_rejected():
    with pytest.raises(ValueError):
        SpatioTemporalCost(lam=1.0, delta=0)

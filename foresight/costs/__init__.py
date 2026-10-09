"""Step-cost models M0-M5. Each method is one class; everything else is shared."""

from foresight.costs.foresight import (
    ForesightCost,
    SpatioTemporalCost,
    SpatioTemporalDirectionalCost,
)
from foresight.costs.heatmap import HeatmapCost
from foresight.costs.highway import HighwayCost
from foresight.costs.unit import UnitCost

METHODS = {
    "tp": UnitCost,  # M0
    "highway": HighwayCost,  # M1
    "heatmap": HeatmapCost,  # M2
    "foresight": ForesightCost,  # M3
    "foresight_st": SpatioTemporalCost,  # M4
    "foresight_std": SpatioTemporalDirectionalCost,  # M5
}

__all__ = [
    "METHODS",
    "UnitCost",
    "HighwayCost",
    "HeatmapCost",
    "ForesightCost",
    "SpatioTemporalCost",
    "SpatioTemporalDirectionalCost",
]

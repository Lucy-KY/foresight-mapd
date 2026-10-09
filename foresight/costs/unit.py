"""M0: unit step cost, i.e. original TP (Ma et al., 2017)."""

from __future__ import annotations

from foresight.costs.base import BaseCostModel


class UnitCost(BaseCostModel):
    name = "tp"

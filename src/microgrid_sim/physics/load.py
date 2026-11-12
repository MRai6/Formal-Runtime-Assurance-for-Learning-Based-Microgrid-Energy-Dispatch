"""Building electricity demand physical interface for microgrid_sim.

Governing Principles:
    1. Instantaneous Power vs Interval Energy:
       P_load [kW] = E_interval [kWh] / dt_hours [h] = E_interval * 4.0 (for dt = 0.25 h)
       E_interval [kWh] = P_load [kW] * dt_hours [h]
    2. Physical Invariants:
       P_load >= 0.0 (Building cannot generate power; non-negativity constraint).
       P_load <= P_load_max (Peak physical threshold check).
    3. Zero Fabrication Policy:
       Missing, NaN, or non-numeric observations raise PhysicsViolationError immediately.
"""

from dataclasses import dataclass
import math
from typing import Optional, Union
import numpy as np
import pandas as pd

from microgrid_sim.config.schemas import LocationConfig
from microgrid_sim.utils.exceptions import PhysicsViolationError
from microgrid_sim.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class LoadDemandResult:
    """Validated active power and interval energy for building load."""
    load_power_kw: float
    interval_energy_kwh: float
    dt_hours: float


class BuildingLoadModel:
    """Commercial building electrical load demand model."""

    def __init__(self, config: LocationConfig, max_allowable_power_kw: float = 500.0) -> None:
        """Initialize the Building Load model with validated location configuration.

        Args:
            config: Validated LocationConfig schema instance.
            max_allowable_power_kw: Maximum physical sanity bound [kW] (default: 500 kW).
        """
        self.config = config
        self.archetype = config.building_archetype
        self.peak_demand_kw = self.archetype.peak_electrical_demand_kw
        self.avg_demand_kw = self.archetype.average_electrical_demand_kw
        self.max_allowable_power_kw = max_allowable_power_kw

        logger.debug(
            "Initialized BuildingLoadModel for '%s' (Peak: %.1f kW, Max Bound: %.1f kW)",
            self.archetype.archetype_id, self.peak_demand_kw, self.max_allowable_power_kw
        )

    def validate_demand(self, demand_kw: float) -> float:
        """Validate an active power demand observation.

        Args:
            demand_kw: Active power demand in kilowatts [kW].

        Returns:
            Validated demand in kilowatts [kW].

        Raises:
            PhysicsViolationError: If demand is NaN, infinite, negative, or exceeds physical bounds.
        """
        if math.isnan(demand_kw) or math.isinf(demand_kw):
            raise PhysicsViolationError(
                f"Invalid non-numeric or NaN building demand: {demand_kw}",
                details={"demand_kw": demand_kw},
            )

        if demand_kw < 0.0:
            raise PhysicsViolationError(
                f"Negative building electricity demand violation: {demand_kw:.3f} kW < 0.0",
                details={"demand_kw": demand_kw},
            )

        if demand_kw > self.max_allowable_power_kw:
            raise PhysicsViolationError(
                f"Building demand {demand_kw:.1f} kW exceeds physical sanity bound {self.max_allowable_power_kw:.1f} kW",
                details={"demand_kw": demand_kw, "max_allowable_kw": self.max_allowable_power_kw},
            )

        return float(demand_kw)

    def step(self, demand_kw: float, dt_hours: float = 0.25) -> LoadDemandResult:
        """Process and validate a single simulation interval load demand.

        Args:
            demand_kw: Continuous active power demand [kW >= 0].
            dt_hours: Interval duration in decimal hours [h] (default: 0.25 h).

        Returns:
            LoadDemandResult dataclass.
        """
        valid_kw = self.validate_demand(demand_kw)
        interval_kwh = valid_kw * dt_hours
        return LoadDemandResult(
            load_power_kw=valid_kw,
            interval_energy_kwh=float(interval_kwh),
            dt_hours=float(dt_hours),
        )

    def convert_interval_energy_to_power(self, energy_consumption_kwh: float, dt_hours: float = 0.25) -> float:
        """Convert interval energy consumption into continuous average power.

        Args:
            energy_consumption_kwh: Electrical energy consumed over interval [kWh].
            dt_hours: Interval duration in decimal hours [h] (default: 0.25 h).

        Returns:
            Average active power demand over interval [kW].
        """
        if dt_hours <= 0.0:
            raise ValueError(f"dt_hours must be positive, got {dt_hours}")
        if energy_consumption_kwh < 0.0:
            raise PhysicsViolationError(f"Negative interval energy {energy_consumption_kwh} kWh")
        power_kw = energy_consumption_kwh / dt_hours
        return self.validate_demand(power_kw)

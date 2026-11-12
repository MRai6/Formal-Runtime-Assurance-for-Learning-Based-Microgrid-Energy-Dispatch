"""Deterministic Rule-Based Dispatch Controller for microgrid_sim.

Governing Policy:
    1. Solar-First Demand Fulfillment:
       Available solar PV is prioritized to serve local building electrical demand.

    2. PV Surplus Absorbed by Battery:
       When PV generation exceeds building demand (P_pv > P_load):
       - If SoC < soc_max, dispatch battery to charge at min(P_pv - P_load, P_ch_max).
       - If SoC >= soc_max or battery cannot absorb all surplus, remaining power is
         exported to the grid up to contractual limits (or curtailed at inverter).

    3. PV Deficit Served by Battery:
       When building demand exceeds PV generation (P_load > P_pv):
       - If SoC > soc_min, dispatch battery to discharge at min(P_load - P_pv, P_dis_max).
       - If SoC <= soc_min or deficit exceeds battery capacity, remaining demand is
         supplied via utility grid import up to contractual limits.

    4. Invariant Protection:
       - Simultaneous charging and discharging is strictly avoided (a is a single scalar).
       - Battery SoC bounds [soc_min, soc_max] and power limits are strictly respected.
"""

from dataclasses import dataclass
from typing import Optional, Union
import numpy as np

from microgrid_sim.controllers.base import BaseController
from microgrid_sim.env.spaces import ObsIndex
from microgrid_sim.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RuleBasedControllerConfig:
    """Configurable parameters for rule-based dispatch controller."""
    soc_min: float = 0.15
    soc_max: float = 0.90
    min_power_deadband_kw: float = 0.05
    allow_grid_charging: bool = False
    allow_grid_export_discharge: bool = False


class RuleBasedController(BaseController):
    """Transparent, deterministic rule-based controller for microgrid energy dispatch."""

    def __init__(
        self,
        config: Optional[RuleBasedControllerConfig] = None,
        p_rated_ch_kw: float = 100.0,
        p_rated_dis_kw: float = 100.0,
        p_norm_load_kw: float = 100.0,
        p_norm_pv_kw: float = 120.0,
    ) -> None:
        """Initialize the rule-based controller.

        Args:
            config: Optional RuleBasedControllerConfig instance.
            p_rated_ch_kw: Maximum battery charging power rating [kW] (default: 100.0 kW).
            p_rated_dis_kw: Maximum battery discharging power rating [kW] (default: 100.0 kW).
            p_norm_load_kw: Load normalization factor used in environment observations [kW].
            p_norm_pv_kw: Solar PV normalization factor used in environment observations [kW].
        """
        self.config = config or RuleBasedControllerConfig()
        self.p_rated_ch_kw = float(p_rated_ch_kw)
        self.p_rated_dis_kw = float(p_rated_dis_kw)
        self.p_norm_load_kw = float(p_norm_load_kw)
        self.p_norm_pv_kw = float(p_norm_pv_kw)

        logger.debug(
            "Initialized RuleBasedController: P_ch=%.1f kW, P_dis=%.1f kW, SoC bounds=[%.2f, %.2f]",
            self.p_rated_ch_kw, self.p_rated_dis_kw, self.config.soc_min, self.config.soc_max
        )

    def compute_action(
        self,
        p_pv_kw: float,
        p_load_kw: float,
        soc: float,
    ) -> np.ndarray:
        """Compute dispatch action from raw physical state variables.

        Args:
            p_pv_kw: Available solar PV AC generation potential [kW >= 0].
            p_load_kw: Building active electrical demand [kW >= 0].
            soc: Battery state of charge [0.0, 1.0].

        Returns:
            1-dimensional numpy array with action a in [-1.0, 1.0].
                a > 0: Discharge battery at power a * P_dis_max
                a < 0: Charge battery at power |a| * P_ch_max
                a == 0: Battery idle
        """
        delta_p = float(p_pv_kw - p_load_kw)
        deadband = self.config.min_power_deadband_kw

        if delta_p > deadband:
            # SURPLUS SOLAR (P_pv > P_load):
            # Prioritize charging battery from green surplus
            if soc < self.config.soc_max:
                p_ch_desired = min(delta_p, self.p_rated_ch_kw)
                # Sign convention: charging request is negative
                action_val = - (p_ch_desired / self.p_rated_ch_kw) if self.p_rated_ch_kw > 0.0 else 0.0
            else:
                # Battery full: idle and let excess export to grid or curtail
                action_val = 0.0

        elif delta_p < -deadband:
            # DEFICIT SOLAR (P_load > P_pv):
            # Prioritize discharging battery to meet unmet load
            deficit = abs(delta_p)
            if soc > self.config.soc_min:
                p_dis_desired = min(deficit, self.p_rated_dis_kw)
                # Sign convention: discharging request is positive
                action_val = (p_dis_desired / self.p_rated_dis_kw) if self.p_rated_dis_kw > 0.0 else 0.0
            else:
                # Battery depleted: idle and let grid import meet unmet load
                action_val = 0.0

        else:
            # EXACT BALANCE (within deadband)
            action_val = 0.0

        action_clamped = float(np.clip(action_val, -1.0, 1.0))
        return np.array([action_clamped], dtype=np.float32)

    def act(self, observation: np.ndarray) -> np.ndarray:
        """Compute dispatch control action from Gymnasium observation vector.

        Args:
            observation: Environment observation vector conforming to create_observation_space().

        Returns:
            1-element action vector in [-1.0, 1.0].
        """
        soc = float(observation[ObsIndex.SOC])
        p_load = float(observation[ObsIndex.LOAD_DEMAND]) * self.p_norm_load_kw
        p_pv = float(observation[ObsIndex.PV_POTENTIAL]) * self.p_norm_pv_kw

        return self.compute_action(p_pv_kw=p_pv, p_load_kw=p_load, soc=soc)

    def reset(self) -> None:
        """Reset internal state between episodes (controller is stateless)."""
        pass


"""Microgrid AC bus power balance and conservation calculator for microgrid_sim.

Governing Physical Law (Kirchhoff Active Power Conservation on 480 V AC Bus):
    Every term in the physical power balance equation represents an actual active power flow
    injected into or extracted from the microgrid AC bus:

    Total Physical Injections (Sources) = Total Physical Extractions (Sinks)

    P_pv_ac_delivered + P_grid_import + P_batt_dis_ac + P_diesel
    =
    P_served_load + P_batt_ch_ac + P_grid_export

Where:
    - P_served_load = P_requested_load - P_unserved_load (Unserved load is unmet demand, NOT a physical source).
    - P_pv_ac_delivered = P_pv_ac_potential - P_pv_curtail_ac (Curtailed PV is generation withheld/throttled by the inverter, NOT an AC bus sink).
    - P_grid_import: Contractually bounded power imported through the PCC [kW >= 0].
    - P_grid_export: Contractually bounded surplus power exported through the PCC [kW >= 0].
    - P_batt_dis_ac: AC power delivered by battery PCS [kW >= 0].
    - P_batt_ch_ac: AC power drawn from bus to charge battery via PCS [kW >= 0].
    - P_diesel: Auxiliary backup generation [kW >= 0] (0.0 in active benchmark).

Conservation Invariant:
    Residual = |P_sources - P_sinks| <= tolerance (default: 1.0e-6 kW / 1 mW)
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np

from microgrid_sim.utils.exceptions import ConservationOfEnergyError, PhysicsViolationError
from microgrid_sim.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class PowerBalanceResult:
    """Detailed resolution of microgrid AC bus power balance."""
    # Physical AC Bus Flows
    p_pv_ac_delivered_kw: float
    p_grid_import_kw: float
    p_batt_dis_ac_kw: float
    p_diesel_kw: float
    p_served_load_kw: float
    p_batt_ch_ac_kw: float
    p_grid_export_kw: float

    # Slack / Operational Accounting (Demand & Solar Potential)
    p_requested_load_kw: float
    p_unserved_load_kw: float
    p_pv_ac_potential_kw: float
    p_pv_curtail_ac_kw: float

    # Verification Metrics
    residual_error_kw: float
    is_balanced: bool

    # Backwards-compatible properties
    @property
    def p_load_kw(self) -> float:
        """Alias for requested load demand [kW]."""
        return self.p_requested_load_kw

    @property
    def p_pv_ac_kw(self) -> float:
        """Alias for delivered solar PV AC power [kW]."""
        return self.p_pv_ac_delivered_kw

    @property
    def p_unserved_kw(self) -> float:
        """Alias for unserved load [kW]."""
        return self.p_unserved_load_kw

    @property
    def p_curtail_kw(self) -> float:
        """Alias for AC curtailed solar power [kW]."""
        return self.p_pv_curtail_ac_kw

    @property
    def p_sources_kw(self) -> float:
        """Total AC bus power sources (Delivered PV + Grid Import + Batt Dis + Diesel) [kW]."""
        return (
            self.p_pv_ac_delivered_kw
            + self.p_grid_import_kw
            + self.p_batt_dis_ac_kw
            + self.p_diesel_kw
        )

    @property
    def p_sinks_kw(self) -> float:
        """Total AC bus power sinks (Served Load + Batt Ch + Grid Export) [kW]."""
        return (
            self.p_served_load_kw
            + self.p_batt_ch_ac_kw
            + self.p_grid_export_kw
        )


class PowerBalanceCalculator:
    """Enforces Kirchhoff power balance and resolves physical energy flows on the microgrid AC bus."""

    def __init__(self, numerical_tolerance_kw: float = 1.0e-6) -> None:
        """Initialize the power balance calculator.

        Args:
            numerical_tolerance_kw: Maximum allowable residual power [kW] (default: 1.0e-6 kW = 1 mW).
        """
        self.tolerance_kw = numerical_tolerance_kw

    def resolve_balance(
        self,
        p_load_kw: float,
        p_pv_ac_kw: float,
        p_batt_ch_ac_kw: float,
        p_batt_dis_ac_kw: float,
        max_grid_import_kw: float,
        max_grid_export_kw: float,
        p_diesel_kw: float = 0.0,
    ) -> PowerBalanceResult:
        """Resolve instantaneous AC bus balance and compute import, export, unserved load, and curtailment.

        Args:
            p_load_kw: Building electrical demand requested [kW >= 0].
            p_pv_ac_kw: Potential solar PV power available from inverter prior to bus-level curtailment [kW >= 0].
            p_batt_ch_ac_kw: Battery charging power absorbed from AC bus [kW >= 0].
            p_batt_dis_ac_kw: Battery discharging power injected into AC bus [kW >= 0].
            max_grid_import_kw: Contractual maximum grid import capacity [kW >= 0].
            max_grid_export_kw: Contractual maximum grid export capacity [kW >= 0].
            p_diesel_kw: Optional backup generator power [kW >= 0] (default: 0.0 kW).

        Returns:
            PowerBalanceResult dataclass containing resolved physical flows and residual.

        Raises:
            PhysicsViolationError: If any input power is negative or physically inconsistent.
            ConservationOfEnergyError: If power conservation is algebraically violated.
        """
        # Validate non-negativity of all inputs
        inputs = {
            "p_load_kw": p_load_kw,
            "p_pv_ac_kw": p_pv_ac_kw,
            "p_batt_ch_ac_kw": p_batt_ch_ac_kw,
            "p_batt_dis_ac_kw": p_batt_dis_ac_kw,
            "max_grid_import_kw": max_grid_import_kw,
            "max_grid_export_kw": max_grid_export_kw,
            "p_diesel_kw": p_diesel_kw,
        }
        for name, val in inputs.items():
            if val < 0.0:
                raise PhysicsViolationError(
                    f"Negative power quantity '{name}' = {val} kW violates physical non-negativity law",
                    details=inputs,
                )

        # Enforce battery mutual exclusivity on the AC bus
        if p_batt_ch_ac_kw > 0.0 and p_batt_dis_ac_kw > 0.0:
            raise PhysicsViolationError(
                f"Simultaneous battery charging ({p_batt_ch_ac_kw} kW) and discharging ({p_batt_dis_ac_kw} kW) violation"
            )

        # Potential net load to be served
        # P_net > 0 means demand exceeds local generation (deficit)
        # P_net < 0 means local generation exceeds demand (surplus)
        p_net = (p_load_kw + p_batt_ch_ac_kw) - (p_pv_ac_kw + p_batt_dis_ac_kw + p_diesel_kw)

        if p_net > 0.0:
            # DEFICIT: All available PV is delivered to the bus
            p_pv_delivered = p_pv_ac_kw
            p_pv_curtail = 0.0
            p_export = 0.0

            # Grid import supplies deficit up to contractual limit
            p_import = min(max_grid_import_kw, p_net)
            # Remaining unmet deficit cannot be served by grid
            p_unserved = max(0.0, p_net - max_grid_import_kw)
            p_served_load = p_load_kw - p_unserved

        elif p_net < 0.0:
            # SURPLUS: All load is served fully (zero unserved load)
            p_served_load = p_load_kw
            p_unserved = 0.0
            p_import = 0.0

            surplus = abs(p_net)
            # Grid export absorbs surplus up to contractual limit
            p_export = min(max_grid_export_kw, surplus)
            # Excess surplus that cannot be exported must be curtailed at the PV inverter
            p_pv_curtail = max(0.0, surplus - max_grid_export_kw)
            # Actual delivered PV to AC bus is reduced by the curtailed amount
            p_pv_delivered = p_pv_ac_kw - p_pv_curtail

        else:
            # EXACT BALANCE
            p_served_load = p_load_kw
            p_unserved = 0.0
            p_pv_delivered = p_pv_ac_kw
            p_pv_curtail = 0.0
            p_import = 0.0
            p_export = 0.0

        # Enforce exact Kirchhoff active power conservation:
        # P_sources = P_pv_delivered + P_grid_import + P_batt_dis_ac + P_diesel
        # P_sinks   = P_served_load + P_batt_ch_ac + P_grid_export
        sources = p_pv_delivered + p_batt_dis_ac_kw + p_import + p_diesel_kw
        sinks = p_served_load + p_batt_ch_ac_kw + p_export
        residual = abs(sources - sinks)

        if residual > self.tolerance_kw:
            raise ConservationOfEnergyError(
                f"Microgrid AC bus power conservation violated: residual {residual:.2e} kW exceeds tolerance {self.tolerance_kw:.2e} kW",
                details={
                    "sources_kw": sources,
                    "sinks_kw": sinks,
                    "residual_kw": residual,
                    "tolerance_kw": self.tolerance_kw,
                },
            )

        return PowerBalanceResult(
            p_pv_ac_delivered_kw=float(p_pv_delivered),
            p_grid_import_kw=float(p_import),
            p_batt_dis_ac_kw=float(p_batt_dis_ac_kw),
            p_diesel_kw=float(p_diesel_kw),
            p_served_load_kw=float(p_served_load),
            p_batt_ch_ac_kw=float(p_batt_ch_ac_kw),
            p_grid_export_kw=float(p_export),
            p_requested_load_kw=float(p_load_kw),
            p_unserved_load_kw=float(p_unserved),
            p_pv_ac_potential_kw=float(p_pv_ac_kw),
            p_pv_curtail_ac_kw=float(p_pv_curtail),
            residual_error_kw=float(residual),
            is_balanced=bool(residual <= self.tolerance_kw),
        )

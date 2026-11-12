"""Battery Energy Storage System (BESS) physical model for microgrid_sim.

Governing Physical Equations:
    1. Sign Convention:
       - In signed power representation P_batt:
         P_batt > 0: Discharging (acting as a source, injecting power to microgrid).
         P_batt < 0: Charging (acting as a sink, absorbing power from microgrid).
         P_batt = 0: Idle.
       - In dual-variable representation (P_ch, P_dis):
         P_ch >= 0 (charging power), P_dis >= 0 (discharging power).
         Mutual exclusivity: P_ch * P_dis = 0.

    2. Dynamic Feasibility Limits (SoC Envelope Protection):
       - Maximum feasible charge power over interval dt without exceeding SoC_max:
         P_ch_max_dyn = min(P_ch_max, [(SoC_max - SoC * (1 - sigma_sd * dt)) * E_nom] / (eta_ch * dt))
       - Maximum feasible discharge power over interval dt without breaching SoC_min:
         P_dis_max_dyn = min(P_dis_max, [(SoC * (1 - sigma_sd * dt) - SoC_min) * E_nom * eta_dis] / dt)

    3. Energy Conservation & Conversion Losses:
       - Energy absorbed during charging: E_terminal_ch = P_ch * dt [kWh]
         Internal cell energy stored:     E_cell_ch = E_terminal_ch * eta_ch [kWh]
         Conversion loss:                 E_loss_ch = E_terminal_ch * (1 - eta_ch) [kWh]
       - Energy delivered during discharge: E_terminal_dis = P_dis * dt [kWh]
         Internal cell energy extracted:    E_cell_dis = E_terminal_dis / eta_dis [kWh]
         Conversion loss:                   E_loss_dis = E_cell_dis - E_terminal_dis [kWh]
       - Self-discharge loss:
         E_loss_sd = SoC * E_nom * sigma_sd * dt [kWh]

    4. State of Charge Evolution:
       SoC(t + dt) = SoC(t) * (1 - sigma_sd * dt) + (E_cell_ch - E_cell_dis) / E_nom

    5. Energy Balance Invariant on Executed Power:
       E_terminal_executed = Delta_E_stored + E_losses_total
       Unexecutable requested energy is tracked explicitly as E_rejected and is NOT absorbed or created.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np

from microgrid_sim.config.schemas import BatteryConfig
from microgrid_sim.utils.exceptions import PhysicsViolationError
from microgrid_sim.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class BatteryStepResult:
    """Detailed physical outputs and telemetry from a single battery simulation step."""
    requested_power_kw: float
    executed_power_kw: float
    rejected_power_kw: float
    energy_rejected_kwh: float
    soc_before: float
    soc_after: float
    energy_charged_kwh: float
    energy_discharged_kwh: float
    internal_energy_stored_kwh: float
    internal_energy_extracted_kwh: float
    losses_kwh: float
    constraint_encountered: str
    wear_cost_usd: float


class BatteryModel:
    """Physics-based Battery Energy Storage System (BESS) model.

    Enforces dynamic SoC limits, conversion efficiencies, self-discharge,
    and mechanical/economic wear accounting.
    """

    def __init__(self, config: BatteryConfig, timestep_hours: float = 0.25) -> None:
        """Initialize the BESS model with validated configuration.

        Args:
            config: Validated BatteryConfig schema instance.
            timestep_hours: Simulation timestep duration [hours] (default: 0.25 h / 15 min).
        """
        self.config = config
        self.dt = timestep_hours

        # Capacity & SoC boundaries
        self.nominal_energy_kwh = config.capacity.nominal_energy_kwh
        self.min_soc = config.capacity.minimum_soc
        self.max_soc = config.capacity.maximum_soc
        self.soc = config.capacity.initial_soc

        # Power ratings
        self.max_p_ch = config.power_and_thermal.max_charge_power_kw
        self.max_p_dis = config.power_and_thermal.max_discharge_power_kw

        # Efficiencies & Self-Discharge
        self.eta_ch = config.performance.charging_efficiency
        self.eta_dis = config.performance.discharging_efficiency
        self.sigma_sd = config.performance.self_discharge_rate_per_hour

        # Degradation parameters
        self.wear_cost_per_kwh = config.degradation.implied_wear_cost_usd_per_kwh
        self.cycle_life_to_eol = config.degradation.cycle_life_to_eol

        # Cumulative tracking
        self.cumulative_energy_charged_kwh = 0.0
        self.cumulative_energy_discharged_kwh = 0.0
        self.cumulative_losses_kwh = 0.0
        self.cumulative_wear_cost_usd = 0.0

        logger.debug(
            "Initialized BatteryModel: %.1f kWh capacity, SoC in [%.2f, %.2f], Initial SoC: %.2f",
            self.nominal_energy_kwh, self.min_soc, self.max_soc, self.soc
        )

    def get_dynamic_power_limits(self, current_soc: float) -> Tuple[float, float]:
        """Compute maximum allowable charging and discharging power over interval dt.

        Ensures that applying the returned power limits strictly preserves the
        configured operational SoC envelope [min_soc, max_soc].

        Args:
            current_soc: Current battery State of Charge [0.0, 1.0].

        Returns:
            Tuple of (p_ch_max_dyn, p_dis_max_dyn) in [kW].
        """
        # Account for self-discharge over the timestep
        soc_decayed = current_soc * (1.0 - self.sigma_sd * self.dt)

        # Max charge power limited by max_soc and charge power rating
        headroom_soc = max(0.0, self.max_soc - soc_decayed)
        p_ch_dyn = (headroom_soc * self.nominal_energy_kwh) / (self.eta_ch * self.dt)
        p_ch_max_dyn = min(self.max_p_ch, p_ch_dyn)

        # Max discharge power limited by min_soc and discharge power rating
        available_soc = max(0.0, soc_decayed - self.min_soc)
        p_dis_dyn = (available_soc * self.nominal_energy_kwh * self.eta_dis) / self.dt
        p_dis_max_dyn = min(self.max_p_dis, p_dis_dyn)

        return float(max(0.0, p_ch_max_dyn)), float(max(0.0, p_dis_max_dyn))

    def step(self, requested_power_kw: float) -> BatteryStepResult:
        """Execute battery simulation step using signed power convention.

        Convention:
            requested_power_kw > 0: Discharging request (delivering power to microgrid).
            requested_power_kw < 0: Charging request (absorbing power from microgrid).
            requested_power_kw == 0: Idle request.

        Args:
            requested_power_kw: Requested battery active power [kW].

        Returns:
            BatteryStepResult dataclass containing execution details.
        """
        soc_before = self.soc
        p_ch_dyn, p_dis_dyn = self.get_dynamic_power_limits(soc_before)

        constraint = "NONE"
        actual_p_ch = 0.0
        actual_p_dis = 0.0

        if requested_power_kw < 0.0:
            # Charging request: requested_power_kw is negative
            req_ch = abs(requested_power_kw)
            if req_ch > self.max_p_ch:
                constraint = "MAX_CHARGE_POWER"
            actual_p_ch = min(req_ch, p_ch_dyn)
            if actual_p_ch < req_ch and constraint == "NONE":
                constraint = "MAX_SOC"
            executed_power = -actual_p_ch

        elif requested_power_kw > 0.0:
            # Discharging request: requested_power_kw is positive
            req_dis = requested_power_kw
            if req_dis > self.max_p_dis:
                constraint = "MAX_DISCHARGE_POWER"
            actual_p_dis = min(req_dis, p_dis_dyn)
            if actual_p_dis < req_dis and constraint == "NONE":
                constraint = "MIN_SOC"
            executed_power = actual_p_dis

        else:
            executed_power = 0.0

        # Rejected unexecuted power and energy (strictly non-negative magnitude)
        rejected_power_kw = max(0.0, abs(requested_power_kw) - abs(executed_power))
        energy_rejected_kwh = float(rejected_power_kw * self.dt)

        # Energy quantities over timestep dt
        e_terminal_ch = actual_p_ch * self.dt
        e_terminal_dis = actual_p_dis * self.dt

        e_cell_ch = e_terminal_ch * self.eta_ch
        e_cell_dis = e_terminal_dis / self.eta_dis if self.eta_dis > 0.0 else 0.0

        loss_ch = e_terminal_ch * (1.0 - self.eta_ch)
        loss_dis = e_cell_dis - e_terminal_dis
        loss_sd = soc_before * self.nominal_energy_kwh * self.sigma_sd * self.dt
        step_losses = loss_ch + loss_dis + loss_sd

        # State of charge evolution
        soc_after = soc_before * (1.0 - self.sigma_sd * self.dt) + (e_cell_ch - e_cell_dis) / self.nominal_energy_kwh
        # Numerical guard: clamp within boundaries
        soc_after = float(min(max(soc_after, self.min_soc), self.max_soc))
        self.soc = soc_after

        # Economic degradation wear
        wear_cost = (e_terminal_ch + e_terminal_dis) * self.wear_cost_per_kwh

        # Cumulative updates
        self.cumulative_energy_charged_kwh += e_terminal_ch
        self.cumulative_energy_discharged_kwh += e_terminal_dis
        self.cumulative_losses_kwh += step_losses
        self.cumulative_wear_cost_usd += wear_cost

        return BatteryStepResult(
            requested_power_kw=float(requested_power_kw),
            executed_power_kw=float(executed_power),
            rejected_power_kw=float(rejected_power_kw),
            energy_rejected_kwh=float(energy_rejected_kwh),
            soc_before=float(soc_before),
            soc_after=float(soc_after),
            energy_charged_kwh=float(e_terminal_ch),
            energy_discharged_kwh=float(e_terminal_dis),
            internal_energy_stored_kwh=float(e_cell_ch),
            internal_energy_extracted_kwh=float(e_cell_dis),
            losses_kwh=float(step_losses),
            constraint_encountered=constraint,
            wear_cost_usd=float(wear_cost),
        )

    def step_ch_dis(
        self,
        charge_power_kw: float = 0.0,
        discharge_power_kw: float = 0.0,
        **kwargs: float,
    ) -> BatteryStepResult:
        """Execute step using explicit separate charging and discharging inputs.

        Enforces mutual exclusivity (P_ch * P_dis = 0).

        Args:
            charge_power_kw: Requested charging power [kW >= 0].
            discharge_power_kw: Requested discharging power [kW >= 0].
            **kwargs: Backward-compatible keyword arguments ('p_ch_kw', 'p_dis_kw').

        Returns:
            BatteryStepResult dataclass.

        Raises:
            PhysicsViolationError: If simultaneous charge and discharge is requested, or if inputs are negative.
        """
        ch = float(kwargs.get("p_ch_kw", charge_power_kw))
        dis = float(kwargs.get("p_dis_kw", discharge_power_kw))

        if ch < 0.0 or dis < 0.0:
            raise PhysicsViolationError(
                f"Negative power inputs to step_ch_dis: charge={ch}, discharge={dis}"
            )

        if ch > 0.0 and dis > 0.0:
            raise PhysicsViolationError(
                f"Simultaneous battery charging ({ch} kW) and discharging ({dis} kW) violation"
            )

        if ch > 0.0:
            return self.step(-ch)
        elif dis > 0.0:
            return self.step(dis)
        else:
            return self.step(0.0)

"""Power Conversion System (Inverter and PCS) physical model for microgrid_sim.

Governing Equations and Scientific Classification:
    1. Solar PV Inverter (Unidirectional DC to AC):
       - Part-load ratio:
           p_pu = P_dc_accepted / P_rated_ac
       - Empirical Quadratic Part-Load Efficiency Model:
           Loss_poly = c0 + c1 * (p_pu - 1.0)^2
           eta_inv = eta_nom * (1.0 - Loss_poly)

       Scientific Note on Model Classification:
       This formulation is an Empirical Quadratic Part-Load Model, NOT the 6-parameter
       empirical Sandia Performance Model for Grid-Connected Photovoltaic Inverters
       (Sandia Report SAND2004-5221 / California Energy Commission).
       Under standard benchmark configuration (eta_nom=0.975, c0=0.015, c1=0.035):
       At rated load (p_pu = 1.0), the quadratic term vanishes, and the baseline loss
       offset c0=0.015 yields an effective efficiency of:
           eta(1.0) = 0.975 * (1.0 - 0.015) = 0.975 * 0.985 = 0.960375 (~96.04%)
       The nominal parameter eta_nom = 0.975 represents the theoretical asymptotic ceiling
       before baseline conduction and curvature deductions are evaluated.

       - Exact Energy and Power Separation:
           P_dc_clipped = max(0.0, P_dc_input - P_max_dc)
           P_dc_accepted = min(P_dc_input, P_max_dc)
           eta_inv = calculate_pv_efficiency(P_dc_accepted)
           P_ac_potential = P_dc_accepted * eta_inv
           P_loss_thermal = P_dc_accepted * (1.0 - eta_inv)
           P_ac_clipped = max(0.0, P_ac_potential - P_rated_ac)
           P_ac_output = min(P_rated_ac, P_ac_potential)
           P_curtailed = P_dc_clipped + P_ac_clipped

       - Conservation of Energy Identity:
           P_dc_input == P_ac_output + P_loss_thermal + P_curtailed

    2. Battery Power Conversion System (PCS, Bidirectional AC-DC):
       - Distinct from PV Inverter with independent electrical parameters:
           P_rated_pcs = 100.0 kW_ac, eta_pcs = 0.96
       - Discharging (DC to AC):
           P_ac_raw = P_dc_dis * eta_pcs
           P_ac_dis = min(P_rated_pcs, P_ac_raw)
           P_clipped_dis = max(0.0, P_ac_raw - P_rated_pcs)
           P_loss_dis = P_dc_dis * (1.0 - eta_pcs)
       - Charging (AC to DC):
           P_ac_ch_clipped = min(P_rated_pcs, P_ac_ch)
           P_clipped_ch = max(0.0, P_ac_ch - P_rated_pcs)
           P_dc_ch = P_ac_ch_clipped * eta_pcs
           P_loss_ch = P_ac_ch_clipped * (1.0 - eta_pcs)

    3. Apparent Power Limit (IEEE 1547):
       S = sqrt(P^2 + Q^2) <= S_max. At unity power factor (Q = 0), P <= S_max.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np

from microgrid_sim.config.schemas import InverterConfig
from microgrid_sim.utils.exceptions import PhysicsViolationError
from microgrid_sim.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class PVInverterResult:
    """Detailed outputs from solar PV inverter conversion."""
    p_dc_input_kw: float
    p_ac_output_kw: float
    p_curtailed_kw: float
    p_loss_kw: float
    efficiency: float
    is_clipped: bool
    p_dc_clipped_kw: float = 0.0
    p_ac_clipped_kw: float = 0.0


@dataclass(frozen=True)
class BatteryPCSResult:
    """Detailed outputs from battery power conversion system (PCS)."""
    mode: str  # "CHARGING", "DISCHARGING", "IDLE"
    p_ac_kw: float
    p_dc_kw: float
    p_loss_kw: float
    efficiency: float
    is_clipped: bool
    p_clipped_kw: float = 0.0


class InverterModel:
    """Physics-based Power Conversion System for Solar PV and Battery BESS.

    Implements empirical quadratic part-load efficiency modeling for the PV inverter and
    dedicated bidirectional conversion for the battery PCS.
    """

    def __init__(self, config: InverterConfig) -> None:
        """Initialize the inverter model with validated configuration.

        Args:
            config: Validated InverterConfig schema instance.
        """
        self.config = config

        # PV Inverter ratings & empirical part-load parameters
        self.p_rated_pv_ac = config.ratings.rated_ac_power_kw
        self.s_rated_pv_kva = config.ratings.rated_apparent_power_kva
        self.max_dc_input_kw = config.ratings.max_dc_input_power_kw
        self.eta_nom = config.efficiency_model.nominal_peak_efficiency
        self.c0 = config.efficiency_model.curvature_coefficient_c0
        self.c1 = config.efficiency_model.curvature_coefficient_c1

        # Battery PCS ratings
        self.p_rated_batt_ac = config.battery_inverter.rated_ac_power_kw
        self.eta_batt_pcs = config.battery_inverter.bidirectional_efficiency

        logger.debug(
            "Initialized InverterModel: PV AC=%.1f kW (eta_nom=%.3f, rated eta=%.4f), Battery PCS AC=%.1f kW (eta=%.3f)",
            self.p_rated_pv_ac, self.eta_nom, self.eta_nom * (1.0 - self.c0), self.p_rated_batt_ac, self.eta_batt_pcs
        )

    def calculate_pv_efficiency(self, dc_power_kw: float) -> float:
        """Compute non-linear conversion efficiency for solar PV inverter.

        Uses an Empirical Quadratic Part-Load Model:
            p_pu = dc_power_kw / p_rated_pv_ac
            loss = c0 + c1 * (p_pu - 1.0)^2
            eta = eta_nom * (1.0 - loss)

        Note: At p_pu = 1.0, eta = eta_nom * (1 - c0) = 0.975 * (1 - 0.015) = 0.960375.

        Args:
            dc_power_kw: DC input power accepted by the inverter front-end [kW].

        Returns:
            Inverter efficiency [0.0, 1.0].
        """
        if dc_power_kw <= 0.0:
            return 0.0

        p_pu = dc_power_kw / self.p_rated_pv_ac
        loss = self.c0 + self.c1 * ((p_pu - 1.0) ** 2)
        eta = self.eta_nom * (1.0 - loss)
        return float(min(max(eta, 0.0), 1.0))

    def convert_pv_dc_to_ac(self, dc_power_kw: float) -> PVInverterResult:
        """Convert solar DC generation to AC grid-frequency power with explicit clipping.

        Delineates:
        1. DC-side front-end clipping: Exceeding max_dc_input_kw.
        2. Thermal dissipation loss: Conduction and switching loss P_accepted * (1 - eta).
        3. AC-side capacity clipping: Inverter thermal/apparent capacity clamp.

        Energy conservation identity:
            P_dc_input == P_ac_output + P_loss_kw + P_curtailed_kw
        where P_curtailed_kw = P_dc_clipped_kw + P_ac_clipped_kw.

        Args:
            dc_power_kw: Solar array DC output power [kW_dc >= 0].

        Returns:
            PVInverterResult dataclass with detailed power flows.
        """
        if dc_power_kw < 0.0:
            raise PhysicsViolationError(
                f"Negative DC power input {dc_power_kw} kW to PV inverter",
                details={"dc_power_kw": dc_power_kw},
            )

        if dc_power_kw == 0.0:
            return PVInverterResult(
                p_dc_input_kw=0.0,
                p_ac_output_kw=0.0,
                p_curtailed_kw=0.0,
                p_loss_kw=0.0,
                efficiency=0.0,
                is_clipped=False,
                p_dc_clipped_kw=0.0,
                p_ac_clipped_kw=0.0,
            )

        # 1. DC-side front-end clipping
        if dc_power_kw > self.max_dc_input_kw:
            p_dc_accepted = self.max_dc_input_kw
            p_dc_clipped = dc_power_kw - self.max_dc_input_kw
        else:
            p_dc_accepted = dc_power_kw
            p_dc_clipped = 0.0

        # 2. Conversion efficiency and thermal losses on accepted DC power
        eta = self.calculate_pv_efficiency(p_dc_accepted)
        p_ac_potential = p_dc_accepted * eta
        p_loss = p_dc_accepted * (1.0 - eta)

        # 3. AC-side capacity clipping at rated AC capacity (and apparent power limit at unity PF)
        ac_limit = min(self.p_rated_pv_ac, self.s_rated_pv_kva)
        if p_ac_potential > ac_limit:
            p_ac_output = ac_limit
            p_ac_clipped = p_ac_potential - ac_limit
            is_clipped = True
        else:
            p_ac_output = p_ac_potential
            p_ac_clipped = 0.0
            is_clipped = (p_dc_clipped > 0.0)

        p_curtailed = p_dc_clipped + p_ac_clipped

        return PVInverterResult(
            p_dc_input_kw=float(dc_power_kw),
            p_ac_output_kw=float(p_ac_output),
            p_curtailed_kw=float(p_curtailed),
            p_loss_kw=float(p_loss),
            efficiency=float(eta),
            is_clipped=is_clipped or (p_curtailed > 0.0),
            p_dc_clipped_kw=float(p_dc_clipped),
            p_ac_clipped_kw=float(p_ac_clipped),
        )

    def convert_battery_discharge_dc_to_ac(self, p_batt_dc_dis_kw: float) -> BatteryPCSResult:
        """Convert battery DC discharge power to AC microgrid power via battery PCS.

        Args:
            p_batt_dc_dis_kw: Battery discharging power from DC side [kW >= 0].

        Returns:
            BatteryPCSResult dataclass.
        """
        if p_batt_dc_dis_kw < 0.0:
            raise PhysicsViolationError(f"Negative DC discharge power {p_batt_dc_dis_kw} kW")

        if p_batt_dc_dis_kw == 0.0:
            return BatteryPCSResult("IDLE", 0.0, 0.0, 0.0, self.eta_batt_pcs, False, 0.0)

        p_ac_raw = p_batt_dc_dis_kw * self.eta_batt_pcs
        p_loss = p_batt_dc_dis_kw * (1.0 - self.eta_batt_pcs)

        if p_ac_raw > self.p_rated_batt_ac:
            p_ac = self.p_rated_batt_ac
            p_clipped = p_ac_raw - self.p_rated_batt_ac
            is_clipped = True
        else:
            p_ac = p_ac_raw
            p_clipped = 0.0
            is_clipped = False

        return BatteryPCSResult(
            mode="DISCHARGING",
            p_ac_kw=float(p_ac),
            p_dc_kw=float(p_batt_dc_dis_kw),
            p_loss_kw=float(p_loss),
            efficiency=float(self.eta_batt_pcs),
            is_clipped=is_clipped,
            p_clipped_kw=float(p_clipped),
        )

    def convert_battery_charge_ac_to_dc(self, p_batt_ac_ch_kw: float) -> BatteryPCSResult:
        """Convert AC microgrid power to battery DC charging power via battery PCS.

        Args:
            p_batt_ac_ch_kw: Charging power drawn from AC bus [kW >= 0].

        Returns:
            BatteryPCSResult dataclass.
        """
        if p_batt_ac_ch_kw < 0.0:
            raise PhysicsViolationError(f"Negative AC charge power {p_batt_ac_ch_kw} kW")

        if p_batt_ac_ch_kw == 0.0:
            return BatteryPCSResult("IDLE", 0.0, 0.0, 0.0, self.eta_batt_pcs, False, 0.0)

        # Clip AC input at PCS rating
        if p_batt_ac_ch_kw > self.p_rated_batt_ac:
            p_ac_actual = self.p_rated_batt_ac
            p_clipped = p_batt_ac_ch_kw - self.p_rated_batt_ac
            is_clipped = True
        else:
            p_ac_actual = p_batt_ac_ch_kw
            p_clipped = 0.0
            is_clipped = False

        p_dc = p_ac_actual * self.eta_batt_pcs
        p_loss = p_ac_actual * (1.0 - self.eta_batt_pcs)

        return BatteryPCSResult(
            mode="CHARGING",
            p_ac_kw=float(p_ac_actual),
            p_dc_kw=float(p_dc),
            p_loss_kw=float(p_loss),
            efficiency=float(self.eta_batt_pcs),
            is_clipped=is_clipped,
            p_clipped_kw=float(p_clipped),
        )

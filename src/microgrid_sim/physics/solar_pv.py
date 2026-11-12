"""Solar Photovoltaic (PV) physical conversion and performance model.

Governing Physical Models:
    1. Transposition Model (Liu & Jordan 1960 / Duffie & Beckman 2013):
       G_poa = G_beam_poa + G_diff_poa + G_gnd_poa
       - G_beam_poa = DNI * max(0, cos(theta))
       - G_diff_poa = DHI * ((1 + cos(beta)) / 2)
       - G_gnd_poa  = GHI * albedo * ((1 - cos(beta)) / 2)
       where:
         theta: Angle of incidence between direct solar beam and tilted module normal.
         beta: Surface tilt angle from horizontal [rad].
         cos(theta) = cos(theta_z)*cos(beta) + sin(theta_z)*sin(beta)*cos(gamma_s - gamma)
         theta_z: Solar zenith angle [rad] (0 = zenith, pi/2 = horizon).
         gamma_s: Solar azimuth angle [rad] (convention: 0 = North, pi = South).
         gamma: Surface azimuth angle [rad] (convention: 180° = Due South).

    2. Cell Temperature Model (King, Boyson, & Kratochvil 2004 / Evans 1981 NOCT):
       T_cell = T_amb + G_poa * ((NOCT - 20) / 800) * (1 - eta_stc / (tau_alpha))
       where:
         NOCT: Nominal Operating Cell Temperature [°C] (typically 45°C).
         eta_stc: Nameplate module conversion efficiency at STC (typically 0.20).
         tau_alpha: Effective transmittance-absorptance product (typically 0.90).

    3. DC Power & Temperature Derating (IEC 60904-3 / Sandia Array Performance Model):
       P_dc_raw = P_stc * (G_poa / G_stc) * [1 + gamma_pmp * (T_cell - T_stc)] * f_derate
       P_dc = min(P_dc_max, max(0.0, P_dc_raw))
       where:
         P_stc: Nameplate DC capacity at STC [kW_dc] (120 kW).
         G_stc: Reference solar irradiance at STC (1000 W/m²).
         T_stc: Reference cell temperature at STC (25°C).
         gamma_pmp: Maximum power temperature coefficient [1/°C] (-0.0038 /°C).
         f_derate: Balance-of-system derate factor (0.95 accounts for wiring, soiling, mismatch).
         P_dc_max: Maximum array DC clipping limit [kW_dc].
"""

from dataclasses import dataclass
import math
from typing import Optional
import numpy as np
import pandas as pd

from microgrid_sim.config.schemas import PVConfig
from microgrid_sim.utils.exceptions import PhysicsViolationError
from microgrid_sim.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class PVGenerationResult:
    """Detailed physical outputs from the solar PV generation model."""
    poa_irradiance_w_per_m2: float
    poa_beam_w_per_m2: float
    poa_diffuse_w_per_m2: float
    poa_ground_w_per_m2: float
    cell_temperature_c: float
    dc_power_kw: float
    dc_power_unclipped_kw: float
    curtailed_dc_power_kw: float
    is_clipped: bool


class SolarPVModel:
    """Physics-based Solar Photovoltaic (PV) array model.

    Implements plane-of-array transposition, empirical NOCT cell temperature
    estimation, temperature-dependent DC power conversion, and DC capacity clipping.
    """

    def __init__(
        self,
        config: PVConfig,
        latitude_deg: float = 39.7420,
        longitude_deg: float = -105.1800,
    ) -> None:
        """Initialize the Solar PV model with validated configuration.

        Args:
            config: Validated PVConfig schema instance.
            latitude_deg: Geographical latitude of the installation [°N] (default: Golden, CO 39.7420°).
            longitude_deg: Geographical longitude of the installation [°E] (default: Golden, CO -105.1800°).
        """
        self.config = config
        self.latitude_deg = latitude_deg
        self.longitude_deg = longitude_deg

        # Capacity parameters
        self.rated_capacity_kw = config.capacity.rated_dc_capacity_kw
        self.p_dc_max = self.rated_capacity_kw  # DC clipping limit

        # Orientation & Geometry
        self.tilt_deg = config.orientation.tilt_degrees
        self.tilt_rad = math.radians(self.tilt_deg)
        self.azimuth_deg = config.orientation.azimuth_degrees
        self.azimuth_rad = math.radians(self.azimuth_deg)
        self.albedo = config.orientation.ground_albedo

        # Thermal & Electrical parameters
        self.g_stc = config.thermal_and_electrical.stc_irradiance_w_per_m2
        self.t_stc = config.thermal_and_electrical.stc_cell_temperature_c
        self.noct = config.thermal_and_electrical.noct_temperature_c
        self.gamma_pmp = config.thermal_and_electrical.temperature_coefficient_pmp_per_c
        self.eta_stc = config.thermal_and_electrical.stc_module_efficiency
        self.tau_alpha = config.thermal_and_electrical.transmittance_absorptance_product

        # Balance-of-system derate factor
        self.f_derate = config.losses.bos_derate_factor

        logger.debug(
            "Initialized SolarPVModel: %.1f kW DC capacity, tilt=%.2f°, azimuth=%.2f°, derate=%.2f",
            self.rated_capacity_kw, self.tilt_deg, self.azimuth_deg, self.f_derate,
        )

    def calculate_solar_azimuth(self, timestamp: pd.Timestamp, solar_zenith_deg: float) -> float:
        """Estimate solar azimuth angle in degrees [0, 360) using solar geometry.

        Convention: 0° = North, 90° = East, 180° = South, 270° = West.

        Args:
            timestamp: Timezone-aware UTC timestamp.
            solar_zenith_deg: Solar zenith angle [°].

        Returns:
            Solar azimuth angle in degrees [0, 360).
        """
        # Day of year and decimal solar hour
        d = timestamp.dayofyear
        hour_utc = timestamp.hour + timestamp.minute / 60.0 + timestamp.second / 3600.0
        # Local solar time approximation from longitude
        lstm = 15.0 * round(self.longitude_deg / 15.0)
        eot_minutes = 9.87 * math.sin(math.radians(2 * (360.0 * (d - 81) / 365.0))) - \
                      7.53 * math.cos(math.radians(360.0 * (d - 81) / 365.0)) - \
                      1.5 * math.sin(math.radians(360.0 * (d - 81) / 365.0))
        time_offset_hours = (4.0 * (self.longitude_deg - lstm) + eot_minutes) / 60.0
        solar_time_hours = (hour_utc + self.longitude_deg / 15.0) % 24.0

        # Hour angle (omega: 0 at solar noon, negative in morning, positive in afternoon)
        omega_deg = (solar_time_hours - 12.0) * 15.0
        omega_rad = math.radians(omega_deg)

        # Solar declination
        decl_rad = math.radians(23.45 * math.sin(math.radians(360.0 * (284 + d) / 365.0)))
        lat_rad = math.radians(self.latitude_deg)
        zenith_rad = math.radians(solar_zenith_deg)

        # Solar azimuth calculation
        cos_zenith = math.cos(zenith_rad)
        sin_zenith = math.sin(zenith_rad)
        if sin_zenith < 1.0e-5:
            return 180.0  # Sun at zenith

        cos_azimuth = (cos_zenith * math.sin(lat_rad) - math.sin(decl_rad)) / (sin_zenith * math.cos(lat_rad))
        cos_azimuth = min(max(cos_azimuth, -1.0), 1.0)
        azimuth_rad = math.acos(cos_azimuth)

        if omega_deg > 0:
            azimuth_deg = 180.0 + math.degrees(azimuth_rad)
        else:
            azimuth_deg = 180.0 - math.degrees(azimuth_rad)

        return float(azimuth_deg % 360.0)

    def calculate_poa_irradiance(
        self,
        ghi_w_per_m2: float,
        dni_w_per_m2: float,
        dhi_w_per_m2: float,
        solar_zenith_deg: float,
        solar_azimuth_deg: Optional[float] = None,
        timestamp: Optional[pd.Timestamp] = None,
    ) -> tuple[float, float, float, float]:
        """Compute plane-of-array (POA) solar irradiance using the Liu-Jordan transposition model.

        Args:
            ghi_w_per_m2: Global Horizontal Irradiance [W/m²].
            dni_w_per_m2: Direct Normal Irradiance [W/m²].
            dhi_w_per_m2: Diffuse Horizontal Irradiance [W/m²].
            solar_zenith_deg: Solar zenith angle [°] (0 = overhead, 90 = horizon).
            solar_azimuth_deg: Optional solar azimuth angle [°] (0 = North, 180 = South).
            timestamp: Optional timestamp used to compute solar azimuth if omitted.

        Returns:
            Tuple of (G_poa, G_beam_poa, G_diff_poa, G_gnd_poa) in [W/m²].
        """
        # Physical input validation
        if ghi_w_per_m2 < 0.0 or dni_w_per_m2 < 0.0 or dhi_w_per_m2 < 0.0:
            raise PhysicsViolationError(
                f"Negative solar irradiance input: GHI={ghi_w_per_m2}, DNI={dni_w_per_m2}, DHI={dhi_w_per_m2}",
                details={"ghi": ghi_w_per_m2, "dni": dni_w_per_m2, "dhi": dhi_w_per_m2},
            )

        if solar_zenith_deg < 0.0 or solar_zenith_deg > 180.0:
            raise PhysicsViolationError(
                f"Solar zenith angle {solar_zenith_deg}° is outside physical range [0, 180]°",
                details={"solar_zenith_deg": solar_zenith_deg},
            )

        # Nighttime invariant: if sun is at or below horizon (zenith >= 90°) or GHI is 0
        if solar_zenith_deg >= 90.0 or ghi_w_per_m2 <= 0.0:
            return 0.0, 0.0, 0.0, 0.0

        zenith_rad = math.radians(solar_zenith_deg)

        # Determine solar azimuth
        if solar_azimuth_deg is None:
            if timestamp is not None:
                solar_azimuth_deg = self.calculate_solar_azimuth(timestamp, solar_zenith_deg)
            else:
                raise PhysicsViolationError(
                    "Solar azimuth angle is required for plane-of-array irradiance calculation. "
                    "Provide either an explicit 'solar_azimuth_deg' or a valid 'timestamp' "
                    "from which solar geometry can be calculated."
                )

        solar_az_rad = math.radians(solar_azimuth_deg)

        # 1. Direct Beam Component: cos(theta) calculation
        cos_theta = math.cos(zenith_rad) * math.cos(self.tilt_rad) + \
                    math.sin(zenith_rad) * math.sin(self.tilt_rad) * math.cos(solar_az_rad - self.azimuth_rad)
        cos_theta_clipped = max(0.0, cos_theta)
        g_beam_poa = dni_w_per_m2 * cos_theta_clipped

        # 2. Sky Diffuse Component (Liu-Jordan Isotropic formulation)
        g_diff_poa = dhi_w_per_m2 * ((1.0 + math.cos(self.tilt_rad)) / 2.0)

        # 3. Ground Reflected Component (isotropic ground reflection)
        g_gnd_poa = ghi_w_per_m2 * self.albedo * ((1.0 - math.cos(self.tilt_rad)) / 2.0)

        g_poa = g_beam_poa + g_diff_poa + g_gnd_poa
        return float(g_poa), float(g_beam_poa), float(g_diff_poa), float(g_gnd_poa)

    def calculate_cell_temperature(
        self,
        poa_irradiance_w_per_m2: float,
        ambient_temperature_c: float,
    ) -> float:
        """Compute operating cell temperature using the King/Evans NOCT formulation.

        Args:
            poa_irradiance_w_per_m2: Plane-of-array irradiance [W/m²].
            ambient_temperature_c: Dry bulb ambient air temperature [°C].

        Returns:
            Operating cell temperature [°C].
        """
        if ambient_temperature_c < -60.0 or ambient_temperature_c > 65.0:
            raise PhysicsViolationError(
                f"Ambient temperature {ambient_temperature_c}°C is outside valid meteorological limits [-60, 65]°C",
                details={"ambient_temperature_c": ambient_temperature_c},
            )

        if poa_irradiance_w_per_m2 <= 0.0:
            return float(ambient_temperature_c)

        # Thermal dissipation factor
        thermal_factor = ((self.noct - 20.0) / 800.0) * (1.0 - self.eta_stc / self.tau_alpha)
        t_cell = ambient_temperature_c + poa_irradiance_w_per_m2 * thermal_factor
        return float(t_cell)

    def calculate_dc_power(
        self,
        poa_irradiance_w_per_m2: float,
        cell_temperature_c: float,
    ) -> tuple[float, float, float, bool]:
        """Compute temperature-derated DC output power with capacity clipping.

        Args:
            poa_irradiance_w_per_m2: Plane-of-array irradiance [W/m²].
            cell_temperature_c: Cell temperature [°C].

        Returns:
            Tuple of (p_dc_clipped, p_dc_unclipped, curtailed_dc, is_clipped) in [kW, kW, kW, bool].
        """
        if poa_irradiance_w_per_m2 <= 0.0:
            return 0.0, 0.0, 0.0, False

        # Temperature derating factor
        temp_correction = 1.0 + self.gamma_pmp * (cell_temperature_c - self.t_stc)
        temp_correction = max(0.0, temp_correction)

        # Raw DC output
        p_dc_unclipped = self.rated_capacity_kw * (poa_irradiance_w_per_m2 / self.g_stc) * temp_correction * self.f_derate

        # DC capacity clipping
        if p_dc_unclipped > self.p_dc_max:
            p_dc = self.p_dc_max
            p_curtail = p_dc_unclipped - self.p_dc_max
            is_clipped = True
        else:
            p_dc = max(0.0, p_dc_unclipped)
            p_curtail = 0.0
            is_clipped = False

        return float(p_dc), float(p_dc_unclipped), float(p_curtail), is_clipped

    def step(
        self,
        ghi_w_per_m2: float,
        dni_w_per_m2: float,
        dhi_w_per_m2: float,
        ambient_temperature_c: float,
        solar_zenith_deg: float,
        solar_azimuth_deg: Optional[float] = None,
        timestamp: Optional[pd.Timestamp] = None,
    ) -> PVGenerationResult:
        """Execute full physical PV conversion step.

        Args:
            ghi_w_per_m2: Global Horizontal Irradiance [W/m²].
            dni_w_per_m2: Direct Normal Irradiance [W/m²].
            dhi_w_per_m2: Diffuse Horizontal Irradiance [W/m²].
            ambient_temperature_c: Ambient temperature [°C].
            solar_zenith_deg: Solar zenith angle [°].
            solar_azimuth_deg: Optional solar azimuth angle [°].
            timestamp: Optional UTC timestamp.

        Returns:
            PVGenerationResult dataclass with detailed outputs.
        """
        # 1. Plane-of-Array Irradiance
        g_poa, g_beam, g_diff, g_gnd = self.calculate_poa_irradiance(
            ghi_w_per_m2=ghi_w_per_m2,
            dni_w_per_m2=dni_w_per_m2,
            dhi_w_per_m2=dhi_w_per_m2,
            solar_zenith_deg=solar_zenith_deg,
            solar_azimuth_deg=solar_azimuth_deg,
            timestamp=timestamp,
        )

        # 2. Operating Cell Temperature
        t_cell = self.calculate_cell_temperature(
            poa_irradiance_w_per_m2=g_poa,
            ambient_temperature_c=ambient_temperature_c,
        )

        # 3. DC Power Generation & Clipping
        p_dc, p_dc_raw, p_curtail, is_clipped = self.calculate_dc_power(
            poa_irradiance_w_per_m2=g_poa,
            cell_temperature_c=t_cell,
        )

        return PVGenerationResult(
            poa_irradiance_w_per_m2=g_poa,
            poa_beam_w_per_m2=g_beam,
            poa_diffuse_w_per_m2=g_diff,
            poa_ground_w_per_m2=g_gnd,
            cell_temperature_c=t_cell,
            dc_power_kw=p_dc,
            dc_power_unclipped_kw=p_dc_raw,
            curtailed_dc_power_kw=p_curtail,
            is_clipped=is_clipped,
        )

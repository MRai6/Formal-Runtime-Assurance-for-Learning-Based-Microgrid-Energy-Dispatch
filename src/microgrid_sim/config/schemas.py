"""Comprehensive Pydantic configuration schemas for microgrid_sim.

Enforces physical validity, dimensional correctness, unit documentation,
and parameter bounds across all system, component, and scenario specifications.
"""

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, model_validator


# ==============================================================================
# System & Temporal Configurations
# ==============================================================================

class TemporalConfig(BaseModel):
    """Temporal discretization parameters for the simulation horizon."""
    timestep_minutes: int = Field(15, ge=1, le=60, description="Primary simulation step in minutes [min]")
    timestep_hours: float = Field(0.25, gt=0.0, le=1.0, description="Step duration in decimal hours [h]")
    steps_per_day: int = Field(96, ge=24, le=1440, description="Number of discrete steps per 24-hour cycle [-]")
    steps_per_year: int = Field(35040, ge=8760, le=525600, description="Total steps in standard 365-day year [-]")
    weather_year: int = Field(2018, ge=1990, le=2030, description="Meteorological calendar reference year")
    start_date: str = Field("2018-01-01T00:00:00", description="Simulation start ISO-8601 timestamp")
    end_date: str = Field("2018-12-31T23:45:00", description="Simulation termination ISO-8601 timestamp")

    @model_validator(mode="after")
    def validate_step_consistency(self) -> "TemporalConfig":
        expected_hours = self.timestep_minutes / 60.0
        if abs(self.timestep_hours - expected_hours) > 1e-6:
            raise ValueError(
                f"timestep_hours ({self.timestep_hours}) does not match timestep_minutes ({self.timestep_minutes}/60 = {expected_hours})"
            )
        expected_steps_day = int(1440 / self.timestep_minutes)
        if self.steps_per_day != expected_steps_day:
            raise ValueError(
                f"steps_per_day ({self.steps_per_day}) does not match 1440 / timestep_minutes ({expected_steps_day})"
            )
        return self


class ElectricalConfig(BaseModel):
    """Microgrid AC bus electrical ratings and thermal environment."""
    ac_bus_voltage_v: float = Field(480.0, gt=0.0, description="Three-phase AC line-to-line voltage [V]")
    grid_frequency_hz: float = Field(60.0, gt=0.0, description="Nominal electrical grid frequency [Hz]")
    power_factor: float = Field(1.0, ge=0.8, le=1.0, description="Operating power factor (unity active baseline) [-]")
    isothermal_temperature_c: float = Field(25.0, ge=-20.0, le=55.0, description="Ambient baseline temperature [°C]")


class SystemConfig(BaseModel):
    """Complete centralized microgrid system configuration."""
    system_id: str = Field(..., min_length=1, description="Unique system identifier")
    description: str = Field("", description="System narrative description")
    version: str = Field("1.0.0", description="Configuration schema version")
    temporal: TemporalConfig
    electrical: ElectricalConfig
    assumptions: list[str] = Field(default_factory=list, description="Explicit engineering assumptions")


# ==============================================================================
# Battery Energy Storage System (BESS) Schemas
# ==============================================================================

class BatteryCapacityConfig(BaseModel):
    """Battery energy storage capacity and State of Charge boundaries."""
    nominal_energy_kwh: float = Field(..., gt=0.0, description="Nameplate total energy storage capacity [kWh]")
    minimum_soc: float = Field(0.15, ge=0.0, le=1.0, description="Lower operational State of Charge limit [-]")
    maximum_soc: float = Field(0.90, ge=0.0, le=1.0, description="Upper operational State of Charge limit [-]")
    initial_soc: float = Field(0.50, ge=0.0, le=1.0, description="Initial State of Charge at simulation start [-]")
    usable_energy_kwh: float = Field(..., gt=0.0, description="Usable energy capacity [kWh]")

    @model_validator(mode="after")
    def validate_soc_boundaries(self) -> "BatteryCapacityConfig":
        if self.minimum_soc >= self.maximum_soc:
            raise ValueError(
                f"minimum_soc ({self.minimum_soc}) must be strictly less than maximum_soc ({self.maximum_soc})"
            )
        if not (self.minimum_soc <= self.initial_soc <= self.maximum_soc):
            raise ValueError(
                f"initial_soc ({self.initial_soc}) must lie within [minimum_soc ({self.minimum_soc}), maximum_soc ({self.maximum_soc})]"
            )
        expected_usable = self.nominal_energy_kwh * (self.maximum_soc - self.minimum_soc)
        if abs(self.usable_energy_kwh - expected_usable) > 0.1:
            raise ValueError(
                f"usable_energy_kwh ({self.usable_energy_kwh}) does not equal nominal_energy * (max_soc - min_soc) = {expected_usable}"
            )
        return self


class BatteryPowerAndThermalConfig(BaseModel):
    """Battery charge/discharge ratings and thermal specifications."""
    max_charge_power_kw: float = Field(..., gt=0.0, description="Maximum continuous charging power limit [kW]")
    max_discharge_power_kw: float = Field(..., gt=0.0, description="Maximum continuous discharging power limit [kW]")
    nominal_cell_temperature_c: float = Field(25.0, ge=-20.0, le=60.0, description="Nominal operating cell temp [°C]")
    thermal_domain: str = Field("isothermal", description="Thermal modeling regime (isothermal or lumped)")


class BatteryPerformanceConfig(BaseModel):
    """Battery conversion efficiencies and self-discharge kinetics."""
    charging_efficiency: float = Field(0.95, gt=0.5, le=1.0, description="One-way charging efficiency [-]")
    discharging_efficiency: float = Field(0.95, gt=0.5, le=1.0, description="One-way discharging efficiency [-]")
    roundtrip_efficiency: float = Field(0.9025, gt=0.25, le=1.0, description="Round-trip efficiency [-]")
    self_discharge_rate_per_hour: float = Field(1e-5, ge=0.0, le=0.01, description="Hourly self-discharge rate [1/h]")

    @model_validator(mode="after")
    def validate_efficiency(self) -> "BatteryPerformanceConfig":
        expected_rt = self.charging_efficiency * self.discharging_efficiency
        if abs(self.roundtrip_efficiency - expected_rt) > 1e-4:
            raise ValueError(
                f"roundtrip_efficiency ({self.roundtrip_efficiency}) does not match eta_ch * eta_dis ({expected_rt:.4f})"
            )
        return self


class BatteryDegradationConfig(BaseModel):
    """Battery cycling and capacity degradation economic parameters."""
    replacement_cost_usd_per_kwh: float = Field(180.0, gt=0.0, description="Cell replacement capital cost [$/kWh]")
    cycle_life_to_eol: int = Field(4000, gt=100, description="Equivalent full cycles to End-of-Life [-]")
    reference_dod: float = Field(0.80, gt=0.1, le=1.0, description="Reference depth of discharge for cycle rating [-]")
    implied_wear_cost_usd_per_kwh: float = Field(..., ge=0.0, description="Calculated wear cost per kWh cycled [$/kWh]")


class BatteryConfig(BaseModel):
    """Complete specification schema for Battery Energy Storage System."""
    battery_id: str = Field(..., min_length=1)
    technology: str = Field(...)
    specification_status: str = Field(...)
    reference_source: str = Field(...)
    capacity: BatteryCapacityConfig
    power_and_thermal: BatteryPowerAndThermalConfig
    performance: BatteryPerformanceConfig
    degradation: BatteryDegradationConfig
    notes: list[str] = Field(default_factory=list)


# ==============================================================================
# Solar Photovoltaic (PV) Schemas
# ==============================================================================

class PVCapacityConfig(BaseModel):
    """Solar PV array capacity sizing."""
    rated_dc_capacity_kw: float = Field(..., gt=0.0, description="Nameplate DC rating under Standard Test Conditions [kW_dc]")
    dc_to_ac_ratio: float = Field(1.0, gt=0.5, le=2.0, description="Array DC rating to inverter AC rating ratio [-]")


class PVOrientationConfig(BaseModel):
    """Solar panel tilt, azimuth, and ground albedo."""
    tilt_degrees: float = Field(..., ge=0.0, le=90.0, description="Panel surface tilt angle from horizontal [°]")
    azimuth_degrees: float = Field(180.0, ge=0.0, le=360.0, description="Panel azimuth angle (180° = Due South) [°]")
    ground_albedo: float = Field(0.20, ge=0.0, le=1.0, description="Ground diffuse reflectance (albedo) [-]")


class PVThermalAndElectricalConfig(BaseModel):
    """PV module electrical characteristics and NOCT temperature coefficients."""
    stc_irradiance_w_per_m2: float = Field(1000.0, gt=0.0, description="STC reference irradiance [W/m²]")
    stc_cell_temperature_c: float = Field(25.0, description="STC reference cell temperature [°C]")
    noct_temperature_c: float = Field(45.0, ge=30.0, le=60.0, description="Nominal Operating Cell Temperature [°C]")
    temperature_coefficient_pmp_per_c: float = Field(-0.0038, lt=0.0, ge=-0.01, description="Max power temp coefficient [1/°C]")
    stc_module_efficiency: float = Field(0.20, gt=0.05, le=0.35, description="Module efficiency at STC [-]")
    transmittance_absorptance_product: float = Field(0.90, gt=0.5, le=1.0, description="Optical product (tau*alpha) [-]")


class PVLossesConfig(BaseModel):
    """Balance-of-system electrical and soiling derating factors."""
    bos_derate_factor: float = Field(0.95, gt=0.7, le=1.0, description="Overall balance-of-system derate factor [-]")


class PVConfig(BaseModel):
    """Complete specification schema for Solar PV Array."""
    pv_id: str = Field(..., min_length=1)
    technology: str = Field(...)
    specification_status: str = Field(...)
    reference_source: str = Field(...)
    capacity: PVCapacityConfig
    orientation: PVOrientationConfig
    thermal_and_electrical: PVThermalAndElectricalConfig
    losses: PVLossesConfig
    notes: list[str] = Field(default_factory=list)


# ==============================================================================
# Inverter / Power Conversion System Schemas
# ==============================================================================

class InverterRatingsConfig(BaseModel):
    """Inverter continuous nameplate AC power capacity and limits."""
    rated_ac_power_kw: float = Field(..., gt=0.0, description="Continuous maximum AC power output rating [kW_ac]")
    rated_apparent_power_kva: float = Field(..., gt=0.0, description="Apparent power capacity [kVA]")
    max_dc_input_power_kw: float = Field(..., gt=0.0, description="Maximum DC input power ceiling [kW_dc]")
    operating_power_factor: float = Field(1.0, ge=0.8, le=1.0, description="Operating power factor [-]")


class InverterEfficiencyConfig(BaseModel):
    """Non-linear part-load efficiency curve parameters."""
    model_type: str = Field("cec_polynomial", description="Inverter efficiency mathematical model")
    nominal_peak_efficiency: float = Field(0.975, gt=0.8, le=1.0, description="Peak conversion efficiency [-]")
    curvature_coefficient_c0: float = Field(0.015, ge=0.0, le=0.1, description="CEC polynomial intercept loss [-]")
    curvature_coefficient_c1: float = Field(0.035, ge=0.0, le=0.1, description="CEC polynomial curvature loss [-]")


class BatteryInverterConfig(BaseModel):
    """Bidirectional battery inverter coupling specifications."""
    rated_ac_power_kw: float = Field(..., gt=0.0, description="Battery bidirectional inverter AC capacity [kW_ac]")
    bidirectional_efficiency: float = Field(0.96, gt=0.8, le=1.0, description="AC-to-DC and DC-to-AC efficiency [-]")


class InverterConfig(BaseModel):
    """Complete specification schema for Power Conversion Inverters."""
    inverter_id: str = Field(..., min_length=1)
    technology: str = Field(...)
    specification_status: str = Field(...)
    reference_source: str = Field(...)
    ratings: InverterRatingsConfig
    efficiency_model: InverterEfficiencyConfig
    battery_inverter: BatteryInverterConfig
    notes: list[str] = Field(default_factory=list)


# ==============================================================================
# Grid Interconnection & Tariff Schemas
# ==============================================================================

class GridInterconnectionConfig(BaseModel):
    """Point of Common Coupling (PCC) import/export limits."""
    max_import_power_kw: float = Field(..., gt=0.0, description="Contractual maximum grid import power [kW]")
    max_export_power_kw: float = Field(..., ge=0.0, description="Contractual maximum grid export power [kW]")
    mutual_exclusivity_required: bool = Field(True, description="Enforce P_import * P_export == 0")


class GridBillingConfig(BaseModel):
    """Fixed monthly facility charges and peak demand charges."""
    monthly_customer_charge_usd: float = Field(45.00, ge=0.0, description="Fixed monthly customer charge [$/month]")
    distribution_demand_charge_usd_per_kw: float = Field(14.25, ge=0.0, description="Peak demand charge [$/kW]")


class SeasonalTOUConfig(BaseModel):
    """Seasonal Time-of-Use schedule and energy charges."""
    months: list[int] = Field(..., min_length=1, max_length=12, description="Active months (1-12)")
    on_peak_hours: list[int] = Field(..., min_length=1, max_length=24, description="On-peak daily hours (0-23)")
    on_peak_weekdays_only: bool = Field(True, description="Whether on-peak applies only on non-holiday weekdays")
    rate_on_peak_usd_per_kwh: float = Field(..., ge=0.0, description="On-peak energy usage rate [$/kWh]")
    rate_off_peak_usd_per_kwh: float = Field(..., ge=0.0, description="Off-peak energy usage rate [$/kWh]")

    @model_validator(mode="after")
    def validate_hours_and_months(self) -> "SeasonalTOUConfig":
        for m in self.months:
            if not (1 <= m <= 12):
                raise ValueError(f"Month {m} is invalid; must be between 1 and 12")
        for h in self.on_peak_hours:
            if not (0 <= h <= 23):
                raise ValueError(f"Hour {h} is invalid; must be between 0 and 23")
        return self


class GridTOURatesConfig(BaseModel):
    """Summer and winter seasonal Time-of-Use schedules."""
    summer: SeasonalTOUConfig
    winter: SeasonalTOUConfig


class GridExportCompensationConfig(BaseModel):
    """Net-metering or avoided-cost export compensation credit rules."""
    compensation_mechanism: str = Field("avoided_cost_credit")
    export_credit_multiplier: float = Field(0.50, ge=0.0, le=1.0, description="Fraction of retail rate credited [-]")


class TariffConfig(BaseModel):
    """Complete specification schema for Utility Grid and Tariff Schedule."""
    grid_id: str = Field(..., min_length=1)
    utility_name: str = Field(...)
    utility_parent: str = Field(...)
    eia_utility_id: int = Field(..., gt=0)
    tariff_schedule: str = Field(...)
    jurisdiction: str = Field(...)
    reference_source: str = Field(...)
    interconnection: GridInterconnectionConfig
    billing: GridBillingConfig
    tou_rates: GridTOURatesConfig
    export_compensation: GridExportCompensationConfig
    notes: list[str] = Field(default_factory=list)


# ==============================================================================
# Benchmark Location & Building Archetype Schemas
# ==============================================================================

class CoordinatesConfig(BaseModel):
    """Geographic positioning and elevation."""
    latitude_deg: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees [°N]")
    longitude_deg: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees [°E]")
    elevation_meters: float = Field(..., ge=0.0, le=5000.0, description="Surface elevation [m]")
    timezone: str = Field("America/Denver", description="IANA timezone name")
    utc_offset_hours: float = Field(-7.0, ge=-12.0, le=14.0, description="Standard time UTC offset [hours]")


class ClimateConfig(BaseModel):
    """Climatological zone classification and reference year."""
    ashrae_climate_zone: str = Field("5B", description="ASHRAE standard climate classification")
    koppen_geiger_class: str = Field("BSk", description="Köppen-Geiger climate classification")
    weather_year: int = Field(2018, ge=1990, le=2030, description="Calibrated meteorological year")


class BuildingArchetypeConfig(BaseModel):
    """Commercial building structural, thermal, and electrical load parameters."""
    archetype_id: str = Field(..., min_length=1)
    model_source: str = Field(...)
    building_type: str = Field("MediumOffice")
    floor_area_sqft: float = Field(..., gt=0.0, description="Total conditioned floor area [ft²]")
    floor_area_m2: float = Field(..., gt=0.0, description="Total conditioned floor area [m²]")
    number_of_stories: int = Field(3, ge=1, le=100, description="Building vertical stories [-]")
    peak_electrical_demand_kw: float = Field(..., gt=0.0, description="Estimated peak summer demand [kW]")
    average_electrical_demand_kw: float = Field(..., gt=0.0, description="Estimated annual average demand [kW]")


class LocationConfig(BaseModel):
    """Complete specification schema for Benchmark Location and Building Site."""
    location_id: str = Field(..., min_length=1)
    site_name: str = Field(...)
    geographic_region: str = Field(...)
    coordinates: CoordinatesConfig
    climate: ClimateConfig
    building_archetype: BuildingArchetypeConfig
    notes: list[str] = Field(default_factory=list)


# ==============================================================================
# Dataset Provenance Registry Schemas
# ==============================================================================

DatasetLifecycleStatus = Literal[
    "source_documentation_verified",
    "dataset_metadata_inspected",
    "raw_data_downloaded",
    "raw_data_checksum_verified",
    "data_quality_validation_passed",
    "benchmark_accepted",
]


class DatasetMetadata(BaseModel):
    """Structured provenance metadata for an official external dataset."""
    dataset_id: str = Field(..., min_length=1)
    provenance_class: Literal[
        "directly_measured_physical_observation",
        "satellite_derived_physical_model",
        "calibrated_building_energy_simulation",
        "codified_regulatory_utility_tariff"
    ]
    provider: str = Field(..., min_length=1)
    dataset_name: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    official_identifier: str = Field(...)
    source_url: str = Field(...)
    download_timestamp: str = Field(...)
    original_temporal_resolution: str = Field(...)
    primary_dispatch_resolution: str = Field(...)
    original_units: dict[str, str] = Field(default_factory=dict)
    geographic_coordinates: dict[str, float] = Field(default_factory=dict)
    geographic_region: str = Field(...)
    timezone: str = Field(...)
    licensing: str = Field(...)
    file_checksum_sha256: str = Field(...)
    status: Optional[str] = Field(None)
    verification_status: Optional[DatasetLifecycleStatus] = Field(None)

    @model_validator(mode="after")
    def populate_status_alias(self) -> "DatasetMetadata":
        if self.verification_status is None and self.status is not None:
            # If status matches one of the lifecycle states, assign to verification_status
            self.verification_status = self.status  # type: ignore[assignment]
        elif self.status is None and self.verification_status is not None:
            self.status = self.verification_status
        return self


class DatasetRegistry(BaseModel):
    """Collection schema for the official dataset registry."""
    registry_version: str = Field("1.0.0")
    updated_at: str = Field(...)
    description: str = Field("")
    datasets: list[DatasetMetadata] = Field(..., min_length=1)

    def get_dataset(self, dataset_id: str) -> Optional[DatasetMetadata]:
        """Look up metadata entry by unique dataset identifier."""
        for ds in self.datasets:
            if ds.dataset_id == dataset_id:
                return ds
        return None


# ==============================================================================
# Unified Master Configuration Schema
# ==============================================================================

class CompleteSystemConfig(BaseModel):
    """Master aggregated configuration assembling all validated component schemas."""
    system: SystemConfig
    battery: BatteryConfig
    pv: PVConfig
    inverter: InverterConfig
    tariff: TariffConfig
    location: LocationConfig
    registry: DatasetRegistry

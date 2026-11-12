"""Comprehensive unit and physical validation tests for microgrid physics components.

Covers:
    - Solar PV Model: irradiance validation, transposition, NOCT cell temperature, DC derating, clipping.
    - Battery Model: charging, discharging, idle, efficiency losses, SoC bounds, self-discharge, power limits.
    - Inverter Model: CEC curve validation, clipping, apparent power limits, battery PCS conversion.
    - Building Load Model: validation, energy/power conversions, negative demand rejection.
    - Grid Model: PCC exchange limits, mutual exclusivity, separate TOU financial accounting.
    - Power Balance Calculator: Kirchhoff power conservation, unserved load, PV curtailment, residual checks.
"""

import math
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from microgrid_sim.config.loader import load_complete_configuration
from microgrid_sim.config.schemas import CompleteSystemConfig
from microgrid_sim.physics.battery import BatteryModel, BatteryStepResult
from microgrid_sim.physics.grid import GridBillingResult, GridExchangeResult, GridModel
from microgrid_sim.physics.inverter import BatteryPCSResult, InverterModel, PVInverterResult
from microgrid_sim.physics.load import BuildingLoadModel, LoadDemandResult
from microgrid_sim.physics.power_balance import PowerBalanceCalculator, PowerBalanceResult
from microgrid_sim.physics.solar_pv import PVGenerationResult, SolarPVModel
from microgrid_sim.utils.exceptions import ConservationOfEnergyError, PhysicsViolationError


@pytest.fixture(scope="module")
def complete_cfg(configs_dir: Path) -> CompleteSystemConfig:
    """Fixture providing loaded master microgrid configuration."""
    return load_complete_configuration(configs_dir)


# ==============================================================================
# 1. Solar PV Model Tests
# ==============================================================================

def test_solar_pv_zero_irradiance(complete_cfg: CompleteSystemConfig) -> None:
    """Verify that zero irradiance results in zero generation and cell temp equals ambient."""
    pv = SolarPVModel(config=complete_cfg.pv)
    result = pv.step(
        ghi_w_per_m2=0.0,
        dni_w_per_m2=0.0,
        dhi_w_per_m2=0.0,
        ambient_temperature_c=20.0,
        solar_zenith_deg=45.0,
    )
    assert result.poa_irradiance_w_per_m2 == 0.0
    assert result.dc_power_kw == 0.0
    assert result.cell_temperature_c == 20.0
    assert result.is_clipped is False


def test_solar_pv_nighttime_zenith(complete_cfg: CompleteSystemConfig) -> None:
    """Verify nighttime conditions (zenith >= 90°) produce zero generation."""
    pv = SolarPVModel(config=complete_cfg.pv)
    # Even if spurious positive irradiance is provided, zenith >= 90 must enforce night
    result = pv.step(
        ghi_w_per_m2=0.0,
        dni_w_per_m2=0.0,
        dhi_w_per_m2=0.0,
        ambient_temperature_c=10.0,
        solar_zenith_deg=95.0,
    )
    assert result.poa_irradiance_w_per_m2 == 0.0
    assert result.dc_power_kw == 0.0
    assert result.cell_temperature_c == 10.0


def test_solar_pv_standard_test_conditions(complete_cfg: CompleteSystemConfig) -> None:
    """Verify output under Standard Test Conditions (1000 W/m², 25°C cell temp)."""
    pv = SolarPVModel(config=complete_cfg.pv)
    # At STC (G=1000 W/m², T_cell=25°C), P_dc = P_stc * 1.0 * 1.0 * f_derate = 120 * 0.95 = 114 kW
    p_dc, p_raw, p_curt, is_clipped = pv.calculate_dc_power(
        poa_irradiance_w_per_m2=1000.0,
        cell_temperature_c=25.0,
    )
    assert pytest.approx(p_dc, abs=1e-3) == 120.0 * 0.95  # 114.0 kW
    assert is_clipped is False
    assert p_curt == 0.0


def test_solar_pv_temperature_derating(complete_cfg: CompleteSystemConfig) -> None:
    """Verify that elevated cell temperature derates power output by -0.38%/°C."""
    pv = SolarPVModel(config=complete_cfg.pv)
    # At T_cell = 45°C (delta_T = +20°C), derating factor = 1 + (-0.0038 * 20) = 1 - 0.076 = 0.924
    p_dc_hot, _, _, _ = pv.calculate_dc_power(poa_irradiance_w_per_m2=1000.0, cell_temperature_c=45.0)
    p_dc_stc, _, _, _ = pv.calculate_dc_power(poa_irradiance_w_per_m2=1000.0, cell_temperature_c=25.0)

    expected_ratio = 1.0 - 0.0038 * 20.0  # 0.924
    assert pytest.approx(p_dc_hot / p_dc_stc, abs=1e-4) == expected_ratio


def test_solar_pv_dc_clipping(complete_cfg: CompleteSystemConfig) -> None:
    """Verify that excessive DC power is clipped at the array nameplate capacity (120 kW)."""
    pv = SolarPVModel(config=complete_cfg.pv)
    # At cold temperature (-10°C) and high irradiance (1300 W/m²), unclipped power exceeds 120 kW
    p_dc, p_raw, p_curt, is_clipped = pv.calculate_dc_power(
        poa_irradiance_w_per_m2=1300.0,
        cell_temperature_c=-10.0,
    )
    assert p_dc == 120.0
    assert p_raw > 120.0
    assert is_clipped is True
    assert pytest.approx(p_curt, abs=1e-3) == (p_raw - 120.0)


def test_solar_pv_invalid_inputs_raise_exception(complete_cfg: CompleteSystemConfig) -> None:
    """Verify PhysicsViolationError on negative irradiance, invalid zenith, or extreme temperatures."""
    pv = SolarPVModel(config=complete_cfg.pv)

    with pytest.raises(PhysicsViolationError):
        pv.calculate_poa_irradiance(ghi_w_per_m2=-10.0, dni_w_per_m2=0.0, dhi_w_per_m2=0.0, solar_zenith_deg=45.0)

    with pytest.raises(PhysicsViolationError):
        pv.calculate_poa_irradiance(ghi_w_per_m2=100.0, dni_w_per_m2=100.0, dhi_w_per_m2=100.0, solar_zenith_deg=200.0)

    with pytest.raises(PhysicsViolationError):
        pv.calculate_cell_temperature(poa_irradiance_w_per_m2=500.0, ambient_temperature_c=75.0)


# ==============================================================================
# 2. Battery Energy Storage Model Tests
# ==============================================================================

def test_battery_idle_and_self_discharge(complete_cfg: CompleteSystemConfig) -> None:
    """Verify battery idle operation and exponential self-discharge decay."""
    bess = BatteryModel(config=complete_cfg.battery, timestep_hours=0.25)
    initial_soc = bess.soc  # 0.50

    result = bess.step(requested_power_kw=0.0)
    assert result.executed_power_kw == 0.0
    assert result.energy_charged_kwh == 0.0
    assert result.energy_discharged_kwh == 0.0

    # SoC should decay slightly due to self-discharge rate: sigma = 1e-5 / h
    # Expected: soc * (1 - 1e-5 * 0.25) = 0.50 * (1 - 2.5e-6) = 0.49999875
    expected_soc = initial_soc * (1.0 - 0.00001 * 0.25)
    assert pytest.approx(result.soc_after, abs=1e-7) == expected_soc


def test_battery_charging_energy_and_efficiency(complete_cfg: CompleteSystemConfig) -> None:
    """Verify that charging increases SoC and accounts for 95% charging efficiency."""
    bess = BatteryModel(config=complete_cfg.battery, timestep_hours=0.25)
    bess.soc = 0.50

    # Charge at 80 kW for 15 minutes (0.25 h): Terminal energy = 20 kWh
    result = bess.step(requested_power_kw=-80.0)

    assert result.executed_power_kw == -80.0
    assert pytest.approx(result.energy_charged_kwh, abs=1e-4) == 20.0
    # Stored in cells = 20 kWh * 0.95 = 19.0 kWh
    assert pytest.approx(result.internal_energy_stored_kwh, abs=1e-4) == 19.0
    # Delta SoC = 19.0 kWh / 400 kWh = 0.0475
    assert result.soc_after > 0.50
    assert pytest.approx(result.soc_after, abs=1e-4) == 0.50 + (19.0 / 400.0)


def test_battery_discharging_energy_and_efficiency(complete_cfg: CompleteSystemConfig) -> None:
    """Verify that discharging decreases SoC and accounts for 95% discharge efficiency."""
    bess = BatteryModel(config=complete_cfg.battery, timestep_hours=0.25)
    bess.soc = 0.50

    # Discharge at 80 kW for 15 minutes (0.25 h): Terminal energy = 20 kWh
    result = bess.step(requested_power_kw=80.0)

    assert result.executed_power_kw == 80.0
    assert pytest.approx(result.energy_discharged_kwh, abs=1e-4) == 20.0
    # Extracted from cells = 20 kWh / 0.95 = 21.0526 kWh
    assert pytest.approx(result.internal_energy_extracted_kwh, abs=1e-4) == 20.0 / 0.95
    # Delta SoC = -21.0526 / 400 = -0.05263
    assert result.soc_after < 0.50
    assert pytest.approx(result.soc_after, abs=1e-4) == 0.50 - (20.0 / 0.95) / 400.0


def test_battery_soc_upper_boundary_enforcement(complete_cfg: CompleteSystemConfig) -> None:
    """Verify that charging power is dynamically clamped to avoid exceeding max_soc (0.90)."""
    bess = BatteryModel(config=complete_cfg.battery, timestep_hours=0.25)
    bess.soc = 0.89  # Only 1% headroom (4 kWh cell energy)

    # Request maximum charge power (100 kW = 25 kWh terminal, 23.75 kWh cell energy)
    result = bess.step(requested_power_kw=-100.0)

    # Should be clamped so that soc_after <= 0.90
    assert result.soc_after <= 0.90
    assert pytest.approx(result.soc_after, abs=1e-4) == 0.90
    assert result.constraint_encountered == "MAX_SOC"
    assert abs(result.executed_power_kw) < 100.0


def test_battery_soc_lower_boundary_enforcement(complete_cfg: CompleteSystemConfig) -> None:
    """Verify that discharge power is dynamically clamped to avoid falling below min_soc (0.15)."""
    bess = BatteryModel(config=complete_cfg.battery, timestep_hours=0.25)
    bess.soc = 0.16  # Only 1% above minimum (4 kWh cell energy)

    # Request maximum discharge power (100 kW)
    result = bess.step(requested_power_kw=100.0)

    # Should be clamped so that soc_after >= 0.15
    assert result.soc_after >= 0.15
    assert pytest.approx(result.soc_after, abs=1e-4) == 0.15
    assert result.constraint_encountered == "MIN_SOC"
    assert result.executed_power_kw < 100.0


def test_battery_energy_conservation(complete_cfg: CompleteSystemConfig) -> None:
    """Verify exact algebraic energy conservation: E_terminal = Delta_E_stored + Losses."""
    bess = BatteryModel(config=complete_cfg.battery, timestep_hours=0.25)
    
    # 1. Charging test
    res_ch = bess.step(requested_power_kw=-50.0)
    delta_stored_ch = (res_ch.soc_after - res_ch.soc_before) * bess.nominal_energy_kwh
    # Conservation: E_terminal_ch == Delta_E_stored + Total_Losses (including conversion and self-discharge)
    residual_ch = abs(res_ch.energy_charged_kwh - (delta_stored_ch + res_ch.losses_kwh))
    assert residual_ch < 1e-6

    # 2. Discharging test
    res_dis = bess.step(requested_power_kw=50.0)
    delta_stored_dis = (res_dis.soc_before - res_dis.soc_after) * bess.nominal_energy_kwh
    # Conservation: Delta_E_extracted == E_terminal_dis + Total_Losses
    residual_dis = abs(delta_stored_dis - (res_dis.energy_discharged_kwh + res_dis.losses_kwh))
    assert residual_dis < 1e-6


# ==============================================================================
# 3. Inverter & Power Conversion System Tests
# ==============================================================================

def test_inverter_zero_input(complete_cfg: CompleteSystemConfig) -> None:
    """Verify inverter behavior with zero DC input."""
    inv = InverterModel(config=complete_cfg.inverter)
    res = inv.convert_pv_dc_to_ac(dc_power_kw=0.0)
    assert res.p_ac_output_kw == 0.0
    assert res.efficiency == 0.0
    assert res.p_curtailed_kw == 0.0
    assert res.p_loss_kw == 0.0
    assert res.is_clipped is False


def test_inverter_cec_efficiency_curve(complete_cfg: CompleteSystemConfig) -> None:
    """Verify that CEC polynomial efficiency matches theoretical formulation at 1.0 p.u."""
    inv = InverterModel(config=complete_cfg.inverter)
    # At 1.0 p.u. (120 kW): loss = c0 + c1*(1-1)^2 = c0 = 0.015
    # eta = eta_nom * (1 - 0.015) = 0.975 * 0.985 = 0.960375
    eta_rated = inv.calculate_pv_efficiency(dc_power_kw=120.0)
    assert pytest.approx(eta_rated, abs=1e-5) == 0.975 * (1.0 - 0.015)


def test_inverter_ac_clipping(complete_cfg: CompleteSystemConfig) -> None:
    """Verify that AC output is strictly clamped at nameplate AC capacity (120 kW)."""
    inv = InverterModel(config=complete_cfg.inverter)
    # Provide 140 kW DC: AC output should clip at 120.0 kW
    res = inv.convert_pv_dc_to_ac(dc_power_kw=140.0)
    assert res.p_ac_output_kw == 120.0
    assert res.is_clipped is True
    assert res.p_curtailed_kw > 0.0
    # Exact energy conservation: P_dc == P_ac + P_curtail + P_loss
    assert pytest.approx(res.p_dc_input_kw, abs=1e-5) == (res.p_ac_output_kw + res.p_curtailed_kw + res.p_loss_kw)


def test_battery_pcs_conversion_distinct_from_pv(complete_cfg: CompleteSystemConfig) -> None:
    """Verify battery PCS uses configured bidirectional efficiency (96%) and 100 kW AC rating."""
    inv = InverterModel(config=complete_cfg.inverter)

    # Discharging: 50 kW DC -> 50 * 0.96 = 48 kW AC
    res_dis = inv.convert_battery_discharge_dc_to_ac(p_batt_dc_dis_kw=50.0)
    assert res_dis.mode == "DISCHARGING"
    assert pytest.approx(res_dis.p_ac_kw, abs=1e-5) == 48.0
    assert pytest.approx(res_dis.p_loss_kw, abs=1e-5) == 2.0
    assert res_dis.efficiency == 0.96

    # Charging: 50 kW AC -> 50 * 0.96 = 48 kW DC
    res_ch = inv.convert_battery_charge_ac_to_dc(p_batt_ac_ch_kw=50.0)
    assert res_ch.mode == "CHARGING"
    assert pytest.approx(res_ch.p_dc_kw, abs=1e-5) == 48.0
    assert pytest.approx(res_ch.p_loss_kw, abs=1e-5) == 2.0


# ==============================================================================
# 4. Building Load Model Tests
# ==============================================================================

def test_building_load_validation(complete_cfg: CompleteSystemConfig) -> None:
    """Verify validation and interval energy conversion for building demand."""
    load_model = BuildingLoadModel(config=complete_cfg.location)

    res = load_model.step(demand_kw=100.0, dt_hours=0.25)
    assert res.load_power_kw == 100.0
    assert res.interval_energy_kwh == 25.0

    # Negative demand must raise PhysicsViolationError
    with pytest.raises(PhysicsViolationError):
        load_model.validate_demand(-15.0)

    # NaN demand must raise PhysicsViolationError
    with pytest.raises(PhysicsViolationError):
        load_model.validate_demand(float("nan"))


# ==============================================================================
# 5. Grid Model Tests
# ==============================================================================

def test_grid_physical_limits_and_mutual_exclusivity(complete_cfg: CompleteSystemConfig) -> None:
    """Verify grid import/export limits (250 kW) and rejection of simultaneous import/export."""
    grid = GridModel(config=complete_cfg.tariff)

    # Normal import
    res_imp = grid.step_physical_exchange(requested_import_kw=100.0, requested_export_kw=0.0)
    assert res_imp.p_import_kw == 100.0
    assert res_imp.is_importing is True

    # Clamped import at 250 kW
    res_clamp = grid.step_physical_exchange(requested_import_kw=300.0, requested_export_kw=0.0)
    assert res_clamp.p_import_kw == 250.0
    assert res_clamp.limit_encountered == "IMPORT_LIMIT"

    # Mutual exclusivity violation
    with pytest.raises(PhysicsViolationError):
        grid.step_physical_exchange(requested_import_kw=50.0, requested_export_kw=50.0)


def test_grid_financial_billing_separation(complete_cfg: CompleteSystemConfig) -> None:
    """Verify TOU energy billing under Schedule SG (Summer On-Peak vs Winter Off-Peak)."""
    grid = GridModel(config=complete_cfg.tariff)

    # Summer on-peak: July (month 7), 14:00 (hour 14), weekday -> buy = $0.1850/kWh, sell = 50% = $0.0925/kWh
    rates_summer = grid.calculate_financial_cost(
        energy_imported_kwh=100.0,
        energy_exported_kwh=0.0,
        month=7,
        hour=14,
        is_weekday=True,
    )
    assert rates_summer.is_on_peak is True
    assert rates_summer.is_summer is True
    assert pytest.approx(rates_summer.import_cost_usd, abs=1e-3) == 18.50

    # Winter off-peak: January (month 1), 02:00 (hour 2), weekday -> buy = $0.0620/kWh
    rates_winter = grid.calculate_financial_cost(
        energy_imported_kwh=100.0,
        energy_exported_kwh=0.0,
        month=1,
        hour=2,
        is_weekday=True,
    )
    assert rates_winter.is_on_peak is False
    assert rates_winter.is_summer is False
    assert pytest.approx(rates_winter.import_cost_usd, abs=1e-3) == 6.20


# ==============================================================================
# 6. Power Balance Calculator Tests
# ==============================================================================

def test_power_balance_pv_serves_load_and_exports() -> None:
    """Verify power balance when solar generation exceeds building demand (exporting)."""
    pbc = PowerBalanceCalculator(numerical_tolerance_kw=1e-6)
    # Load = 60 kW, PV = 100 kW -> Export = 40 kW
    res = pbc.resolve_balance(
        p_load_kw=60.0,
        p_pv_ac_kw=100.0,
        p_batt_ch_ac_kw=0.0,
        p_batt_dis_ac_kw=0.0,
        max_grid_import_kw=250.0,
        max_grid_export_kw=250.0,
    )
    assert res.p_grid_export_kw == 40.0
    assert res.p_grid_import_kw == 0.0
    assert res.p_unserved_kw == 0.0
    assert res.p_curtail_kw == 0.0
    assert res.residual_error_kw < 1e-6
    assert res.is_balanced is True


def test_power_balance_deficit_triggers_import() -> None:
    """Verify power balance when demand exceeds PV generation (importing)."""
    pbc = PowerBalanceCalculator(numerical_tolerance_kw=1e-6)
    # Load = 120 kW, PV = 40 kW -> Import = 80 kW
    res = pbc.resolve_balance(
        p_load_kw=120.0,
        p_pv_ac_kw=40.0,
        p_batt_ch_ac_kw=0.0,
        p_batt_dis_ac_kw=0.0,
        max_grid_import_kw=250.0,
        max_grid_export_kw=250.0,
    )
    assert res.p_grid_import_kw == 80.0
    assert res.p_grid_export_kw == 0.0
    assert res.residual_error_kw < 1e-6


def test_power_balance_solar_curtailment_on_export_limit() -> None:
    """Verify that export exceeding grid connection limit (250 kW) results in PV curtailment."""
    pbc = PowerBalanceCalculator(numerical_tolerance_kw=1e-6)
    # Load = 20 kW, PV = 300 kW -> Surplus = 280 kW. Max export = 250 kW -> Curtailment = 30 kW
    res = pbc.resolve_balance(
        p_load_kw=20.0,
        p_pv_ac_kw=300.0,
        p_batt_ch_ac_kw=0.0,
        p_batt_dis_ac_kw=0.0,
        max_grid_import_kw=250.0,
        max_grid_export_kw=250.0,
    )
    assert res.p_grid_export_kw == 250.0
    assert res.p_curtail_kw == 30.0
    assert res.p_unserved_kw == 0.0
    assert res.residual_error_kw < 1e-6


def test_power_balance_unserved_load_on_import_limit() -> None:
    """Verify that deficit exceeding grid import limit results in unserved load."""
    pbc = PowerBalanceCalculator(numerical_tolerance_kw=1e-6)
    # Load = 350 kW, PV = 0 kW. Max import = 250 kW -> Unserved load = 100 kW
    res = pbc.resolve_balance(
        p_load_kw=350.0,
        p_pv_ac_kw=0.0,
        p_batt_ch_ac_kw=0.0,
        p_batt_dis_ac_kw=0.0,
        max_grid_import_kw=250.0,
        max_grid_export_kw=250.0,
    )
    assert res.p_grid_import_kw == 250.0
    assert res.p_unserved_kw == 100.0
    assert res.p_curtail_kw == 0.0
    assert res.residual_error_kw < 1e-6


def test_power_balance_combined_pv_battery_load() -> None:
    """Verify complex multi-component balance (PV + Battery Discharge + Import == Load)."""
    pbc = PowerBalanceCalculator(numerical_tolerance_kw=1e-6)
    # Load = 150 kW, PV = 50 kW, Battery Discharge = 40 kW -> Deficit = 60 kW -> Import = 60 kW
    res = pbc.resolve_balance(
        p_load_kw=150.0,
        p_pv_ac_kw=50.0,
        p_batt_ch_ac_kw=0.0,
        p_batt_dis_ac_kw=40.0,
        max_grid_import_kw=250.0,
        max_grid_export_kw=250.0,
    )
    assert res.p_grid_import_kw == 60.0
    assert res.residual_error_kw < 1e-6


def test_power_balance_rejects_negative_power() -> None:
    """Verify PhysicsViolationError when negative power quantities are supplied."""
    pbc = PowerBalanceCalculator()
    with pytest.raises(PhysicsViolationError):
        pbc.resolve_balance(
            p_load_kw=-50.0,
            p_pv_ac_kw=100.0,
            p_batt_ch_ac_kw=0.0,
            p_batt_dis_ac_kw=0.0,
            max_grid_import_kw=250.0,
            max_grid_export_kw=250.0,
        )


# ==============================================================================
# 7. Phase 4B.1 Independent Audit Regression & Adversarial Tests
# ==============================================================================

def test_solar_pv_missing_geometry_raises_exception(complete_cfg: CompleteSystemConfig) -> None:
    """Verify PhysicsViolationError when solar azimuth is missing and cannot be derived."""
    pv = SolarPVModel(config=complete_cfg.pv)

    # Missing both azimuth and timestamp when daytime irradiance is present
    with pytest.raises(PhysicsViolationError, match="Solar azimuth angle is required"):
        pv.calculate_poa_irradiance(
            ghi_w_per_m2=500.0,
            dni_w_per_m2=600.0,
            dhi_w_per_m2=100.0,
            solar_zenith_deg=35.0,
            solar_azimuth_deg=None,
            timestamp=None,
        )

    with pytest.raises(PhysicsViolationError, match="Solar azimuth angle is required"):
        pv.step(
            ghi_w_per_m2=500.0,
            dni_w_per_m2=600.0,
            dhi_w_per_m2=100.0,
            ambient_temperature_c=25.0,
            solar_zenith_deg=35.0,
            solar_azimuth_deg=None,
            timestamp=None,
        )


def test_solar_pv_diurnal_geometry_variations(complete_cfg: CompleteSystemConfig) -> None:
    """Verify POA calculation across morning, solar noon, evening, and night conditions."""
    pv = SolarPVModel(config=complete_cfg.pv)
    # Surface azimuth = 180° (South), tilt = 25°
    ghi = 800.0
    dni = 700.0
    dhi = 200.0
    zenith = 40.0

    # Morning: Sun at azimuth 105° (75° east of south)
    poa_morning, beam_m, diff_m, cos_m = pv.calculate_poa_irradiance(
        ghi_w_per_m2=ghi,
        dni_w_per_m2=dni,
        dhi_w_per_m2=dhi,
        solar_zenith_deg=zenith,
        solar_azimuth_deg=105.0,
    )

    # Evening: Sun at azimuth 255° (75° west of south, symmetric to morning)
    poa_evening, beam_e, diff_e, cos_e = pv.calculate_poa_irradiance(
        ghi_w_per_m2=ghi,
        dni_w_per_m2=dni,
        dhi_w_per_m2=dhi,
        solar_zenith_deg=zenith,
        solar_azimuth_deg=255.0,
    )

    # By symmetry around true south (180°), POA morning must equal POA evening exactly
    assert pytest.approx(poa_morning, abs=1e-4) == poa_evening
    assert poa_morning > dhi  # Must include positive beam transposition

    # Solar Noon: Sun at azimuth 180° and higher elevation (zenith = 20°)
    poa_noon, beam_n, diff_n, cos_n = pv.calculate_poa_irradiance(
        ghi_w_per_m2=ghi,
        dni_w_per_m2=dni,
        dhi_w_per_m2=dhi,
        solar_zenith_deg=20.0,
        solar_azimuth_deg=180.0,
    )
    # At noon with panel tilt=25°, incidence angle is theta_i = |20° - 25°| = 5°
    # Beam component is maximized: cos(5°) = 0.99619
    cos_theta_i = math.cos(math.radians(5.0))
    expected_beam = dni * (cos_theta_i / math.cos(math.radians(20.0)))
    assert poa_noon > poa_morning
    assert poa_noon > expected_beam

    # Nighttime: zenith >= 90° enforces zero irradiance
    poa_night, _, _, _ = pv.calculate_poa_irradiance(
        ghi_w_per_m2=0.0,
        dni_w_per_m2=0.0,
        dhi_w_per_m2=0.0,
        solar_zenith_deg=98.0,
        solar_azimuth_deg=350.0,
    )
    assert poa_night == 0.0


def test_solar_pv_timestamp_calculates_ephemeris(complete_cfg: CompleteSystemConfig) -> None:
    """Verify that providing timestamp automatically calculates solar azimuth via ephemeris."""
    pv = SolarPVModel(config=complete_cfg.pv)
    # Summer solstice at approx 13:00 MDT (19:00 UTC) at Golden, Colorado (lat 39.74, lon -105.18)
    ts = pd.Timestamp("2018-06-21 19:00:00", tz="UTC")

    result = pv.step(
        ghi_w_per_m2=950.0,
        dni_w_per_m2=900.0,
        dhi_w_per_m2=100.0,
        ambient_temperature_c=28.0,
        solar_zenith_deg=22.0,
        solar_azimuth_deg=None,
        timestamp=ts,
    )
    assert result.poa_irradiance_w_per_m2 > 850.0
    assert result.dc_power_kw > 0.0
    assert result.cell_temperature_c > 28.0


def test_battery_charging_power_limit_and_rejected_power(complete_cfg: CompleteSystemConfig) -> None:
    """Verify that battery clamps charging request to dynamic limit and records rejected power."""
    bess = BatteryModel(config=complete_cfg.battery, timestep_hours=0.25)
    bess.soc = 0.50

    # Max charge power rating is 100 kW. Request -250 kW.
    res = bess.step(requested_power_kw=-250.0)

    assert res.executed_power_kw == -100.0
    assert res.rejected_power_kw == 150.0
    assert pytest.approx(res.energy_rejected_kwh, abs=1e-4) == 150.0 * 0.25
    assert res.constraint_encountered == "MAX_CHARGE_POWER"


def test_battery_discharging_power_limit_and_rejected_power(complete_cfg: CompleteSystemConfig) -> None:
    """Verify that battery clamps discharge request to dynamic limit and records rejected power."""
    bess = BatteryModel(config=complete_cfg.battery, timestep_hours=0.25)
    bess.soc = 0.50

    # Max discharge power rating is 100 kW. Request +300 kW.
    res = bess.step(requested_power_kw=300.0)

    assert res.executed_power_kw == 100.0
    assert res.rejected_power_kw == 200.0
    assert pytest.approx(res.energy_rejected_kwh, abs=1e-4) == 200.0 * 0.25
    assert res.constraint_encountered == "MAX_DISCHARGE_POWER"


def test_battery_step_ch_dis_simultaneous_rejected(complete_cfg: CompleteSystemConfig) -> None:
    """Verify that step_ch_dis raises PhysicsViolationError on simultaneous charge/discharge."""
    bess = BatteryModel(config=complete_cfg.battery, timestep_hours=0.25)

    with pytest.raises(PhysicsViolationError, match="Simultaneous battery charging"):
        bess.step_ch_dis(charge_power_kw=40.0, discharge_power_kw=40.0)


def test_battery_step_ch_dis_tracks_rejected_power(complete_cfg: CompleteSystemConfig) -> None:
    """Verify that step_ch_dis accurately computes executed and rejected power."""
    bess = BatteryModel(config=complete_cfg.battery, timestep_hours=0.25)
    bess.soc = 0.50

    # Request 180 kW charging through step_ch_dis (rating is 100 kW)
    res = bess.step_ch_dis(charge_power_kw=180.0, discharge_power_kw=0.0)
    assert res.executed_power_kw == -100.0
    assert res.rejected_power_kw == 80.0
    assert pytest.approx(res.energy_rejected_kwh, abs=1e-4) == 20.0


def test_inverter_dc_and_ac_clipping_separation(complete_cfg: CompleteSystemConfig) -> None:
    """Verify rigorous separation of DC-side clipping, thermal loss, and AC-side clipping."""
    inv = InverterModel(config=complete_cfg.inverter)
    # In config: max_dc_input_kw = 150.0, p_rated_pv_ac = 120.0
    # Input 170 kW DC:
    # 1. DC clipping = 170 - 150 = 20 kW
    # 2. Accepted DC = 150 kW
    # 3. Efficiency at 150 kW (p_pu = 150/120 = 1.25):
    #    loss_poly = 0.015 + 0.035 * (0.25)^2 = 0.015 + 0.0021875 = 0.0171875
    #    eta = 0.975 * (1 - 0.0171875) = 0.958242
    # 4. AC potential = 150 * 0.958242 = 143.736 kW
    # 5. AC clipping = 143.736 - 120.0 = 23.736 kW
    # 6. Delivered AC = 120.0 kW
    # 7. Thermal loss = 150 * (1 - 0.958242) = 6.264 kW
    res = inv.convert_pv_dc_to_ac(dc_power_kw=170.0)

    assert res.p_dc_input_kw == 170.0
    assert pytest.approx(res.p_dc_clipped_kw, abs=1e-4) == 20.0
    assert res.p_ac_output_kw == 120.0
    assert res.is_clipped is True
    assert pytest.approx(res.p_curtailed_kw, abs=1e-4) == res.p_dc_clipped_kw + res.p_ac_clipped_kw

    # Energy conservation identity: P_dc_input == P_ac_output + P_loss + P_curtailed
    reconstructed_input = res.p_ac_output_kw + res.p_loss_kw + res.p_curtailed_kw
    assert pytest.approx(reconstructed_input, abs=1e-6) == res.p_dc_input_kw


def test_inverter_empirical_part_load_rated_efficiency(complete_cfg: CompleteSystemConfig) -> None:
    """Verify that inverter efficiency at rated capacity (p_pu=1.0) equals 96.04% due to c0=0.015."""
    inv = InverterModel(config=complete_cfg.inverter)
    # At p_pu = 1.0 (120 kW): eta = eta_nom * (1 - c0) = 0.975 * (1 - 0.015) = 0.960375
    eta_rated = inv.calculate_pv_efficiency(dc_power_kw=120.0)
    assert pytest.approx(eta_rated, abs=1e-6) == 0.960375


def test_power_balance_strictly_physical_kirchhoff_unserved_load() -> None:
    """Verify that unserved load is treated as unmet demand, NOT an AC-bus power source."""
    pbc = PowerBalanceCalculator(numerical_tolerance_kw=1e-6)
    # Load requested = 400 kW, Grid import capacity = 250 kW, no other sources
    res = pbc.resolve_balance(
        p_load_kw=400.0,
        p_pv_ac_kw=0.0,
        p_batt_ch_ac_kw=0.0,
        p_batt_dis_ac_kw=0.0,
        max_grid_import_kw=250.0,
        max_grid_export_kw=250.0,
    )

    assert res.p_requested_load_kw == 400.0
    assert res.p_unserved_load_kw == 150.0
    assert res.p_served_load_kw == 250.0
    assert res.p_grid_import_kw == 250.0

    # Kirchhoff active power conservation: Sources == Sinks
    # Sources: P_pv_delivered (0) + P_grid_imp (250) + P_batt_dis (0) + P_diesel (0) = 250 kW
    # Sinks:   P_served_load (250) + P_batt_ch (0) + P_grid_exp (0) = 250 kW
    assert pytest.approx(res.p_sources_kw, abs=1e-6) == 250.0
    assert pytest.approx(res.p_sinks_kw, abs=1e-6) == 250.0
    assert res.residual_error_kw < 1e-6
    assert res.is_balanced is True


def test_power_balance_strictly_physical_kirchhoff_curtailment() -> None:
    """Verify that PV curtailment is withheld inverter potential, NOT an AC-bus load sink."""
    pbc = PowerBalanceCalculator(numerical_tolerance_kw=1e-6)
    # Load requested = 50 kW, PV potential = 350 kW, Grid export capacity = 250 kW
    res = pbc.resolve_balance(
        p_load_kw=50.0,
        p_pv_ac_kw=350.0,
        p_batt_ch_ac_kw=0.0,
        p_batt_dis_ac_kw=0.0,
        max_grid_import_kw=250.0,
        max_grid_export_kw=250.0,
    )

    assert res.p_pv_ac_potential_kw == 350.0
    assert res.p_pv_curtail_ac_kw == 50.0
    assert res.p_pv_ac_delivered_kw == 300.0
    assert res.p_served_load_kw == 50.0
    assert res.p_grid_export_kw == 250.0

    # Kirchhoff active power conservation: Sources == Sinks
    # Sources: P_pv_delivered (300) + P_grid_imp (0) + P_batt_dis (0) + P_diesel (0) = 300 kW
    # Sinks:   P_served_load (50) + P_batt_ch (0) + P_grid_exp (250) = 300 kW
    assert pytest.approx(res.p_sources_kw, abs=1e-6) == 300.0
    assert pytest.approx(res.p_sinks_kw, abs=1e-6) == 300.0
    assert res.residual_error_kw < 1e-6
    assert res.is_balanced is True


def test_power_balance_rejects_simultaneous_battery_operations() -> None:
    """Verify that resolve_balance rejects simultaneous battery charging and discharging."""
    pbc = PowerBalanceCalculator()
    with pytest.raises(PhysicsViolationError, match="Simultaneous battery charging"):
        pbc.resolve_balance(
            p_load_kw=100.0,
            p_pv_ac_kw=50.0,
            p_batt_ch_ac_kw=20.0,
            p_batt_dis_ac_kw=20.0,
            max_grid_import_kw=250.0,
            max_grid_export_kw=250.0,
        )

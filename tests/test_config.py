"""Unit tests for configuration loading, Pydantic schema validation, and parameter bounds."""

from pathlib import Path
import pytest

from microgrid_sim.config.loader import (
    load_battery_config,
    load_complete_configuration,
    load_dataset_registry,
    load_inverter_config,
    load_location_config,
    load_pv_config,
    load_system_config,
    load_tariff_config,
    load_yaml_file,
)
from microgrid_sim.config.schemas import (
    BatteryConfig,
    CompleteSystemConfig,
    DatasetRegistry,
    InverterConfig,
    LocationConfig,
    PVConfig,
    SystemConfig,
    TariffConfig,
)
from microgrid_sim.utils.exceptions import ConfigurationError, InvalidParameterError


def test_load_all_official_configs(configs_dir: Path) -> None:
    """Verify that all baseline YAML files load and satisfy their Pydantic schemas."""
    system = load_system_config(configs_dir / "system_spec.yaml")
    assert isinstance(system, SystemConfig)
    assert system.system_id == "denver_commercial_microgrid"
    assert system.temporal.timestep_minutes == 15
    assert system.temporal.timestep_hours == 0.25
    assert system.temporal.steps_per_year == 35040

    battery = load_battery_config(configs_dir / "battery_spec.yaml")
    assert isinstance(battery, BatteryConfig)
    assert battery.capacity.nominal_energy_kwh == 400.0
    assert battery.capacity.minimum_soc == 0.15
    assert battery.capacity.maximum_soc == 0.90
    assert battery.capacity.initial_soc == 0.50
    assert battery.performance.charging_efficiency == 0.95
    assert battery.performance.discharging_efficiency == 0.95
    assert battery.power_and_thermal.max_charge_power_kw == 100.0
    assert battery.power_and_thermal.max_discharge_power_kw == 100.0

    pv = load_pv_config(configs_dir / "pv_spec.yaml")
    assert isinstance(pv, PVConfig)
    assert pv.capacity.rated_dc_capacity_kw == 120.0
    assert pv.orientation.tilt_degrees == 39.74
    assert pv.orientation.azimuth_degrees == 180.0
    assert pv.thermal_and_electrical.stc_irradiance_w_per_m2 == 1000.0
    assert pv.losses.bos_derate_factor == 0.95

    inverter = load_inverter_config(configs_dir / "inverter_spec.yaml")
    assert isinstance(inverter, InverterConfig)
    assert inverter.ratings.rated_ac_power_kw == 120.0
    assert inverter.efficiency_model.nominal_peak_efficiency == 0.975
    assert inverter.battery_inverter.bidirectional_efficiency == 0.96

    tariff = load_tariff_config(configs_dir / "grid_tariff_spec.yaml")
    assert isinstance(tariff, TariffConfig)
    assert tariff.eia_utility_id == 15466
    assert tariff.interconnection.max_import_power_kw == 250.0
    assert tariff.interconnection.max_export_power_kw == 250.0
    assert tariff.billing.distribution_demand_charge_usd_per_kw == 14.25

    location = load_location_config(configs_dir / "benchmark_location.yaml")
    assert isinstance(location, LocationConfig)
    assert location.coordinates.latitude_deg == 39.7420
    assert location.coordinates.longitude_deg == -105.1800
    assert location.climate.ashrae_climate_zone == "5B"
    assert location.building_archetype.building_type == "MediumOffice"

    registry = load_dataset_registry(configs_dir / "dataset_registry.yaml")
    assert isinstance(registry, DatasetRegistry)
    assert len(registry.datasets) >= 3


def test_load_complete_configuration(configs_dir: Path) -> None:
    """Verify that load_complete_configuration aggregates all specifications into a single object."""
    config = load_complete_configuration(configs_dir)
    assert isinstance(config, CompleteSystemConfig)
    assert config.system.temporal.steps_per_year == 35040
    assert config.battery.capacity.nominal_energy_kwh == 400.0
    assert config.pv.capacity.rated_dc_capacity_kw == 120.0
    assert config.inverter.ratings.rated_ac_power_kw == 120.0
    assert config.tariff.interconnection.max_import_power_kw == 250.0
    assert config.location.climate.weather_year == 2018


def test_missing_config_file_raises_error(tmp_path: Path) -> None:
    """Verify that loading a non-existent configuration file raises ConfigurationError."""
    non_existent = tmp_path / "does_not_exist.yaml"
    with pytest.raises(ConfigurationError) as exc_info:
        load_system_config(non_existent)
    assert "not found" in str(exc_info.value).lower()


def test_malformed_yaml_raises_error(tmp_path: Path) -> None:
    """Verify that malformed YAML syntax raises ConfigurationError."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("system_id: [unclosed list", encoding="utf-8")
    with pytest.raises(ConfigurationError) as exc_info:
        load_yaml_file(bad_yaml)
    assert "malformed" in str(exc_info.value).lower() or "syntax" in str(exc_info.value).lower()


def test_reject_battery_negative_capacity(configs_dir: Path, tmp_path: Path) -> None:
    """Verify rejection when battery nominal energy capacity is non-positive."""
    raw_data = load_yaml_file(configs_dir / "battery_spec.yaml")
    raw_data["capacity"]["nominal_energy_kwh"] = -50.0

    bad_file = tmp_path / "bad_battery.yaml"
    import yaml
    bad_file.write_text(yaml.dump(raw_data), encoding="utf-8")

    with pytest.raises(InvalidParameterError):
        load_battery_config(bad_file)


def test_reject_battery_inverted_soc_limits(configs_dir: Path, tmp_path: Path) -> None:
    """Verify rejection when minimum_soc >= maximum_soc."""
    raw_data = load_yaml_file(configs_dir / "battery_spec.yaml")
    raw_data["capacity"]["minimum_soc"] = 0.80
    raw_data["capacity"]["maximum_soc"] = 0.20

    bad_file = tmp_path / "bad_soc.yaml"
    import yaml
    bad_file.write_text(yaml.dump(raw_data), encoding="utf-8")

    with pytest.raises(InvalidParameterError):
        load_battery_config(bad_file)


def test_reject_battery_initial_soc_out_of_bounds(configs_dir: Path, tmp_path: Path) -> None:
    """Verify rejection when initial_soc is outside [minimum_soc, maximum_soc]."""
    raw_data = load_yaml_file(configs_dir / "battery_spec.yaml")
    raw_data["capacity"]["initial_soc"] = 0.05  # below minimum_soc of 0.15

    bad_file = tmp_path / "bad_initial_soc.yaml"
    import yaml
    bad_file.write_text(yaml.dump(raw_data), encoding="utf-8")

    with pytest.raises(InvalidParameterError):
        load_battery_config(bad_file)


def test_reject_battery_unphysical_efficiency(configs_dir: Path, tmp_path: Path) -> None:
    """Verify rejection when charging efficiency > 1.0."""
    raw_data = load_yaml_file(configs_dir / "battery_spec.yaml")
    raw_data["performance"]["charging_efficiency"] = 1.05

    bad_file = tmp_path / "bad_efficiency.yaml"
    import yaml
    bad_file.write_text(yaml.dump(raw_data), encoding="utf-8")

    with pytest.raises(InvalidParameterError):
        load_battery_config(bad_file)


def test_reject_temporal_inconsistency(configs_dir: Path, tmp_path: Path) -> None:
    """Verify rejection when timestep_hours does not match timestep_minutes / 60."""
    raw_data = load_yaml_file(configs_dir / "system_spec.yaml")
    raw_data["temporal"]["timestep_minutes"] = 15
    raw_data["temporal"]["timestep_hours"] = 0.50  # inconsistent: 15 min = 0.25 h

    bad_file = tmp_path / "bad_temporal.yaml"
    import yaml
    bad_file.write_text(yaml.dump(raw_data), encoding="utf-8")

    with pytest.raises(InvalidParameterError):
        load_system_config(bad_file)


def test_reject_pv_invalid_tilt(configs_dir: Path, tmp_path: Path) -> None:
    """Verify rejection when solar panel tilt is greater than 90 degrees."""
    raw_data = load_yaml_file(configs_dir / "pv_spec.yaml")
    raw_data["orientation"]["tilt_degrees"] = 110.0  # beyond vertical

    bad_file = tmp_path / "bad_tilt.yaml"
    import yaml
    bad_file.write_text(yaml.dump(raw_data), encoding="utf-8")

    with pytest.raises(InvalidParameterError):
        load_pv_config(bad_file)


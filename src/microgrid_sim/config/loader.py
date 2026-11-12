"""Configuration loader for microgrid_sim.

Safely loads, parses, and validates declarative YAML configuration files into
strongly typed Pydantic models with clear error reporting.
"""

from pathlib import Path
from typing import Any, Union
import yaml
from pydantic import ValidationError

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
from microgrid_sim.utils.logger import get_logger

logger = get_logger(__name__)


def load_yaml_file(file_path: Union[str, Path]) -> dict[str, Any]:
    """Load and parse a YAML file from disk.

    Args:
        file_path: Path to the YAML file.

    Returns:
        Parsed dictionary content.

    Raises:
        ConfigurationError: If the file does not exist, cannot be read, or contains invalid YAML syntax.
    """
    path = Path(file_path)
    if not path.is_file():
        raise ConfigurationError(
            f"Configuration file not found: {path}",
            details={"file_path": str(path)},
        )

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                raise ConfigurationError(
                    f"YAML file must contain a top-level mapping/dictionary, got {type(data).__name__}",
                    details={"file_path": str(path)},
                )
            return data
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"Malformed YAML syntax in {path}: {exc}",
            details={"file_path": str(path), "yaml_error": str(exc)},
        ) from exc
    except OSError as exc:
        raise ConfigurationError(
            f"Failed to read configuration file {path}: {exc}",
            details={"file_path": str(path), "os_error": str(exc)},
        ) from exc


def load_system_config(file_path: Union[str, Path]) -> SystemConfig:
    """Load and validate the master system specification."""
    data = load_yaml_file(file_path)
    try:
        return SystemConfig.model_validate(data)
    except ValidationError as exc:
        raise InvalidParameterError(
            f"System configuration validation failed for {file_path}",
            details={"errors": exc.errors()},
        ) from exc


def load_battery_config(file_path: Union[str, Path]) -> BatteryConfig:
    """Load and validate the Battery Energy Storage System specification."""
    data = load_yaml_file(file_path)
    try:
        return BatteryConfig.model_validate(data)
    except ValidationError as exc:
        raise InvalidParameterError(
            f"Battery configuration validation failed for {file_path}",
            details={"errors": exc.errors()},
        ) from exc


def load_pv_config(file_path: Union[str, Path]) -> PVConfig:
    """Load and validate the Solar PV system specification."""
    data = load_yaml_file(file_path)
    try:
        return PVConfig.model_validate(data)
    except ValidationError as exc:
        raise InvalidParameterError(
            f"PV configuration validation failed for {file_path}",
            details={"errors": exc.errors()},
        ) from exc


def load_inverter_config(file_path: Union[str, Path]) -> InverterConfig:
    """Load and validate the Inverter/PCS specification."""
    data = load_yaml_file(file_path)
    try:
        return InverterConfig.model_validate(data)
    except ValidationError as exc:
        raise InvalidParameterError(
            f"Inverter configuration validation failed for {file_path}",
            details={"errors": exc.errors()},
        ) from exc


def load_tariff_config(file_path: Union[str, Path]) -> TariffConfig:
    """Load and validate the Grid and Tariff schedule specification."""
    data = load_yaml_file(file_path)
    try:
        return TariffConfig.model_validate(data)
    except ValidationError as exc:
        raise InvalidParameterError(
            f"Tariff configuration validation failed for {file_path}",
            details={"errors": exc.errors()},
        ) from exc


def load_location_config(file_path: Union[str, Path]) -> LocationConfig:
    """Load and validate the Benchmark Location and Building archetype specification."""
    data = load_yaml_file(file_path)
    try:
        return LocationConfig.model_validate(data)
    except ValidationError as exc:
        raise InvalidParameterError(
            f"Location configuration validation failed for {file_path}",
            details={"errors": exc.errors()},
        ) from exc


def load_dataset_registry(file_path: Union[str, Path]) -> DatasetRegistry:
    """Load and validate the official dataset provenance registry."""
    data = load_yaml_file(file_path)
    try:
        return DatasetRegistry.model_validate(data)
    except ValidationError as exc:
        raise InvalidParameterError(
            f"Dataset registry validation failed for {file_path}",
            details={"errors": exc.errors()},
        ) from exc


def load_complete_configuration(configs_dir: Union[str, Path]) -> CompleteSystemConfig:
    """Load and assemble all individual component configurations from a directory.

    Expected directory structure:
        configs_dir/
            system_spec.yaml
            battery_spec.yaml
            pv_spec.yaml
            inverter_spec.yaml
            grid_tariff_spec.yaml
            benchmark_location.yaml
            dataset_registry.yaml

    Returns:
        CompleteSystemConfig assembling all validated schemas.
    """
    directory = Path(configs_dir)
    if not directory.is_dir():
        raise ConfigurationError(f"Configuration directory does not exist: {directory}")

    system = load_system_config(directory / "system_spec.yaml")
    battery = load_battery_config(directory / "battery_spec.yaml")
    pv = load_pv_config(directory / "pv_spec.yaml")
    inverter = load_inverter_config(directory / "inverter_spec.yaml")
    tariff = load_tariff_config(directory / "grid_tariff_spec.yaml")
    location = load_location_config(directory / "benchmark_location.yaml")
    registry = load_dataset_registry(directory / "dataset_registry.yaml")

    logger.info("Successfully loaded and validated complete microgrid configuration from %s", directory)

    return CompleteSystemConfig(
        system=system,
        battery=battery,
        pv=pv,
        inverter=inverter,
        tariff=tariff,
        location=location,
        registry=registry,
    )

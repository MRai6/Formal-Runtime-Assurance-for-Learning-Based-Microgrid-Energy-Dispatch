"""Pytest test configuration and fixtures for microgrid_sim."""

from pathlib import Path
import pytest

from microgrid_sim.config.loader import load_complete_configuration
from microgrid_sim.config.schemas import CompleteSystemConfig


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def configs_dir(project_root: Path) -> Path:
    """Return the path to the official declarative configs directory."""
    return project_root / "configs"


@pytest.fixture(scope="session")
def complete_config(configs_dir: Path) -> CompleteSystemConfig:
    """Fixture providing a loaded and validated CompleteSystemConfig object."""
    return load_complete_configuration(configs_dir)


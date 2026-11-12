"""Unit tests for dataset provenance registry, cryptographic checksums, and metadata validation."""

from pathlib import Path
import pytest

from microgrid_sim.config.loader import load_dataset_registry
from microgrid_sim.config.schemas import DatasetRegistry
from microgrid_sim.data.registry import DatasetProvenanceManager
from microgrid_sim.utils.exceptions import ChecksumMismatchError, DatasetMissingError
from microgrid_sim.utils.metadata import calculate_file_sha256


def test_dataset_registry_structure(configs_dir: Path) -> None:
    """Verify that dataset_registry.yaml satisfies the DatasetRegistry schema."""
    registry = load_dataset_registry(configs_dir / "dataset_registry.yaml")
    assert isinstance(registry, DatasetRegistry)
    assert registry.registry_version in ("1.0.0", "2.0.0", "2.1.0")

    # Verify NSRDB entry
    nsrdb = registry.get_dataset("nsrdb_goes_conus_2018")
    assert nsrdb is not None
    assert nsrdb.provenance_class == "satellite_derived_physical_model"
    assert "NREL" in nsrdb.provider
    assert "5-minute" in nsrdb.original_temporal_resolution
    assert "15-minute" in nsrdb.primary_dispatch_resolution
    assert "CC0" in nsrdb.licensing
    assert nsrdb.geographic_coordinates["latitude"] == 39.7420
    assert nsrdb.verification_status in ("source_documentation_verified", "benchmark_accepted")

    # Verify ComStock entry and corrected official DOI
    comstock = registry.get_dataset("comstock_medium_office_cz5b_2018")
    assert comstock is not None
    assert comstock.provenance_class == "calibrated_building_energy_simulation"
    assert "10.25984/1876417" in comstock.official_identifier
    assert comstock.original_temporal_resolution == "15-minute"
    assert "CC-BY 4.0" in comstock.licensing
    assert comstock.verification_status in ("source_documentation_verified", "benchmark_accepted")

    # Verify PSCo tariff entry (Provisional Economic Benchmark)
    tariff = registry.get_dataset("urdb_psco_xcel_schedule_sg_2023")
    assert tariff is not None
    assert tariff.provenance_class == "codified_regulatory_utility_tariff"
    assert "Provisional Economic Benchmark" in tariff.dataset_name
    assert tariff.verification_status == "source_documentation_verified"

    # Verify SRRL BMS entry (Candidate ground truth)
    srrl = registry.get_dataset("nrel_srrl_bms_ground_truth_2018")
    assert srrl is not None
    assert srrl.provenance_class == "directly_measured_physical_observation"
    assert srrl.verification_status == "source_documentation_verified"


def test_provenance_manager_unknown_dataset(configs_dir: Path, project_root: Path) -> None:
    """Verify KeyError when requesting an unregistered dataset ID."""
    registry = load_dataset_registry(configs_dir / "dataset_registry.yaml")
    manager = DatasetProvenanceManager(registry=registry, data_root=project_root / "data")

    with pytest.raises(KeyError) as exc_info:
        manager.get_metadata("non_existent_dataset_123")
    assert "not registered" in str(exc_info.value)


def test_provenance_manager_missing_file_raises_error(configs_dir: Path, project_root: Path) -> None:
    """Verify DatasetMissingError when verifying integrity of a non-existent file."""
    registry = load_dataset_registry(configs_dir / "dataset_registry.yaml")
    manager = DatasetProvenanceManager(registry=registry, data_root=project_root / "data")

    missing_path = project_root / "data" / "raw" / "does_not_exist.csv"
    with pytest.raises(DatasetMissingError):
        manager.verify_file_integrity("nsrdb_goes_conus_2018", missing_path)


def test_sha256_computation_and_checksum_verification(tmp_path: Path, configs_dir: Path) -> None:
    """Verify SHA-256 calculation and ChecksumMismatchError on altered files."""
    test_file = tmp_path / "authentic_data.csv"
    test_file.write_text("timestamp,ghi,dni,dhi\n2018-01-01 00:00:00,0,0,0\n", encoding="utf-8")

    expected_hash = calculate_file_sha256(test_file)
    assert len(expected_hash) == 64  # SHA-256 hex string is 64 characters

    # Create a dummy registry with the expected hash
    registry_data = {
        "registry_version": "1.0.0",
        "updated_at": "2026-11-12T00:00:00Z",
        "description": "Test registry",
        "datasets": [
            {
                "dataset_id": "test_dataset",
                "provenance_class": "directly_measured_physical_observation",
                "provider": "Test Provider",
                "dataset_name": "Test Dataset",
                "version": "1.0",
                "official_identifier": "TEST-001",
                "source_url": "https://example.org/test",
                "download_timestamp": "2026-11-12T00:00:00Z",
                "original_temporal_resolution": "15-minute",
                "primary_dispatch_resolution": "15-minute",
                "original_units": {"val": "kW"},
                "geographic_coordinates": {"latitude": 39.74, "longitude": -105.18},
                "geographic_region": "Golden, CO",
                "timezone": "America/Denver",
                "licensing": "CC0",
                "file_checksum_sha256": expected_hash,
                "verification_status": "raw_data_downloaded",
            }
        ],
    }
    registry = DatasetRegistry.model_validate(registry_data)
    manager = DatasetProvenanceManager(registry=registry, data_root=tmp_path)

    # Verification must succeed with identical file
    assert manager.verify_file_integrity("test_dataset", test_file) is True

    # Tamper with the file: checksum mismatch must be raised
    corrupted_file = tmp_path / "corrupted_data.csv"
    corrupted_file.write_text("tampered content\n", encoding="utf-8")

    with pytest.raises(ChecksumMismatchError) as exc_info:
        manager.verify_file_integrity("test_dataset", corrupted_file)
    assert "mismatch" in str(exc_info.value).lower()


"""Dataset registry and scientific provenance manager for microgrid_sim.

Maintains strict provenance, licensing, versioning, and cryptographic integrity
verification for all imported empirical energy datasets.
"""

from pathlib import Path
from typing import Optional

from microgrid_sim.config.schemas import DatasetMetadata, DatasetRegistry
from microgrid_sim.utils.exceptions import ChecksumMismatchError, DatasetMissingError
from microgrid_sim.utils.logger import get_logger
from microgrid_sim.utils.metadata import calculate_file_sha256

logger = get_logger(__name__)


class DatasetProvenanceManager:
    """Manages dataset verification, checksum auditing, and provenance tracking."""

    def __init__(self, registry: DatasetRegistry, data_root: Path) -> None:
        """Initialize the provenance manager.

        Args:
            registry: Validated DatasetRegistry schema instance.
            data_root: Root directory containing data/raw and data/processed.
        """
        self.registry = registry
        self.data_root = Path(data_root)

    def get_metadata(self, dataset_id: str) -> DatasetMetadata:
        """Retrieve the official metadata record for a dataset."""
        metadata = self.registry.get_dataset(dataset_id)
        if metadata is None:
            raise KeyError(f"Dataset '{dataset_id}' is not registered in dataset_registry.yaml")
        return metadata

    def verify_file_integrity(self, dataset_id: str, file_path: Path) -> bool:
        """Verify the SHA-256 checksum of an imported file against its registered value.

        Args:
            dataset_id: Identifier of the dataset in registry.
            file_path: Path to the local data file.

        Returns:
            True if verification succeeds or is pending acquisition.

        Raises:
            DatasetMissingError: If the file does not exist.
            ChecksumMismatchError: If the computed hash differs from the registered hash.
        """
        metadata = self.get_metadata(dataset_id)

        if not file_path.exists():
            raise DatasetMissingError(
                f"Data file for '{dataset_id}' does not exist at {file_path}",
                details={"dataset_id": dataset_id, "expected_path": str(file_path)},
            )

        # If checksum is marked pending, log notice and return
        if metadata.file_checksum_sha256 in ("pending_download", "not_applicable_declarative_yaml"):
            logger.info("Dataset '%s' checksum is marked as '%s'; bypassing strict hash check",
                        dataset_id, metadata.file_checksum_sha256)
            return True

        actual_hash = calculate_file_sha256(file_path)
        if actual_hash.lower() != metadata.file_checksum_sha256.lower():
            raise ChecksumMismatchError(
                f"Cryptographic checksum mismatch for dataset '{dataset_id}'",
                details={
                    "dataset_id": dataset_id,
                    "expected_sha256": metadata.file_checksum_sha256,
                    "actual_sha256": actual_hash,
                    "file_path": str(file_path),
                },
            )

        logger.info("Integrity verified for dataset '%s' (SHA-256: %s)", dataset_id, actual_hash)
        return True

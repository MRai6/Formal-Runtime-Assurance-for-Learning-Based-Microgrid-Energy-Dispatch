"""Centralized exception hierarchy for microgrid_sim.

All exceptions inherit from MicrogridSimError to enable clean exception handling
and distinguish domain errors from generic Python runtime errors.
"""

from typing import Any, Optional


class MicrogridSimError(Exception):
    """Base exception for all microgrid simulation errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class ConfigurationError(MicrogridSimError):
    """Raised when configuration files are missing, malformed, or fail validation."""
    pass


class InvalidParameterError(ConfigurationError):
    """Raised when a specific physical or operational parameter is outside admissible bounds."""
    pass


class PhysicsViolationError(MicrogridSimError):
    """Raised when physical conservation laws, capacity limits, or invariants are violated."""
    pass


class ConservationOfEnergyError(PhysicsViolationError):
    """Raised when the microgrid AC bus power balance residual exceeds numerical tolerance."""
    pass


class StateBoundaryError(PhysicsViolationError):
    """Raised when a dynamic state (e.g., Battery SoC) escapes its admissible physical envelope."""
    pass


class DataProvenanceError(MicrogridSimError):
    """Raised when dataset metadata, file integrity, checksums, or provenance checks fail."""
    pass


class DatasetMissingError(DataProvenanceError):
    """Raised when an expected dataset file is not found in the raw or processed repository."""
    pass


class ChecksumMismatchError(DataProvenanceError):
    """Raised when an authentic data file does not match its registered SHA-256 checksum."""
    pass


class ControllerError(MicrogridSimError):
    """Raised when a baseline or learned controller produces an invalid or unexecutable action."""
    pass

"""Reproducibility and experiment metadata utility for microgrid_sim.

Captures system architecture, library versions, git commits, configuration hashes,
and random seeds to ensure full scientific auditability of simulation runs.
"""

import hashlib
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import pydantic


def get_git_commit_hash(repo_dir: Optional[Path] = None) -> Optional[str]:
    """Retrieve the current Git commit hash if running in a Git repository."""
    try:
        cmd = ["git", "rev-parse", "HEAD"]
        result = subprocess.run(
            cmd,
            cwd=str(repo_dir or Path.cwd()),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            timeout=2.0,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None


def calculate_file_sha256(file_path: Path) -> str:
    """Compute the SHA-256 hash of a file for integrity and provenance tracking."""
    if not file_path.exists():
        raise FileNotFoundError(f"Cannot compute checksum: file not found: {file_path}")

    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class ExperimentMetadata(pydantic.BaseModel):
    """Immutable record of an experiment run environment for reproducibility."""

    experiment_timestamp_utc: str
    python_version: str
    operating_system: str
    processor: str
    numpy_version: str
    pandas_version: str
    pydantic_version: str
    git_commit_hash: Optional[str] = None
    random_seed: Optional[int] = None
    config_hashes: dict[str, str] = pydantic.Field(default_factory=dict)

    @classmethod
    def capture(
        cls,
        random_seed: Optional[int] = None,
        config_dir: Optional[Path] = None,
    ) -> "ExperimentMetadata":
        """Capture the current execution environment metadata."""
        config_hashes = {}
        if config_dir and config_dir.exists():
            for yaml_file in sorted(config_dir.glob("*.yaml")):
                config_hashes[yaml_file.name] = calculate_file_sha256(yaml_file)

        return cls(
            experiment_timestamp_utc=datetime.now(timezone.utc).isoformat(),
            python_version=sys.version.split()[0],
            operating_system=f"{platform.system()} {platform.release()}",
            processor=platform.processor() or "unknown",
            numpy_version=np.__version__,
            pandas_version=pd.__version__,
            pydantic_version=pydantic.__version__,
            git_commit_hash=get_git_commit_hash(),
            random_seed=random_seed,
            config_hashes=config_hashes,
        )

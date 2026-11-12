"""Standardized preprocessor and temporal alignment pipeline for microgrid_sim.

Merges solar irradiance, meteorological observations, and building electric demand
into a verified, chronologically contiguous 35,040-step annual 15-minute Parquet dataset.
"""

from pathlib import Path
from typing import Optional
import json
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from microgrid_sim.data.quality import QualityReport, TimeSeriesQualityAuditor
from microgrid_sim.utils.exceptions import DataProvenanceError
from microgrid_sim.utils.logger import get_logger

logger = get_logger(__name__)


class BenchmarkDataPreprocessor:
    """Synchronizes, validates, and exports standardized benchmark time-series datasets."""

    def __init__(
        self,
        target_year: int = 2018,
        freq_minutes: int = 15,
        expected_intervals: Optional[int] = None,
    ) -> None:
        """Initialize the preprocessor.

        Args:
            target_year: Target calendar year (2018).
            freq_minutes: Step frequency in minutes (15 min).
            expected_intervals: Required rows for complete horizon (e.g. 35,040 for full year, or None for dynamic overlap).
        """
        self.target_year = target_year
        self.freq_minutes = freq_minutes
        self.expected_intervals = expected_intervals
        self.auditor = TimeSeriesQualityAuditor(
            expected_intervals=expected_intervals,
            freq_minutes=freq_minutes,
        )

    def align_and_merge(
        self,
        df_solar_15min: pd.DataFrame,
        df_load_15min: pd.DataFrame,
        dataset_name: str = "denver_cz5b_2018_15min",
    ) -> tuple[pd.DataFrame, QualityReport]:
        """Align solar and building load datasets onto an identical canonical UTC index.

        Identifies the genuine common chronological coverage (intersection) without
        interpolating, duplicating, fabricating, or cyclically relocating observations.

        Args:
            df_solar_15min: Pre-processed/aggregated solar DataFrame with UTC index.
            df_load_15min: Pre-processed building load DataFrame with UTC index.
            dataset_name: Name identifier for the combined benchmark.

        Returns:
            Tuple of (Aligned DataFrame, QualityReport).

        Raises:
            DataProvenanceError: If indices do not align, intervals are missing, or quality checks fail.
        """
        # Verify UTC DatetimeIndex on both inputs
        if not isinstance(df_solar_15min.index, pd.DatetimeIndex) or not isinstance(df_load_15min.index, pd.DatetimeIndex):
            raise DataProvenanceError("Both solar and load DataFrames must have a pandas DatetimeIndex")

        if df_solar_15min.index.tz is None or df_load_15min.index.tz is None:
            raise DataProvenanceError("Both inputs must have timezone-aware DatetimeIndices (UTC canonical)")

        # Determine genuine common chronological coverage without shifting or relocating measurements
        common_index = df_solar_15min.index.intersection(df_load_15min.index).sort_values()
        if len(common_index) == 0:
            raise DataProvenanceError(
                f"No overlapping timestamps found between solar ({df_solar_15min.index.min()} to {df_solar_15min.index.max()}) "
                f"and load ({df_load_15min.index.min()} to {df_load_15min.index.max()})"
            )

        # Merge strictly on genuinely overlapping observations (inner alignment)
        solar_aligned = df_solar_15min.loc[common_index]
        load_aligned = df_load_15min.loc[common_index]
        merged_df = pd.concat([solar_aligned, load_aligned], axis=1)

        # Remove duplicate column names if any
        merged_df = merged_df.loc[:, ~merged_df.columns.duplicated()]

        # Perform comprehensive quality audit
        report = self.auditor.audit(merged_df, dataset_name=dataset_name)

        if not report.all_checks_passed:
            raise DataProvenanceError(
                f"Data quality audit failed for '{dataset_name}'. "
                f"Rejection reasons: {report.rejection_reasons}",
                details={"rejection_reasons": report.rejection_reasons},
            )

        logger.info(
            "Successfully aligned and verified benchmark dataset '%s' (%d contiguous overlapping steps, %s to %s)",
            dataset_name, len(merged_df), merged_df.index.min(), merged_df.index.max()
        )
        return merged_df, report

    def save_processed_parquet(
        self,
        df: pd.DataFrame,
        output_path: Path,
        quality_report: Optional[QualityReport] = None,
    ) -> Path:
        """Save validated DataFrame to standardized Parquet file with embedded metadata.

        Args:
            df: Validated 35,040-step DataFrame.
            output_path: Destination path (.parquet).
            quality_report: Optional QualityReport model to save as companion JSON.

        Returns:
            Path to the saved Parquet file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert DataFrame to PyArrow Table
        table = pa.Table.from_pandas(df)

        # Write Parquet with Snappy compression for fast read access
        pq.write_table(table, output_path, compression="snappy")
        logger.info("Saved processed benchmark dataset to %s (%d rows)", output_path, len(df))

        # Save companion JSON quality report if provided
        if quality_report:
            json_path = output_path.with_suffix(".quality_report.json")
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(quality_report.model_dump_json(indent=2))
            logger.info("Saved companion quality report to %s", json_path)

        return output_path


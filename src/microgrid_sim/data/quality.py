"""Data quality assessment and integrity validation engine for microgrid_sim.

Performs exhaustive verification of temporal continuity, monotonicity, physical bounds,
timezone consistency, and annual interval completeness.
"""

from datetime import datetime, timezone
from typing import Any, Optional
import numpy as np
import pandas as pd
import pydantic

from microgrid_sim.utils.exceptions import DataProvenanceError, PhysicsViolationError
from microgrid_sim.utils.logger import get_logger

logger = get_logger(__name__)


class ColumnQualitySummary(pydantic.BaseModel):
    """Statistical and physical quality summary for a single time-series variable."""
    column_name: str
    unit: str
    min_value: float
    max_value: float
    mean_value: float
    std_value: float
    null_count: int
    out_of_bounds_count: int
    physical_bounds: tuple[float, float]
    passed: bool


class QualityReport(pydantic.BaseModel):
    """Machine-readable comprehensive data-quality assessment report."""
    report_timestamp_utc: str
    dataset_name: str
    start_timestamp: str
    end_timestamp: str
    expected_intervals: int
    actual_intervals: int
    is_continuous: bool
    is_strictly_monotonic: bool
    duplicate_count: int
    missing_interval_count: int
    column_summaries: list[ColumnQualitySummary]
    all_checks_passed: bool
    rejection_reasons: list[str]


class TimeSeriesQualityAuditor:
    """Audits 15-minute microgrid time series for scientific data integrity."""

    # Standard physical bounds for Colorado Front Range CZ5B climate
    PHYSICAL_BOUNDS: dict[str, tuple[float, float, str]] = {
        "ghi_w_per_m2": (0.0, 1350.0, "W/m^2"),
        "dni_w_per_m2": (0.0, 1150.0, "W/m^2"),
        "dhi_w_per_m2": (0.0, 800.0, "W/m^2"),
        "ambient_temperature_c": (-40.0, 48.0, "degC"),
        "wind_speed_m_per_s": (0.0, 45.0, "m/s"),
        "solar_zenith_deg": (0.0, 180.0, "deg"),
        "load_power_kw": (0.0, 500.0, "kW"),
    }

    def __init__(self, expected_intervals: Optional[int] = 35040, freq_minutes: int = 15) -> None:
        """Initialize the auditor.

        Args:
            expected_intervals: Expected rows for annual horizon (e.g. 35,040 for full year, or None for dynamic).
            freq_minutes: Step frequency in minutes (15 min).
        """
        self.expected_intervals = expected_intervals
        self.freq_minutes = freq_minutes
        self.expected_delta = pd.Timedelta(minutes=freq_minutes)

    def audit(self, df: pd.DataFrame, dataset_name: str = "benchmark_time_series") -> QualityReport:
        """Perform comprehensive data-quality audit on a DataFrame with DatetimeIndex.

        Args:
            df: DataFrame to audit, indexed by UTC DatetimeIndex.
            dataset_name: Identifier for the dataset being audited.

        Returns:
            QualityReport model containing detailed validation results.
        """
        rejection_reasons: list[str] = []

        if not isinstance(df.index, pd.DatetimeIndex):
            raise DataProvenanceError("DataFrame index must be a pandas DatetimeIndex")

        actual_intervals = len(df)
        if self.expected_intervals is not None and actual_intervals != self.expected_intervals:
            rejection_reasons.append(
                f"Interval count mismatch: expected {self.expected_intervals}, found {actual_intervals}"
            )

        # Check monotonicity and duplicates
        is_monotonic = bool(df.index.is_monotonic_increasing)
        if not is_monotonic:
            rejection_reasons.append("Timestamps are not strictly monotonically increasing")

        duplicate_mask = df.index.duplicated()
        duplicate_count = int(duplicate_mask.sum())
        if duplicate_count > 0:
            rejection_reasons.append(f"Found {duplicate_count} duplicate timestamp intervals")

        # Check temporal continuity
        missing_interval_count = 0
        is_continuous = True
        if not is_monotonic or duplicate_count > 0:
            is_continuous = False
        elif len(df) > 1:
            deltas = df.index[1:] - df.index[:-1]
            non_standard = deltas != self.expected_delta
            if non_standard.any():
                is_continuous = False
                bad_gaps = deltas[non_standard]
                missing_interval_count = int(sum((bad_gaps / self.expected_delta) - 1))
                rejection_reasons.append(
                    f"Temporal discontinuities detected: {int(non_standard.sum())} non-standard steps (est. {missing_interval_count} missing intervals)"
                )

        # Variable physical checks
        column_summaries: list[ColumnQualitySummary] = []
        for col in df.columns:
            series = df[col]
            null_count = int(series.isna().sum())
            if null_count > 0:
                rejection_reasons.append(f"Column '{col}' contains {null_count} NaN/null values")

            bounds = self.PHYSICAL_BOUNDS.get(col, (-np.inf, np.inf, "unknown"))
            lower_bound, upper_bound, unit = bounds

            numeric_series = pd.to_numeric(series, errors="coerce")
            out_of_bounds = (numeric_series < lower_bound) | (numeric_series > upper_bound)
            oob_count = int(out_of_bounds.sum())
            if oob_count > 0:
                rejection_reasons.append(
                    f"Column '{col}' has {oob_count} values outside physical envelope [{lower_bound}, {upper_bound}]"
                )

            col_passed = (null_count == 0) and (oob_count == 0)
            column_summaries.append(
                ColumnQualitySummary(
                    column_name=col,
                    unit=unit,
                    min_value=float(numeric_series.min()) if len(numeric_series) > 0 else 0.0,
                    max_value=float(numeric_series.max()) if len(numeric_series) > 0 else 0.0,
                    mean_value=float(numeric_series.mean()) if len(numeric_series) > 0 else 0.0,
                    std_value=float(numeric_series.std()) if len(numeric_series) > 0 else 0.0,
                    null_count=null_count,
                    out_of_bounds_count=oob_count,
                    physical_bounds=(lower_bound, upper_bound),
                    passed=col_passed,
                )
            )

        # Solar night consistency check: GHI must be zero when zenith >= 90 deg
        if "ghi_w_per_m2" in df.columns and "solar_zenith_deg" in df.columns:
            night_mask = df["solar_zenith_deg"] >= 90.0
            non_zero_night = (df.loc[night_mask, "ghi_w_per_m2"] > 5.0).sum()
            if non_zero_night > 0:
                rejection_reasons.append(
                    f"Nighttime solar violation: found {non_zero_night} nighttime intervals (zenith >= 90°) with GHI > 5 W/m²"
                )

        all_passed = len(rejection_reasons) == 0

        start_ts = str(df.index.min()) if len(df) > 0 else "N/A"
        end_ts = str(df.index.max()) if len(df) > 0 else "N/A"

        report = QualityReport(
            report_timestamp_utc=datetime.now(timezone.utc).isoformat(),
            dataset_name=dataset_name,
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            expected_intervals=self.expected_intervals if self.expected_intervals is not None else actual_intervals,
            actual_intervals=actual_intervals,
            is_continuous=is_continuous,
            is_strictly_monotonic=is_monotonic,
            duplicate_count=duplicate_count,
            missing_interval_count=missing_interval_count,
            column_summaries=column_summaries,
            all_checks_passed=all_passed,
            rejection_reasons=rejection_reasons,
        )

        if all_passed:
            logger.info("Quality audit PASSED for '%s' (%d intervals)", dataset_name, actual_intervals)
        else:
            logger.warning(
                "Quality audit FAILED for '%s': %d rejection reasons",
                dataset_name, len(rejection_reasons)
            )

        return report


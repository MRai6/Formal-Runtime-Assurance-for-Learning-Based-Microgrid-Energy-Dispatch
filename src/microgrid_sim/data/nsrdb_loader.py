"""NREL National Solar Radiation Database (NSRDB) ingestion and aggregation pipeline.

Supports NREL Physical Solar Model (PSM) v4 and v3 data exports.
Implements physically grounded 5-minute to 15-minute energy-preserving block averaging.
"""

from pathlib import Path
from typing import Any, Optional, Union
import numpy as np
import pandas as pd
import pydantic

from microgrid_sim.utils.exceptions import ConfigurationError, DataProvenanceError
from microgrid_sim.utils.logger import get_logger

logger = get_logger(__name__)


class NSRDBHeaderMetadata(pydantic.BaseModel):
    """Metadata extracted from the NSRDB CSV header."""
    location_id: str
    latitude: float
    longitude: float
    elevation_m: float
    timezone_offset_hours: float
    source_model: str
    year: int


def circular_mean_degrees(angles_deg: Union[pd.Series, np.ndarray]) -> float:
    """Compute circular mean of directional angles in degrees [0, 360).

    Args:
        angles_deg: Series or array of directional angles [°].

    Returns:
        Mean directional angle in degrees [0, 360).
    """
    rad = np.deg2rad(angles_deg)
    sin_sum = np.sum(np.sin(rad))
    cos_sum = np.sum(np.cos(rad))
    mean_rad = np.arctan2(sin_sum, cos_sum)
    mean_deg = float(np.rad2deg(mean_rad)) % 360.0
    if abs(mean_deg - 360.0) < 1e-7 or abs(mean_deg) < 1e-7:
        mean_deg = 0.0
    return mean_deg


class NSRDBLoader:
    """Ingests and validates NREL NSRDB solar irradiance and meteorological data."""

    REQUIRED_RAW_COLUMNS = [
        "Year", "Month", "Day", "Hour", "Minute",
        "GHI", "DNI", "DHI", "Temperature", "Wind Speed", "Solar Zenith Angle"
    ]

    STANDARDIZED_COLUMN_MAP = {
        "GHI": "ghi_w_per_m2",
        "DNI": "dni_w_per_m2",
        "DHI": "dhi_w_per_m2",
        "Temperature": "ambient_temperature_c",
        "Wind Speed": "wind_speed_m_per_s",
        "Wind Direction": "wind_direction_deg",
        "Solar Zenith Angle": "solar_zenith_deg",
        "Surface Albedo": "surface_albedo",
    }

    def __init__(self, target_latitude: float = 39.7420, target_longitude: float = -105.1800, coord_tolerance_deg: float = 0.05) -> None:
        """Initialize the loader with expected benchmark coordinates.

        Args:
            target_latitude: Expected latitude [°N].
            target_longitude: Expected longitude [°W].
            coord_tolerance_deg: Maximum spatial deviation allowed between header and benchmark.
        """
        self.target_lat = target_latitude
        self.target_lon = target_longitude
        self.coord_tolerance = coord_tolerance_deg

    def parse_header(self, file_path: Path) -> NSRDBHeaderMetadata:
        """Extract and validate location and source metadata from standard NSRDB CSV header.

        Standard NSRDB CSV structure:
            Line 1: Metadata field names (Source,Location ID,Latitude,Longitude,Time Zone,Elevation,...)
            Line 2: Metadata values
            Line 3: Column variable names
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                header_names = f.readline().strip().split(",")
                header_vals = f.readline().strip().split(",")

            meta_dict = dict(zip(header_names, header_vals))

            # Case-insensitive header matching
            norm_dict = {k.strip().lower(): v.strip() for k, v in meta_dict.items()}

            lat = float(norm_dict.get("latitude", 0.0))
            lon = float(norm_dict.get("longitude", 0.0))
            elev = float(norm_dict.get("elevation", 0.0))
            tz = float(norm_dict.get("time zone", -7.0))
            source = norm_dict.get("source", "NSRDB PSM")
            loc_id = norm_dict.get("location id", "unknown")

            # Validate coordinates against target benchmark
            if abs(lat - self.target_lat) > self.coord_tolerance or abs(lon - self.target_lon) > self.coord_tolerance:
                raise DataProvenanceError(
                    f"NSRDB spatial coordinates ({lat:.4f}, {lon:.4f}) deviate from expected benchmark "
                    f"({self.target_lat:.4f}, {self.target_lon:.4f}) by more than tolerance {self.coord_tolerance}°",
                    details={"file_lat": lat, "file_lon": lon, "target_lat": self.target_lat, "target_lon": self.target_lon},
                )

            return NSRDBHeaderMetadata(
                location_id=str(loc_id),
                latitude=lat,
                longitude=lon,
                elevation_m=elev,
                timezone_offset_hours=tz,
                source_model=source,
                year=2018,
            )
        except (ValueError, IndexError, KeyError) as exc:
            raise DataProvenanceError(
                f"Failed to parse standard NSRDB CSV metadata header from {file_path}: {exc}",
                details={"file_path": str(file_path)},
            ) from exc

    def load_raw_csv(self, file_path: Path) -> tuple[pd.DataFrame, NSRDBHeaderMetadata]:
        """Load and validate raw NSRDB CSV time-series data.

        Returns:
            Tuple of (DataFrame with UTC DatetimeIndex, NSRDBHeaderMetadata).
        """
        if not file_path.is_file():
            raise FileNotFoundError(f"NSRDB raw data file not found: {file_path}")

        metadata = self.parse_header(file_path)

        # NSRDB CSV data begins at row index 2 (line 3 is column names)
        df_raw = pd.read_csv(file_path, skiprows=2)

        # Validate required columns
        missing_cols = [c for c in self.REQUIRED_RAW_COLUMNS if c not in df_raw.columns]
        if missing_cols:
            raise DataProvenanceError(
                f"NSRDB file {file_path.name} is missing required physical columns: {missing_cols}",
                details={"missing_columns": missing_cols, "available_columns": list(df_raw.columns)},
            )

        # Construct datetime from calendar fields (NSRDB native is Local Standard Time without DST)
        # For Colorado (Time Zone -7), native timestamps are Mountain Standard Time (UTC-7 year-round)
        tz_offset = int(metadata.timezone_offset_hours)
        dt_strings = (
            df_raw["Year"].astype(str) + "-" +
            df_raw["Month"].astype(str).str.zfill(2) + "-" +
            df_raw["Day"].astype(str).str.zfill(2) + " " +
            df_raw["Hour"].astype(str).str.zfill(2) + ":" +
            df_raw["Minute"].astype(str).str.zfill(2) + ":00"
        )
        # Parse into UTC by accounting for fixed local standard time offset
        # Note: Local Standard Time (e.g. UTC-7) has NO daylight saving jump, ensuring strict continuity
        tz_name = f"Etc/GMT{'+' if tz_offset <= 0 else '-'}{abs(tz_offset)}"
        timestamps_local = pd.to_datetime(dt_strings, format="%Y-%m-%d %H:%M:%S")
        timestamps_utc = timestamps_local.dt.tz_localize(tz_name).dt.tz_convert("UTC")

        df = pd.DataFrame(index=timestamps_utc)
        df.index.name = "timestamp_utc"

        # Standardize column names
        for raw_col, std_col in self.STANDARDIZED_COLUMN_MAP.items():
            if raw_col in df_raw.columns:
                df[std_col] = pd.to_numeric(df_raw[raw_col], errors="coerce").to_numpy().astype(np.float64)

        metadata.year = int(df_raw["Year"].iloc[0])
        return df, metadata

    def aggregate_to_15min(self, df_5min: pd.DataFrame) -> pd.DataFrame:
        """Perform physically grounded energy-preserving block averaging from 5-min to 15-min intervals.

        Physical Aggregation Rules:
            - Fluxes (GHI, DNI, DHI): Arithmetic mean over 3 intervals (preserves integrated radiant energy Wh/m²).
            - State Variables (Temperature, Wind Speed, Albedo): Arithmetic mean.
            - Directional Variables (Wind Direction): Circular vector mean.
            - Geometric Variables (Solar Zenith): Midpoint sample (index 1 of 3).
        """
        if len(df_5min) == 0:
            raise ValueError("Input DataFrame is empty")

        # Determine interval frequency
        deltas = df_5min.index[1:] - df_5min.index[:-1]
        median_delta_min = deltas.median().total_seconds() / 60.0

        if abs(median_delta_min - 15.0) < 0.1:
            logger.info("Data is already at 15-minute resolution; skipping aggregation")
            return df_5min

        if abs(median_delta_min - 5.0) > 0.1:
            raise DataProvenanceError(
                f"NSRDB data has native resolution of {median_delta_min:.1f} minutes. "
                "Only native 5-minute data can be block-averaged to 15 minutes. "
                "Coarser resolutions (e.g. 30-min or hourly) cannot be fabricated into 15-minute data."
            )

        # Group by 15-minute intervals starting at the top of each hour
        grouped = df_5min.groupby(pd.Grouper(freq="15min", closed="left", label="left"))

        agg_dict: dict[str, Any] = {}

        # 1. Radiant fluxes: arithmetic mean
        for flux_col in ["ghi_w_per_m2", "dni_w_per_m2", "dhi_w_per_m2"]:
            if flux_col in df_5min.columns:
                agg_dict[flux_col] = grouped[flux_col].mean()

        # 2. State variables: arithmetic mean
        for state_col in ["ambient_temperature_c", "wind_speed_m_per_s", "surface_albedo"]:
            if state_col in df_5min.columns:
                agg_dict[state_col] = grouped[state_col].mean()

        # 3. Wind direction: circular mean
        if "wind_direction_deg" in df_5min.columns:
            agg_dict["wind_direction_deg"] = grouped["wind_direction_deg"].apply(circular_mean_degrees)

        # 4. Solar zenith angle: midpoint sample
        if "solar_zenith_deg" in df_5min.columns:
            # Pick the middle sample of the 3 five-minute steps (index len//2)
            agg_dict["solar_zenith_deg"] = grouped["solar_zenith_deg"].apply(
                lambda s: s.iloc[len(s) // 2] if len(s) > 0 else np.nan
            )

        df_15min = pd.DataFrame(agg_dict)
        df_15min.index.name = "timestamp_utc"

        logger.info(
            "Successfully aggregated 5-min NSRDB data (%d rows) to 15-min intervals (%d rows)",
            len(df_5min), len(df_15min)
        )
        return df_15min


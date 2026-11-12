"""NREL ComStock commercial building electric load ingestion pipeline.

Ingests and validates NREL End-Use Load Profiles (EULP) for the MediumOffice archetype.
Converts 15-minute interval energy consumption [kWh] to average continuous power demand [kW].
"""

from pathlib import Path
from typing import Optional, Union
import numpy as np
import pandas as pd
import pydantic

from microgrid_sim.utils.exceptions import DataProvenanceError
from microgrid_sim.utils.logger import get_logger

logger = get_logger(__name__)


class ComStockBuildingMetadata(pydantic.BaseModel):
    """Metadata describing the specific ComStock building simulation model."""
    building_id: str
    building_type: str = "MediumOffice"
    county_fips: str
    county_name: str
    state: str = "CO"
    climate_zone: str = "5B"
    weather_year: int = 2018
    release_version: str = "ComStock Release 2022/2023 (AMY2018)"
    floor_area_sqft: float = 53600.0


class ComStockLoadLoader:
    """Ingests and validates NREL ComStock MediumOffice 15-minute load profiles."""

    STANDARD_TOTAL_ELEC_COLS = [
        "out.electricity.total.energy_consumption",
        "electricity_total_kwh",
        "total_electricity_kwh",
        "Electricity:Facility",
    ]

    SUB_LOAD_MAPPING = {
        "out.electricity.cooling.energy_consumption": "load_cooling_kw",
        "out.electricity.heating.energy_consumption": "load_heating_kw",
        "out.electricity.interior_equipment.energy_consumption": "load_equipment_kw",
        "out.electricity.interior_lighting.energy_consumption": "load_lighting_kw",
        "out.electricity.fans.energy_consumption": "load_fans_kw",
    }

    def __init__(self, target_county_fips: str = "08059", expected_year: int = 2018) -> None:
        """Initialize the load loader.

        Args:
            target_county_fips: Expected County FIPS code ("08059" for Jefferson County/Golden, CO;
                                "08031" for Denver County, CO).
            expected_year: Target weather calendar year (2018).
        """
        self.target_county_fips = target_county_fips
        self.expected_year = expected_year

    def load_load_profile(
        self,
        file_path: Path,
        metadata: Optional[ComStockBuildingMetadata] = None,
    ) -> tuple[pd.DataFrame, ComStockBuildingMetadata]:
        """Load and validate ComStock 15-minute load profile from Parquet or CSV.

        Args:
            file_path: Path to the data file.
            metadata: Optional pre-constructed metadata. If None, default metadata is generated.

        Returns:
            Tuple of (DataFrame with UTC DatetimeIndex and load_power_kw, ComStockBuildingMetadata).
        """
        if not file_path.is_file():
            raise FileNotFoundError(f"ComStock building load file not found: {file_path}")

        # Ingest file based on extension
        if file_path.suffix.lower() == ".parquet":
            df_raw = pd.read_parquet(file_path)
        else:
            df_raw = pd.read_csv(file_path)

        # Identify timestamp column
        ts_col = None
        for candidate in ["timestamp", "timestamp_utc", "datetime", "Date/Time", "time"]:
            if candidate in df_raw.columns:
                ts_col = candidate
                break

        if ts_col is None and not isinstance(df_raw.index, pd.DatetimeIndex):
            raise DataProvenanceError(
                f"Could not identify a timestamp column in {file_path.name}. "
                f"Available columns: {list(df_raw.columns[:10])}"
            )

        # Parse timestamps into canonical UTC without altering measurement times
        if isinstance(df_raw.index, pd.DatetimeIndex):
            dt_index = df_raw.index
        else:
            dt_index = pd.DatetimeIndex(pd.to_datetime(df_raw[ts_col]))

        # Localize naive timestamps to Mountain Standard Time (UTC-7, no DST) and convert to UTC
        if dt_index.tz is None:
            timestamps_utc = dt_index.tz_localize("Etc/GMT+7").tz_convert("UTC")
        else:
            timestamps_utc = dt_index.tz_convert("UTC")

        df = pd.DataFrame(index=timestamps_utc)
        df.index.name = "timestamp_utc"

        # Identify total electricity column
        total_col = None
        for candidate in self.STANDARD_TOTAL_ELEC_COLS:
            if candidate in df_raw.columns:
                total_col = candidate
                break

        if total_col is None:
            raise DataProvenanceError(
                f"Could not identify total electricity column in {file_path.name}. "
                f"Searched for candidates: {self.STANDARD_TOTAL_ELEC_COLS}"
            )

        # ComStock interval outputs are energy consumption [kWh per 15-min interval].
        # Convert energy [kWh] to average power [kW]: P_avg = E_interval / dt_hours = E * 4.0
        # If the column already represents power in kW (e.g. from a pre-processed file), keep as-is.
        raw_vals = pd.to_numeric(df_raw[total_col], errors="coerce").to_numpy().astype(np.float64)

        if "kw" in total_col.lower() or "facility" in total_col.lower():
            df["load_power_kw"] = raw_vals
        else:
            df["load_power_kw"] = raw_vals * 4.0

        # Map optional end-use sub-loads if available
        for raw_sub, std_sub in self.SUB_LOAD_MAPPING.items():
            if raw_sub in df_raw.columns:
                sub_vals = pd.to_numeric(df_raw[raw_sub], errors="coerce").to_numpy().astype(np.float64)
                df[std_sub] = sub_vals * 4.0 if "kw" not in raw_sub.lower() else sub_vals

        # Ensure chronological ordering
        df = df.sort_index()

        if metadata is None:
            metadata = ComStockBuildingMetadata(
                building_id=file_path.stem,
                county_fips=self.target_county_fips,
                county_name="Jefferson County (Golden, CO)" if self.target_county_fips == "08059" else "Denver County, CO",
                weather_year=self.expected_year,
            )

        logger.info(
            "Successfully ingested ComStock load profile (%d intervals, Peak: %.1f kW, Mean: %.1f kW)",
            len(df), df["load_power_kw"].max(), df["load_power_kw"].mean()
        )
        return df, metadata


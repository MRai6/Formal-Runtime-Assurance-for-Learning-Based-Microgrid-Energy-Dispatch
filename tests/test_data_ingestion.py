"""Unit and integration tests for authentic data ingestion, quality auditing, and preprocessor.

All test fixtures here are explicitly constructed for software unit testing of parsers,
statistical aggregations, physical bounds checkers, and temporal alignment logic.
They are isolated within temporary test directories and never written to production data stores.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from microgrid_sim.data.load_loader import ComStockBuildingMetadata, ComStockLoadLoader
from microgrid_sim.data.nsrdb_loader import (
    NSRDBHeaderMetadata,
    NSRDBLoader,
    circular_mean_degrees,
)
from microgrid_sim.data.preprocessor import BenchmarkDataPreprocessor
from microgrid_sim.data.quality import TimeSeriesQualityAuditor
from microgrid_sim.utils.exceptions import DataProvenanceError


# ==============================================================================
# 1. Circular Statistics Tests
# ==============================================================================

def test_circular_mean_degrees() -> None:
    """Verify circular vector averaging around the 0° / 360° north boundary."""
    # Symmetrical angles across 0° (North)
    angles = np.array([350.0, 0.0, 10.0])
    mean_angle = circular_mean_degrees(angles)
    assert pytest.approx(mean_angle, abs=1e-3) == 0.0 or pytest.approx(mean_angle, abs=1e-3) == 360.0

    # Angles in the first quadrant
    angles_quad1 = np.array([10.0, 20.0, 30.0])
    assert pytest.approx(circular_mean_degrees(angles_quad1), abs=1e-3) == 20.0

    # Wrapping around 360°
    angles_wrap = np.array([350.0, 355.0, 5.0])  # (-10, -5, +5) -> mean = -3.333° -> 356.667°
    assert pytest.approx(circular_mean_degrees(angles_wrap), abs=1e-2) == 356.67


# ==============================================================================
# 2. NSRDB Loader Tests
# ==============================================================================

@pytest.fixture
def sample_nsrdb_csv(tmp_path: Path) -> Path:
    """Generate a synthetic NSRDB CSV fixture conforming to official NREL PSM export format."""
    csv_file = tmp_path / "nsrdb_sample_5min.csv"
    
    # Official NSRDB CSV header structure:
    # Line 1: Metadata variable names
    # Line 2: Metadata values
    # Line 3: Time-series column names
    header = (
        "Source,Location ID,Latitude,Longitude,Time Zone,Elevation\n"
        "NSRDB PSM v4.0.0,123456,39.7420,-105.1800,-7,1829\n"
        "Year,Month,Day,Hour,Minute,GHI,DNI,DHI,Temperature,Wind Speed,Wind Direction,Solar Zenith Angle,Surface Albedo\n"
    )
    
    # 6 five-minute intervals (equivalent to 2 fifteen-minute intervals)
    # Timestamps in Local Standard Time (MST, UTC-7)
    rows = [
        "2018,6,21,12,0,800,900,100,25.0,3.0,350,15.0,0.18",
        "2018,6,21,12,5,830,910,105,25.3,3.2,0,14.5,0.18",
        "2018,6,21,12,10,860,920,110,25.6,3.4,10,14.0,0.18",
        "2018,6,21,12,15,890,930,115,25.9,3.6,20,13.8,0.18",
        "2018,6,21,12,20,910,940,120,26.2,3.8,25,13.5,0.18",
        "2018,6,21,12,25,930,950,125,26.5,4.0,30,13.2,0.18",
    ]
    csv_file.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    return csv_file


def test_nsrdb_header_parsing(sample_nsrdb_csv: Path) -> None:
    """Verify metadata extraction from standard NSRDB CSV header."""
    loader = NSRDBLoader(target_latitude=39.7420, target_longitude=-105.1800, coord_tolerance_deg=0.01)
    meta = loader.parse_header(sample_nsrdb_csv)
    
    assert isinstance(meta, NSRDBHeaderMetadata)
    assert meta.latitude == 39.7420
    assert meta.longitude == -105.1800
    assert meta.elevation_m == 1829.0
    assert meta.timezone_offset_hours == -7.0
    assert "PSM" in meta.source_model


def test_nsrdb_header_coordinate_mismatch_rejection(tmp_path: Path) -> None:
    """Verify DataProvenanceError when dataset coordinates deviate from expected benchmark."""
    csv_file = tmp_path / "nsrdb_wrong_coords.csv"
    csv_file.write_text(
        "Source,Location ID,Latitude,Longitude,Time Zone,Elevation\n"
        "NSRDB PSM,999,34.05,-118.24,-8,100\n"  # Los Angeles coordinates
        "Year,Month,Day,Hour,Minute,GHI,DNI,DHI,Temperature,Wind Speed,Solar Zenith Angle\n",
        encoding="utf-8"
    )
    loader = NSRDBLoader(target_latitude=39.7420, target_longitude=-105.1800, coord_tolerance_deg=0.05)
    with pytest.raises(DataProvenanceError) as exc_info:
        loader.parse_header(csv_file)
    assert "deviate from expected benchmark" in str(exc_info.value)


def test_nsrdb_raw_csv_loading_and_utc_conversion(sample_nsrdb_csv: Path) -> None:
    """Verify raw CSV loading, column standardization, and UTC index transformation."""
    loader = NSRDBLoader()
    df, meta = loader.load_raw_csv(sample_nsrdb_csv)
    
    assert len(df) == 6
    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) == "UTC"
    
    # Check that Local Standard Time 2018-06-21 12:00 (UTC-7) becomes 19:00 UTC
    assert df.index[0] == pd.Timestamp("2018-06-21 19:00:00", tz="UTC")
    
    # Check standardized column names
    assert "ghi_w_per_m2" in df.columns
    assert "dni_w_per_m2" in df.columns
    assert "ambient_temperature_c" in df.columns
    assert "solar_zenith_deg" in df.columns


def test_nsrdb_5min_to_15min_energy_preserving_aggregation(sample_nsrdb_csv: Path) -> None:
    """Verify that 5-to-15 minute block-averaging strictly preserves integrated radiant energy."""
    loader = NSRDBLoader()
    df_5min, _ = loader.load_raw_csv(sample_nsrdb_csv)
    df_15min = loader.aggregate_to_15min(df_5min)
    
    assert len(df_15min) == 2
    assert (df_15min.index[1] - df_15min.index[0]) == pd.Timedelta(minutes=15)
    
    # Expected GHI for first 15-min interval: mean(800, 830, 860) = 830.0 W/m²
    assert pytest.approx(df_15min["ghi_w_per_m2"].iloc[0], abs=1e-3) == 830.0
    # Expected GHI for second 15-min interval: mean(890, 910, 930) = 910.0 W/m²
    assert pytest.approx(df_15min["ghi_w_per_m2"].iloc[1], abs=1e-3) == 910.0
    
    # Conservation of radiant energy exposure:
    # Energy_5min = sum(GHI_5min * 5/60 hours)
    # Energy_15min = sum(GHI_15min * 15/60 hours)
    energy_5min_wh = (df_5min["ghi_w_per_m2"] * (5.0 / 60.0)).sum()
    energy_15min_wh = (df_15min["ghi_w_per_m2"] * (15.0 / 60.0)).sum()
    assert pytest.approx(energy_15min_wh, abs=1e-6) == energy_5min_wh

    # Verify circular mean for wind direction: [350, 0, 10] -> 0.0°
    assert pytest.approx(df_15min["wind_direction_deg"].iloc[0], abs=1e-2) == 0.0

    # Verify midpoint sample for solar zenith:
    # Interval 1 zenith angles: [15.0, 14.5, 14.0] -> midpoint (index 1) is 14.5°
    assert pytest.approx(df_15min["solar_zenith_deg"].iloc[0], abs=1e-3) == 14.5


def test_nsrdb_aggregation_rejects_non_5min_frequency(tmp_path: Path) -> None:
    """Verify rejection of 30-minute or hourly datasets attempting interpolation to 15-min."""
    loader = NSRDBLoader()
    # Create 30-minute data
    idx_30min = pd.date_range("2018-01-01 00:00:00", periods=4, freq="30min", tz="UTC")
    df_30min = pd.DataFrame({"ghi_w_per_m2": [100.0, 200.0, 300.0, 400.0]}, index=idx_30min)
    
    with pytest.raises(DataProvenanceError) as exc_info:
        loader.aggregate_to_15min(df_30min)
    assert "Only native 5-minute data can be block-averaged" in str(exc_info.value)


# ==============================================================================
# 3. ComStock Load Loader Tests
# ==============================================================================

@pytest.fixture
def sample_comstock_csv(tmp_path: Path) -> Path:
    """Generate a synthetic ComStock building load profile fixture (15-min interval energy)."""
    csv_file = tmp_path / "comstock_sample_15min.csv"
    
    # Timestamps in Local Standard Time (MST, UTC-7)
    timestamps = [
        "2018-06-21 12:00:00",
        "2018-06-21 12:15:00",
        "2018-06-21 12:30:00",
        "2018-06-21 12:45:00",
    ]
    # Energy consumption in kWh per 15-minute interval
    # e.g. 25.0 kWh in 15 min = 100.0 kW average power
    data = {
        "timestamp": timestamps,
        "out.electricity.total.energy_consumption": [25.0, 30.0, 28.0, 32.0],
        "out.electricity.cooling.energy_consumption": [10.0, 12.0, 11.0, 13.0],
    }
    pd.DataFrame(data).to_csv(csv_file, index=False)
    return csv_file


def test_comstock_load_profile_ingestion_and_kwh_to_kw(sample_comstock_csv: Path) -> None:
    """Verify conversion of 15-minute interval energy [kWh] to average continuous power [kW]."""
    loader = ComStockLoadLoader(target_county_fips="08059", expected_year=2018)
    df, meta = loader.load_load_profile(sample_comstock_csv)
    
    assert len(df) == 4
    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) == "UTC"
    
    # 2018-06-21 12:00:00 MST (UTC-7) becomes 19:00:00 UTC
    assert df.index[0] == pd.Timestamp("2018-06-21 19:00:00", tz="UTC")
    
    # Energy to power conversion: P = E / dt = 25.0 / 0.25 = 100.0 kW
    assert pytest.approx(df["load_power_kw"].iloc[0], abs=1e-3) == 100.0
    assert pytest.approx(df["load_power_kw"].iloc[1], abs=1e-3) == 120.0
    assert pytest.approx(df["load_power_kw"].iloc[2], abs=1e-3) == 112.0
    assert pytest.approx(df["load_power_kw"].iloc[3], abs=1e-3) == 128.0
    
    # Sub-load conversion
    assert pytest.approx(df["load_cooling_kw"].iloc[0], abs=1e-3) == 40.0
    
    # Metadata verification
    assert meta.county_fips == "08059"
    assert "Jefferson County" in meta.county_name
    assert meta.climate_zone == "5B"


def test_comstock_missing_columns_raises_error(tmp_path: Path) -> None:
    """Verify DataProvenanceError when total electricity column is absent."""
    csv_file = tmp_path / "invalid_comstock.csv"
    pd.DataFrame({"timestamp": ["2018-01-01 00:00:00"], "gas_consumption": [10.0]}).to_csv(csv_file, index=False)
    
    loader = ComStockLoadLoader()
    with pytest.raises(DataProvenanceError) as exc_info:
        loader.load_load_profile(csv_file)
    assert "Could not identify total electricity column" in str(exc_info.value)


# ==============================================================================
# 4. Data Quality Auditor Tests
# ==============================================================================

def test_quality_auditor_clean_annual_dataset() -> None:
    """Verify that a compliant 35,040-step annual dataset passes all audit checks."""
    idx = pd.date_range("2018-01-01 00:00:00", "2018-12-31 23:45:00", freq="15min", tz="UTC")
    assert len(idx) == 35040

    df = pd.DataFrame(
        {
            "ghi_w_per_m2": np.full(35040, 200.0),
            "dni_w_per_m2": np.full(35040, 300.0),
            "dhi_w_per_m2": np.full(35040, 100.0),
            "ambient_temperature_c": np.full(35040, 15.0),
            "wind_speed_m_per_s": np.full(35040, 4.0),
            "solar_zenith_deg": np.full(35040, 45.0),
            "load_power_kw": np.full(35040, 80.0),
        },
        index=idx,
    )
    
    auditor = TimeSeriesQualityAuditor(expected_intervals=35040, freq_minutes=15)
    report = auditor.audit(df, dataset_name="annual_test_clean")
    
    assert report.all_checks_passed is True
    assert report.is_continuous is True
    assert report.is_strictly_monotonic is True
    assert report.duplicate_count == 0
    assert report.missing_interval_count == 0
    assert len(report.rejection_reasons) == 0


def test_quality_auditor_detects_interval_count_mismatch() -> None:
    """Verify detection when annual intervals are missing (incomplete year)."""
    idx = pd.date_range("2018-01-01 00:00:00", periods=1000, freq="15min", tz="UTC")
    df = pd.DataFrame({"ghi_w_per_m2": np.full(1000, 200.0)}, index=idx)
    
    auditor = TimeSeriesQualityAuditor(expected_intervals=35040, freq_minutes=15)
    report = auditor.audit(df, dataset_name="short_dataset")
    
    assert report.all_checks_passed is False
    assert any("Interval count mismatch" in r for r in report.rejection_reasons)


def test_quality_auditor_detects_duplicate_timestamps() -> None:
    """Verify rejection when duplicate timestamp intervals exist."""
    idx = list(pd.date_range("2018-01-01 00:00:00", periods=5, freq="15min", tz="UTC"))
    idx.append(idx[-1])  # Duplicate last timestamp
    idx_series = pd.DatetimeIndex(idx)
    
    df = pd.DataFrame({"ghi_w_per_m2": np.full(len(idx), 200.0)}, index=idx_series)
    auditor = TimeSeriesQualityAuditor(expected_intervals=len(idx), freq_minutes=15)
    report = auditor.audit(df)
    
    assert report.all_checks_passed is False
    assert report.duplicate_count == 1
    assert any("duplicate timestamp intervals" in r for r in report.rejection_reasons)


def test_quality_auditor_detects_physical_out_of_bounds() -> None:
    """Verify rejection of unphysical values: negative GHI, excessive load, extreme temp."""
    idx = pd.date_range("2018-01-01 00:00:00", periods=5, freq="15min", tz="UTC")
    df = pd.DataFrame(
        {
            "ghi_w_per_m2": [100.0, -5.0, 200.0, 300.0, 1400.0],  # -5 is < 0; 1400 is > 1350
            "ambient_temperature_c": [15.0, 20.0, -50.0, 25.0, 30.0],  # -50 is < -40
            "load_power_kw": [50.0, 60.0, 70.0, -10.0, 600.0],  # -10 is < 0; 600 is > 500
        },
        index=idx,
    )
    auditor = TimeSeriesQualityAuditor(expected_intervals=5, freq_minutes=15)
    report = auditor.audit(df)
    
    assert report.all_checks_passed is False
    assert any("ghi_w_per_m2" in r and "outside physical envelope" in r for r in report.rejection_reasons)
    assert any("ambient_temperature_c" in r and "outside physical envelope" in r for r in report.rejection_reasons)
    assert any("load_power_kw" in r and "outside physical envelope" in r for r in report.rejection_reasons)


def test_quality_auditor_detects_nighttime_solar_violation() -> None:
    """Verify rejection when positive irradiance occurs while solar zenith >= 90°."""
    idx = pd.date_range("2018-01-01 00:00:00", periods=3, freq="15min", tz="UTC")
    df = pd.DataFrame(
        {
            "ghi_w_per_m2": [0.0, 50.0, 0.0],  # 50 W/m² at night is a physical violation
            "solar_zenith_deg": [100.0, 110.0, 120.0],
        },
        index=idx,
    )
    auditor = TimeSeriesQualityAuditor(expected_intervals=3, freq_minutes=15)
    report = auditor.audit(df)
    
    assert report.all_checks_passed is False
    assert any("Nighttime solar violation" in r for r in report.rejection_reasons)


def test_quality_auditor_detects_non_monotonic_timestamps() -> None:
    """Verify rejection when timestamps are not strictly monotonically increasing."""
    # Construct out-of-order timestamps
    t0 = pd.Timestamp("2018-01-01 00:00:00", tz="UTC")
    t1 = pd.Timestamp("2018-01-01 00:30:00", tz="UTC")
    t2 = pd.Timestamp("2018-01-01 00:15:00", tz="UTC")  # Out of order!
    idx = pd.DatetimeIndex([t0, t1, t2])
    
    df = pd.DataFrame({"load_power_kw": [50.0, 60.0, 70.0]}, index=idx)
    auditor = TimeSeriesQualityAuditor(expected_intervals=3, freq_minutes=15)
    report = auditor.audit(df)
    
    assert report.all_checks_passed is False
    assert report.is_strictly_monotonic is False
    assert report.is_continuous is False
    assert any("not strictly monotonically increasing" in r for r in report.rejection_reasons)


def test_quality_auditor_detects_temporal_gap() -> None:
    """Verify detection when a 15-minute gap exists between monotonic observations."""
    t0 = pd.Timestamp("2018-01-01 00:00:00", tz="UTC")
    t1 = pd.Timestamp("2018-01-01 00:15:00", tz="UTC")
    t2 = pd.Timestamp("2018-01-01 00:45:00", tz="UTC")  # Missing 00:30:00!
    idx = pd.DatetimeIndex([t0, t1, t2])
    
    df = pd.DataFrame({"load_power_kw": [50.0, 60.0, 70.0]}, index=idx)
    auditor = TimeSeriesQualityAuditor(expected_intervals=3, freq_minutes=15)
    report = auditor.audit(df)
    
    assert report.all_checks_passed is False
    assert report.is_continuous is False
    assert report.missing_interval_count == 1
    assert any("Temporal discontinuities detected" in r for r in report.rejection_reasons)


# ==============================================================================
# 5. Benchmark Data Preprocessor & Parquet Export Tests
# ==============================================================================

def test_benchmark_data_preprocessor_merge_and_export(tmp_path: Path) -> None:
    """Verify end-to-end alignment onto canonical 35,040-step UTC index and Parquet export."""
    idx = pd.date_range("2018-01-01 00:00:00", "2018-12-31 23:45:00", freq="15min", tz="UTC")
    
    df_solar = pd.DataFrame(
        {
            "ghi_w_per_m2": np.full(35040, 250.0),
            "dni_w_per_m2": np.full(35040, 400.0),
            "dhi_w_per_m2": np.full(35040, 80.0),
            "ambient_temperature_c": np.full(35040, 18.0),
            "wind_speed_m_per_s": np.full(35040, 3.5),
            "solar_zenith_deg": np.full(35040, 50.0),
        },
        index=idx,
    )
    
    df_load = pd.DataFrame(
        {"load_power_kw": np.full(35040, 95.0)},
        index=idx,
    )
    
    preprocessor = BenchmarkDataPreprocessor(target_year=2018, freq_minutes=15, expected_intervals=35040)
    merged_df, report = preprocessor.align_and_merge(
        df_solar_15min=df_solar,
        df_load_15min=df_load,
        dataset_name="denver_cz5b_2018_test",
    )
    
    assert len(merged_df) == 35040
    assert report.all_checks_passed is True
    assert "ghi_w_per_m2" in merged_df.columns
    assert "load_power_kw" in merged_df.columns
    
    # Export to Parquet
    parquet_path = tmp_path / "processed" / "denver_cz5b_2018_test.parquet"
    preprocessor.save_processed_parquet(merged_df, parquet_path, quality_report=report)
    
    assert parquet_path.is_file()
    assert parquet_path.with_suffix(".quality_report.json").is_file()
    
    # Reload and verify integrity
    reloaded_df = pd.read_parquet(parquet_path)
    assert len(reloaded_df) == 35040
    assert list(reloaded_df.columns) == list(merged_df.columns)
    assert pytest.approx(reloaded_df["load_power_kw"].mean(), abs=1e-3) == 95.0


def test_benchmark_data_preprocessor_timezone_naive_rejection() -> None:
    """Verify DataProvenanceError when inputs lack timezone-aware UTC DatetimeIndex."""
    idx_naive = pd.date_range("2018-01-01 00:00:00", periods=10, freq="15min")  # No tz!
    df_solar = pd.DataFrame({"ghi_w_per_m2": np.full(10, 200.0)}, index=idx_naive)
    df_load = pd.DataFrame({"load_power_kw": np.full(10, 80.0)}, index=idx_naive)
    
    preprocessor = BenchmarkDataPreprocessor(target_year=2018, freq_minutes=15, expected_intervals=10)
    with pytest.raises(DataProvenanceError) as exc_info:
        preprocessor.align_and_merge(df_solar, df_load)
    assert "timezone-aware" in str(exc_info.value).lower()


def test_benchmark_data_preprocessor_incomplete_horizon_rejection() -> None:
    """Verify DataProvenanceError when inputs do not cover the complete annual horizon."""
    # Only 10 intervals provided instead of 35,040
    idx = pd.date_range("2018-01-01 00:00:00", periods=10, freq="15min", tz="UTC")
    df_solar = pd.DataFrame({"ghi_w_per_m2": np.full(10, 200.0)}, index=idx)
    df_load = pd.DataFrame({"load_power_kw": np.full(10, 80.0)}, index=idx)
    
    preprocessor = BenchmarkDataPreprocessor(target_year=2018, freq_minutes=15, expected_intervals=35040)
    with pytest.raises(DataProvenanceError) as exc_info:
        preprocessor.align_and_merge(df_solar, df_load)
    assert "quality audit failed" in str(exc_info.value).lower()


def test_authentic_processed_benchmark_dataset_integrity(project_root: Path) -> None:
    """Verify authentic processed benchmark dataset if present in data/processed/."""
    benchmark_path = project_root / "data" / "processed" / "denver_cz5b_2018_15min.parquet"
    if not benchmark_path.is_file():
        pytest.skip("Authentic benchmark dataset not downloaded; skipping live data integrity test")

    df = pd.read_parquet(benchmark_path)
    # The genuine common chronological overlap between UTC 2018 solar and MST 2018 load is 35,011 intervals
    assert len(df) == 35011
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.tz is not None
    assert str(df.index.tz) == "UTC"
    assert df.index[0] == pd.Timestamp("2018-01-01 07:15:00", tz="UTC")
    assert df.index[-1] == pd.Timestamp("2018-12-31 23:45:00", tz="UTC")

    # Core required physical variables
    expected_cols = [
        "ghi_w_per_m2", "dni_w_per_m2", "dhi_w_per_m2",
        "ambient_temperature_c", "solar_zenith_deg", "load_power_kw"
    ]
    for col in expected_cols:
        assert col in df.columns
        assert df[col].isna().sum() == 0

    # Physical bounds checks
    assert df["ghi_w_per_m2"].min() >= 0.0
    assert df["ghi_w_per_m2"].max() <= 1350.0
    assert df["load_power_kw"].min() > 0.0
    assert df["load_power_kw"].max() < 500.0


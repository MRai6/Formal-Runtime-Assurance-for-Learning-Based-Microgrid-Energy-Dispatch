# Data Quality Assurance and Audit Specification

## 1. Quality Assurance Architecture

The `microgrid_sim` data pipeline incorporates a dedicated validation engine: `TimeSeriesQualityAuditor` (implemented in `src/microgrid_sim/data/quality.py`). This engine guarantees that empirical datasets satisfy physical, statistical, and temporal invariants before being ingested by the physics simulation or reinforcement learning environment.

Every preprocessed benchmark file generates a companion machine-readable certification:
`<dataset_name>.quality_report.json`

---

## 2. Physical Bounds for Colorado Front Range (Climate Zone 5B)

All continuous state variables are evaluated against physical feasibility envelopes established for Golden/Denver, Colorado (Elevation $\approx 1829\,\text{m}$, ASHRAE Climate Zone 5B):

| Variable Name | Internal Column | Min Bound | Max Bound | Unit | Physical Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Global Horizontal Irradiance** | `ghi_w_per_m2` | $0.0$ | $1350.0$ | $\text{W}/\text{m}^2$ | Solar constant upper bound ($\approx 1361\,\text{W}/\text{m}^2$) plus cloud edge enhancement. |
| **Direct Normal Irradiance** | `dni_w_per_m2` | $0.0$ | $1150.0$ | $\text{W}/\text{m}^2$ | Maximum terrestrial direct beam radiation at high elevation. |
| **Diffuse Horizontal Irradiance** | `dhi_w_per_m2` | $0.0$ | $800.0$ | $\text{W}/\text{m}^2$ | Maximum atmospheric Rayleigh/Mie scattering flux. |
| **Ambient Temperature** | `ambient_temperature_c` | $-40.0$ | $48.0$ | $^\circ\text{C}$ | Historical extreme temperatures recorded in Colorado Front Range. |
| **Wind Speed** | `wind_speed_m_per_s` | $0.0$ | $45.0$ | $\text{m}/\text{s}$ | High-elevation Chinook gust upper envelope ($45\,\text{m}/\text{s} \approx 162\,\text{km}/\text{h}$). |
| **Solar Zenith Angle** | `solar_zenith_deg` | $0.0$ | $180.0$ | $\text{deg}$ | Geometric horizon boundaries ($0^\circ = \text{zenith}$, $90^\circ = \text{horizon}$, $180^\circ = \text{nadir}$). |
| **Building Load Demand** | `load_power_kw` | $0.0$ | $500.0$ | $\text{kW}$ | Building non-generation invariant ($P_{\text{load}} \ge 0$) and $3\times$ peak design limit for $53,600\,\text{ft}^2$ office. |

---

## 3. Strict Rejection Invariants

An empirical time series is **immediately rejected** if any of the following conditions are violated:

1. **Incomplete Annual Horizon**:
   The number of rows must equal exactly $N = 35,040$ for the 2018 non-leap year ($365 \times 24 \times 4$). Incomplete time series cannot support complete annual energy balance.
2. **Non-Monotonic Timestamps**:
   Timestamps must be strictly monotonically increasing: $t_{k+1} > t_k$. Out-of-order records indicate corrupted data transfers.
3. **Duplicate Timestamps**:
   No repeated intervals are allowed: $|\{t_k\}| = N$.
4. **Temporal Discontinuities**:
   All adjacent intervals must satisfy $t_{k+1} - t_k = 15\,\text{minutes}$. Any missing interval is flagged.
5. **Null or Missing Data (NaN)**:
   Any missing measurement causes immediate rejection. Silent interpolation or zero-filling is forbidden.
6. **Physical Out-of-Bounds**:
   Any measurement outside the physical envelope raises a violation.
7. **Nighttime Solar Irradiance Violation**:
   When the solar zenith angle $\theta_z \ge 90.0^\circ$ (sun below horizon), measured GHI must be $\le 5.0\,\text{W}/\text{m}^2$. Non-zero irradiance during night indicates pyranometer sensor thermal offset or calibration drift.

---

## 4. Machine-Readable Quality Report Schema

The `QualityReport` Pydantic model produces structured JSON reports conforming to the following structure:

```json
{
  "report_timestamp_utc": "2026-11-12T17:45:00.000000+00:00",
  "dataset_name": "denver_cz5b_2018_15min",
  "start_timestamp": "2018-01-01 00:00:00+00:00",
  "end_timestamp": "2018-12-31 23:45:00+00:00",
  "expected_intervals": 35040,
  "actual_intervals": 35040,
  "is_continuous": true,
  "is_strictly_monotonic": true,
  "duplicate_count": 0,
  "missing_interval_count": 0,
  "column_summaries": [
    {
      "column_name": "ghi_w_per_m2",
      "unit": "W/m^2",
      "min_value": 0.0,
      "max_value": 1058.2,
      "mean_value": 204.6,
      "std_value": 298.4,
      "null_count": 0,
      "out_of_bounds_count": 0,
      "physical_bounds": [0.0, 1350.0],
      "passed": true
    },
    {
      "column_name": "load_power_kw",
      "unit": "kW",
      "min_value": 18.4,
      "max_value": 164.8,
      "mean_value": 62.7,
      "std_value": 31.2,
      "null_count": 0,
      "out_of_bounds_count": 0,
      "physical_bounds": [0.0, 500.0],
      "passed": true
    }
  ],
  "all_checks_passed": true,
  "rejection_reasons": []
}
```

---

## 5. Official Dataset Verification Statuses

Following the required four-tier research lifecycle:

| Status Tier | Definition |
| :--- | :--- |
| **Tier 1: Source documentation verified** | Official documentation, persistent identifiers, APIs, endpoints, and coordinate parameters verified and logged. |
| **Tier 2: Dataset successfully downloaded** | Raw files acquired from official provider without alteration and verified with SHA-256 hash. |
| **Tier 3: Dataset successfully validated** | Ingested, aggregated, temporally aligned to 35,040 steps, and audited with zero quality rejections. |
| **Tier 4: Dataset accepted for experiments** | Standardized Parquet dataset approved by research leads for physical simulation and reinforcement learning. |

### Current Status Matrix

| Dataset Identifier | Provenance Class | Current Status | Notes |
| :--- | :--- | :--- | :--- |
| `nsrdb_goes_conus_2018` | Satellite-derived model (NREL PSM v4) | **Tier 1: Source documentation verified** | Endpoint and 5-to-15 min block-averaging verified; ready for download via NREL API key. |
| `comstock_medium_office_cz5b_2018` | Calibrated building simulation (ComStock Release 1) | **Tier 1: Source documentation verified** | Endpoint and energy-to-power conversion ($P=4E$) verified; ready for download via OEDI S3 bucket. |
| `urdb_psco_xcel_schedule_sg_2023` | Codified regulatory utility tariff (PSCo Schedule SG) | **Tier 1: Source documentation verified** | Codified in `configs/grid_tariff_spec.yaml`; fully validated in test suite. |
| `nrel_srrl_bms_ground_truth_2018` | Directly measured observation (NREL MIDC SRRL) | **Tier 1: Source documentation verified** | Ground-truth reference for physical validation comparison. |


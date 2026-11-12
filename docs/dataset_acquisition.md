# Dataset Acquisition and Scientific Provenance Specification

## 1. Scientific Principles & Non-Negotiable Rules

In accordance with academic research standards and the project charter for **Formal Runtime Assurance for Learning-Based Microgrid Energy Dispatch**, dataset acquisition adheres strictly to these principles:

1. **Authenticity Only**: No synthetic, randomly generated, interpolated, or fabricated observations are permitted in the empirical training or evaluation pipelines.
2. **Preservation of Raw Ingestion**: All downloaded raw files must remain unmodified in `data/raw/`. Checksums are calculated immediately upon receipt.
3. **Traceability and DOIs**: Every dataset must be referenced with its official persistent identifier (DOI), providing organization, license, and acquisition timestamp.
4. **Reproducibility**: Acquisition scripts and parameters must be fully documented and executable by independent researchers.
5. **Separation of Provenance Classes**: Clearly distinguish between satellite-derived physical models, building energy simulation outputs, regulatory utility tariffs, and ground-truth measurement observations.

---

## 2. NREL NSRDB Solar Irradiance & Weather Resource

### 2.1 Dataset Profile
- **Provider**: National Renewable Energy Laboratory (NREL), National Aeronautics and Space Administration (NASA), National Oceanic and Atmospheric Administration (NOAA).
- **Official Dataset Name**: National Solar Radiation Database (NSRDB) Physical Solar Model (PSM) GOES CONUS.
- **Product Versions**:
  - **PSM v4.0.0 (High Resolution)**: 2 km spatial grid, native 5-minute temporal resolution.
  - **PSM v3.2.2 (Standard Archive)**: 4 km spatial grid, native 30-minute / 60-minute resolution.
- **Official Persistent Identifier**: DOI: [10.1016/j.rser.2018.03.003](https://doi.org/10.1016/j.rser.2018.03.003)
- **Licensing**: Public Domain / Creative Commons CC0 1.0 Universal (U.S. Federal Government Work).
- **Target Coordinates**:
  - Latitude: $39.7420^\circ\text{N}$
  - Longitude: $-105.1800^\circ\text{W}$
  - Elevation: $1829.0\,\text{m}$
  - Region: Golden, Colorado (NREL South Table Mountain Campus).
- **Target Weather Year**: 2018 (365 days, 35,040 15-minute dispatch steps).

### 2.2 Native Source Resolution vs API Output Interval Semantics
Official NREL Developer API documentation (`https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-GOES-conus-v4-0-0-download/`) clarifies an important technical distinction:
- **Native Physical Model Resolution**: The underlying GOES CONUS PSM v4 dataset has a **native 5-minute temporal resolution** and a 2 km spatial grid.
- **API Output Intervals**: The NREL Developer API allows users to request output intervals of **`5`**, **`15`**, **`30`**, or **`60`** minutes via the `interval` query parameter.
- **Provider-Generated 15-minute Output vs Local Aggregation**:
  1. *Provider-Generated (NREL API `interval=15`)*: The API downsamples native 5-minute data on the server. Depending on API version internals, server-side downsampling may apply snapshot sampling or simple averaging.
  2. *Local Energy-Preserving Aggregation (`NSRDBLoader.aggregate_to_15min`)*: Our ingestion engine downloads the native 5-minute observations and performs mathematically verified block averaging:
     $$\bar{G}_{15} = \frac{1}{3} \sum_{k=1}^3 G_{5,k}$$
     This explicitly preserves integrated radiant exposure $\int G dt$, computes the circular vector mean for wind direction ($\text{atan2}$), and samples the geometric midpoint ($k=1$) for solar zenith angle.
- **Benchmark Selection**:
  - Our primary scientific benchmark uses **local aggregation of native 5-minute data** because it guarantees exact energy conservation, directional wind integrity, and verifiable auditability.
  - However, `NSRDBLoader` fully supports **direct ingestion of provider-generated 15-minute files** (detecting native 15-min cadence when $\Delta t = 15\,\text{min}$) to accommodate users who download pre-aggregated files directly.

### 2.3 AWS Open Data Paths vs Developer API
- **NREL Developer REST API**: Points to `https://developer.nrel.gov/api/nsrdb/v2/solar/nsrdb-GOES-conus-v4-0-0-download.csv`. Requires an API key (obtained from `developer.nrel.gov`).
- **AWS Registry of Open Data**:
  - `s3://nrel-pds-nsrdb/v3/`: Contains PSM v3 at 4 km $\times$ 30-minute resolution (1998–2020).
  - `s3://nrel-pds-nsrdb/conus/v4.0.0/`: Contains GOES CONUS PSM v4 at 2 km $\times$ 5-minute resolution (2018–present) in HDF5 format.

### 2.4 Acquisition Methods

#### Method A: Official NREL Developer API (Single-Point 5-min or 15-min Download)
```bash
# Set NREL API key in environment
export NREL_API_KEY="YOUR_API_KEY_HERE"

# Download 2018 native 5-minute GOES CONUS PSM v4 dataset for Golden, CO
curl -G "https://developer.nrel.gov/api/nsrdb/v2/solar/nsrdb-GOES-conus-v4-0-0-download.csv" \
  --data-urlencode "wkt=POINT(-105.1800 39.7420)" \
  --data-urlencode "names=2018" \
  --data-urlencode "leap_day=false" \
  --data-urlencode "interval=5" \
  --data-urlencode "utc=false" \
  --data-urlencode "full_name=MicrogridResearch" \
  --data-urlencode "email=research@microgrid.org" \
  --data-urlencode "affiliation=EnergySystemsLab" \
  --data-urlencode "mailing_list=false" \
  --data-urlencode "reason=AcademicResearch" \
  --data-urlencode "api_key=${NREL_API_KEY}" \
  --data-urlencode "attributes=ghi,dni,dhi,air_temperature,wind_speed,wind_direction,solar_zenith_angle,surface_albedo" \
  -o "data/raw/nsrdb_golden_co_2018_5min.csv"
```

#### Method B: AWS Open Data (S3 Direct Access)
```bash
# Query S3 public bucket without AWS credentials
aws s3 cp s3://nrel-pds-nsrdb/conus/v4.0.0/2018/nsrdb_2018.h5 ./data/raw/ --no-sign-request
```

---

## 3. NREL ComStock Commercial Building Electric Load

### 3.1 Dataset Profile
- **Provider**: National Renewable Energy Laboratory (NREL) / U.S. Department of Energy (DOE) Building Technologies Office.
- **Dataset Name**: End-Use Load Profiles for the U.S. Building Stock (ComStock).
- **Release Version**: ComStock Release 1 (AMY2018 Weather) / OpenEI Submission 4520.
- **Official Persistent Identifiers**:
  - **Dataset Citation DOI**: [10.25984/1876417](https://doi.org/10.25984/1876417) (OSTI ID: 1876417, OpenEI Submission 4520).
  - **Methodology Technical Report**: DOI: [10.2172/1832646](https://doi.org/10.2172/1832646) (NREL/TP-5500-80889).
- **Licensing**: Creative Commons Attribution 4.0 International (CC-BY 4.0).
- **Target Building Archetype**: `MediumOffice` (ASHRAE Standard 90.1 prototype).
  - Conditioned Floor Area: $53,600\,\text{ft}^2$ ($4,980\,\text{m}^2$).
  - Climate Zone: ASHRAE Climate Zone 5B (Cool - Dry).
  - Weather Alignment: Actual Meteorological Year 2018 (AMY2018).
  - Peak Electrical Demand: $\approx 165\,\text{kW}$.

### 3.2 S3 Bucket Structure & Metadata Inspection Discipline
The ComStock AMY2018 dataset is hosted on AWS S3 via the Open Energy Data Initiative (OEDI) Data Lake:
`s3://oedi-data-lake/nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/2021/comstock_amy2018_release_1/`

Sub-paths:
- **Building Stock Metadata**:
  `metadata_and_annual_results/national/parquet/metadata.parquet`
- **Individual Timeseries Results**:
  `timeseries_individual_buildings/by_state/upgrade=0/state=CO/`

### 3.3 Geographic Discipline: Jefferson County (FIPS 08059) vs Denver County (FIPS 08031)
- Golden, Colorado (NREL South Table Mountain) is in **Jefferson County (FIPS 08059)**.
- Denver, Colorado is in **Denver County (FIPS 08031)**.
- Both counties belong to ASHRAE Climate Zone 5B.
- **Scientific Audit Rule**: We do **not** assume a specific `bldg_id` exists in Jefferson County without inspecting `metadata.parquet`.
- **Protocol**:
  1. Inspect `metadata.parquet` for rows where `in.state = 'CO'`, `in.building_type_comstock = 'MediumOffice'`, and `in.county = 'G0800590'` (Jefferson County).
  2. If one or more `MediumOffice` models exist in Jefferson County, select the representative median-sized baseline building.
  3. If **no** `MediumOffice` model exists for Jefferson County in the ComStock sample, report available alternatives within Climate Zone 5B (e.g., Denver County `G0800310` or Arapahoe County `G0800050`). **Do not substitute Denver County without explicit team and user approval.**

### 3.4 Raw Electrical Demand Column and Units
- Primary Timeseries Column: `out.electricity.total.energy_consumption`.
- Native Units: **kWh** per 15-minute interval.
- Conversion to Average Power: $P_{\text{load}} [\text{kW}] = 4.0 \times E_{\text{interval}} [\text{kWh}]$.

---

## 4. PSCo / Xcel Energy Electric Tariff (Schedule SG)

### 4.1 Tariff Profile & Regulatory Source
- **Utility**: Public Service Company of Colorado (PSCo), operating company of Xcel Energy.
- **Regulatory Jurisdiction**: Colorado Public Utilities Commission (CPUC).
- **Tariff Book**: Colorado P.U.C. No. 8 – Electric Tariff Book.
- **Schedule**: Schedule SG – Secondary General Service (Sheet No. 43 et seq.).
- **CPUC Reference**: Advice Letter No. 1923-Electric / Proceeding No. 19AL-0268E / OpenEI URDB Rate ID 15466.

### 4.2 Provisional Economic Benchmark Designation
In 2018, Schedule SG rates in Colorado P.U.C. No. 8 were structured under earlier general rate cases (with non-TOU demand rates or early pilot TOU riders), while modern TOU rates (e.g. Schedule SG-TOU) were phased in under CPUC Proceeding No. 19AL-0268E / Advice Letter No. 1923-Electric with effective dates around 2021–2023.

Therefore, this schedule is formally designated as a **Provisional Economic Benchmark Tariff**, providing a realistic, regulatory-grounded Time-of-Use price signal for evaluating dispatch algorithms, rather than an unverified historical 2018 rate book.

### 4.3 Codified Rate Determinants

| Determinant | Period / Applicability | Value | Unit |
| :--- | :--- | :--- | :--- |
| **Service & Facility Charge** | Monthly customer base charge | \$45.00 | \$/month |
| **Distribution Demand Charge** | Monthly peak 15-minute measured demand ($P_{\text{max}}$) | \$14.25 | \$/kW/month |
| **Summer On-Peak Energy** | June 1 – Sept 30, 13:00–19:00 Mon–Fri | \$0.1850 | \$/kWh |
| **Summer Off-Peak Energy** | All other summer hours and weekends | \$0.0680 | \$/kWh |
| **Winter On-Peak Energy** | Oct 1 – May 31, 13:00–19:00 Mon–Fri | \$0.1250 | \$/kWh |
| **Winter Off-Peak Energy** | All other winter hours and weekends | \$0.0620 | \$/kWh |
| **Export Credit** | Avoided wholesale cost energy credit | 50% retail rate | \$/kWh |

---

## 5. Candidate Ground-Truth Validation: NREL SRRL BMS

### 5.1 Station Profile
- **Station**: NREL Solar Radiation Research Laboratory (SRRL) Baseline Measurement System (BMS).
- **Location**: South Table Mountain Mesa, Golden, Colorado ($39.7420^\circ\text{N}, -105.1800^\circ\text{W}$, elevation $1829.0\,\text{m}$).
- **Instrumentation**:
  - GHI: Kipp & Zonen CMP21 / CMP22 thermopile pyranometers (ISO 9060 Class A).
  - DNI: Kipp & Zonen CHP1 / Eppley NIP pyrheliometers mounted on automated solar trackers.
  - DHI: Shaded pyranometers on automated tracker balls.
- **Cadence**: Native 1-minute temporal resolution.
- **Quality Control**: Automated SERI-QC quality filters and daily calibration traceable to the World Radiometric Reference (WRR) in Davos, Switzerland.

### 5.2 Scientific Compatibility Assessment
- **Spatial Colocation**: The SRRL station is physically located within the exact 2 km $\times$ 2 km NSRDB grid pixel covering Golden, CO.
- **Point vs Areal Representation**: SRRL is a single point thermopile sensor, whereas NSRDB PSM v4 estimates 2 km areal average irradiance from GOES satellite imagery. Sub-hourly broken cloud fields introduce localized dispersion.
- **Validation Role**: SRRL BMS is designated as a **candidate ground-truth validation reference**. It will not be registered as benchmark-accepted until raw 1-minute data are downloaded, aggregated to 15-minute intervals, and statistically benchmarked (evaluating MBE, RMSE, and Kolmogorov-Smirnov distribution parity).

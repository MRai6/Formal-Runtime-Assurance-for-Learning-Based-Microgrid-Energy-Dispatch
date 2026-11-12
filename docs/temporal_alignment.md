# Temporal Alignment, Coordinate Standardization, and Aggregation Methodology

## 1. The Canonical Timeline: Coordinated Universal Time (UTC)

### 1.1 The Daylight Saving Time (DST) Anomaly in Microgrid Simulation
Power systems and physics simulation require a strictly monotonic, uniform, and contiguous time coordinate:
$$t_{k+1} - t_k = \Delta t = \text{constant} \quad \forall k \in [0, N-1]$$

In local civil time (e.g., `America/Denver`), Daylight Saving Time creates two severe discontinuities each year:
1. **Spring Forward (March)**: Clocks jump from 01:59:59 to 03:00:00, creating an artificial **60-minute gap** (4 missing 15-minute intervals).
2. **Fall Back (November)**: Clocks repeat the 01:00:00 to 01:59:59 hour, creating **duplicate timestamps** and non-monotonicity.

Applying civil time directly to reinforcement learning agents corrupts state transitions $(s_t, a_t, s_{t+1})$ and invalidates dynamic equations.

### 1.2 Canonical UTC Standardization
To resolve this, `microgrid_sim` enforces **canonical UTC indexing** across all ingested datasets:
- **Annual non-leap horizon (2018)**: Exactly 365 days $\times$ 24 hours $\times$ 4 intervals/hour = **35,040 contiguous steps**.
- **Time range**: `2018-01-01 00:00:00+00:00` to `2018-12-31 23:45:00+00:00`.
- **Local Standard Time Mapping**: Raw NREL NSRDB files are published in **Local Standard Time (LST)** without DST. For Colorado, LST is Mountain Standard Time ($\text{UTC}-7$, formatted in POSIX as `Etc/GMT+7`). The transformation to UTC is exact and invertible:
  $$t_{\text{UTC}} = t_{\text{LST}} + 7\,\text{hours}$$

```text
Local Standard Time (MST, UTC-7):  2018-06-21 12:00:00
UTC Canonical Timestamp:           2018-06-21 19:00:00+00:00
```

---

## 2. Solar Irradiance Aggregation (5-Min to 15-Min)

### 2.0 Native Source Resolution vs API Output Interval Semantics
The NREL NSRDB GOES CONUS PSM v4 physical dataset is produced at a **native 5-minute temporal resolution** on a 2 km grid. However, the NREL Developer API (`/api/nsrdb/v2/solar/nsrdb-GOES-conus-v4-0-0-download`) supports requesting output intervals of **`5`**, **`15`**, **`30`**, or **`60`** minutes.

- **Provider-Generated 15-Minute Output**: If downloaded with `interval=15`, NREL downsamples data on its server before delivering the CSV. Depending on the API version, server-side algorithms may employ snapshot sampling or simple averaging.
- **Local Energy-Preserving Block Aggregation**: When downloaded with `interval=5`, our pipeline (`NSRDBLoader.aggregate_to_15min`) performs verified, explicit local aggregation.
- **Comparison & Selection Rationale**:
  Local aggregation is chosen as the primary scientific method for the benchmark because:
  1. It guarantees that radiant exposure $\int G dt$ is mathematically conserved without black-box server interpolation.
  2. It correctly applies the circular vector mean to wind direction, avoiding the catastrophic boundary error at $0^\circ / 360^\circ$.
  3. It samples the exact midpoint of the 15-minute window for non-linear optical geometry ($\theta_z$).
  Both formats remain supported: if a user inputs pre-aggregated 15-minute data, `NSRDBLoader` detects the 15-minute cadence and bypasses redundant aggregation.

### 2.1 Conservation of Radiant Energy Exposure
Irradiance ($G$) represents an instantaneous power flux density $[\text{W}/\text{m}^2]$. The physical quantity received by a photovoltaic surface is radiant exposure ($H$) $[\text{Wh}/\text{m}^2]$ or $[\text{J}/\text{m}^2]$:
$$H = \int_{t}^{t+\Delta t_{15}} G(\tau) d\tau$$

For a 15-minute interval containing 3 discrete 5-minute measurements $(G_1, G_2, G_3)$ with $\Delta t_5 = \frac{5}{60}\,\text{h}$:
$$H_{5} = \sum_{k=1}^3 G_{5,k} \cdot \Delta t_5 = \frac{5}{60} (G_1 + G_2 + G_3)$$

Defining the 15-minute block-averaged irradiance as the arithmetic mean:
$$\bar{G}_{15} = \frac{1}{3} \sum_{k=1}^3 G_{5,k}$$

The radiant exposure over $\Delta t_{15} = \frac{15}{60}\,\text{h}$ is:
$$H_{15} = \bar{G}_{15} \cdot \Delta t_{15} = \left(\frac{G_1 + G_2 + G_3}{3}\right) \cdot \frac{15}{60} = \frac{5}{60} (G_1 + G_2 + G_3) \equiv H_5$$

$$\boxed{H_{15} \equiv H_5}$$

**Result**: Arithmetic block averaging of Global Horizontal Irradiance (GHI), Direct Normal Irradiance (DNI), and Diffuse Horizontal Irradiance (DHI) **strictly conserves total incident solar energy**.

### 2.2 Directional Variables: Circular Mean for Wind Direction
Wind direction ($\theta$) is an angular azimuth $[\text{deg}]$ defined on the circle $[0^\circ, 360^\circ)$. Standard arithmetic averaging fails catastrophically near the North boundary. For example, averaging $\theta_1 = 350^\circ$ and $\theta_2 = 10^\circ$:
- **Arithmetic mean**: $\frac{350 + 10}{2} = 180^\circ$ (South, an error of $180^\circ$!).
- **True physical wind**: North ($0^\circ / 360^\circ$).

In `src/microgrid_sim/data/nsrdb_loader.py`, wind direction is aggregated using the **circular vector mean**:
$$\bar{\theta} = \text{atan2}\left(\sum_{k=1}^K \sin\theta_k, \; \sum_{k=1}^K \cos\theta_k\right) \pmod{360^\circ}$$

### 2.3 Geometric Variables: Midpoint Sampling for Solar Zenith Angle
Solar zenith angle ($\theta_z$) is a non-linear geometric variable determining atmospheric air mass and solar incidence angle. Averaging zenith angles over an interval introduces non-linear optical distortion.

`microgrid_sim` extracts the **midpoint sample** ($k=1$ of indices $0, 1, 2$ in 0-indexed form), representing the exact solar position at the geometric center of the 15-minute dispatch interval:
$$\theta_{z, 15}(t) = \theta_{z, 5}(t + 7.5\,\text{min})$$

---

## 3. Building Load Energy-to-Power Transformation

### 3.1 Interval Energy vs Instantaneous Power
NREL ComStock outputs building electric consumption as **integrated interval energy** $[E_{\text{interval}}]$ with units of kilowatt-hours $[\text{kWh}]$:
$$E_{\text{interval}} = \int_{t}^{t+\Delta t} P(\tau) d\tau$$

For microgrid physical simulation, the active power balance equation operates in instantaneous or interval-average power $[P_{\text{avg}}]$ with units of kilowatts $[\text{kW}]$:
$$P_{\text{balance}}(t) = P_{\text{pv}}(t) + P_{\text{batt}}(t) + P_{\text{grid}}(t) - P_{\text{load}}(t) = 0$$

### 3.2 Conversion Equation
The continuous average power over $\Delta t = 15\,\text{minutes} = 0.25\,\text{hours}$ is:
$$P_{\text{load}} [\text{kW}] = \frac{E_{\text{interval}} [\text{kWh}]}{\Delta t [\text{hours}]} = \frac{E_{\text{interval}}}{0.25} = 4.0 \times E_{\text{interval}} [\text{kWh}]$$

$$\boxed{P_{\text{load}} = 4.0 \cdot E_{\text{interval}}}$$

This transformation is implemented in `src/microgrid_sim/data/load_loader.py` and validated to maintain exact energy equivalence across monthly and annual totals:
$$\sum_{k=1}^{35040} P_{\text{load}, k} \cdot 0.25\,\text{h} \equiv \sum_{k=1}^{35040} E_{\text{interval}, k}$$

---

## 4. Benchmark Preprocessing Pipeline

The complete ingestion and alignment workflow is coordinated by `BenchmarkDataPreprocessor`:

```
Raw NSRDB 5-min CSV ──> NSRDBLoader ──> Block Averaging ──> 15-min Solar DataFrame (UTC)
                                                                       │
                                                                       ▼
Raw ComStock Parquet ──> LoadLoader  ──> Energy-to-Power ──> 15-min Load DataFrame (UTC)
                                                                       │
                                                                       ▼
                                                       Canonical UTC Re-indexing
                                                        (35,040 continuous steps)
                                                                       │
                                                                       ▼
                                                          TimeSeriesQualityAuditor
                                                          (Strict Invariant Checks)
                                                                       │
                                                                       ▼
                                                         Export: Parquet + Quality JSON
```

### 4.1 Zero-Tolerance Missing Data Policy
If any timestamp in the canonical 35,040-step annual grid is missing from an empirical input dataset:
1. `reindex()` inserts a `NaN`.
2. `TimeSeriesQualityAuditor` flags the `null_count > 0` violation.
3. The preprocessor **aborts immediately** with `DataProvenanceError`.
4. **No forward-filling, back-filling, zero-insertion, or spline interpolation is permitted.**


# `microgrid_sim` Configuration Guide

This guide documents the declarative YAML configuration files located in `configs/`. All configurations are strictly validated by Pydantic schemas in `microgrid_sim.config.schemas`.

---

## 1. `configs/system_spec.yaml`
Central system parameters defining the simulation horizon, timestep, and electrical bus specifications.

| Key | Type | Unit | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `temporal.timestep_minutes` | int | min | `15` | Discrete simulation dispatch interval |
| `temporal.timestep_hours` | float | h | `0.25` | Step duration in decimal hours |
| `temporal.steps_per_year` | int | - | `35040` | Total steps in a non-leap 365-day year |
| `temporal.weather_year` | int | - | `2018` | Reference meteorological calendar year |
| `electrical.ac_bus_voltage_v` | float | V | `480.0` | Nominal three-phase AC bus voltage |
| `electrical.grid_frequency_hz` | float | Hz | `60.0` | Nominal electrical frequency |
| `electrical.power_factor` | float | - | `1.0` | Unity active-power dispatch baseline |
| `electrical.isothermal_temperature_c` | float | °C | `25.0` | Baseline container temperature |

---

## 2. `configs/battery_spec.yaml`
Li-ion Battery Energy Storage System (BESS) specifications based on the NREL ATB 2023 Commercial Storage benchmark.

| Key | Type | Unit | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `capacity.nominal_energy_kwh` | float | kWh | `400.0` | Nameplate storage capacity |
| `capacity.minimum_soc` | float | - | `0.15` | Lower operational SoC limit (15%) |
| `capacity.maximum_soc` | float | - | `0.90` | Upper operational SoC limit (90%) |
| `capacity.initial_soc` | float | - | `0.50` | Simulation initial SoC (50%) |
| `power_and_thermal.max_charge_power_kw` | float | kW | `100.0` | Continuous charging limit (0.25C) |
| `power_and_thermal.max_discharge_power_kw` | float | kW | `100.0` | Continuous discharging limit (0.25C) |
| `performance.charging_efficiency` | float | - | `0.95` | One-way charging efficiency |
| `performance.discharging_efficiency` | float | - | `0.95` | One-way discharging efficiency |
| `performance.self_discharge_rate_per_hour` | float | 1/h | `1.0e-5` | Self-discharge rate (~0.72%/month) |
| `degradation.replacement_cost_usd_per_kwh` | float | $/kWh | `180.0` | Cell capital replacement cost |
| `degradation.cycle_life_to_eol` | int | cycles | `4000` | Cycles to 80% capacity retention |
| `degradation.implied_wear_cost_usd_per_kwh` | float | $/kWh | `0.028125` | Linear amortized cycling wear cost |

---

## 3. `configs/pv_spec.yaml`
Fixed-tilt commercial rooftop Solar Photovoltaic (PV) system specifications.

| Key | Type | Unit | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `capacity.rated_dc_capacity_kw` | float | kW_dc | `120.0` | Nameplate peak capacity under STC |
| `orientation.tilt_degrees` | float | ° | `39.74` | Array tilt angle (latitude matched) |
| `orientation.azimuth_degrees` | float | ° | `180.0` | Array azimuth angle (due South) |
| `orientation.ground_albedo` | float | - | `0.20` | Ground diffuse reflectance |
| `thermal_and_electrical.stc_irradiance_w_per_m2` | float | W/m² | `1000.0` | Reference irradiance at STC |
| `thermal_and_electrical.noct_temperature_c` | float | °C | `45.0` | Nominal Operating Cell Temperature |
| `thermal_and_electrical.temperature_coefficient_pmp_per_c` | float | 1/°C | `-0.0038` | Power derating coefficient (-0.38%/°C) |
| `losses.bos_derate_factor` | float | - | `0.95` | Balance-of-system derate factor |

---

## 4. `configs/inverter_spec.yaml`
Inverter power conversion specifications following the CEC polynomial efficiency curve.

| Key | Type | Unit | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `ratings.rated_ac_power_kw` | float | kW_ac | `120.0` | Nameplate continuous AC output limit |
| `efficiency_model.nominal_peak_efficiency` | float | - | `0.975` | Peak conversion efficiency (97.5%) |
| `efficiency_model.curvature_coefficient_c0` | float | - | `0.015` | Intercept loss coefficient |
| `efficiency_model.curvature_coefficient_c1` | float | - | `0.035` | Curvature loss coefficient |
| `battery_inverter.bidirectional_efficiency` | float | - | `0.96` | Battery bidirectional inverter efficiency |

---

## 5. `configs/grid_tariff_spec.yaml`
Interconnection limits and Time-of-Use tariff structure for Public Service Company of Colorado (PSCo / Xcel Energy) Schedule SG.

| Key | Type | Unit | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `interconnection.max_import_power_kw` | float | kW | `250.0` | Contractual maximum import power |
| `interconnection.max_export_power_kw` | float | kW | `250.0` | Contractual maximum export power |
| `billing.monthly_customer_charge_usd` | float | $/mo | `45.00` | Fixed monthly customer charge |
| `billing.distribution_demand_charge_usd_per_kw` | float | $/kW | `14.25` | Monthly peak distribution demand charge |
| `tou_rates.summer.rate_on_peak_usd_per_kwh` | float | $/kWh | `0.1850` | Summer On-Peak energy rate (13:00–19:00) |
| `tou_rates.summer.rate_off_peak_usd_per_kwh` | float | $/kWh | `0.0680` | Summer Off-Peak energy rate |
| `tou_rates.winter.rate_on_peak_usd_per_kwh` | float | $/kWh | `0.1250` | Winter On-Peak energy rate (13:00–19:00) |
| `tou_rates.winter.rate_off_peak_usd_per_kwh` | float | $/kWh | `0.0620` | Winter Off-Peak energy rate |
| `export_compensation.export_credit_multiplier` | float | - | `0.50` | Avoided wholesale cost export credit |

---

## 6. `configs/benchmark_location.yaml`
Coordinates, climate zone, and reference commercial building archetype for Golden / Denver, CO.

| Key | Type | Unit | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `coordinates.latitude_deg` | float | °N | `39.7420` | Golden, CO latitude |
| `coordinates.longitude_deg` | float | °W | `-105.1800` | Golden, CO longitude |
| `coordinates.elevation_meters` | float | m | `1829.0` | Elevation above sea level |
| `coordinates.timezone` | str | - | `America/Denver` | Mountain Timezone (MST/MDT) |
| `climate.ashrae_climate_zone` | str | - | `5B` | Cold, Semi-Arid climate |
| `building_archetype.floor_area_sqft` | float | ft² | `53600.0` | Conditioned office floor area |
| `building_archetype.peak_electrical_demand_kw` | float | kW | `165.4` | Estimated summer peak load |


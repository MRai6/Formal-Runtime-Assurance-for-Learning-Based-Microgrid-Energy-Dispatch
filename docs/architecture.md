# `microgrid_sim` Architecture & Engineering Design

**Project:** Formal Runtime Assurance for Learning-Based Microgrid Energy Dispatch  
**Author:** Member 4: Microgrid Simulation & Physics Lead (Environment Specialist)  
**Date:** November 2026  
**Status:** Verified & Validated (88 Passing Automated Tests)  

---

## 1. System Topology & Electrical Power Flow

`microgrid_sim` models a commercial active-power microgrid coupled at a single Point of Common Coupling (PCC) 480 V, 60 Hz AC bus:

```text
                             ┌───────────────────────────────┐
                             │    Utility Grid (Xcel PSCo)   │
                             └───────────────┬───────────────┘
                                             │ P_grid (Import / Export)
                                             ▼
═════════════════════════════════════════════╤═════════════════════════════════  PCC AC Bus (480 V, 60 Hz)
          ▲                                       ▲                               ▲
          │ P_pv_ac_delivered                     │ P_batt_dis_ac                 │ P_served_load
          │                                       │ P_batt_ch_ac                  │
┌─────────┴───────────────┐              ┌────────┴──────────────┐       ┌────────┴──────────────┐
│  PV Inverter (120 kW)   │              │  Battery PCS (100 kW) │       │ ComStock MediumOffice │
│  Part-Load Quadratic    │              │  Bidirectional eta=96%│       │ Peak Demand: 165 kW   │
└─────────▲───────────────┘              └────────▲──────────────┘       └───────────────────────┘
          │ P_dc_accepted                         │ P_batt_dc
┌─────────┴───────────────┐              ┌────────┴──────────────┐
│  Solar PV Array 120 kW  │              │ BESS: 400 kWh Nominal │
│  Fixed-Tilt (25.0°)     │              │ SoC in [0.15, 0.90]   │
└─────────────────────────┘              └───────────────────────┘
```

---

## 2. Decoupled Modular Packages

The codebase is organized into isolated, single-responsibility modules:

- **`microgrid_sim.config`:** Declarative YAML parsing, Pydantic validation schemas, and master configuration aggregation.
- **`microgrid_sim.data`:** Authentic dataset loaders (NSRDB, ComStock), circular statistics, temporal alignment, and SHA-256 provenance auditing.
- **`microgrid_sim.physics`:** First-principles mathematical formulation of solar transposition, cell thermal dynamics, empirical quadratic inverter efficiency, battery state evolution with dynamic feasibility envelopes, and Kirchhoff AC bus balance.
- **`microgrid_sim.env`:** Farama Gymnasium environment interface (`MicrogridEnv`), continuous 12-dim observation space, 1-dim normalized action space, and reward formulation.
- **`microgrid_sim.controllers`:** Abstract base controller (`BaseController`) and deterministic baseline dispatch algorithms (`RuleBasedController`).
- **`microgrid_sim.validation`:** Invariant checkers verifying conservation of active power ($|\Delta P| < 10^{-6}\,\text{kW}$) and battery operational envelope containment ($SoC \in [SoC_{min}, SoC_{max}]$).
- **`microgrid_sim.utils`:** Centralized domain exceptions, structured logging, and experiment reproducibility metadata capture.

---

## 3. Mathematical Physics & Simulation Summary

### 3.1 Solar PV Generation (`solar_pv.py`, `inverter.py`)
1. **Transposition (Liu-Jordan Model):**
   $$G_{poa} = DNI \max(0, \cos\theta) + DHI \left(\frac{1 + \cos\beta}{2}\right) + GHI \rho_g \left(\frac{1 - \cos\beta}{2}\right)$$
   $$\cos\theta = \cos\theta_z \cos\beta + \sin\theta_z \sin\beta \cos(\gamma_s - \gamma)$$
2. **Cell Operating Temperature (NOCT Model):**
   $$T_{cell} = T_{amb} + G_{poa} \left(\frac{NOCT - 20}{800}\right) \left(1 - \frac{\eta_{stc}}{\tau\alpha}\right)$$
3. **Array DC Power Output:**
   $$P_{dc,raw} = P_{stc} \left(\frac{G_{poa}}{1000}\right) \left[1 + \gamma_{pmp} (T_{cell} - 25)\right] f_{derate}$$
   $$P_{dc,accepted} = \min(P_{max,dc}, P_{dc,raw})$$
4. **Empirical Quadratic Part-Load Inverter Model:**
   $$\eta_{inv}(p_{pu}) = \eta_{nom} \left[1 - c_0 - c_1 (p_{pu} - 1)^2\right] \quad (p_{pu} = P_{dc,accepted} / P_{rated,ac})$$
   $$P_{ac,potential} = \min(P_{rated,ac}, P_{dc,accepted} \cdot \eta_{inv})$$

### 3.2 Battery Energy Storage System (`battery.py`, `inverter.py`)
1. **Dynamic Feasibility Limits (Pre-step Envelope Protection):**
   $$P_{ch,max,dyn} = \min\left(P_{ch,max}, \; \frac{\left[SoC_{max} - SoC(t)(1 - \sigma_{sd}\Delta t)\right] E_{nom}}{\eta_{ch} \Delta t}\right)$$
   $$P_{dis,max,dyn} = \min\left(P_{dis,max}, \; \frac{\left[SoC(t)(1 - \sigma_{sd}\Delta t) - SoC_{min}\right] E_{nom} \eta_{dis}}{\Delta t}\right)$$
2. **State Transition & Degradation Tracking:**
   $$SoC(t + \Delta t) = SoC(t)(1 - \sigma_{sd}\Delta t) + \frac{\Delta t}{E_{nom}} \left[\eta_{ch} P_{ch} - \frac{P_{dis}}{\eta_{dis}}\right]$$
   $$P_{rejected} = \max(0.0, \; |P_{requested}| - |P_{executed}|)$$
3. **Power Conversion System (PCS) Bidirectional AC/DC Interface:**
   - Discharging: $P_{ac,dis} = \min(P_{rated,pcs}, P_{dc,dis} \cdot \eta_{pcs})$
   - Charging: $P_{dc,ch} = \min(P_{rated,pcs}, P_{ac,ch}) \cdot \eta_{pcs}$

### 3.3 Physically Consistent Kirchhoff AC Bus Power Balance (`power_balance.py`)
$$P_{\text{pv,ac,delivered}} + P_{\text{grid,import}} + P_{\text{batt,dis,ac}} + P_{\text{diesel}} \equiv P_{\text{served\_load}} + P_{\text{batt,ch,ac}} + P_{\text{grid,export}}$$
where:
- $P_{\text{served\_load}} = P_{\text{requested\_load}} - P_{\text{unserved\_load}}$ (unserved load is unmet demand, NOT a power source)
- $P_{\text{pv,ac,delivered}} = P_{\text{pv,ac,potential}} - P_{\text{pv,curtail,ac}}$ (curtailment is withheld inverter potential, NOT an AC load)
- Residual error invariant: $|\sum P_{sources} - \sum P_{sinks}| < 10^{-6}\,\text{kW}$ ($1\,\text{mW}$) at every simulation step.

---

## 4. Gymnasium Environment Architecture (`MicrogridEnv`)

### 4.1 State & Observation Space (`spaces.py`)
12-dimensional continuous `Box` space:
- Index 0: Battery SoC $\in [0.0, 1.0]$
- Index 1: Normalized Building Demand ($P_{\text{load}} / 100\,\text{kW}$) $\in [0.0, 5.0]$
- Index 2: Normalized Solar PV Potential ($P_{\text{pv,pot}} / 120\,\text{kW}$) $\in [0.0, 5.0]$
- Index 3: Normalized Grid Import Capacity ($P_{\text{imp,max}} / 250\,\text{kW}$) $\in [0.0, 2.0]$
- Index 4: Normalized Grid Export Capacity ($P_{\text{exp,max}} / 250\,\text{kW}$) $\in [0.0, 2.0]$
- Index 5: Normalized Electricity Buy Rate ($c_{\text{buy}} / 0.25\,\$/\text{kWh}$) $\in [0.0, 2.0]$
- Index 6: Normalized Electricity Sell Rate ($c_{\text{sell}} / 0.25\,\$/\text{kWh}$) $\in [0.0, 2.0]$
- Index 7: Cyclical Time-of-Day Sine $\in [-1.0, 1.0]$
- Index 8: Cyclical Time-of-Day Cosine $\in [-1.0, 1.0]$
- Index 9: Cyclical Day-of-Year Sine $\in [-1.0, 1.0]$
- Index 10: Cyclical Day-of-Year Cosine $\in [-1.0, 1.0]$
- Index 11: Weekday indicator flag ($1.0$ if Mon-Fri, $0.0$ if Sat-Sun) $\in [0.0, 1.0]$

### 4.2 Action Space & Generator Sign Convention
1-dimensional continuous `Box` space: action $a \in [-1.0, 1.0]$:
- $a > 0$: **Discharge request** (injecting active power into AC bus). Physical power: $P_{\text{req}} = a \cdot P_{\text{dis,max}}$.
- $a < 0$: **Charge request** (absorbing active power from AC bus). Physical power: $P_{\text{req}} = a \cdot P_{\text{ch,max}}$.
- $a = 0$: **Idle request** ($P_{\text{req}} = 0\,\text{kW}$).

### 4.3 Step Sequence
1. Ingest load demand and weather data at timestamp $t$.
2. Compute PV DC output and inverter AC potential $P_{\text{pv,ac,pot}}$.
3. Map action $a$ through battery PCS and battery model; clamp to dynamic limits; track $P_{\text{rejected}}$.
4. Resolve AC bus balance; compute grid import/export, unserved demand, and curtailment.
5. Compute economic billing cost, battery wear, and unserved penalty:
   $$\text{Cost} = \text{Cost}_{\text{import}} - \text{Revenue}_{\text{export}} + \text{Cost}_{\text{wear}} + \text{Penalty}_{\text{unserved}}$$
   $$\text{Reward} = -\text{Cost}$$
6. Advance step index by $\Delta t = 0.25\,\text{h}$. Check episode termination.

---

## 5. Deterministic Rule-Based Baseline Controller (`RuleBasedController`)

Policy:
1. **Solar First:** Local demand is served directly by available PV generation.
2. **Surplus PV ($P_{\text{pv}} > P_{\text{load}}$):** Charge battery up to $P_{\text{ch,max}}$ if $SoC < SoC_{\text{max}}$. Excess is exported to grid or curtailed.
3. **Deficit PV ($P_{\text{pv}} < P_{\text{load}}$):** Discharge battery up to $P_{\text{dis,max}}$ if $SoC > SoC_{\text{min}}$. Remaining unmet demand is imported from grid.
4. **Exact Balance:** Battery is idle ($a = 0.0$).

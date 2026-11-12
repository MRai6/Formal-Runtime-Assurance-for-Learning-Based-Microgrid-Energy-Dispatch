# Physical Microgrid Simulation Engine Specification

**Document:** Mathematical Modeling and Physical Implementation Specification  
**Project:** Formal Runtime Assurance for Learning-Based Microgrid Energy Dispatch  
**Author:** Member 4: Microgrid Simulation & Physics Lead (Environment Specialist)  
**Date:** 2026-11-12  
**Status:** Audited, Corrected & Formally Verified (69 Passing Automated Tests)  

---

## 1. System Topology & Electrical Architecture

The `microgrid_sim` engine models a commercial three-phase active-power microgrid operating at a nominal 480 V, 60 Hz line-to-line AC bus, coupled to the Public Service Company of Colorado (PSCo / Xcel Energy) distribution network at a single Point of Common Coupling (PCC).

```text
                                 ┌───────────────────────────────┐
                                 │   Utility Grid (PSCo 480 V)   │
                                 └───────────────┬───────────────┘
                                                 │ P_grid_import / P_grid_export (PCC)
                                                 ▼
═════════════════════════════════════════════════╤═════════════════════════════════════  PCC AC Bus (480 V, 60 Hz)
          ▲                                       ▲                               ▲
          │ P_pv_ac_delivered                     │ P_batt_dis_ac                 │ P_served_load
          │                                       │ P_batt_ch_ac                  │
┌────────┴──────────────┐               ┌────────┴──────────────┐       ┌────────┴──────────────┐
│  PV Inverter (120 kW) │               │  Battery PCS (100 kW) │       │ ComStock MediumOffice │
│  Part-Load Quadratic  │               │  Bidirectional eta=96%│       │ Peak Demand: 165 kW   │
└────────▲──────────────┘               └────────▲──────────────┘       └───────────────────────┘
         │ P_dc_accepted                         │ P_batt_dc
┌────────┴──────────────┐               ┌────────┴──────────────┐
│ Solar PV Array 120 kW │               │ BESS: 400 kWh Nominal │
│ Fixed-Tilt (25.0°)    │               │ SoC in [0.15, 0.90]   │
└───────────────────────┘               └───────────────────────┘
```

---

## 2. Solar PV Conversion Model (`solar_pv.py`)

### 2.1 Irradiance Transposition (Liu-Jordan Model)
Plane-of-Array (POA) irradiance $G_{\text{poa}}$ is resolved into three physical components:
$$G_{\text{poa}} = G_{\text{beam,poa}} + G_{\text{diff,poa}} + G_{\text{gnd,poa}}$$

1. **Direct Beam Component**:
   $$G_{\text{beam,poa}} = DNI \cdot \max(0, \cos\theta)$$
   where the incidence angle $\theta$ between the direct beam and the panel normal vector is:
   $$\cos\theta = \cos\theta_z \cos\beta + \sin\theta_z \sin\beta \cos(\gamma_s - \gamma)$$
   - $\theta_z$: Solar zenith angle [rad] ($0 = \text{zenith}$, $\pi/2 = \text{horizon}$).
   - $\beta$: Panel tilt from horizontal [rad] ($25.0^\circ$, optimized for commercial flat-roof racking in Denver/Golden, CO).
   - $\gamma_s$: Solar azimuth angle [rad] ($0^\circ = \text{North}, 180^\circ = \text{South}$).
   - $\gamma$: Array azimuth angle [rad] ($180.0^\circ = \text{Due South}$).
2. **Sky Diffuse Component (Liu-Jordan Isotropic Formulation)**:
   $$G_{\text{diff,poa}} = DHI \cdot \left(\frac{1 + \cos\beta}{2}\right)$$
   *Isotropic Assumption Note*: The Liu-Jordan model treats diffuse sky radiance as uniformly distributed across the hemispherical dome. While anisotropic models (e.g., Perez, Hay-Davies) model circumsolar brightening and horizon brightening, the isotropic formulation is standard for baseline building-integrated solar modeling with conservative clear-sky transposition.
3. **Ground-Reflected Component**:
   $$G_{\text{gnd,poa}} = GHI \cdot \rho_{\text{albedo}} \cdot \left(\frac{1 - \cos\beta}{2}\right)$$
   where $\rho_{\text{albedo}} = 0.20$ (standard commercial gravel rooftop).

### 2.2 Solar Ephemeris & Azimuth Integrity Rule
In compliance with scientific audit requirements:
- The model **never silently assumes** panel azimuth $\gamma_s \equiv \gamma = 180^\circ$ (solar noon) when solar azimuth is missing.
- Either an explicit `solar_azimuth_deg` must be provided, or a valid UTC `timestamp` with geographical coordinates must be supplied to calculate the ephemeris azimuth.
- If both are omitted and daytime irradiance is present ($GHI > 0$ and $\theta_z < 90^\circ$), execution halts with a `PhysicsViolationError`.

### 2.3 Operating Cell Temperature (King/Evans NOCT Model)
$$T_{\text{cell}} = T_{\text{amb}} + G_{\text{poa}} \cdot \left(\frac{NOCT - 20^\circ\text{C}}{800\,\text{W}/\text{m}^2}\right) \cdot \left(1 - \frac{\eta_{\text{stc}}}{\tau\alpha}\right)$$
- $NOCT = 45.0^\circ\text{C}$ (Nominal Operating Cell Temperature).
- $\eta_{\text{stc}} = 0.20$ (Module nameplate efficiency at Standard Test Conditions).
- $\tau\alpha = 0.90$ (Effective optical transmittance-absorptance product).
- $T_{\text{amb}}$: Ambient dry bulb temperature [°C].

### 2.4 DC Power Output & Capacity Clipping
$$P_{\text{dc,raw}} = P_{\text{rated,dc}} \cdot \left(\frac{G_{\text{poa}}}{G_{\text{stc}}}\right) \cdot \left[1 + \gamma_{\text{pmp}} (T_{\text{cell}} - T_{\text{stc}})\right] \cdot f_{\text{derate}}$$
$$P_{\text{dc}} = \min(P_{\text{rated,dc}}, \max(0.0, P_{\text{dc,raw}}))$$
- $P_{\text{rated,dc}} = 120.0\,\text{kW}_{\text{dc}}$ (Nameplate DC capacity).
- $G_{\text{stc}} = 1000.0\,\text{W}/\text{m}^2$, $T_{\text{stc}} = 25.0^\circ\text{C}$.
- $\gamma_{\text{pmp}} = -0.0038\,^\circ\text{C}^{-1}$ (Power temperature coefficient: $-0.38\%/^\circ\text{C}$).
- $f_{\text{derate}} = 0.95$ (Balance-of-system derate for soiling, wiring, and mismatch).
- $P_{\text{curtail,dc}} = \max(0.0, P_{\text{dc,raw}} - P_{\text{rated,dc}})$ (Array-level DC clipping curtailment).

---

## 3. Battery Energy Storage System Model (`battery.py`)

### 3.1 Sign Conventions & Parameter Definitions
- **Signed Power Convention**:
  - $P_{\text{batt}} > 0$: Discharging (power source, delivering power to microgrid).
  - $P_{\text{batt}} < 0$: Charging (power sink, absorbing power from microgrid).
  - $P_{\text{batt}} = 0$: Idle.
- **Dual-Variable Representation**: $P_{\text{ch}} \ge 0, P_{\text{dis}} \ge 0$, with mutual exclusivity $P_{\text{ch}} \cdot P_{\text{dis}} = 0$.
  Simultaneous charge and discharge requests in `step_ch_dis` strictly raise `PhysicsViolationError`.

### 3.2 Dynamic Feasibility Limits (Envelope Protection)
To avoid non-physical SoC overshoot, power limits are dynamically evaluated over each timestep $\Delta t = 0.25\,\text{h}$ prior to state updating:
$$P_{\text{ch,max,dyn}} = \min\left(P_{\text{ch,max}}, \; \frac{\left[SoC_{\text{max}} - SoC(t)(1 - \sigma_{\text{sd}}\Delta t)\right] E_{\text{nom}}}{\eta_{\text{ch}} \Delta t}\right)$$
$$P_{\text{dis,max,dyn}} = \min\left(P_{\text{dis,max}}, \; \frac{\left[SoC(t)(1 - \sigma_{\text{sd}}\Delta t) - SoC_{\text{min}}\right] E_{\text{nom}} \eta_{\text{dis}}}{\Delta t}\right)$$
- $E_{\text{nom}} = 400.0\,\text{kWh}$ (Nominal capacity).
- $SoC_{\text{min}} = 0.15$, $SoC_{\text{max}} = 0.90$.
- $P_{\text{ch,max}} = 100.0\,\text{kW}$, $P_{\text{dis,max}} = 100.0\,\text{kW}$ (0.25 C-rate).
- $\eta_{\text{ch}} = 0.95$, $\eta_{\text{dis}} = 0.95$ (Round-trip DC efficiency $= 90.25\%$).
- $\sigma_{\text{sd}} = 1.0 \times 10^{-5}\,\text{h}^{-1}$ (Self-discharge rate).

### 3.3 Rejected Power & Energy Tracking
When an external controller or RL agent requests power beyond physical ratings or SoC envelopes, the unexecuted excess is tracked:
$$P_{\text{rejected}} = \max(0.0, \; |P_{\text{requested}}| - |P_{\text{executed}}|)$$
$$E_{\text{rejected}} = P_{\text{rejected}} \cdot \Delta t$$
This provides unambiguous gradient feedback to learning algorithms and runtime assurance monitors.

### 3.4 Energy Conversion & SoC State Evolution
1. **Charging**:
   $$E_{\text{terminal,ch}} = P_{\text{ch,actual}} \cdot \Delta t$$
   $$E_{\text{stored,cell}} = E_{\text{terminal,ch}} \cdot \eta_{\text{ch}}$$
   $$E_{\text{loss,ch}} = E_{\text{terminal,ch}} \cdot (1 - \eta_{\text{ch}})$$
2. **Discharging**:
   $$E_{\text{terminal,dis}} = P_{\text{dis,actual}} \cdot \Delta t$$
   $$E_{\text{extracted,cell}} = \frac{E_{\text{terminal,dis}}}{\eta_{\text{dis}}}$$
   $$E_{\text{loss,dis}} = E_{\text{extracted,cell}} - E_{\text{terminal,dis}}$$
3. **State Transition**:
   $$SoC(t + \Delta t) = SoC(t) \cdot (1 - \sigma_{\text{sd}} \Delta t) + \frac{E_{\text{stored,cell}} - E_{\text{extracted,cell}}}{E_{\text{nom}}}$$
4. **Conservation Invariant**:
   $$E_{\text{terminal}} = \Delta E_{\text{stored}} + E_{\text{loss,total}} \quad \forall t$$
   Verified numerically to residual $< 10^{-6}\,\text{kWh}$.

---

## 4. Inverter and Power Conversion System (`inverter.py`)

### 4.1 Solar PV Inverter (Unidirectional DC to AC)
- **Model Classification**: Empirical Quadratic Part-Load Model (distinguished from the 6-parameter Sandia/CEC model).
- **Part-Load Ratio**: $p_{\text{pu}} = \frac{P_{\text{dc,accepted}}}{P_{\text{rated,pv,ac}}}$
- **Empirical Efficiency Curve**:
  $$\text{Loss}_{\text{poly}} = c_0 + c_1 (p_{\text{pu}} - 1.0)^2$$
  $$\eta_{\text{inv}} = \eta_{\text{nom}} \cdot (1.0 - \text{Loss}_{\text{poly}})$$
  - $\eta_{\text{nom}} = 0.975$ (Theoretical asymptotic ceiling).
  - $c_0 = 0.015$ (Baseline conduction loss deduction).
  - $c_1 = 0.035$ (Curvature loss coefficient).
  - *Rated Load Efficiency*: At $p_{\text{pu}} = 1.0$, the quadratic term vanishes, giving:
    $$\eta(1.0) = 0.975 \times (1.0 - 0.015) = 0.975 \times 0.985 = 0.960375 \approx 96.04\%$$
- **Rigorous Multi-Stage Energy & Clipping Separation**:
  1. *DC Front-End Acceptance*:
     $$P_{\text{dc,clipped}} = \max(0.0, P_{\text{dc,input}} - P_{\text{max,dc}})$$
     $$P_{\text{dc,accepted}} = \min(P_{\text{dc,input}}, P_{\text{max,dc}})$$
  2. *Thermal Conversion Loss*:
     $$P_{\text{loss,thermal}} = P_{\text{dc,accepted}} \cdot (1 - \eta_{\text{inv}})$$
     $$P_{\text{ac,potential}} = P_{\text{dc,accepted}} \cdot \eta_{\text{inv}}$$
  3. *AC Output & Clipping*:
     $$P_{\text{ac,clipped}} = \max(0.0, P_{\text{ac,potential}} - P_{\text{rated,pv,ac}})$$
     $$P_{\text{ac,output}} = \min(P_{\text{rated,pv,ac}}, P_{\text{ac,potential}})$$
  4. *Total Curtailment*:
     $$P_{\text{curtailed}} = P_{\text{dc,clipped}} + P_{\text{ac,clipped}}$$
  5. *Exact Energy Conservation Identity*:
     $$P_{\text{dc,input}} \equiv P_{\text{ac,output}} + P_{\text{loss,thermal}} + P_{\text{curtailed}}$$

### 4.2 Battery Power Conversion System (PCS, Bidirectional AC-DC)
- Continuous Rating: $P_{\text{rated,pcs}} = 100.0\,\text{kW}_{\text{ac}}$.
- Bidirectional Efficiency: $\eta_{\text{pcs}} = 0.96$ (independent of PV inverter).
- **Discharging (DC to AC)**:
  $$P_{\text{ac,raw}} = P_{\text{dc,dis}} \cdot \eta_{\text{pcs}}$$
  $$P_{\text{ac,dis}} = \min(P_{\text{rated,pcs}}, P_{\text{ac,raw}})$$
  $$P_{\text{loss,pcs,dis}} = P_{\text{dc,dis}} \cdot (1 - \eta_{\text{pcs}})$$
- **Charging (AC to DC)**:
  $$P_{\text{ac,ch,actual}} = \min(P_{\text{rated,pcs}}, P_{\text{ac,ch}})$$
  $$P_{\text{dc,ch}} = P_{\text{ac,ch,actual}} \cdot \eta_{\text{pcs}}$$
  $$P_{\text{loss,pcs,ch}} = P_{\text{ac,ch,actual}} \cdot (1 - \eta_{\text{pcs}})$$

---

## 5. Building Load & Grid Interface (`load.py`, `grid.py`)

### 5.1 Building Load Interface
- **Active Power Demand**: $P_{\text{load}} \ge 0.0\,\text{kW}$.
- **Interval Energy Conversion**: $E_{\text{load}} [\text{kWh}] = P_{\text{load}} [\text{kW}] \times \Delta t [\text{h}]$.
- **Negative Demand Invariant**: Any $P_{\text{load}} < 0.0$ raises `PhysicsViolationError`.

### 5.2 Point of Common Coupling Grid Interface
- Contractual Import Capacity: $P_{\text{import,max}} = 250.0\,\text{kW}$.
- Contractual Export Capacity: $P_{\text{export,max}} = 250.0\,\text{kW}$.
- Mutual Exclusivity: $P_{\text{import}} \cdot P_{\text{export}} = 0.0$.
- **Financial Tariff Separation**: Physical power flow calculations are strictly decoupled from economic cost accounting. TOU rates and monthly demand charges operate in independent financial accounting functions.

---

## 6. AC Power-Balance Model (`power_balance.py`)

### 6.1 Physically Consistent Kirchhoff Active Power Balance
At every simulation step $t$, Kirchhoff active power balance on the 480 V AC bus must hold strictly among physical sources and physical sinks:

$$\sum P_{\text{sources}} = \sum P_{\text{sinks}}$$

$$P_{\text{pv,ac,delivered}} + P_{\text{grid,import}} + P_{\text{batt,dis,ac}} + P_{\text{diesel}} \equiv P_{\text{served\_load}} + P_{\text{batt,ch,ac}} + P_{\text{grid,export}}$$

where:
- **Served Load** is physical demand delivered after accounting for any unmet load:
  $$P_{\text{served\_load}} = P_{\text{requested\_load}} - P_{\text{unserved\_load}}$$
  *Unserved load is unmet demand, NOT an AC-bus power source.*
- **Delivered PV AC Power** is solar power injected into the AC bus after subtracting bus-level curtailment:
  $$P_{\text{pv,ac,delivered}} = P_{\text{pv,ac,potential}} - P_{\text{pv,curtail,ac}}$$
  *PV curtailment is withheld inverter potential, NOT an AC-bus load sink.*

### 6.2 Slack Resolution Algorithm
Net electrical demand on the AC bus:
$$P_{\text{net}} = (P_{\text{requested\_load}} + P_{\text{batt,ch,ac}}) - (P_{\text{pv,ac,potential}} + P_{\text{batt,dis,ac}} + P_{\text{diesel}})$$

1. **Deficit ($P_{\text{net}} > 0$)**:
   - All available PV is delivered: $P_{\text{pv,ac,delivered}} = P_{\text{pv,ac,potential}}$, $P_{\text{pv,curtail,ac}} = 0$.
   - Grid export is zero: $P_{\text{grid,export}} = 0$.
   - Grid import serves deficit up to contractual limit:
     $$P_{\text{grid,import}} = \min(P_{\text{import,max}}, P_{\text{net}})$$
   - Unserved load represents any deficit exceeding import capability:
     $$P_{\text{unserved\_load}} = \max(0.0, P_{\text{net}} - P_{\text{import,max}})$$
     $$P_{\text{served\_load}} = P_{\text{requested\_load}} - P_{\text{unserved\_load}}$$

2. **Surplus ($P_{\text{net}} < 0$)**:
   - All requested load is fully served: $P_{\text{served\_load}} = P_{\text{requested\_load}}$, $P_{\text{unserved\_load}} = 0$.
   - Grid import is zero: $P_{\text{grid,import}} = 0$.
   - Surplus power: $\text{Surplus} = |P_{\text{net}}|$.
   - Grid export absorbs surplus up to contractual limit:
     $$P_{\text{grid,export}} = \min(P_{\text{export,max}}, \text{Surplus})$$
   - Excess surplus exceeding export limit is curtailed at the inverter:
     $$P_{\text{pv,curtail,ac}} = \max(0.0, \text{Surplus} - P_{\text{export,max}})$$
     $$P_{\text{pv,ac,delivered}} = P_{\text{pv,ac,potential}} - P_{\text{pv,curtail,ac}}$$

3. **Exact Balance ($P_{\text{net}} = 0$)**:
   $$P_{\text{grid,import}} = P_{\text{grid,export}} = P_{\text{unserved\_load}} = P_{\text{pv,curtail,ac}} = 0$$
   $$P_{\text{served\_load}} = P_{\text{requested\_load}}, \quad P_{\text{pv,ac,delivered}} = P_{\text{pv,ac,potential}}$$

### 6.3 Conservation Invariant & Residual Tolerance
The algebraic residual error is computed at each step:
$$\text{Residual} = \left|\sum P_{\text{sources}} - \sum P_{\text{sinks}}\right|$$
Invariant: $\text{Residual} \le 1.0 \times 10^{-6}\,\text{kW}$ ($1\,\text{mW}$).  
Violations abort execution with a structured `ConservationOfEnergyError`.

---

## 7. Model Limitations and Known Assumptions

1. **Unity Power Factor Assumption**: Reactive power ($Q = 0$) and voltage angle dynamics are omitted. Tertiary energy dispatch focuses on active energy balance over 15-minute intervals.
2. **Isothermal Container Baseline**: The battery model assumes an active HVAC temperature-controlled enclosure maintaining $25^\circ\text{C}$ baseline. Internal electro-thermal coupling (temperature rise under high C-rates) is neglected in the primary benchmark.
3. **Internal Bus Line Losses**: Distribution cable resistance within the building AC microgrid is neglected relative to major inverter/PCS conversion losses.
4. **Linearized Aging Approximation**: Battery degradation tracking accounts for equivalent full cycles and wear costs. Detailed non-linear SEI layer growth and calendar aging dynamics are modeled as external cumulative indicators rather than instantaneous capacity derating.

# Formal Runtime Assurance for Learning-Based Microgrid Energy Dispatch

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Database](https://img.shields.io/badge/PostgreSQL%20%7C%20TimescaleDB-Neon%20Cloud-blue?logo=postgresql)](https://neon.tech)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A provably safe runtime assurance framework that wraps Reinforcement Learning (RL) energy dispatch policies in microgrids with a formal safety shield. The system enforces physical State-of-Charge (SoC) bounds, inverter power constraints, and real-time generation/load power balance while streaming high-throughput telemetry and audit verification records to a PostgreSQL / TimescaleDB state engine.

---

## 1. Project Overview

Reinforcement Learning agents applied to microgrid energy management can maximize economic dispatch and renewable self-consumption, but neural network function approximators lack worst-case safety guarantees. Under distribution shifts or unconstrained exploration, RL policies frequently issue battery commands that cause deep-discharge degradation, overcharging, or inverter thermal overloads.

This framework introduces a **formal runtime assurance shield** acting as a safety filter between the RL agent and the physical microgrid actuator:
- **Physical Boundary Verification**: Enforces battery SoC limits ($20\% \le \text{SoC} \le 90\%$) and bidirectional power limits ($|\Delta P| \le 50\text{ kW}$).
- **Exact Convex Safe Projection**: Dynamically projects unsafe proposed actions to the closest admissible action in the safe polyhedron with sub-millisecond execution latency ($\sim 0.0018\text{ ms}$).
- **Telemetry & State Engine**: Streams baseline grid generation/load measurements and logs every audit decision (RL proposed action, safe fallback, intervention reason, verification latency) to a hybrid **PostgreSQL / TimescaleDB** database.

---

## 2. Repository Structure

```
Formal-Runtime-Assurance-for-Learning-Based-Microgrid-Energy-Dispatch/
├── .env.example                 # Environment configuration template (database credentials)
├── .gitignore                   # Excludes .env, virtual environments, and bytecode
├── README.md                    # Project documentation & team setup guide
├── requirements.txt             # Python dependencies (NumPy, Pandas, Matplotlib, Psycopg2)
├── results.csv                  # Multi-seed experimental benchmark metrics
├── soc_comparison.png           # Visual trajectory comparing unshielded vs shielded SoC
├── shared/
│   ├── config.py                # System specifications, physical constraints, and .env loader
│   ├── make_dataset.py          # Synthetic generator for 8,760-hour microgrid generation & tariffs
│   └── microgrid_data.csv       # Baseline 1-year telemetry dataset (timestamp, solar, load, price)
├── shield/
│   ├── rules.py                 # Mathematical safety predicates (rule_soc, rule_power_limit, etc.)
│   ├── shield.py                # Safe bounds computation and convex projection engine
│   ├── demo.py                  # End-to-end 8,760-hour simulation pipeline with live audit logging
│   └── results.py               # Multi-seed evaluation harness for RQ1 (safety) and RQ3 (latency)
└── database/
    ├── __init__.py              # Package interface exports
    ├── schema.sql               # PostgreSQL / TimescaleDB table definitions and hypertable DDL
    ├── connection.py            # Context manager, connectivity probing, and table initializer
    ├── ingest_telemetry.py      # High-performance batch ingest for baseline grid telemetry
    └── audit_logger.py          # Non-blocking, fault-tolerant shield decision audit logger
```

---

## 3. Team Quick-Start Setup

Follow these steps to set up the development environment and run the simulation:

### Step 1 — Pull Latest Code
```bash
git pull origin main
```

### Step 2 — Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3 — Configure Environment Variables
Copy the template to create a local `.env` file:
```bash
cp .env.example .env
```
Open `.env` and paste the team's shared connection URL:
```env
DATABASE_URL=postgresql://neondb_owner:npg_5EBDek4prbfP@ep-broad-bonus-a1izw4a7-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
> [!NOTE]
> Database credentials are never committed to version control. `.env` is ignored by `.gitignore`.

### Step 4 — Run Simulation & Audit Pipeline
```bash
python shield/demo.py
```
* The pipeline automatically checks database connectivity. If the database is reachable, every step streams to the `action_audit_log` table.
* If the database is unreachable, the system automatically falls back to offline simulation with a graceful warning—**the simulation never crashes**.

---

## 4. Database Architecture (PostgreSQL & TimescaleDB)

The state engine supports a dual-target architecture:
1. **Neon PostgreSQL Cloud Instance**: Provides 24/7 remote team access with enabled TimescaleDB extension and hypertables for cloud analytics.
2. **Local / Pinggy TimescaleDB Docker**: High-frequency hypertable chunking and columnar compression for high-load edge deployments.

### Core Tables

* **`microgrid_telemetry`**: Stores baseline and operational microgrid time-series data.
  * Columns: `time` (TIMESTAMPTZ, PK), `solar_generation_kw`, `load_demand_kw`, `battery_soc_percent`, `grid_tariff`.
* **`action_audit_log`**: Records formal verification decisions for every dispatch step.
  * Columns: `time` (TIMESTAMPTZ), `current_soc`, `rl_proposed_action`, `shield_intervention_flag`, `shield_fallback_action`, `executed_action`, `computation_latency_ms`, `violation_reason`.

### Database Maintenance Commands

Initialize or migrate schema tables:
```bash
python -c "from database import init_tables; init_tables()"
```

Ingest baseline historical telemetry (8,760 hours):
```bash
python database/ingest_telemetry.py
```

---

## 5. Annual Simulation Benchmarks (8,760 Hours)

Evaluation over a complete 1-year operational cycle (8,760 hourly dispatch steps) comparing the unshielded RL policy against the formally shielded policy:

| Metric | Unshielded RL Policy | Formally Shielded Policy | Delta / Improvement |
| :--- | :---: | :---: | :---: |
| **Safety Violations (RQ1)** | `6,166` | **`0`** | **100% Elimination (Zero Violations)** |
| **Total Operating Cost (RQ2)** | `Rs 1,947,652` | **`Rs 1,640,032`** | **Rs 307,620 Saved (15.8% Cost Reduction)** |
| **Shield Mean Latency (RQ3)** | — | **`0.0018 ms`** | **5,500x faster than 10 ms budget** |
| **Shield Max Latency (RQ3)** | — | **`0.2306 ms`** | **43x faster than 10 ms budget** |

The runtime shield eliminates 100% of physical constraint violations while reducing net grid shortfall backup costs and maintaining sub-millisecond execution times.

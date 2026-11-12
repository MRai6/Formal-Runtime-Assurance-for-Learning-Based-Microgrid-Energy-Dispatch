import sys
import os
import time
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Setup import paths
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
for p in [_REPO_ROOT / "shared", _REPO_ROOT / "database", _REPO_ROOT]:
    if str(p) not in sys.path:
        sys.path.append(str(p))

from config import BATTERY_KWH, DT_HOURS, SEED, SOC_MIN, SOC_MAX, MAX_POWER_KW
from rules import rule_soc, rule_power_limit, rule_power_balance, next_soc
from shield import project
from database.audit_logger import log_shield_decision, flush_shield_decisions

data_path = _REPO_ROOT / "shared" / "microgrid_data.csv"
df = pd.read_csv(data_path)
df.columns = df.columns.str.strip().str.replace("\ufeff", "", regex=False)
print("Columns:", list(df.columns))


def run(use_shield: bool, log_to_db: bool = True):
    rng = np.random.default_rng(SEED)
    soc, violations, cost, times = 0.5, 0, 0.0, []
    soc_trace = []

    for row in df.itertuples():
        p_proposed = rng.uniform(-80, 80)               # unconstrained "AI" action

        if use_shield:
            t0 = time.perf_counter()
            p_executed = project(soc, p_proposed)
            latency_ms = (time.perf_counter() - t0) * 1000
            times.append(latency_ms)

            # Determine constraint violation on raw proposed action
            breaks_soc = not rule_soc(soc, p_proposed)
            breaks_power = not rule_power_limit(p_proposed)
            shield_intervention_flag = breaks_soc or breaks_power or (abs(p_executed - p_proposed) > 1e-6)

            if shield_intervention_flag:
                reasons = []
                if breaks_power:
                    reasons.append(f"Power limit exceeded (|{p_proposed:.1f} kW| > {MAX_POWER_KW} kW)")
                if breaks_soc:
                    s_next = next_soc(soc, p_proposed)
                    if s_next < SOC_MIN:
                        reasons.append(f"SoC underflow ({s_next*100:.1f}% < {SOC_MIN*100:.0f}%)")
                    else:
                        reasons.append(f"SoC overflow ({s_next*100:.1f}% > {SOC_MAX*100:.0f}%)")
                violation_reason = "; ".join(reasons)
                shield_fallback_action = f"{p_executed:.2f} kW"
            else:
                violation_reason = None
                shield_fallback_action = None
        else:
            p_executed = p_proposed
            latency_ms = 0.0
            times.append(latency_ms)
            shield_intervention_flag = False
            shield_fallback_action = None

            breaks_soc = not rule_soc(soc, p_proposed)
            breaks_power = not rule_power_limit(p_proposed)
            if breaks_soc or breaks_power:
                reasons = []
                if breaks_power:
                    reasons.append(f"Power limit exceeded (|{p_proposed:.1f} kW| > {MAX_POWER_KW} kW)")
                if breaks_soc:
                    s_next = next_soc(soc, p_proposed)
                    if s_next < SOC_MIN:
                        reasons.append(f"SoC underflow ({s_next*100:.1f}% < {SOC_MIN*100:.0f}%)")
                    else:
                        reasons.append(f"SoC overflow ({s_next*100:.1f}% > {SOC_MAX*100:.0f}%)")
                violation_reason = "; ".join(reasons)
            else:
                violation_reason = None

        # Log formal shield decision telemetry to database (gracefully degrades if DB unreachable)
        if log_to_db:
            log_shield_decision(
                current_soc=soc,
                rl_proposed_action=f"{p_proposed:.2f} kW",
                shield_intervention_flag=shield_intervention_flag,
                shield_fallback_action=shield_fallback_action,
                executed_action=f"{p_executed:.2f} kW",
                computation_latency_ms=latency_ms,
                violation_reason=violation_reason,
                timestamp=getattr(row, "timestamp", None),
                buffer=True
            )

        # count a violation if the executed action breaks Rule 1 or Rule 2
        if not (rule_soc(soc, p_executed) and rule_power_limit(p_executed)):
            if use_shield and violations < 3:
                print("VIOLATION:", soc, p_executed, next_soc(soc, p_executed))
            violations += 1

        # backup covers any shortfall; extra solar is curtailed
        net = row.load_kw - row.solar_kw - p_executed
        backup, curtail = max(0, net), max(0, -net)
        assert rule_power_balance(row.solar_kw - curtail, row.load_kw, p_executed, backup)

        cost += backup * DT_HOURS * row.price_inr_kwh
        soc = min(max(next_soc(soc, p_executed), 0.0), 1.0)   # physical limit 0-100%
        soc_trace.append(soc)

    if log_to_db:
        flush_shield_decisions()

    return violations, cost, times, soc_trace


print("Running unshielded simulation baseline...")
v0, c0, _, trace0 = run(use_shield=False, log_to_db=False)

print("Running formally shielded simulation...")
v1, c1, t, trace1 = run(use_shield=True, log_to_db=True)

print(f"Steps simulated:        {len(df)}")
print(f"Unshielded violations:  {v0}   cost: Rs {c0:,.0f}")
print(f"Shielded violations:    {v1}   cost: Rs {c1:,.0f}")
print(f"Shield latency:         mean {np.mean(t):.4f} ms, max {np.max(t):.4f} ms")

# Record summary alongside database audit log to results.csv
results_csv_path = _REPO_ROOT / "results.csv"
demo_record = {
    "seed": SEED,
    "unshielded_violations": v0,
    "shielded_violations": v1,
    "unshielded_cost_inr": round(c0),
    "shielded_cost_inr": round(c1),
    "latency_mean_ms": round(float(np.mean(t)), 4),
    "latency_p99_ms": round(float(np.percentile(t, 99)), 4),
    "latency_max_ms": round(float(np.max(t)), 4),
}

if results_csv_path.exists():
    try:
        res_df = pd.read_csv(results_csv_path)
        if SEED in res_df["seed"].values:
            for k, val in demo_record.items():
                res_df.loc[res_df["seed"] == SEED, k] = val
        else:
            res_df = pd.concat([res_df, pd.DataFrame([demo_record])], ignore_index=True)
        res_df.to_csv(results_csv_path, index=False)
    except Exception:
        pd.DataFrame([demo_record]).to_csv(results_csv_path, index=False)
else:
    pd.DataFrame([demo_record]).to_csv(results_csv_path, index=False)

print(f"Summary metrics logged to: {results_csv_path}")

# Generate and save SoC comparison visual
N = 24 * 7  # first week
fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
ax[0].plot(trace0[:N])
ax[0].set_title("Unshielded agent: SoC")
ax[1].plot(trace1[:N])
ax[1].set_title("Shielded agent: SoC")
for a in ax:
    a.set_ylim(-0.05, 1.05)
    a.axhline(SOC_MIN, color="r", ls="--")
    a.axhline(SOC_MAX, color="r", ls="--")
    a.set_ylabel("SoC")

ax[1].set_xlabel("Hour")
plt.tight_layout()
chart_path = _REPO_ROOT / "soc_comparison.png"
plt.savefig(chart_path, dpi=150)
print(f"Comparison chart saved to: {chart_path}")
plt.close(fig)

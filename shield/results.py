import sys
import os
import time
from pathlib import Path
import numpy as np
import pandas as pd

# Setup import paths
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
for p in [_REPO_ROOT / "shared", _REPO_ROOT / "database", _REPO_ROOT]:
    if str(p) not in sys.path:
        sys.path.append(str(p))

from config import DT_HOURS, SOC_MIN, SOC_MAX, MAX_POWER_KW
from rules import rule_soc, rule_power_limit, next_soc
from shield import project
from database.audit_logger import log_shield_decision, flush_shield_decisions

df = pd.read_csv(_REPO_ROOT / "shared" / "microgrid_data.csv")
df.columns = df.columns.str.strip().str.replace("\ufeff", "", regex=False)


def run(use_shield: bool, seed: int, log_to_db: bool = False):
    rng = np.random.default_rng(seed)
    soc, violations, cost, times = 0.5, 0, 0.0, []
    for row in df.itertuples():
        p_proposed = rng.uniform(-80, 80)
        if use_shield:
            t0 = time.perf_counter()
            p_executed = project(soc, p_proposed)
            latency = (time.perf_counter() - t0) * 1000
            times.append(latency)

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
            latency = 0.0
            times.append(latency)
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

        if log_to_db:
            log_shield_decision(
                current_soc=soc,
                rl_proposed_action=f"{p_proposed:.2f} kW",
                shield_intervention_flag=shield_intervention_flag,
                shield_fallback_action=shield_fallback_action,
                executed_action=f"{p_executed:.2f} kW",
                computation_latency_ms=latency,
                violation_reason=violation_reason,
                timestamp=getattr(row, "timestamp", None),
                buffer=True
            )

        if not (rule_soc(soc, p_executed) and rule_power_limit(p_executed)):
            violations += 1
        backup = max(0, row.load_kw - row.solar_kw - p_executed)
        cost += backup * DT_HOURS * row.price_inr_kwh
        soc = min(max(next_soc(soc, p_executed), 0.0), 1.0)

    if log_to_db:
        flush_shield_decisions()

    return violations, cost, times


if __name__ == "__main__":
    rows = []
    for seed in range(5):
        v0, c0, _ = run(False, seed)
        v1, c1, t = run(True, seed)
        rows.append({
            "seed": seed,
            "unshielded_violations": v0,
            "shielded_violations": v1,
            "unshielded_cost_inr": round(c0),
            "shielded_cost_inr": round(c1),
            "latency_mean_ms": round(np.mean(t), 4),
            "latency_p99_ms": round(np.percentile(t, 99), 4),
            "latency_max_ms": round(np.max(t), 4),
        })

    res = pd.DataFrame(rows)
    print(res.to_string(index=False))
    results_path = _REPO_ROOT / "results.csv"
    res.to_csv(results_path, index=False)

    print("\nRQ1: total violations across", len(rows), "runs:",
          res.unshielded_violations.sum(), "->", res.shielded_violations.sum())
    print("RQ3: worst-case latency:", res.latency_max_ms.max(), "ms (budget 10 ms)")

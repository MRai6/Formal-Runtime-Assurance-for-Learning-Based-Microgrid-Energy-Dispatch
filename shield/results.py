import sys, os, time
import numpy as np, pandas as pd
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))

from config import DT_HOURS
from rules import rule_soc, rule_power_limit, next_soc
from shield import project

HERE = os.path.dirname(__file__)
df = pd.read_csv(os.path.join(HERE, "..", "shared", "microgrid_data.csv"))
df.columns = df.columns.str.strip().str.replace("\ufeff", "", regex=False)


def run(use_shield, seed):
    rng = np.random.default_rng(seed)
    soc, violations, cost, times = 0.5, 0, 0.0, []
    for row in df.itertuples():
        p = rng.uniform(-80, 80)
        if use_shield:
            t0 = time.perf_counter()
            p = project(soc, p)
            times.append((time.perf_counter() - t0) * 1000)
        if not (rule_soc(soc, p) and rule_power_limit(p)):
            violations += 1
        backup = max(0, row.load_kw - row.solar_kw - p)
        cost += backup * DT_HOURS * row.price_inr_kwh
        soc = min(max(next_soc(soc, p), 0.0), 1.0)
    return violations, cost, times


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
res.to_csv("results.csv", index=False)

print("\nRQ1: total violations across", len(rows), "runs:",
      res.unshielded_violations.sum(), "->", res.shielded_violations.sum())
print("RQ3: worst-case latency:", res.latency_max_ms.max(), "ms (budget 10 ms)")
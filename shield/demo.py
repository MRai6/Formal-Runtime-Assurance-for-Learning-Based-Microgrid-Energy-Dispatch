import sys, os, time
import numpy as np, pandas as pd
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))

from config import BATTERY_KWH, DT_HOURS, SEED
from rules import rule_soc, rule_power_limit, rule_power_balance, next_soc
from shield import project

df = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "shared", "microgrid_data.csv"))
df.columns = df.columns.str.strip().str.replace("\ufeff", "", regex=False)
print("Columns:", list(df.columns))


def run(use_shield):
    rng = np.random.default_rng(SEED)
    soc, violations, cost, times = 0.5, 0, 0.0, []
    soc_trace = []
    for row in df.itertuples():
        p = rng.uniform(-80, 80)               # wild "AI" action

        if use_shield:
            t0 = time.perf_counter()
            p = project(soc, p)
            times.append((time.perf_counter() - t0) * 1000)

        # count a violation if the action breaks Rule 1 or Rule 2
        if not (rule_soc(soc, p) and rule_power_limit(p)):
            violations += 1

        # backup covers any shortfall; extra solar is curtailed
        net = row.load_kw - row.solar_kw - p
        backup, curtail = max(0, net), max(0, -net)
        assert rule_power_balance(row.solar_kw - curtail, row.load_kw, p, backup)

        cost += backup * DT_HOURS * row.price_inr_kwh
        soc = min(max(next_soc(soc, p), 0.0), 1.0)   # physical limit 0-100%
        soc_trace.append(soc)
    return violations, cost, times, soc_trace


v0, c0, _, _ = run(use_shield=False)
v1, c1, t, _ = run(use_shield=True)

print(f"Steps simulated:        {len(df)}")
print(f"Unshielded violations:  {v0}   cost: Rs {c0:,.0f}")
print(f"Shielded violations:    {v1}   cost: Rs {c1:,.0f}")
print(f"Shield latency:         mean {np.mean(t):.4f} ms, max {np.max(t):.4f} ms")
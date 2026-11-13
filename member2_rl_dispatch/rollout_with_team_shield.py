
import sys, glob, numpy as np, pandas as pd
import matplotlib.pyplot as plt
# --- paths (edit if your folders are different) ---
REPO  = "/content/team_repo"                                         # clone of the team GitHub repo
DATA  = "/content/team_data.npz"                                     # solar/load/tariff from microgrid_data.csv
MODEL = "/content/drive/MyDrive/team_final/sac_cf_demo/sac_demo.zip" # trained SAC agent
CODE  = "/content"                                                   # folder containing microgrid_env.py
OUT   = "/content/member2_deliverable/results"
sys.path.insert(0, REPO + "/shared"); sys.path.insert(0, REPO + "/shield"); sys.path.insert(0, CODE)
from config import DT_HOURS, SOC_MIN, SOC_MAX, MAX_POWER_KW
from rules import rule_soc, rule_power_limit, next_soc
from shield import project                      # the team shield (Member 1)
from microgrid_env import rule_based_policy
from stable_baselines3 import SAC

d = np.load(DATA)
solar, load, price = d["solar"].astype(float), d["load"].astype(float), d["tariff"].astype(float)
N = len(solar)
keep = np.ones(N, dtype=bool)
for day in (45, 135, 225, 315):
    keep[day * 24: day * 24 + 432] = False       # same training subset as train_dispatch.py
s_n, l_n, t_n = solar[keep].max(), load[keep].max(), price[keep].max()

def obs_at(i, soc):
    h = i % 24
    return np.array([solar[i] / s_n, load[i] / l_n, price[i] / t_n, soc,
                     np.sin(2 * np.pi * h / 24), np.cos(2 * np.pi * h / 24),
                     solar[min(i + 1, N - 1)] / s_n], dtype=np.float32)

model = SAC.load(MODEL)
policies = {
    "Rule-based":             lambda i, soc: float(rule_based_policy(obs_at(i, soc))[0]) * MAX_POWER_KW,
    "Trained SAC (Member 2)": lambda i, soc: float(model.predict(obs_at(i, soc), deterministic=True)[0][0]) * MAX_POWER_KW,
}

def run(policy, use_shield, hours=N):
    soc, viol, cost, ints, trace = 0.5, 0, 0.0, 0, []
    for i in range(hours):
        p = policy(i, soc)
        pe = project(soc, p) if use_shield else p
        ints += int(abs(pe - p) > 1e-6)
        if not (rule_soc(soc, pe) and rule_power_limit(pe)):
            viol += 1
        cost += max(0.0, load[i] - solar[i] - pe) * DT_HOURS * price[i]   # team cost model (import only)
        soc = min(max(next_soc(soc, pe), 0.0), 1.0)
        trace.append(soc)
    return viol, cost, ints, trace

rows, traces = [], {}
for name, pol in policies.items():
    for sh in (False, True):
        v, c, n_int, tr = run(pol, sh)
        rows.append([name, "shielded" if sh else "unshielded", v, round(c), n_int if sh else "-"])
        traces[(name, sh)] = tr
nb = sum(max(0.0, load[i] - solar[i]) * DT_HOURS * price[i] for i in range(N))
rows.append(["No battery (reference)", "-", 0, round(nb), "-"])
tbl = pd.DataFrame(rows, columns=["Policy", "Mode", "Violation hours", "Cost (INR)", "Interventions"])
print(tbl.to_string(index=False))
tbl.to_csv(OUT + "/table_full_year_shield.csv", index=False)

name = "Trained SAC (Member 2)"
fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
for a_, sh, title in ((ax[0], False, "Unshielded trained agent: SoC"), (ax[1], True, "Shielded trained agent: SoC")):
    a_.plot(traces[(name, sh)][:168]); a_.axhline(SOC_MIN, color="r", ls="--"); a_.axhline(SOC_MAX, color="r", ls="--")
    a_.set_ylabel("SoC"); a_.set_title(title); a_.set_ylim(-0.05, 1.05)
ax[1].set_xlabel("Hour"); plt.tight_layout(); plt.savefig(OUT + "/soc_trained_agent.png", dpi=150)

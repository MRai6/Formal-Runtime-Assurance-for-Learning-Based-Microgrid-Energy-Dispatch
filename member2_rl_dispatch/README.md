# Member 2: RL dispatch agent (SAC)

SAC agent for economic dispatch of the PV + battery + grid microgrid, trained on `shared/microgrid_data.csv` against the same battery limits as `shield/shield.py` (100 kWh, 50 kW, SoC 20% to 90%).

## Files
- `microgrid_env.py`: Gymnasium environment (state: solar, load, tariff, SoC, hour sin/cos, next-hour solar; action: battery setpoint in [-1, 1]; reward: -cost + solar self-consumption bonus - intervention penalty - violation penalty).
- `train_dispatch.py`: SAC/PPO training, counterfactual feedback loop (penalty + replay relabelling), optional optimiser demonstrations (`--demos`), held-out evaluation.
- `rollout_with_team_shield.py`: runs the trained agent for the full year through the team's `project()` shield and rules.
- `results/`: `final_comparison.png`, `final_table.png`, CSV tables, the SoC plot and the trained model (`sac_demo.zip`).

## Held-out results (4 seasonal test blocks, 50k training steps)
Demo-SAC, mean over 3 seeds: saving vs rule-based 7.0% ± 0.3, interventions 0.26 (rule-based 0.33), zero violations.

## Run
    python train_dispatch.py --algo sac --cf-loop --demos --steps 50000
    python rollout_with_team_shield.py


import pandas as pd

from integration.simulator import run_simulation

# Load the existing dataset.
data = pd.read_csv("shared/microgrid_data.csv")

# Run without the shield.
baseline_results, baseline_metrics = run_simulation(
    data,
    use_shield=False,
    seed=42,
    controller_name="random_unshielded",
)

# Run with the shield.
shielded_results, shielded_metrics = run_simulation(
    data,
    use_shield=True,
    seed=42,
    controller_name="random_shielded",
)

print("\n===== UNShielded Controller =====")
for key, value in baseline_metrics.items():
    print(f"{key}: {value}")

print("\n===== Shielded Controller =====")
for key, value in shielded_metrics.items():
    print(f"{key}: {value}")

# Save results locally.
baseline_results.to_csv("integration/baseline_results.csv", index=False)
shielded_results.to_csv("integration/shielded_results.csv", index=False)

print("\nSimulation completed. Results saved.")

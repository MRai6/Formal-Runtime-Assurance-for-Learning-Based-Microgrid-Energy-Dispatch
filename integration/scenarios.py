"""
Scenario generator for the microgrid runtime-assurance project.

Creates five input scenarios from shared/microgrid_data.csv, runs each
with and without the existing safety shield, and saves detailed CSV results.

Run from the repository root:
    python integration/scenarios.py

This script does NOT modify shared/config.py, shield/, or integration/simulator.py.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd


# Resolve the repository root so this script works when launched from
# the repository root with: python integration/scenarios.py
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from integration.simulator import run_simulation  # noqa: E402


INPUT_FILE = REPO_ROOT / "shared" / "microgrid_data.csv"
OUTPUT_DIR = REPO_ROOT / "integration" / "results"
RANDOM_SEED = 42

REQUIRED_COLUMNS = {"solar_kw", "load_kw", "price_inr_kwh"}


def _validate_dataset(data: pd.DataFrame) -> None:
    """Check that the source dataset has the columns required by the simulator."""
    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing:
        raise ValueError(
            f"Input dataset is missing required columns: {sorted(missing)}"
        )

    if data.empty:
        raise ValueError("The input dataset is empty.")

    for column in REQUIRED_COLUMNS:
        values = pd.to_numeric(data[column], errors="coerce")
        if values.isna().any():
            raise ValueError(
                f"Column '{column}' contains missing or non-numeric values."
            )
        if (values < 0).any():
            raise ValueError(f"Column '{column}' contains negative values.")


def _hour_of_day(data: pd.DataFrame) -> pd.Series:
    """
    Infer hour of day from row order.

    This assumes the dataset contains consecutive hourly rows, which matches
    the current simulator's 1-hour time step and 8,760-row annual dataset.
    """
    return pd.Series(range(len(data)), index=data.index) % 24


def create_scenarios(data: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Return scenario-specific copies of the original dataset.

    All scenarios preserve the original row count and time ordering.
    The transformations are intentionally transparent and deterministic.
    """
    _validate_dataset(data)

    scenarios: dict[str, pd.DataFrame] = {}

    # 1. Normal operation: unchanged source data.
    scenarios["normal"] = data.copy(deep=True)

    # 2. Cloudy days: reduce solar output and add deterministic variability.
    # Solar is reduced to roughly 30%-55% of its original value.
    cloudy = data.copy(deep=True)
    step = pd.Series(range(len(cloudy)), index=cloudy.index)
    cloud_factor = 0.30 + 0.25 * ((step % 48) / 47.0)
    cloudy["solar_kw"] = cloudy["solar_kw"] * cloud_factor
    scenarios["cloudy"] = cloudy

    # 3. Demand spike: once every seven days, increase demand during
    # the 17:00-20:00 period by 60%.
    demand_spike = data.copy(deep=True)
    hour = _hour_of_day(demand_spike)
    day_number = pd.Series(range(len(demand_spike)), index=demand_spike.index) // 24
    spike_window = ((day_number % 7) == 2) & hour.between(17, 20)
    demand_spike.loc[spike_window, "load_kw"] *= 1.60
    scenarios["demand_spike"] = demand_spike

    # 4. Evening peak: increase demand and tariff during 17:00-22:00 daily.
    evening_peak = data.copy(deep=True)
    hour = _hour_of_day(evening_peak)
    evening_window = hour.between(17, 22)
    evening_peak.loc[evening_window, "load_kw"] *= 1.35
    evening_peak.loc[evening_window, "price_inr_kwh"] *= 1.50
    scenarios["evening_peak"] = evening_peak

    # 5. Combined stress: cloudy solar conditions plus higher evening demand
    # and tariff. This is a deliberately challenging synthetic scenario.
    combined = data.copy(deep=True)
    step = pd.Series(range(len(combined)), index=combined.index)
    cloud_factor = 0.30 + 0.20 * ((step % 48) / 47.0)
    combined["solar_kw"] = combined["solar_kw"] * cloud_factor

    hour = _hour_of_day(combined)
    evening_window = hour.between(17, 22)
    combined.loc[evening_window, "load_kw"] *= 1.50
    combined.loc[evening_window, "price_inr_kwh"] *= 1.60
    scenarios["combined_stress"] = combined

    return scenarios


def _run_one_scenario(
    scenario_name: str,
    scenario_data: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    """Run one scenario with and without the shield using matching random seeds."""

    baseline_results, baseline_metrics = run_simulation(
        data=scenario_data,
        use_shield=False,
        seed=RANDOM_SEED,
        scenario_name=scenario_name,
        controller_name="random_test_unshielded",
    )

    shielded_results, shielded_metrics = run_simulation(
        data=scenario_data,
        use_shield=True,
        seed=RANDOM_SEED,
        scenario_name=scenario_name,
        controller_name="random_test_shielded",
    )

    return (
        baseline_results,
        shielded_results,
        baseline_metrics,
        shielded_metrics,
    )


def main() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Could not find the input dataset:\n{INPUT_FILE}\n\n"
            "Check that shared/microgrid_data.csv exists in your repository."
        )

    print(f"Loading source dataset: {INPUT_FILE}")
    source_data = pd.read_csv(INPUT_FILE)
    _validate_dataset(source_data)

    print(f"Loaded {len(source_data):,} hourly rows.")
    scenarios = create_scenarios(source_data)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_metrics: list[dict] = []

    for scenario_name, scenario_data in scenarios.items():
        print(f"\nRunning scenario: {scenario_name}")

        # Save the transformed input so the scenario can be inspected later.
        input_path = OUTPUT_DIR / f"{scenario_name}_input.csv"
        scenario_data.to_csv(input_path, index=False)

        (
            baseline_results,
            shielded_results,
            baseline_metrics,
            shielded_metrics,
        ) = _run_one_scenario(scenario_name, scenario_data)

        baseline_path = OUTPUT_DIR / f"{scenario_name}_baseline.csv"
        shielded_path = OUTPUT_DIR / f"{scenario_name}_shielded.csv"

        baseline_results.to_csv(baseline_path, index=False)
        shielded_results.to_csv(shielded_path, index=False)

        all_metrics.append(baseline_metrics)
        all_metrics.append(shielded_metrics)

        print(
            f"  Baseline violations: {baseline_metrics['safety_violations']:,}"
        )
        print(
            f"  Shielded violations: {shielded_metrics['safety_violations']:,}"
        )
        print(
            "  Baseline cost: "
            f"Rs. {baseline_metrics['total_cost_inr']:,.2f}"
        )
        print(
            "  Shielded cost: "
            f"Rs. {shielded_metrics['total_cost_inr']:,.2f}"
        )
        print(f"  Saved: {baseline_path.name}, {shielded_path.name}")

    metrics_path = OUTPUT_DIR / "scenario_metrics.csv"
    pd.DataFrame(all_metrics).to_csv(metrics_path, index=False)

    print("\nScenario generation completed.")
    print(f"All outputs are in: {OUTPUT_DIR}")
    print(f"Summary metrics: {metrics_path.name}")
    print(
        "\nReminder: the controller is a random test controller, not an RL agent. "
        "Unmet load remains zero because the simulator assumes unlimited grid backup."
    )


if __name__ == "__main__":
    main()

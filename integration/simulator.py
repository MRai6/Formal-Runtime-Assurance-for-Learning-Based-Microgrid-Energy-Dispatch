
import time
import numpy as np
import pandas as pd

from shield.shield import project
from shared.config import (
    BATTERY_KWH,
    DT_HOURS,
    SOC_MIN,
    SOC_MAX,
    MAX_POWER_KW,
)
from shield.rules import next_soc, rule_soc, rule_power_limit


def random_controller(state, rng):
    """
    Temporary test controller.

    Proposes random battery power between -80 and +80 kW.
    Positive = discharging.
    Negative = charging.

    This is NOT an RL agent.
    """
    return float(rng.uniform(-80, 80))


def run_simulation(
    data,
    controller=random_controller,
    use_shield=True,
    initial_soc=0.50,
    seed=42,
    scenario_name="normal",
    controller_name="random_test",
):
    """
    Runs a microgrid simulation.

    Parameters:
        data: DataFrame containing solar_kw, load_kw and price_inr_kwh.
        controller: Function that receives state and rng, returns proposed kW.
        use_shield: Whether to apply the safety shield.
        initial_soc: Starting battery state of charge (0 to 1).
        seed: Random seed.
        scenario_name: Name of the experiment scenario.
        controller_name: Name of the controller.

    Returns:
        results: DataFrame containing every simulation step.
        metrics: Dictionary containing summary statistics.
    """

    required_columns = {
        "solar_kw",
        "load_kw",
        "price_inr_kwh",
    }

    missing = required_columns - set(data.columns)

    if missing:
        raise ValueError(f"Dataset is missing columns: {missing}")

    if not 0 <= initial_soc <= 1:
        raise ValueError("Initial SoC must be between 0 and 1.")

    rng = np.random.default_rng(seed)

    soc = float(initial_soc)
    total_cost = 0.0
    total_unmet_load = 0.0
    total_curtailed_energy = 0.0

    intervention_count = 0
    violation_count = 0

    shield_latencies = []
    records = []

    for step, row in enumerate(data.itertuples(index=False)):

        solar = float(row.solar_kw)
        load = float(row.load_kw)
        tariff = float(row.price_inr_kwh)

        if not all(np.isfinite(x) for x in [solar, load, tariff]):
            raise ValueError(f"Invalid input data at step {step}.")

        if solar < 0 or load < 0 or tariff < 0:
            raise ValueError(f"Negative input value at step {step}.")

        # State passed to the controller.
        state = {
            "soc": soc,
            "solar_kw": solar,
            "load_kw": load,
            "price_inr_kwh": tariff,
            "step": step,
        }

        # 1. Controller proposes an action.
        proposed_kw = float(controller(state, rng))

        if not np.isfinite(proposed_kw):
            raise ValueError(f"Controller returned invalid action at step {step}.")

        # 2. Safety shield checks the proposed action.
        if use_shield:
            start = time.perf_counter()
            executed_kw = float(project(soc, proposed_kw))
            latency_ms = (time.perf_counter() - start) * 1000

            shield_latencies.append(latency_ms)

            intervened = not np.isclose(
                proposed_kw,
                executed_kw,
                atol=1e-6,
            )

            if intervened:
                intervention_count += 1

        else:
            executed_kw = proposed_kw
            latency_ms = 0.0
            intervened = False

        # 3. Verify whether the executed action is safe.
        safe = (
            rule_soc(soc, executed_kw)
            and rule_power_limit(executed_kw)
        )

        if not safe:
            violation_count += 1

        # 4. Calculate microgrid power balance.
        # Positive battery power means discharge.
        net_demand = load - solar - executed_kw

        backup_kw = max(0.0, net_demand)
        curtailed_kw = max(0.0, -net_demand)

        # 5. Calculate unmet load and operating cost.
        # Current model assumes unlimited grid backup.
        unmet_load_kw = 0.0

        step_cost = backup_kw * DT_HOURS * tariff

        total_cost += step_cost
        total_unmet_load += unmet_load_kw * DT_HOURS
        total_curtailed_energy += curtailed_kw * DT_HOURS

        # 6. Update battery SoC.
        next_battery_soc = next_soc(soc, executed_kw)

        # Physical clipping prevents impossible battery states.
        # It does NOT make an unsafe action safe.
        soc = float(np.clip(next_battery_soc, 0.0, 1.0))

        # 7. Save this simulation step.
        records.append({
            "step": step,
            "scenario": scenario_name,
            "controller": controller_name,
            "solar_kw": solar,
            "load_kw": load,
            "price_inr_kwh": tariff,
            "soc_before": state["soc"],
            "proposed_kw": proposed_kw,
            "executed_kw": executed_kw,
            "shield_intervened": intervened,
            "shield_latency_ms": latency_ms,
            "safe_action": safe,
            "backup_kw": backup_kw,
            "curtailed_kw": curtailed_kw,
            "unmet_load_kw": unmet_load_kw,
            "step_cost_inr": step_cost,
            "soc_after": soc,
        })

    results = pd.DataFrame(records)

    if len(results) == 0:
        raise ValueError("Cannot simulate an empty dataset.")

    latencies = np.array(shield_latencies, dtype=float)

    metrics = {
        "scenario": scenario_name,
        "controller": controller_name,
        "shield_enabled": use_shield,
        "simulation_steps": len(results),
        "total_cost_inr": total_cost,
        "safety_violations": violation_count,
        "interventions": intervention_count,
        "intervention_rate_percent": (
            intervention_count / len(results) * 100
        ),
        "violation_rate_percent": (
            violation_count / len(results) * 100
        ),
        "unmet_load_kwh": total_unmet_load,
        "curtailed_energy_kwh": total_curtailed_energy,
        "mean_shield_latency_ms": (
            float(np.mean(latencies)) if len(latencies) else 0.0
        ),
        "p95_shield_latency_ms": (
            float(np.percentile(latencies, 95)) if len(latencies) else 0.0
        ),
        "max_shield_latency_ms": (
            float(np.max(latencies)) if len(latencies) else 0.0
        ),
    }

    return results, metrics

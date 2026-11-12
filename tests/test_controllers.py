"""Unit and closed-loop validation tests for microgrid dispatch controllers.

Verifies:
    - Rule-based controller dispatch logic under PV surplus, deficit, and balance.
    - Observance of battery SoC boundaries (min_soc, max_soc) and power ratings.
    - Strict avoidance of simultaneous charging and discharging (single scalar action).
    - Gym observation interface compatibility (controller.act(obs)).
    - Closed-loop 24-hour simulation performance in MicrogridEnv.
    - Economic comparison against passive zero-battery dispatch baseline.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from microgrid_sim.config.loader import load_complete_configuration
from microgrid_sim.config.schemas import CompleteSystemConfig
from microgrid_sim.controllers.rule_based import RuleBasedController, RuleBasedControllerConfig
from microgrid_sim.env.microgrid_env import MicrogridEnv
from microgrid_sim.env.spaces import ObsIndex, create_observation_space


@pytest.fixture(scope="module")
def complete_cfg(configs_dir: Path) -> CompleteSystemConfig:
    """Fixture providing loaded master microgrid configuration."""
    return load_complete_configuration(configs_dir)


@pytest.fixture
def deterministic_24h_df() -> pd.DataFrame:
    """Deterministic 24-hour (96-step) time-series fixture for controller testing."""
    idx = pd.date_range("2018-06-21 00:00:00", periods=96, freq="15min", tz="UTC")

    ghi = np.zeros(96, dtype=np.float64)
    dni = np.zeros(96, dtype=np.float64)
    dhi = np.zeros(96, dtype=np.float64)
    zenith = np.full(96, 98.0, dtype=np.float64)
    azimuth = np.full(96, 180.0, dtype=np.float64)

    for i in range(24, 80):
        frac = (i - 24) / 55.0
        sun_elev = np.sin(np.pi * frac)
        ghi[i] = 950.0 * sun_elev
        dni[i] = 850.0 * sun_elev
        dhi[i] = 100.0 * sun_elev
        zenith[i] = max(10.0, 90.0 - 75.0 * sun_elev)
        azimuth[i] = 90.0 + 180.0 * frac

    load = np.full(96, 40.0, dtype=np.float64)
    for i in range(32, 72):
        load[i] = 40.0 + 80.0 * np.sin(np.pi * (i - 32) / 40.0)

    amb_temp = 18.0 + 10.0 * (ghi / 950.0)

    return pd.DataFrame(
        {
            "ghi_w_per_m2": ghi,
            "dni_w_per_m2": dni,
            "dhi_w_per_m2": dhi,
            "ambient_temperature_c": amb_temp,
            "solar_zenith_deg": zenith,
            "solar_azimuth_deg": azimuth,
            "load_power_kw": load,
        },
        index=idx,
    )


# ==============================================================================
# 1. Rule-Based Controller Logic Tests
# ==============================================================================

def test_rule_based_controller_surplus_charges_battery() -> None:
    """Verify that solar surplus (P_pv > P_load) commands battery charging (a < 0)."""
    controller = RuleBasedController(p_rated_ch_kw=100.0, p_rated_dis_kw=100.0)

    # PV = 100 kW, Load = 40 kW -> Surplus = 60 kW
    action = controller.compute_action(p_pv_kw=100.0, p_load_kw=40.0, soc=0.50)

    # a should be -60 / 100 = -0.60
    assert isinstance(action, np.ndarray)
    assert action.shape == (1,)
    assert pytest.approx(action[0], abs=1e-4) == -0.60


def test_rule_based_controller_surplus_full_battery_idles() -> None:
    """Verify that solar surplus when battery is at or above max SoC (0.90) results in idle (a = 0)."""
    controller = RuleBasedController()

    # Battery already at 0.90
    action = controller.compute_action(p_pv_kw=120.0, p_load_kw=30.0, soc=0.90)
    assert action[0] == 0.0

    # Battery above 0.90
    action_high = controller.compute_action(p_pv_kw=120.0, p_load_kw=30.0, soc=0.92)
    assert action_high[0] == 0.0


def test_rule_based_controller_deficit_discharges_battery() -> None:
    """Verify that solar deficit (P_pv < P_load) commands battery discharging (a > 0)."""
    controller = RuleBasedController(p_rated_ch_kw=100.0, p_rated_dis_kw=100.0)

    # PV = 20 kW, Load = 70 kW -> Deficit = 50 kW
    action = controller.compute_action(p_pv_kw=20.0, p_load_kw=70.0, soc=0.50)

    # a should be +50 / 100 = +0.50
    assert pytest.approx(action[0], abs=1e-4) == 0.50


def test_rule_based_controller_deficit_depleted_battery_idles() -> None:
    """Verify that solar deficit when battery is at or below min SoC (0.15) results in idle (a = 0)."""
    controller = RuleBasedController()

    # Battery already at 0.15
    action = controller.compute_action(p_pv_kw=0.0, p_load_kw=80.0, soc=0.15)
    assert action[0] == 0.0

    # Battery below 0.15
    action_low = controller.compute_action(p_pv_kw=0.0, p_load_kw=80.0, soc=0.12)
    assert action_low[0] == 0.0


def test_rule_based_controller_deadband_idles() -> None:
    """Verify that small imbalances within deadband (0.05 kW) result in idle (a = 0)."""
    cfg = RuleBasedControllerConfig(min_power_deadband_kw=0.10)
    controller = RuleBasedController(config=cfg)

    # Difference is 0.05 kW <= deadband (0.10 kW)
    action = controller.compute_action(p_pv_kw=50.05, p_load_kw=50.0, soc=0.50)
    assert action[0] == 0.0


def test_rule_based_controller_action_clamping() -> None:
    """Verify that action never exceeds [-1.0, 1.0] even under extreme surplus or deficit."""
    controller = RuleBasedController(p_rated_ch_kw=100.0, p_rated_dis_kw=100.0)

    # Extreme surplus: 300 kW surplus vs 100 kW rating
    action_surplus = controller.compute_action(p_pv_kw=350.0, p_load_kw=50.0, soc=0.50)
    assert action_surplus[0] == -1.0

    # Extreme deficit: 300 kW deficit vs 100 kW rating
    action_deficit = controller.compute_action(p_pv_kw=0.0, p_load_kw=300.0, soc=0.50)
    assert action_deficit[0] == 1.0


def test_rule_based_controller_gym_act_interface() -> None:
    """Verify that act() correctly parses observation vector and returns valid action."""
    controller = RuleBasedController(p_norm_load_kw=100.0, p_norm_pv_kw=120.0)

    # Create dummy observation vector matching create_observation_space()
    obs = np.zeros(12, dtype=np.float32)
    obs[ObsIndex.SOC] = 0.50
    obs[ObsIndex.LOAD_DEMAND] = 0.60   # Load = 60 kW
    obs[ObsIndex.PV_POTENTIAL] = 0.83333  # PV = 100 kW
    # Surplus = 100 - 60 = 40 kW -> action = -0.40

    action = controller.act(obs)
    assert isinstance(action, np.ndarray)
    assert action.shape == (1,)
    assert pytest.approx(action[0], abs=1e-3) == -0.40


# ==============================================================================
# 2. Closed-Loop Simulation & Economic Benchmark Tests
# ==============================================================================

def test_rule_based_controller_closed_loop_simulation(
    complete_cfg: CompleteSystemConfig,
    deterministic_24h_df: pd.DataFrame,
) -> None:
    """Execute complete 24-hour closed-loop simulation of RuleBasedController in MicrogridEnv."""
    env = MicrogridEnv(config=complete_cfg, dataset=deterministic_24h_df)
    controller = RuleBasedController(
        p_rated_ch_kw=complete_cfg.battery.power_and_thermal.max_charge_power_kw,
        p_rated_dis_kw=complete_cfg.battery.power_and_thermal.max_discharge_power_kw,
    )

    obs, _ = env.reset(options={"initial_soc": 0.50})
    terminated = False
    step_count = 0

    while not terminated:
        action = controller.act(obs)
        obs, reward, terminated, truncated, info = env.step(action)
        step_count += 1

        # Check in-flight physical invariants:
        assert info["residual_error_kw"] < 1e-6
        assert info["is_balanced"] is True
        assert complete_cfg.battery.capacity.minimum_soc - 1e-6 <= info["soc"] <= complete_cfg.battery.capacity.maximum_soc + 1e-6

        # Check mutual exclusivity on battery AC bus
        assert not (info["p_batt_ch_ac_kw"] > 1e-6 and info["p_batt_dis_ac_kw"] > 1e-6)

    assert step_count == len(deterministic_24h_df)


def test_rule_based_controller_economic_outperformance(
    complete_cfg: CompleteSystemConfig,
    deterministic_24h_df: pd.DataFrame,
) -> None:
    """Verify that rule-based battery dispatch reduces total grid electricity cost vs passive baseline."""
    # 1. Run Rule-Based Controlled Microgrid
    env_rb = MicrogridEnv(config=complete_cfg, dataset=deterministic_24h_df)
    controller = RuleBasedController()

    obs_rb, _ = env_rb.reset(options={"initial_soc": 0.50})
    term_rb = False
    while not term_rb:
        act = controller.act(obs_rb)
        obs_rb, _, term_rb, _, _ = env_rb.step(act)
    cost_rb = env_rb.cumulative_cost_usd

    # 2. Run Passive (Zero-Battery / Idle) Microgrid
    env_passive = MicrogridEnv(config=complete_cfg, dataset=deterministic_24h_df)
    obs_p, _ = env_passive.reset(options={"initial_soc": 0.50})
    term_p = False
    while not term_p:
        # Action is always 0.0 (no battery dispatch)
        obs_p, _, term_p, _, _ = env_passive.step(np.array([0.0], dtype=np.float32))
    cost_passive = env_passive.cumulative_cost_usd

    # Active battery dispatch stores cheap daytime surplus solar and offsets expensive grid purchases,
    # thereby lowering net operating cost compared to a passive installation.
    assert cost_rb < cost_passive
    savings_pct = (cost_passive - cost_rb) / cost_passive * 100.0
    assert savings_pct > 5.0  # Demonstrates meaningful economic benefit

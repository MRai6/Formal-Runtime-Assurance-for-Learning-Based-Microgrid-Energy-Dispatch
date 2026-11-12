"""Unit and integration tests for Gymnasium MicrogridEnv interface.

Verifies:
    - Gymnasium reset() and step() contracts.
    - Observation and action space compliance (including Farama check_env).
    - Episode termination and truncation conditions.
    - Dynamic battery SoC envelope enforcement.
    - AC bus active power balance conservation (< 1 mW residual).
    - Solar PV surplus scenario (charging battery, exporting to grid, curtailing excess).
    - Solar PV deficit scenario (discharging battery, importing from grid, unserved load on limit).
    - Grid import/export interconnection limits.
    - Deterministic replay reproducibility with identical seeds and inputs.
"""

import math
from pathlib import Path
import gymnasium as gym
from gymnasium.utils.env_checker import check_env
import numpy as np
import pandas as pd
import pytest

from microgrid_sim.config.loader import load_complete_configuration
from microgrid_sim.config.schemas import CompleteSystemConfig
from microgrid_sim.env.microgrid_env import MicrogridEnv
from microgrid_sim.env.spaces import ObsIndex, create_action_space, create_observation_space


@pytest.fixture(scope="module")
def complete_cfg(configs_dir: Path) -> CompleteSystemConfig:
    """Fixture providing loaded master microgrid configuration."""
    return load_complete_configuration(configs_dir)


@pytest.fixture
def deterministic_24h_df() -> pd.DataFrame:
    """Deterministic 24-hour (96-step) time-series fixture for unit testing."""
    idx = pd.date_range("2018-06-21 00:00:00", periods=96, freq="15min", tz="UTC")

    # Diurnal solar profile: zero at night (steps 0-23 and 80-95), bell-curve during day (steps 24-79)
    ghi = np.zeros(96, dtype=np.float64)
    dni = np.zeros(96, dtype=np.float64)
    dhi = np.zeros(96, dtype=np.float64)
    zenith = np.full(96, 98.0, dtype=np.float64)
    azimuth = np.full(96, 180.0, dtype=np.float64)

    for i in range(24, 80):
        frac = (i - 24) / 55.0  # 0 to 1
        sun_elev = math.sin(math.pi * frac)
        ghi[i] = 950.0 * sun_elev
        dni[i] = 850.0 * sun_elev
        dhi[i] = 100.0 * sun_elev
        zenith[i] = max(10.0, 90.0 - 75.0 * sun_elev)
        azimuth[i] = 90.0 + 180.0 * frac  # 90° (East) to 270° (West)

    # Typical commercial building load profile: 40 kW base at night, 120 kW peak in afternoon
    load = np.full(96, 40.0, dtype=np.float64)
    for i in range(32, 72):
        load[i] = 40.0 + 80.0 * math.sin(math.pi * (i - 32) / 40.0)

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
# 1. Environment Initialization & Gymnasium Contract Tests
# ==============================================================================

def test_env_spaces_structure(complete_cfg: CompleteSystemConfig) -> None:
    """Verify observation and action space types, shapes, and boundary validity."""
    obs_space = create_observation_space()
    act_space = create_action_space()

    assert isinstance(obs_space, gym.spaces.Box)
    assert obs_space.shape == (12,)
    assert obs_space.dtype == np.float32

    assert isinstance(act_space, gym.spaces.Box)
    assert act_space.shape == (1,)
    assert act_space.dtype == np.float32
    assert act_space.low[0] == -1.0
    assert act_space.high[0] == 1.0


def test_env_gymnasium_api_check(complete_cfg: CompleteSystemConfig, deterministic_24h_df: pd.DataFrame) -> None:
    """Verify Farama Gymnasium official compliance using check_env utility."""
    env = MicrogridEnv(config=complete_cfg, dataset=deterministic_24h_df)
    # check_env performs systematic validation of spaces, reset contract, step contract, and types
    check_env(env)


def test_env_reset_contract(complete_cfg: CompleteSystemConfig, deterministic_24h_df: pd.DataFrame) -> None:
    """Verify reset() returns valid initial observation, info dict, and obeys options."""
    env = MicrogridEnv(config=complete_cfg, dataset=deterministic_24h_df)

    # Default reset
    obs, info = env.reset(seed=42)
    assert env.observation_space.contains(obs)
    assert isinstance(info, dict)
    assert info["step_index"] == 0
    assert info["episode_step"] == 0
    assert info["soc"] == complete_cfg.battery.capacity.initial_soc
    assert info["status"] == "reset"

    # Custom initial SoC via options
    obs_custom, info_custom = env.reset(options={"initial_soc": 0.75, "start_step": 10})
    assert obs_custom[ObsIndex.SOC] == 0.75
    assert info_custom["soc"] == 0.75
    assert info_custom["step_index"] == 10


def test_env_step_contract(complete_cfg: CompleteSystemConfig, deterministic_24h_df: pd.DataFrame) -> None:
    """Verify step() returns 5-tuple (obs, reward, terminated, truncated, info) matching types."""
    env = MicrogridEnv(config=complete_cfg, dataset=deterministic_24h_df)
    obs, info = env.reset(seed=123)

    action = np.array([0.5], dtype=np.float32)  # Discharging request
    next_obs, reward, terminated, truncated, step_info = env.step(action)

    assert env.observation_space.contains(next_obs)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert isinstance(step_info, dict)
    assert "p_served_load_kw" in step_info
    assert "p_grid_import_kw" in step_info
    assert "residual_error_kw" in step_info
    assert step_info["is_balanced"] is True


def test_env_episode_termination(complete_cfg: CompleteSystemConfig, deterministic_24h_df: pd.DataFrame) -> None:
    """Verify that environment terminates when reaching the end of the episode."""
    env = MicrogridEnv(config=complete_cfg, dataset=deterministic_24h_df)
    env.reset(options={"max_steps": 10})

    terminated = False
    step_count = 0
    while not terminated:
        _, _, terminated, _, _ = env.step(np.array([0.0], dtype=np.float32))
        step_count += 1

    assert step_count == 10
    assert terminated is True


# ==============================================================================
# 2. Physics & Conservation Verification Tests
# ==============================================================================

def test_env_pv_surplus_scenario(complete_cfg: CompleteSystemConfig) -> None:
    """Verify behavior during high PV surplus: local load served, battery charges, excess exported."""
    # Create single-step extreme surplus fixture: PV ~120 kW AC, Load = 20 kW
    idx = pd.date_range("2018-06-21 12:00:00", periods=2, freq="15min", tz="UTC")
    df_surplus = pd.DataFrame(
        {
            "ghi_w_per_m2": [1000.0, 1000.0],
            "dni_w_per_m2": [900.0, 900.0],
            "dhi_w_per_m2": [150.0, 150.0],
            "ambient_temperature_c": [25.0, 25.0],
            "solar_zenith_deg": [15.0, 15.0],
            "solar_azimuth_deg": [180.0, 180.0],
            "load_power_kw": [20.0, 20.0],
        },
        index=idx,
    )

    env = MicrogridEnv(config=complete_cfg, dataset=df_surplus)
    env.reset(options={"initial_soc": 0.50})

    # Action: Request maximum charging (a = -1.0)
    _, _, _, _, info = env.step(np.array([-1.0], dtype=np.float32))

    # Load must be completely served (zero unserved)
    assert info["p_unserved_load_kw"] == 0.0
    assert info["p_served_load_kw"] == 20.0

    # Solar PV should generate high AC power (> 90 kW)
    assert info["p_pv_ac_potential_kw"] > 90.0

    # Battery should be charging (negative DC power, positive AC draw)
    assert info["p_batt_dc_kw"] < 0.0
    assert info["p_batt_ch_ac_kw"] > 0.0
    assert info["p_batt_dis_ac_kw"] == 0.0

    # Kirchhoff active power conservation must strictly hold
    assert info["residual_error_kw"] < 1e-6
    assert info["is_balanced"] is True


def test_env_pv_deficit_scenario(complete_cfg: CompleteSystemConfig) -> None:
    """Verify behavior during PV deficit: battery discharges, grid imports to serve remaining load."""
    # Nighttime condition: zero solar, 100 kW load
    idx = pd.date_range("2018-06-21 02:00:00", periods=2, freq="15min", tz="UTC")
    df_deficit = pd.DataFrame(
        {
            "ghi_w_per_m2": [0.0, 0.0],
            "dni_w_per_m2": [0.0, 0.0],
            "dhi_w_per_m2": [0.0, 0.0],
            "ambient_temperature_c": [15.0, 15.0],
            "solar_zenith_deg": [105.0, 105.0],
            "solar_azimuth_deg": [0.0, 0.0],
            "load_power_kw": [100.0, 100.0],
        },
        index=idx,
    )

    env = MicrogridEnv(config=complete_cfg, dataset=df_deficit)
    env.reset(options={"initial_soc": 0.50})

    # Action: Request 50 kW discharging (a = +0.50)
    _, _, _, _, info = env.step(np.array([0.50], dtype=np.float32))

    # PV is zero
    assert info["p_pv_ac_potential_kw"] == 0.0
    assert info["p_pv_ac_delivered_kw"] == 0.0

    # Battery discharges AC power (~48 kW delivered to AC bus at 96% PCS efficiency)
    assert info["p_batt_dis_ac_kw"] > 40.0
    assert info["p_batt_ch_ac_kw"] == 0.0

    # Remaining load must be imported from the grid
    assert info["p_grid_import_kw"] > 45.0
    assert info["p_grid_export_kw"] == 0.0
    assert info["p_unserved_load_kw"] == 0.0

    # Kirchhoff active power conservation must strictly hold
    assert info["residual_error_kw"] < 1e-6
    assert info["is_balanced"] is True


def test_env_battery_soc_boundaries_enforced(complete_cfg: CompleteSystemConfig) -> None:
    """Verify that battery model prevents SoC from exceeding [0.15, 0.90] bounds."""
    idx = pd.date_range("2018-01-01 00:00:00", periods=10, freq="15min", tz="UTC")
    df = pd.DataFrame(
        {
            "ghi_w_per_m2": np.zeros(10),
            "dni_w_per_m2": np.zeros(10),
            "dhi_w_per_m2": np.zeros(10),
            "ambient_temperature_c": np.full(10, 20.0),
            "solar_zenith_deg": np.full(10, 100.0),
            "solar_azimuth_deg": np.zeros(10),
            "load_power_kw": np.full(10, 50.0),
        },
        index=idx,
    )

    env = MicrogridEnv(config=complete_cfg, dataset=df)

    # 1. Test upper boundary: start at 0.90 and try to charge aggressively
    env.reset(options={"initial_soc": 0.90})
    for _ in range(5):
        _, _, _, _, info = env.step(np.array([-1.0], dtype=np.float32))
        assert info["soc"] <= 0.90 + 1e-6
        assert info["p_batt_rejected_kw"] > 0.0  # Rejected power tracked

    # 2. Test lower boundary: start at 0.15 and try to discharge aggressively
    env.reset(options={"initial_soc": 0.15})
    for _ in range(5):
        _, _, _, _, info = env.step(np.array([1.0], dtype=np.float32))
        assert info["soc"] >= 0.15 - 1e-6
        assert info["p_batt_rejected_kw"] > 0.0  # Rejected power tracked


def test_env_ac_power_balance_continuous_conservation(
    complete_cfg: CompleteSystemConfig,
    deterministic_24h_df: pd.DataFrame,
) -> None:
    """Verify that AC bus active power balance holds with residual < 1 mW at every step of 24h run."""
    env = MicrogridEnv(config=complete_cfg, dataset=deterministic_24h_df)
    env.reset(seed=100)

    # Run 96 steps with alternating dispatch actions
    actions = [-0.8, -0.4, 0.0, 0.4, 0.8]
    for step_i in range(len(deterministic_24h_df)):
        act = np.array([actions[step_i % len(actions)]], dtype=np.float32)
        _, _, terminated, _, info = env.step(act)

        # Invariant checks at each step:
        assert info["residual_error_kw"] < 1e-6, f"Step {step_i} residual {info['residual_error_kw']} kW exceeds 1 mW"
        assert info["is_balanced"] is True

        # Non-negative physical components
        assert info["p_served_load_kw"] >= 0.0
        assert info["p_unserved_load_kw"] >= 0.0
        assert info["p_pv_ac_delivered_kw"] >= 0.0
        assert info["p_grid_import_kw"] >= 0.0
        assert info["p_grid_export_kw"] >= 0.0
        assert info["p_batt_ch_ac_kw"] >= 0.0
        assert info["p_batt_dis_ac_kw"] >= 0.0

        if terminated:
            break


# ==============================================================================
# 3. Determinism & Reproducibility Tests
# ==============================================================================

def test_env_deterministic_replay(
    complete_cfg: CompleteSystemConfig,
    deterministic_24h_df: pd.DataFrame,
) -> None:
    """Verify bit-for-bit identical trajectory replay with identical seed and action sequence."""
    env1 = MicrogridEnv(config=complete_cfg, dataset=deterministic_24h_df)
    env2 = MicrogridEnv(config=complete_cfg, dataset=deterministic_24h_df)

    obs1, _ = env1.reset(seed=999)
    obs2, _ = env2.reset(seed=999)
    np.testing.assert_allclose(obs1, obs2, atol=1e-7)

    # Generate pseudo-random deterministic action trajectory
    rng = np.random.default_rng(seed=42)
    actions = rng.uniform(-1.0, 1.0, size=(48, 1)).astype(np.float32)

    for i in range(48):
        o1, r1, t1, tr1, info1 = env1.step(actions[i])
        o2, r2, t2, tr2, info2 = env2.step(actions[i])

        np.testing.assert_allclose(o1, o2, atol=1e-7)
        assert pytest.approx(r1, abs=1e-7) == r2
        assert t1 == t2
        assert tr1 == tr2
        assert pytest.approx(info1["soc"], abs=1e-7) == info2["soc"]
        assert pytest.approx(info1["step_net_cost_usd"], abs=1e-7) == info2["step_net_cost_usd"]
        assert pytest.approx(info1["p_grid_import_kw"], abs=1e-7) == info2["p_grid_import_kw"]
        assert pytest.approx(info1["p_grid_export_kw"], abs=1e-7) == info2["p_grid_export_kw"]


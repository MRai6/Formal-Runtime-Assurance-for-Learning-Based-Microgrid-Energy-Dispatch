"""
train_dispatch.py -- Member 2: train PPO / SAC dispatch agents + counterfactual shield feedback.

Usage:
    python train_dispatch.py --algo sac --steps 100000
    python train_dispatch.py --algo ppo --steps 200000
    python train_dispatch.py --algo sac --steps 100000 --no-cf      # ablation: no counterfactual loop

Counterfactual feedback loop
----------------------------
When the shield overrides the agent's proposed action a  ->  a_safe:
  1. Penalty loss  : env reward already contains  -lambda * |a - a_safe|   (works for PPO and SAC)
  2. Relabelling   : (SAC only) CounterfactualCallback inserts an EXTRA transition
                     (s, a_safe, r_base, s')  into the replay buffer, so the critic learns that the
                     safe action is good in this state, not only that the proposed one was bad.
Result: the policy drifts toward actions the shield accepts -> fewer interventions over training.
"""
import argparse, os
import numpy as np
import pandas as pd
from stable_baselines3 import PPO, SAC
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor

from microgrid_env import MicrogridEnv, make_synthetic_data, rule_based_policy


class CounterfactualCallback(BaseCallback):
    """Feeds shield overrides back into the SAC replay buffer + logs intervention rate."""

    def __init__(self, use_cf=True, log_every=2000):
        super().__init__()
        self.use_cf, self.log_every = use_cf, log_every
        self.n_int, self.n_steps, self.history = 0, 0, []

    def _on_step(self) -> bool:
        info = self.locals["infos"][0]
        self.n_steps += 1
        if info.get("intervened"):
            self.n_int += 1
            if self.use_cf and hasattr(self.model, "replay_buffer"):
                rb = self.model.replay_buffer
                obs = self.model._last_obs                                   # s   (before this step is stored)
                next_obs = self.locals["new_obs"]                            # s'  (result of the SAFE action)
                a_safe = np.array([[info["safe_action"]]], dtype=np.float32)
                rb.add(obs, next_obs, a_safe, np.array([info["r_base"]], dtype=np.float32),
                       np.array([False]), [{}])                              # counterfactual transition
        if self.n_steps % self.log_every == 0:
            rate = self.n_int / self.n_steps
            self.history.append((self.num_timesteps, rate))
            print(f"[t={self.num_timesteps}] intervention rate (last {self.log_every}): {rate:.3f}")
            self.n_int, self.n_steps = 0, 0
        return True


def evaluate(policy_fn, env, episodes=20, seed=123):
    rows = []
    for ep in range(episodes):
        obs, _ = env.reset(seed=seed + ep)
        cost = ints = viol = steps = 0
        sc = 0.0
        done = False
        while not done:
            obs, r, te, tr, info = env.step(policy_fn(obs))
            cost += info["cost"]; ints += info["intervened"]; viol += info["violation"]
            sc += info["solar_used"]; steps += 1
            done = te or tr
        rows.append(dict(cost=cost, interventions=ints / steps, violations=viol, solar_used_kwh=sc))
    return pd.DataFrame(rows).mean().to_dict()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--algo", choices=["ppo", "sac"], default="sac")
    p.add_argument("--steps", type=int, default=100_000)
    p.add_argument("--penalty", type=float, default=1.0, help="lambda for intervention penalty")
    p.add_argument("--no-cf", action="store_true", help="disable counterfactual relabelling")
    p.add_argument("--no-shield", action="store_true", help="train/eval WITHOUT a shield (baseline)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default="results")
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)

    data = make_synthetic_data(days=90, seed=a.seed)            # TODO: swap in Member 4's real data
    shield = None if a.no_shield else "default"                 # TODO: swap in Member 1's shield function
    env = Monitor(MicrogridEnv(data, shield=shield, intervention_penalty=a.penalty, seed=a.seed))
    eval_env = MicrogridEnv(data, shield=shield, intervention_penalty=a.penalty, seed=999)

    Algo = SAC if a.algo == "sac" else PPO
    model = Algo("MlpPolicy", env, verbose=0, seed=a.seed,
                 **(dict(learning_rate=3e-4, batch_size=256) if a.algo == "sac" else dict(n_steps=1024)))
    cb = CounterfactualCallback(use_cf=(not a.no_cf) and a.algo == "sac")
    model.learn(a.steps, callback=cb)

    tag = f"{a.algo}{'_nocf' if a.no_cf else ''}{'_noshield' if a.no_shield else ''}"
    model.save(f"{a.out}/{tag}")
    pd.DataFrame(cb.history, columns=["timestep", "intervention_rate"]).to_csv(f"{a.out}/{tag}_interventions.csv", index=False)

    table = {
        tag: evaluate(lambda o: model.predict(o, deterministic=True)[0], eval_env),
        "rule_based": evaluate(rule_based_policy, eval_env),
        "random": evaluate(lambda o: eval_env.action_space.sample(), eval_env),
    }
    df = pd.DataFrame(table).T
    print(df.round(2)); df.to_csv(f"{a.out}/{tag}_eval.csv")


if __name__ == "__main__":
    main()

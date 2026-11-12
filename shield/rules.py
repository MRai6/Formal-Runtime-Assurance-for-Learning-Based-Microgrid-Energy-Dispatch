import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))

from config import SOC_MIN, SOC_MAX, MAX_POWER_KW, BATTERY_KWH, DT_HOURS

# Convention: battery_kw > 0 means DISCHARGING, < 0 means CHARGING


def next_soc(soc, battery_kw):
    """SoC after applying this action for one time step."""
    return soc - (battery_kw * DT_HOURS) / BATTERY_KWH


# RULE 1: SoC must stay between SOC_MIN and SOC_MAX after the action
def rule_soc(soc, battery_kw):
    return SOC_MIN <= next_soc(soc, battery_kw) <= SOC_MAX


# RULE 2: battery power must not exceed the max rate in either direction
def rule_power_limit(battery_kw):
    return abs(battery_kw) <= MAX_POWER_KW


# RULE 3: power balance. Supply (solar + battery discharge + backup) must equal load
def rule_power_balance(solar_kw, load_kw, battery_kw, backup_kw):
    return abs(solar_kw + battery_kw + backup_kw - load_kw) < 1e-6


if __name__ == "__main__":
    print(rule_soc(0.25, 30))      # False: 0.25 - 0.30 = -0.05, below SOC_MIN
    print(rule_soc(0.60, 30))      # True:  0.60 - 0.30 = 0.30
    print(rule_power_limit(70))    # False: 70 > 50
    print(rule_power_limit(-20))   # True:  20 <= 50
    print(rule_power_balance(40, 60, 20, 0))   # True:  40 + 20 + 0 = 60
    print(rule_power_balance(40, 60, 0, 0))    # False: only 40 supplied, 60 needed

EPS = 1e-9   # numerical tolerance

def rule_soc(soc, battery_kw):
    s = next_soc(soc, battery_kw)
    return SOC_MIN - EPS <= s <= SOC_MAX + EPS
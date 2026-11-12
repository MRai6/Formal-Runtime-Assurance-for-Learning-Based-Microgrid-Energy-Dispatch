import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))

from config import SOC_MIN, SOC_MAX, MAX_POWER_KW, BATTERY_KWH, DT_HOURS


def safe_bounds(soc):
    """Lowest and highest battery_kw that keep every rule satisfied."""
    hi = min(MAX_POWER_KW, (soc - SOC_MIN) * BATTERY_KWH / DT_HOURS)   # max discharge
    lo = max(-MAX_POWER_KW, (soc - SOC_MAX) * BATTERY_KWH / DT_HOURS)  # max charge
    return lo, hi


def project(soc, requested_kw):
    """Return the safe action closest to what the AI requested."""
    lo, hi = safe_bounds(soc)
    return min(max(requested_kw, lo), hi)
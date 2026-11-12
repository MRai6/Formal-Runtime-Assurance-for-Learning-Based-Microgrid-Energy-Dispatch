import sys
import os
from pathlib import Path

# Ensure 'shared' path is added
_CURRENT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _CURRENT_DIR.parent
if str(_REPO_ROOT / "shared") not in sys.path:
    sys.path.append(str(_REPO_ROOT / "shared"))

from config import SOC_MIN, SOC_MAX, MAX_POWER_KW, BATTERY_KWH, DT_HOURS


def safe_bounds(soc: float) -> tuple[float, float]:
    """
    Lowest and highest battery_kw that keep every rule satisfied.
    Convention: battery_kw > 0 is discharging, battery_kw < 0 is charging.
    """
    hi = min(MAX_POWER_KW, (soc - SOC_MIN) * BATTERY_KWH / DT_HOURS)   # max discharge
    lo = max(-MAX_POWER_KW, (soc - SOC_MAX) * BATTERY_KWH / DT_HOURS)  # max charge
    return lo, hi


def project(soc: float, requested_kw: float) -> float:
    """Return the safe action closest to what the AI requested."""
    lo, hi = safe_bounds(soc)
    return min(max(requested_kw, lo), hi)


def verify_and_project(soc: float, requested_kw: float) -> tuple[float, bool, str | None]:
    """
    Evaluates requested action against formal bounds, returning:
    (projected_safe_kw, intervention_required, violation_reason)
    """
    lo, hi = safe_bounds(soc)
    safe_kw = min(max(requested_kw, lo), hi)
    is_violation = abs(safe_kw - requested_kw) > 1e-6

    reasons = []
    if abs(requested_kw) > MAX_POWER_KW:
        reasons.append(f"Power limit exceeded (|{requested_kw:.2f}| > {MAX_POWER_KW} kW)")

    next_s = soc - (requested_kw * DT_HOURS) / BATTERY_KWH
    if next_s < SOC_MIN:
        reasons.append(f"SoC underflow ({next_s:.3f} < {SOC_MIN})")
    elif next_s > SOC_MAX:
        reasons.append(f"SoC overflow ({next_s:.3f} > {SOC_MAX})")

    violation_reason = "; ".join(reasons) if reasons else None
    return safe_kw, is_violation, violation_reason

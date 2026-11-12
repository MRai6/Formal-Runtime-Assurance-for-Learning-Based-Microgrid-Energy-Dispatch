"""Physical validation invariants and conservation checks for microgrid_sim."""

from microgrid_sim.utils.exceptions import ConservationOfEnergyError, StateBoundaryError


def assert_energy_conservation(
    p_sources_kw: float,
    p_sinks_kw: float,
    tolerance_kw: float = 1.0e-6,
) -> None:
    """Assert that total microgrid power sources equal total power sinks within tolerance.

    Args:
        p_sources_kw: Sum of generation, discharge, import, and unserved energy [kW].
        p_sinks_kw: Sum of load, charge, export, and curtailment [kW].
        tolerance_kw: Numerical residual tolerance [kW] (default: 1.0e-6 kW / 1 mW).

    Raises:
        ConservationOfEnergyError: If |p_sources - p_sinks| exceeds tolerance.
    """
    residual = abs(p_sources_kw - p_sinks_kw)
    if residual > tolerance_kw:
        raise ConservationOfEnergyError(
            f"Kirchhoff power balance invariant violated: residual {residual:.2e} kW > tolerance {tolerance_kw:.2e} kW",
            details={"sources_kw": p_sources_kw, "sinks_kw": p_sinks_kw, "residual_kw": residual},
        )


def assert_soc_boundaries(
    soc: float,
    min_soc: float = 0.15,
    max_soc: float = 0.90,
    tolerance: float = 1.0e-5,
) -> None:
    """Assert that battery State of Charge remains strictly within admissible physical envelope.

    Args:
        soc: Current battery State of Charge [-].
        min_soc: Lower operational boundary [-].
        max_soc: Upper operational boundary [-].
        tolerance: Numerical floating point tolerance [-].

    Raises:
        StateBoundaryError: If soc is outside [min_soc - tol, max_soc + tol].
    """
    if soc < (min_soc - tolerance) or soc > (max_soc + tolerance):
        raise StateBoundaryError(
            f"Battery SoC {soc:.6f} violated operational envelope [{min_soc:.2f}, {max_soc:.2f}]",
            details={"soc": soc, "min_soc": min_soc, "max_soc": max_soc},
        )

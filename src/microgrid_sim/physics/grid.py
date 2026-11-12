"""Utility Grid and Point of Common Coupling (PCC) model for microgrid_sim.

Governing Principles:
    1. Physical Power Flow at PCC:
       P_net_grid = P_import - P_export
       0.0 <= P_import <= P_import_max (Contractual interconnection limit: 250 kW)
       0.0 <= P_export <= P_export_max (Contractual interconnection limit: 250 kW)
       Mutual Exclusivity: P_import * P_export = 0.0 (Single physical transformer coupling)

    2. Strict Architectural Separation:
       - Physical power flow calculations (P_import, P_export) are purely electrical.
       - Economic billing calculations (TOU rates, demand charges) are evaluated in separate
         isolated accounting functions and do not alter physical conservation equations.

    3. Tariff Schedule:
       Evaluated under PSCo Schedule SG (Secondary General Service), formally designated as a
       Provisional Economic Benchmark Tariff.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import pandas as pd

from microgrid_sim.config.schemas import TariffConfig
from microgrid_sim.utils.exceptions import PhysicsViolationError
from microgrid_sim.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class GridExchangeResult:
    """Physical power and energy exchange at Point of Common Coupling (PCC)."""
    p_import_kw: float
    p_export_kw: float
    energy_imported_kwh: float
    energy_exported_kwh: float
    is_importing: bool
    is_exporting: bool
    limit_encountered: Optional[str]


@dataclass(frozen=True)
class GridBillingResult:
    """Economic financial accounting for grid electricity consumption and exports."""
    rate_buy_usd_per_kwh: float
    rate_sell_usd_per_kwh: float
    import_cost_usd: float
    export_credit_usd: float
    net_cost_usd: float
    is_on_peak: bool
    is_summer: bool


class GridModel:
    """Utility grid interconnection and retail tariff model.

    Maintains strict separation between physical power exchange constraints
    and economic TOU / demand billing accounting.
    """

    def __init__(self, config: TariffConfig) -> None:
        """Initialize the Grid model with validated tariff configuration.

        Args:
            config: Validated TariffConfig schema instance.
        """
        self.config = config
        self.max_import_kw = config.interconnection.max_import_power_kw
        self.max_export_kw = config.interconnection.max_export_power_kw
        self.mutual_exclusivity_required = config.interconnection.mutual_exclusivity_required

        # Economic determinants (Provisional Economic Benchmark)
        self.monthly_customer_charge_usd = config.billing.monthly_customer_charge_usd
        self.demand_charge_usd_per_kw = config.billing.distribution_demand_charge_usd_per_kw
        self.export_multiplier = config.export_compensation.export_credit_multiplier

        # Demand tracking
        self.monthly_peak_demand_kw = 0.0

        logger.debug(
            "Initialized GridModel: Import limit: %.1f kW, Export limit: %.1f kW (Provisional Schedule SG)",
            self.max_import_kw, self.max_export_kw
        )

    def step_physical_exchange(
        self,
        requested_import_kw: float,
        requested_export_kw: float,
        dt_hours: float = 0.25,
    ) -> GridExchangeResult:
        """Execute physical power exchange at the Point of Common Coupling (PCC).

        Enforces contractual import/export limits and mutual exclusivity.

        Args:
            requested_import_kw: Desired power import from grid [kW >= 0].
            requested_export_kw: Desired power export to grid [kW >= 0].
            dt_hours: Step duration in hours [h] (default: 0.25 h).

        Returns:
            GridExchangeResult dataclass.
        """
        if requested_import_kw < 0.0 or requested_export_kw < 0.0:
            raise PhysicsViolationError(
                f"Negative grid exchange request: import={requested_import_kw}, export={requested_export_kw}"
            )

        # Enforce mutual exclusivity
        if self.mutual_exclusivity_required and requested_import_kw > 0.0 and requested_export_kw > 0.0:
            raise PhysicsViolationError(
                f"Simultaneous import ({requested_import_kw} kW) and export ({requested_export_kw} kW) violation"
            )

        limit_encountered = None

        # Clamp import to contractual capacity
        if requested_import_kw > self.max_import_kw:
            p_import = self.max_import_kw
            limit_encountered = "IMPORT_LIMIT"
        else:
            p_import = requested_import_kw

        # Clamp export to contractual capacity
        if requested_export_kw > self.max_export_kw:
            p_export = self.max_export_kw
            limit_encountered = "EXPORT_LIMIT"
        else:
            p_export = requested_export_kw

        # Track monthly peak demand for demand charges
        if p_import > self.monthly_peak_demand_kw:
            self.monthly_peak_demand_kw = p_import

        energy_import_kwh = p_import * dt_hours
        energy_export_kwh = p_export * dt_hours

        return GridExchangeResult(
            p_import_kw=float(p_import),
            p_export_kw=float(p_export),
            energy_imported_kwh=float(energy_import_kwh),
            energy_exported_kwh=float(energy_export_kwh),
            is_importing=bool(p_import > 0.0),
            is_exporting=bool(p_export > 0.0),
            limit_encountered=limit_encountered,
        )

    def get_tou_rates(self, month: int, hour: int, is_weekday: bool) -> Tuple[float, float, bool, bool]:
        """Look up active retail energy purchase and export credit rates.

        Args:
            month: Calendar month (1-12).
            hour: Local hour of day (0-23).
            is_weekday: True if non-holiday Monday through Friday.

        Returns:
            Tuple of (c_buy_usd_per_kwh, c_sell_usd_per_kwh, is_on_peak, is_summer).
        """
        summer_cfg = self.config.tou_rates.summer
        winter_cfg = self.config.tou_rates.winter

        is_summer = month in summer_cfg.months
        cfg = summer_cfg if is_summer else winter_cfg

        is_on_peak = (hour in cfg.on_peak_hours) and (is_weekday or not cfg.on_peak_weekdays_only)

        if is_on_peak:
            c_buy = cfg.rate_on_peak_usd_per_kwh
        else:
            c_buy = cfg.rate_off_peak_usd_per_kwh

        c_sell = c_buy * self.export_multiplier
        return float(c_buy), float(c_sell), is_on_peak, is_summer

    def calculate_financial_cost(
        self,
        energy_imported_kwh: float,
        energy_exported_kwh: float,
        month: int,
        hour: int,
        is_weekday: bool,
    ) -> GridBillingResult:
        """Compute economic energy billing and export credit independently of physical power flow.

        Args:
            energy_imported_kwh: Electrical energy imported over step [kWh].
            energy_exported_kwh: Electrical energy exported over step [kWh].
            month: Calendar month (1-12).
            hour: Local hour of day (0-23).
            is_weekday: True if weekday.

        Returns:
            GridBillingResult dataclass.
        """
        c_buy, c_sell, is_on_peak, is_summer = self.get_tou_rates(month, hour, is_weekday)

        import_cost = energy_imported_kwh * c_buy
        export_credit = energy_exported_kwh * c_sell
        net_cost = import_cost - export_credit

        return GridBillingResult(
            rate_buy_usd_per_kwh=c_buy,
            rate_sell_usd_per_kwh=c_sell,
            import_cost_usd=float(import_cost),
            export_credit_usd=float(export_credit),
            net_cost_usd=float(net_cost),
            is_on_peak=is_on_peak,
            is_summer=is_summer,
        )

    def reset_monthly_demand(self) -> float:
        """Reset and return the monthly peak demand for demand-charge billing."""
        peak = self.monthly_peak_demand_kw
        self.monthly_peak_demand_kw = 0.0
        return float(peak)

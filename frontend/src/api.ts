/**
 * API client connecting React frontend to the FastAPI microgrid assurance backend.
 */

const API_BASE = "http://localhost:8000/api";

export interface HealthResponse {
  status: string;
  timestamp: string;
  database: {
    connected: boolean;
    engine: string;
  };
  system_spec: {
    battery_capacity_kwh: number;
    max_power_kw: number;
    safe_soc_range: [number, number];
    control_interval_hours: number;
    latency_deadline_ms: number;
  };
}

export interface OverviewResponse {
  kpis: {
    current_solar_kw: number;
    current_load_kw: number;
    current_soc_pct: number;
    current_battery_kw: number;
    current_grid_import_kw: number;
    current_tariff_inr: number;
    annual_unshielded_violations: number;
    annual_shielded_violations: number;
    annual_unshielded_cost_inr: number;
    annual_shielded_cost_inr: number;
    annual_cost_savings_inr: number;
    annual_cost_savings_pct: number;
    shield_mean_latency_ms: number;
    shield_max_latency_ms: number;
  };
  timeseries_24h: Array<{
    step: number;
    timestamp: string;
    solar_kw: number;
    load_kw: number;
    battery_soc: number;
    battery_kw: number;
    grid_import_kw: number;
    grid_export_kw: number;
    price_inr: number;
    power_balance_residual: number;
  }>;
}

export interface EnergyFlowResponse {
  timestamp: string;
  solar_pv: {
    power_kw: number;
    status: string;
  };
  load_demand: {
    power_kw: number;
    status: string;
  };
  battery: {
    power_kw: number;
    soc_pct: number;
    mode: 'charging' | 'discharging' | 'idle';
    safe_discharge_limit_kw: number;
    safe_charge_limit_kw: number;
  };
  grid: {
    import_kw: number;
    export_kw: number;
    mode: 'importing' | 'exporting' | 'balanced';
    tariff_inr_kwh: number;
  };
  power_balance: {
    total_generation_kw: number;
    total_consumption_kw: number;
    residual_kw: number;
    is_balanced: boolean;
  };
}

export interface BatterySolarResponse {
  specifications: {
    nominal_capacity_kwh: number;
    max_charge_kw: number;
    max_discharge_kw: number;
    min_soc_pct: number;
    max_soc_pct: number;
    roundtrip_efficiency_pct: number;
    thermal_domain: string;
  };
  timeseries: Array<{
    hour: number;
    timestamp: string;
    solar_kw: number;
    load_kw: number;
    battery_soc_pct: number;
    battery_power_kw: number;
    soc_min_bound: number;
    soc_max_bound: number;
  }>;
}

export interface AIDispatchResponse {
  model_architecture: {
    algorithm: string;
    observation_space: string[];
    action_space: string;
    reward_formulation: string;
    safety_framework: string;
  };
  full_year_comparison: Array<{
    Controller: string;
    "Violation hours (no shield → shield)": string;
    "Cost with shield": string;
    "Saving vs rule-based": string;
    "Saving vs no battery": string;
    "Shield interventions": string;
  }>;
  seasonal_heldout_blocks: Array<{
    Method: string;
    "Cost (INR)": string | number;
    "Saving vs rule-based": string;
    "Interventions (rate)": string | number;
    "Solar used (kWh)": number;
  }>;
}

export interface ShieldVerifyResponse {
  status: string;
  current_soc_pct: number;
  proposed_action_kw: number;
  safe_executed_action_kw: number;
  shield_intervened: boolean;
  admissible_safe_interval: [number, number];
  violation_reasons: string[];
  next_soc_with_shield_pct: number;
  next_soc_without_shield_pct: number;
  computation_latency_us: number;
  computation_latency_ms: number;
}

export interface BenchmarkResponse {
  multi_seed_benchmarks: Array<{
    seed: number;
    unshielded_violations: number;
    shielded_violations: number;
    unshielded_cost_inr: number;
    shielded_cost_inr: number;
    latency_mean_ms: number;
    latency_p99_ms: number;
    latency_max_ms: number;
  }>;
  first_week_trajectory: Array<{
    hour: number;
    timestamp: string;
    unshielded_soc: number;
    shielded_soc: number;
    proposed_kw: number;
    executed_kw: number;
    min_limit: number;
    max_limit: number;
  }>;
  summary: {
    unshielded_mean_violations: number;
    shielded_mean_violations: number;
    violations_reduction_pct: number;
    mean_cost_savings_inr: number;
    mean_latency_ms: number;
    max_latency_ms: number;
  };
}

export interface AuditLogRecord {
  time: string;
  current_soc: number;
  rl_proposed_action: string;
  shield_intervention_flag: boolean;
  shield_fallback_action: string | null;
  executed_action: string;
  computation_latency_ms: number;
  violation_reason: string | null;
}

export interface AuditLogResponse {
  source: string;
  total_records: number;
  page: number;
  page_size: number;
  total_pages: number;
  records: AuditLogRecord[];
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export async function fetchOverview(): Promise<OverviewResponse> {
  const res = await fetch(`${API_BASE}/overview`);
  if (!res.ok) throw new Error("Failed to load overview");
  return res.json();
}

export async function fetchEnergyFlow(): Promise<EnergyFlowResponse> {
  const res = await fetch(`${API_BASE}/energy-flow`);
  if (!res.ok) throw new Error("Failed to load energy flow");
  return res.json();
}

export async function fetchBatterySolar(windowDays: number = 7): Promise<BatterySolarResponse> {
  const res = await fetch(`${API_BASE}/battery-solar?window_days=${windowDays}`);
  if (!res.ok) throw new Error("Failed to load battery/solar data");
  return res.json();
}

export async function fetchAIDispatch(): Promise<AIDispatchResponse> {
  const res = await fetch(`${API_BASE}/ai-dispatch`);
  if (!res.ok) throw new Error("Failed to load AI dispatch results");
  return res.json();
}

export async function verifyShieldAction(params: {
  current_soc: number;
  proposed_kw: number;
  battery_kwh?: number;
  max_power_kw?: number;
  soc_min?: number;
  soc_max?: number;
}): Promise<ShieldVerifyResponse> {
  const res = await fetch(`${API_BASE}/shield/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error("Shield verification request failed");
  return res.json();
}

export async function fetchBenchmark(): Promise<BenchmarkResponse> {
  const res = await fetch(`${API_BASE}/simulation/benchmark`);
  if (!res.ok) throw new Error("Failed to load benchmark results");
  return res.json();
}

export async function runCustomSimulation(params: {
  horizon_steps: number;
  battery_kwh: number;
  max_power_kw: number;
  soc_min: number;
  soc_max: number;
  initial_soc: number;
  policy_type: string;
  seed: number;
}) {
  const res = await fetch(`${API_BASE}/simulation/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error("Simulation execution failed");
  return res.json();
}

export async function fetchAuditLogs(
  page: number = 1,
  pageSize: number = 25,
  interventionsOnly: boolean = false,
  search?: string
): Promise<AuditLogResponse> {
  let url = `${API_BASE}/telemetry/audit-logs?page=${page}&page_size=${pageSize}&interventions_only=${interventionsOnly}`;
  if (search) {
    url += `&search=${encodeURIComponent(search)}`;
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to load audit logs");
  return res.json();
}

export async function fetchConfigs(): Promise<Record<string, any>> {
  const res = await fetch(`${API_BASE}/configs`);
  if (!res.ok) throw new Error("Failed to load configurations");
  return res.json();
}

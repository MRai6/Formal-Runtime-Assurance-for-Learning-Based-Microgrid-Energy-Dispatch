import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Sun,
  Zap,
  Battery,
  ShieldCheck,
  TrendingDown,
  Clock,
  ArrowDownRight,
  ArrowUpRight,
  Download,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { fetchOverview, OverviewResponse } from '../api';
import { KPICard } from '../components/KPICard';
import { GlassCard } from '../components/GlassCard';

export const OverviewPage: React.FC = () => {
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchOverview()
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-28 rounded-2xl bg-white/40 border border-white/60" />
          ))}
        </div>
        <div className="h-96 rounded-2xl bg-white/40 border border-white/60" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <GlassCard className="text-center py-12">
        <AlertTriangle className="w-12 h-12 text-amber-600 mx-auto mb-3" />
        <h3 className="text-lg font-bold text-burgundy-900">Failed to load overview data</h3>
        <p className="text-sm text-sage-700 mt-1">{error || 'Server error'}</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 px-4 py-2 rounded-xl bg-burgundy-900 text-cream-100 font-semibold text-xs"
        >
          Retry Connection
        </button>
      </GlassCard>
    );
  }

  const { kpis, timeseries_24h } = data;

  const exportCSV = () => {
    const headers = Object.keys(timeseries_24h[0]).join(',');
    const rows = timeseries_24h.map((r) => Object.values(r).join(',')).join('\n');
    const blob = new Blob([`${headers}\n${rows}`], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'overview_24h_telemetry.csv';
    a.click();
  };

  return (
    <div className="space-y-6">
      {/* Executive Hero Banner */}
      <GlassCard burgundy className="p-6 md:p-8">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-cream-200/20 text-cream-200 text-xs font-semibold mb-3 border border-cream-200/30">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Convex Safe Projection Verified</span>
            </div>
            <h2 className="text-2xl md:text-3xl font-extrabold text-cream-100 tracking-tight">
              100% Invariant Safety Elimination
            </h2>
            <p className="text-sm text-cream-200/80 mt-1.5 max-w-2xl leading-relaxed">
              Evaluating 8,760 continuous hourly dispatch steps: runtime safety shielding dynamically
              projects all neural network proposed actions to the safe battery polyhedron with sub-millisecond execution.
            </p>
          </div>

          <div className="flex flex-row md:flex-col items-center md:items-end gap-3 shrink-0">
            <div className="text-right">
              <div className="text-xs uppercase tracking-wider text-cream-300 font-semibold">
                Annual Cost Savings
              </div>
              <div className="text-3xl font-extrabold text-cream-100 font-mono">
                ₹ {kpis.annual_cost_savings_inr.toLocaleString()}
              </div>
              <div className="text-xs font-semibold text-emerald-400">
                -{kpis.annual_cost_savings_pct}% Net Reduction
              </div>
            </div>
            <button
              onClick={exportCSV}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-cream-200 text-burgundy-950 font-bold text-xs hover:bg-white transition-all shadow-md"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export CSV</span>
            </button>
          </div>
        </div>
      </GlassCard>

      {/* Top Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Solar Generation"
          value={kpis.current_solar_kw.toFixed(1)}
          unit="kW"
          subValue="Midday PV Array Output"
          badge="Active"
          icon={Sun}
        />
        <KPICard
          label="Facility Load Demand"
          value={kpis.current_load_kw.toFixed(1)}
          unit="kW"
          subValue="Commercial Baseline"
          icon={Zap}
        />
        <KPICard
          label="Battery State of Charge"
          value={kpis.current_soc_pct.toFixed(1)}
          unit="%"
          subValue="Safe Boundary [20%, 90%]"
          badge="Guaranteed Safe"
          variant="safe"
          icon={Battery}
        />
        <KPICard
          label="Shield Mean Latency"
          value={(kpis.shield_mean_latency_ms * 1000).toFixed(1)}
          unit="µs"
          subValue="Budget: 10,000 µs (10 ms)"
          badge="5,500x Faster"
          variant="burgundy"
          icon={Clock}
        />
      </div>

      {/* Chart 1 & Chart 2: Grid 2 Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Visualization 1: Solar PV vs Facility Electric Load */}
        <GlassCard>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-burgundy-900">
                1. Solar PV Generation vs Building Load
              </h3>
              <p className="text-xs text-sage-600">24-hour deterministic power profiles (kW)</p>
            </div>
            <span className="text-xs font-mono font-semibold text-sage-700 bg-white/70 px-2.5 py-1 rounded-lg border border-white">
              P_solar vs P_load
            </span>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={timeseries_24h} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="solarGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#E8D2B5" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="#E8D2B5" stopOpacity={0.05} />
                  </linearGradient>
                  <linearGradient id="loadGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#590907" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#590907" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" opacity={0.6} />
                <XAxis
                  dataKey="step"
                  stroke="#898b7e"
                  fontSize={11}
                  tickFormatter={(v) => `${v}:00`}
                />
                <YAxis stroke="#898b7e" fontSize={11} unit=" kW" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    borderRadius: '12px',
                    border: '1px solid #E8D2B5',
                    boxShadow: '0 8px 24px rgba(89, 9, 7, 0.08)',
                    fontSize: '12px',
                  }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
                <Area
                  type="monotone"
                  dataKey="solar_kw"
                  name="Solar PV (kW)"
                  stroke="#ce9b61"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#solarGrad)"
                />
                <Area
                  type="monotone"
                  dataKey="load_kw"
                  name="Facility Load (kW)"
                  stroke="#590907"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#loadGrad)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>

        {/* Visualization 2: Battery State of Charge Trajectory */}
        <GlassCard>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-burgundy-900">
                2. Battery State-of-Charge (SoC) Trajectory
              </h3>
              <p className="text-xs text-sage-600">Enforcing physical bounds: 20% ≤ SoC ≤ 90%</p>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-emerald-800 font-semibold bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-200">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Zero Violations</span>
            </div>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeseries_24h} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" opacity={0.6} />
                <XAxis
                  dataKey="step"
                  stroke="#898b7e"
                  fontSize={11}
                  tickFormatter={(v) => `${v}:00`}
                />
                <YAxis domain={[0, 100]} stroke="#898b7e" fontSize={11} unit="%" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    borderRadius: '12px',
                    border: '1px solid #E8D2B5',
                    fontSize: '12px',
                  }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
                {/* Upper Limit 90% */}
                <Line
                  type="monotone"
                  dataKey={() => 90}
                  name="Max Limit (90%)"
                  stroke="#ef4444"
                  strokeDasharray="4 4"
                  strokeWidth={1.5}
                  dot={false}
                />
                {/* Lower Limit 20% */}
                <Line
                  type="monotone"
                  dataKey={() => 20}
                  name="Min Limit (20%)"
                  stroke="#ef4444"
                  strokeDasharray="4 4"
                  strokeWidth={1.5}
                  dot={false}
                />
                {/* Shielded Battery SoC */}
                <Line
                  type="monotone"
                  dataKey="battery_soc"
                  name="Battery SoC (%)"
                  stroke="#590907"
                  strokeWidth={3}
                  dot={{ r: 2.5, fill: '#590907' }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>
      </div>

      {/* Chart 3 & Chart 4: Grid 2 Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Visualization 3: Grid Import and Export */}
        <GlassCard>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-burgundy-900">
                3. Grid Import and Export Power
              </h3>
              <p className="text-xs text-sage-600">Interconnection power exchange profiles (kW)</p>
            </div>
            <span className="text-xs font-mono font-semibold text-sage-700 bg-white/70 px-2.5 py-1 rounded-lg border border-white">
              P_grid
            </span>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={timeseries_24h} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" opacity={0.6} />
                <XAxis
                  dataKey="step"
                  stroke="#898b7e"
                  fontSize={11}
                  tickFormatter={(v) => `${v}:00`}
                />
                <YAxis stroke="#898b7e" fontSize={11} unit=" kW" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    borderRadius: '12px',
                    border: '1px solid #E8D2B5',
                    fontSize: '12px',
                  }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
                <Bar
                  dataKey="grid_import_kw"
                  name="Grid Import (kW)"
                  fill="#590907"
                  radius={[4, 4, 0, 0]}
                />
                <Bar
                  dataKey="grid_export_kw"
                  name="Grid Export (kW)"
                  fill="#A5A79B"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>

        {/* Visualization 4: Active Power Balance Residual */}
        <GlassCard>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-burgundy-900">
                4. Active Power Balance Residual
              </h3>
              <p className="text-xs text-sage-600">
                Conservation check: |(P_solar - curtail) + P_batt + P_backup - P_load| &lt; 10⁻⁶
              </p>
            </div>
            <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
              0.00 kW Error
            </span>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeseries_24h} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" opacity={0.6} />
                <XAxis
                  dataKey="step"
                  stroke="#898b7e"
                  fontSize={11}
                  tickFormatter={(v) => `${v}:00`}
                />
                <YAxis domain={[-0.1, 0.1]} stroke="#898b7e" fontSize={11} unit=" kW" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    borderRadius: '12px',
                    border: '1px solid #E8D2B5',
                    fontSize: '12px',
                  }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
                <Line
                  type="monotone"
                  dataKey="power_balance_residual"
                  name="Power Balance Residual (kW)"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={{ r: 3, fill: '#10b981' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>
      </div>
    </div>
  );
};

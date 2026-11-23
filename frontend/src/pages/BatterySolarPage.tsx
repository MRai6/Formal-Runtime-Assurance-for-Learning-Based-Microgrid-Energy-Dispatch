import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Battery,
  Sun,
  Shield,
  Zap,
  Activity,
  Layers,
  CheckCircle,
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
import { fetchBatterySolar, BatterySolarResponse } from '../api';
import { GlassCard } from '../components/GlassCard';
import { KPICard } from '../components/KPICard';

export const BatterySolarPage: React.FC = () => {
  const [data, setData] = useState<BatterySolarResponse | null>(null);
  const [windowDays, setWindowDays] = useState(7);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchBatterySolar(windowDays)
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [windowDays]);

  if (loading || !data) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-28 rounded-2xl bg-white/40" />
        <div className="h-96 rounded-2xl bg-white/40" />
      </div>
    );
  }

  const { specifications, timeseries } = data;
  const currentPoint = timeseries[timeseries.length - 1] || timeseries[0];

  return (
    <div className="space-y-6">
      {/* Battery Gauge & Specs Banner */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Visual Circular / Horizontal SoC Gauge */}
        <GlassCard className="flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-bold text-burgundy-900 uppercase">
                Battery State of Charge Gauge
              </span>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200">
                Safe Polyhedron
              </span>
            </div>

            <div className="relative my-4 flex flex-col items-center justify-center">
              <div className="text-4xl font-extrabold text-burgundy-900 font-mono">
                {currentPoint.battery_soc_pct.toFixed(1)}%
              </div>
              <div className="text-xs text-sage-600 mt-1">Operational State of Charge</div>

              {/* Progress Bar with Invariant Markers */}
              <div className="w-full mt-6 relative">
                <div className="h-4 w-full bg-sage-200/80 rounded-full overflow-hidden p-0.5 border border-sage-300">
                  <div
                    className="h-full bg-burgundy-900 rounded-full transition-all duration-500"
                    style={{ width: `${currentPoint.battery_soc_pct}%` }}
                  />
                </div>
                {/* 20% Min Marker */}
                <div className="absolute top-[-18px] left-[20%] -translate-x-1/2 text-[10px] font-mono font-bold text-red-600">
                  20% Min
                </div>
                {/* 90% Max Marker */}
                <div className="absolute top-[-18px] left-[90%] -translate-x-1/2 text-[10px] font-mono font-bold text-red-600">
                  90% Max
                </div>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-white/60 text-xs text-sage-700 flex justify-between">
            <span>Usable Capacity: 70 kWh (70%)</span>
            <span>Total: {specifications.nominal_capacity_kwh} kWh</span>
          </div>
        </GlassCard>

        {/* Battery Technical Limits Card */}
        <GlassCard className="lg:col-span-2">
          <h3 className="text-base font-bold text-burgundy-900 mb-4 flex items-center gap-2">
            <Shield className="w-4 h-4 text-burgundy-900" />
            <span>Battery Energy Storage System (BESS) Engineering Ratings</span>
          </h3>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="p-3 rounded-xl bg-white/60 border border-white">
              <div className="text-[11px] uppercase text-sage-600 font-semibold">Nominal Energy</div>
              <div className="text-lg font-bold text-burgundy-900 font-mono">
                {specifications.nominal_capacity_kwh} kWh
              </div>
              <div className="text-[10px] text-sage-600">Lithium-ion LiFePO4</div>
            </div>

            <div className="p-3 rounded-xl bg-white/60 border border-white">
              <div className="text-[11px] uppercase text-sage-600 font-semibold">Max Power Rate</div>
              <div className="text-lg font-bold text-burgundy-900 font-mono">
                ±{specifications.max_charge_kw} kW
              </div>
              <div className="text-[10px] text-sage-600">0.50 C-rate Continuous</div>
            </div>

            <div className="p-3 rounded-xl bg-white/60 border border-white">
              <div className="text-[11px] uppercase text-sage-600 font-semibold">Safe Operational SoC</div>
              <div className="text-lg font-bold text-burgundy-900 font-mono">
                {specifications.min_soc_pct}% – {specifications.max_soc_pct}%
              </div>
              <div className="text-[10px] text-emerald-700 font-medium">Degradation Protected</div>
            </div>

            <div className="p-3 rounded-xl bg-white/60 border border-white">
              <div className="text-[11px] uppercase text-sage-600 font-semibold">Round-Trip Efficiency</div>
              <div className="text-lg font-bold text-burgundy-900 font-mono">
                {specifications.roundtrip_efficiency_pct}%
              </div>
              <div className="text-[10px] text-sage-600">η_ch × η_dis = 90.25%</div>
            </div>

            <div className="p-3 rounded-xl bg-white/60 border border-white">
              <div className="text-[11px] uppercase text-sage-600 font-semibold">Thermal Domain</div>
              <div className="text-lg font-bold text-burgundy-900 font-mono">
                {specifications.thermal_domain}
              </div>
              <div className="text-[10px] text-sage-600">Isothermal Container</div>
            </div>

            <div className="p-3 rounded-xl bg-white/60 border border-white">
              <div className="text-[11px] uppercase text-sage-600 font-semibold">Formal Shield Invariant</div>
              <div className="text-lg font-bold text-emerald-700 font-mono">
                Active
              </div>
              <div className="text-[10px] text-sage-600">Closed-form 1D Projection</div>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Historical SoC Trajectory Window Selector & Chart */}
      <GlassCard>
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-4">
          <div>
            <h3 className="text-base font-bold text-burgundy-900">
              Historical Battery SoC Trajectory
            </h3>
            <p className="text-xs text-sage-600">
              Multi-day trajectory tracking state of charge compliance within [20%, 90%]
            </p>
          </div>

          <div className="flex items-center gap-1.5 p-1 rounded-xl bg-white/70 border border-white">
            {[1, 7, 14, 30].map((days) => (
              <button
                key={days}
                onClick={() => setWindowDays(days)}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                  windowDays === days
                    ? 'bg-burgundy-900 text-cream-100 shadow-sm'
                    : 'text-sage-700 hover:text-burgundy-900'
                }`}
              >
                {days === 1 ? '24 Hours' : `${days} Days`}
              </button>
            ))}
          </div>
        </div>

        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={timeseries} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" opacity={0.6} />
              <XAxis dataKey="hour" stroke="#898b7e" fontSize={11} tickFormatter={(v) => `H${v}`} />
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
              <Line
                type="monotone"
                dataKey="soc_max_bound"
                name="Max Bound (90%)"
                stroke="#ef4444"
                strokeDasharray="4 4"
                strokeWidth={1.5}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="soc_min_bound"
                name="Min Bound (20%)"
                stroke="#ef4444"
                strokeDasharray="4 4"
                strokeWidth={1.5}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="battery_soc_pct"
                name="Battery SoC (%)"
                stroke="#590907"
                strokeWidth={2.5}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </GlassCard>

      {/* Solar Generation vs Facility Load Demand Comparison */}
      <GlassCard>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-burgundy-900">
              Solar Photovoltaic Generation vs Facility Load
            </h3>
            <p className="text-xs text-sage-600">
              Solar irradiance absorption and peak load coincidence (kW)
            </p>
          </div>
        </div>

        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={timeseries} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="solarArea" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#E8D2B5" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="#E8D2B5" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" opacity={0.6} />
              <XAxis dataKey="hour" stroke="#898b7e" fontSize={11} tickFormatter={(v) => `H${v}`} />
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
              <Area
                type="monotone"
                dataKey="solar_kw"
                name="Solar Output (kW)"
                stroke="#ce9b61"
                strokeWidth={2}
                fill="url(#solarArea)"
              />
              <Line
                type="monotone"
                dataKey="load_kw"
                name="Building Load (kW)"
                stroke="#590907"
                strokeWidth={2}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </GlassCard>
    </div>
  );
};

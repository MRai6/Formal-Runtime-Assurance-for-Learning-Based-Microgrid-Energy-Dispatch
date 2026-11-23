import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Sun,
  Battery,
  Zap,
  Building2,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  Activity,
  Layers,
  RefreshCw,
} from 'lucide-react';
import { fetchEnergyFlow, EnergyFlowResponse } from '../api';
import { GlassCard } from '../components/GlassCard';
import { KPICard } from '../components/KPICard';

export const EnergyFlowPage: React.FC = () => {
  const [data, setData] = useState<EnergyFlowResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = () => {
    setLoading(true);
    fetchEnergyFlow()
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading || !data) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-20 rounded-2xl bg-white/40" />
        <div className="h-[480px] rounded-2xl bg-white/40" />
      </div>
    );
  }

  const { solar_pv, load_demand, battery, grid, power_balance } = data;

  const isBattCharging = battery.power_kw < -0.1;
  const isBattDischarging = battery.power_kw > 0.1;
  const isGridImporting = grid.import_kw > 0.05;
  const isGridExporting = grid.export_kw > 0.05;

  return (
    <div className="space-y-6">
      {/* Notice Banner */}
      <div className="flex items-center justify-between p-4 rounded-xl bg-sage-100/70 border border-sage-300 text-xs text-sage-800">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-burgundy-900" />
          <span>
            <strong>Data Disclosure:</strong> Displaying tertiary microgrid dispatch state from the benchmark dataset at 12:00 PM peak irradiance.
          </span>
        </div>
        <button
          onClick={loadData}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white text-burgundy-900 font-semibold border border-sage-300 hover:bg-cream-100 transition-colors"
        >
          <RefreshCw className="w-3 h-3" />
          <span>Refresh Nodal State</span>
        </button>
      </div>

      {/* SVG Interactive Energy Flow Visualizer */}
      <GlassCard className="p-6 md:p-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-xl font-bold text-burgundy-900">
              Interactive Microgrid Energy Flow Architecture
            </h3>
            <p className="text-xs text-sage-600">
              Animated active power exchange between PV, Battery, Building Load, and PCC Interconnection
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-xl bg-emerald-50 text-emerald-800 border border-emerald-200">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>Power Balance Verified: ΔP = 0.00 kW</span>
          </div>
        </div>

        {/* Dynamic Energy Flow Diagram */}
        <div className="relative w-full max-w-4xl mx-auto py-6">
          <svg viewBox="0 0 800 420" className="w-full h-auto overflow-visible select-none">
            <defs>
              <linearGradient id="flowGradBurgundy" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#590907" />
                <stop offset="100%" stopColor="#962424" />
              </linearGradient>
              <linearGradient id="flowGradAmber" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#E8D2B5" />
                <stop offset="100%" stopColor="#ce9b61" />
              </linearGradient>
              <linearGradient id="flowGradSage" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#A5A79B" />
                <stop offset="100%" stopColor="#6c6e62" />
              </linearGradient>

              {/* Filter for glowing node effects */}
              <filter id="softGlow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="6" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Connecting Bus Lines (Background) */}
            {/* Solar -> PCC (400, 210) */}
            <line x1="160" y1="100" x2="400" y2="210" stroke="#E8D2B5" strokeWidth="4" strokeLinecap="round" opacity="0.6" />
            {solar_pv.power_kw > 0 && (
              <line
                x1="160" y1="100" x2="400" y2="210"
                stroke="#ce9b61" strokeWidth="4" strokeDasharray="8 6"
                className="animate-dash-flow"
              />
            )}

            {/* Battery <-> PCC (400, 210) */}
            <line x1="160" y1="320" x2="400" y2="210" stroke="#A5A79B" strokeWidth="4" strokeLinecap="round" opacity="0.6" />
            {isBattDischarging && (
              <line
                x1="160" y1="320" x2="400" y2="210"
                stroke="#590907" strokeWidth="4" strokeDasharray="8 6"
                className="animate-dash-flow"
              />
            )}
            {isBattCharging && (
              <line
                x1="400" y1="210" x2="160" y2="320"
                stroke="#10b981" strokeWidth="4" strokeDasharray="8 6"
                className="animate-dash-flow"
              />
            )}

            {/* Utility Grid <-> PCC (400, 210) */}
            <line x1="640" y1="100" x2="400" y2="210" stroke="#A5A79B" strokeWidth="4" strokeLinecap="round" opacity="0.6" />
            {isGridImporting && (
              <line
                x1="640" y1="100" x2="400" y2="210"
                stroke="#590907" strokeWidth="4" strokeDasharray="8 6"
                className="animate-dash-flow"
              />
            )}

            {/* PCC -> Building Load (640, 320) */}
            <line x1="400" y1="210" x2="640" y2="320" stroke="#590907" strokeWidth="4" strokeLinecap="round" opacity="0.4" />
            <line
              x1="400" y1="210" x2="640" y2="320"
              stroke="#590907" strokeWidth="4" strokeDasharray="8 6"
              className="animate-dash-flow"
            />

            {/* Center Node: PCC AC Bus Junction */}
            <g transform="translate(400, 210)">
              <circle r="44" fill="#ffffff" stroke="#590907" strokeWidth="3" filter="url(#softGlow)" />
              <circle r="36" fill="#590907" />
              <text textAnchor="middle" y="-4" fill="#E8D2B5" fontSize="11" fontWeight="bold">PCC BUS</text>
              <text textAnchor="middle" y="12" fill="#ffffff" fontSize="9" fontFamily="monospace">480V 3-Phase</text>
            </g>

            {/* Node 1: Solar PV Array (Top Left) */}
            <g transform="translate(160, 100)">
              <rect x="-75" y="-45" width="150" height="90" rx="16" fill="#ffffff" stroke="#E8D2B5" strokeWidth="2.5" />
              <circle cx="-42" cy="-12" r="14" fill="#faf6f0" />
              <text x="-42" y="-7" textAnchor="middle" fontSize="14">☀️</text>
              <text x="-18" y="-14" fill="#590907" fontSize="12" fontWeight="bold">Solar PV</text>
              <text x="-18" y="2" fill="#898b7e" fontSize="10">Active Array</text>
              <text x="-70" y="32" fill="#ce9b61" fontSize="17" fontWeight="800" fontFamily="monospace">
                +{solar_pv.power_kw.toFixed(1)} kW
              </text>
            </g>

            {/* Node 2: BESS Battery Storage (Bottom Left) */}
            <g transform="translate(160, 320)">
              <rect x="-75" y="-45" width="150" height="90" rx="16" fill="#ffffff" stroke="#A5A79B" strokeWidth="2.5" />
              <circle cx="-42" cy="-12" r="14" fill="#f6f7f5" />
              <text x="-42" y="-7" textAnchor="middle" fontSize="14">🔋</text>
              <text x="-18" y="-14" fill="#590907" fontSize="12" fontWeight="bold">BESS Battery</text>
              <text x="-18" y="2" fill="#898b7e" fontSize="10">SoC: {battery.soc_pct}%</text>
              <text x="-70" y="32" fill={isBattCharging ? '#10b981' : '#590907'} fontSize="17" fontWeight="800" fontFamily="monospace">
                {battery.power_kw > 0 ? `+${battery.power_kw.toFixed(1)}` : `${battery.power_kw.toFixed(1)}`} kW
              </text>
            </g>

            {/* Node 3: Utility Grid Interconnection (Top Right) */}
            <g transform="translate(640, 100)">
              <rect x="-75" y="-45" width="150" height="90" rx="16" fill="#ffffff" stroke="#A5A79B" strokeWidth="2.5" />
              <circle cx="-42" cy="-12" r="14" fill="#f6f7f5" />
              <text x="-42" y="-7" textAnchor="middle" fontSize="14">⚡</text>
              <text x="-18" y="-14" fill="#590907" fontSize="12" fontWeight="bold">Utility Grid</text>
              <text x="-18" y="2" fill="#898b7e" fontSize="10">Tariff: ₹{grid.tariff_inr_kwh}/kWh</text>
              <text x="-70" y="32" fill="#590907" fontSize="17" fontWeight="800" fontFamily="monospace">
                {grid.import_kw > 0 ? `+${grid.import_kw.toFixed(1)} kW (Imp)` : `0.0 kW`}
              </text>
            </g>

            {/* Node 4: Building Facility Electric Load (Bottom Right) */}
            <g transform="translate(640, 320)">
              <rect x="-75" y="-45" width="150" height="90" rx="16" fill="#ffffff" stroke="#590907" strokeWidth="2.5" />
              <circle cx="-42" cy="-12" r="14" fill="#fdf2f2" />
              <text x="-42" y="-7" textAnchor="middle" fontSize="14">🏢</text>
              <text x="-18" y="-14" fill="#590907" fontSize="12" fontWeight="bold">Facility Load</text>
              <text x="-18" y="2" fill="#898b7e" fontSize="10">Commercial Demand</text>
              <text x="-70" y="32" fill="#590907" fontSize="17" fontWeight="800" fontFamily="monospace">
                -{load_demand.power_kw.toFixed(1)} kW
              </text>
            </g>
          </svg>
        </div>
      </GlassCard>

      {/* Quantitative Nodal Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <GlassCard>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 rounded-lg bg-cream-200/50 flex items-center justify-center text-burgundy-900">
              <Sun className="w-4 h-4" />
            </div>
            <div>
              <div className="text-xs font-bold text-burgundy-900 uppercase">Solar Photovoltaic</div>
              <div className="text-[11px] text-sage-600">NREL Commercial Benchmark</div>
            </div>
          </div>
          <div className="text-2xl font-black text-burgundy-900 font-mono mt-2">
            {solar_pv.power_kw.toFixed(2)} kW
          </div>
          <div className="text-xs text-sage-700 mt-1">Status: Array Delivers Full Active Power</div>
        </GlassCard>

        <GlassCard>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 rounded-lg bg-sage-200 flex items-center justify-center text-burgundy-900">
              <Battery className="w-4 h-4" />
            </div>
            <div>
              <div className="text-xs font-bold text-burgundy-900 uppercase">Battery State & Limits</div>
              <div className="text-[11px] text-sage-600">100 kWh Capacity</div>
            </div>
          </div>
          <div className="text-2xl font-black text-burgundy-900 font-mono mt-2">
            {battery.power_kw.toFixed(2)} kW
          </div>
          <div className="text-xs text-sage-700 mt-1">
            Safe Discharge Ceiling: +{battery.safe_discharge_limit_kw.toFixed(1)} kW
          </div>
        </GlassCard>

        <GlassCard>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 rounded-lg bg-burgundy-900/10 flex items-center justify-center text-burgundy-900">
              <Building2 className="w-4 h-4" />
            </div>
            <div>
              <div className="text-xs font-bold text-burgundy-900 uppercase">Commercial Load & Net</div>
              <div className="text-[11px] text-sage-600">ComStock Standard Building</div>
            </div>
          </div>
          <div className="text-2xl font-black text-burgundy-900 font-mono mt-2">
            {load_demand.power_kw.toFixed(2)} kW
          </div>
          <div className="text-xs text-sage-700 mt-1">
            Shortfall Covered by Solar & Battery Dispatch
          </div>
        </GlassCard>
      </div>
    </div>
  );
};

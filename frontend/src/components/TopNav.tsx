import React from 'react';
import { Menu, Database, Shield, Clock, Bell, Sparkles } from 'lucide-react';
import { NavItemKey } from './Sidebar';

interface TopNavProps {
  activeTab: NavItemKey;
  onOpenMobile: () => void;
  dbConnected: boolean;
  lastUpdated: string;
}

const titles: Record<NavItemKey, { title: string; subtitle: string }> = {
  overview: {
    title: 'Overview Dashboard',
    subtitle: 'System performance, 24h baseline dispatch, and annual KPIs',
  },
  'energy-flow': {
    title: 'Energy Monitoring',
    subtitle: 'Nodal power balance and active energy flow dynamics',
  },
  'battery-solar': {
    title: 'Solar & Battery Analytics',
    subtitle: 'Storage state-of-charge trajectories and generation metrics',
  },
  'ai-dispatch': {
    title: 'AI Dispatch Agent',
    subtitle: 'Soft Actor-Critic (SAC) reinforcement learning dispatch evaluations',
  },
  'safety-shield': {
    title: 'Runtime Safety Shield',
    subtitle: 'Formal verification bounds, convex projection, and real-time tester',
  },
  'simulation-results': {
    title: 'Simulation & Benchmarks',
    subtitle: 'Multi-seed statistical rigor and 8,760-hour benchmark comparison',
  },
  'telemetry-logs': {
    title: 'Telemetry & Audit Logs',
    subtitle: 'Live TimescaleDB action audit stream and historical records',
  },
  'system-configs': {
    title: 'System Configuration',
    subtitle: 'Physical hardware constraints, inverter ratings, and tariff schedules',
  },
};

export const TopNav: React.FC<TopNavProps> = ({
  activeTab,
  onOpenMobile,
  dbConnected,
  lastUpdated,
}) => {
  const current = titles[activeTab];

  return (
    <header className="sticky top-0 z-20 glass-panel border-b border-white/60 px-4 md:px-8 py-3.5 mb-6">
      <div className="flex items-center justify-between gap-4">
        {/* Left: Mobile Toggle & Breadcrumbs */}
        <div className="flex items-center gap-3">
          <button
            onClick={onOpenMobile}
            className="md:hidden p-2 rounded-xl bg-white/70 text-sage-800 hover:text-burgundy-900 border border-white/80"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div>
            <div className="flex items-center gap-2 text-xs text-sage-600 font-medium">
              <span>Platform</span>
              <span>/</span>
              <span className="text-burgundy-900 font-semibold">{current.title}</span>
            </div>
            <h1 className="text-lg md:text-xl font-bold text-burgundy-900 tracking-tight">
              {current.title}
            </h1>
          </div>
        </div>

        {/* Right: Status Indicators & Hardware Specs */}
        <div className="flex items-center gap-2 md:gap-3.5">
          {/* Hardware Spec Pill (Desktop only) */}
          <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/60 border border-white/80 text-xs text-sage-800 font-medium shadow-sm">
            <span className="text-burgundy-900 font-bold">100 kWh</span>
            <span className="text-sage-400">|</span>
            <span>±50 kW Inverter</span>
            <span className="text-sage-400">|</span>
            <span className="text-sage-700">SoC [20%, 90%]</span>
          </div>

          {/* Database Connectivity Status */}
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold border shadow-sm ${
              dbConnected
                ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                : 'bg-amber-50 text-amber-800 border-amber-200'
            }`}
          >
            <Database className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">
              {dbConnected ? 'TimescaleDB Connected' : 'Offline Fallback'}
            </span>
            <span
              className={`w-2 h-2 rounded-full ${
                dbConnected ? 'bg-emerald-500' : 'bg-amber-500 animate-pulse'
              }`}
            />
          </div>

          {/* Timestamp Badge */}
          <div className="hidden xl:flex items-center gap-1.5 text-xs text-sage-600 font-mono bg-white/40 px-2.5 py-1.5 rounded-xl border border-white/60">
            <Clock className="w-3.5 h-3.5 text-sage-500" />
            <span>{lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : '--:--:--'}</span>
          </div>
        </div>
      </div>
    </header>
  );
};

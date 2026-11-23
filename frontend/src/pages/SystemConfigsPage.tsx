import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Settings,
  Battery,
  Zap,
  Sun,
  Shield,
  FileCode,
  DollarSign,
  Info,
} from 'lucide-react';
import { fetchConfigs } from '../api';
import { GlassCard } from '../components/GlassCard';

export const SystemConfigsPage: React.FC = () => {
  const [configs, setConfigs] = useState<Record<string, any> | null>(null);
  const [selectedConfig, setSelectedConfig] = useState('active_runtime_benchmark');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchConfigs()
      .then((res) => {
        setConfigs(res);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading || !configs) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-28 rounded-2xl bg-white/40" />
        <div className="h-96 rounded-2xl bg-white/40" />
      </div>
    );
  }

  const activeConf = configs[selectedConfig] || configs['active_runtime_benchmark'];

  return (
    <div className="space-y-6">
      {/* Configuration Scope Banner */}
      <GlassCard burgundy className="p-6 md:p-8">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-cream-200/20 text-cream-200 text-xs font-semibold mb-3 border border-cream-200/30">
            <Settings className="w-3.5 h-3.5" />
            <span>Hardware Registry & Engineering Specs</span>
          </div>
          <h2 className="text-2xl md:text-3xl font-extrabold text-cream-100 tracking-tight">
            Microgrid Configuration & Parameter Domains
          </h2>
          <p className="text-sm text-cream-200/80 mt-1.5 leading-relaxed">
            The repository contains two rigorously separated hardware scenarios:
            (1) The 100 kWh primary evaluation benchmark (INR-denominated, 8,760 hours), and
            (2) The 400 kWh NREL ATB commercial specification (USD-denominated, PSCo TOU tariff).
          </p>
        </div>
      </GlassCard>

      {/* Configuration Selector Tabs */}
      <div className="flex flex-wrap items-center gap-2">
        {Object.keys(configs).map((key) => (
          <button
            key={key}
            onClick={() => setSelectedConfig(key)}
            className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
              selectedConfig === key
                ? 'bg-burgundy-900 text-cream-100 shadow-md shadow-burgundy-900/20'
                : 'glass-card text-sage-800 hover:text-burgundy-900 hover:bg-white'
            }`}
          >
            {key.replace(/_/g, ' ').toUpperCase()}
          </button>
        ))}
      </div>

      {/* Selected Config JSON / Parameter Viewer */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <GlassCard className="lg:col-span-5 space-y-4">
          <h3 className="text-base font-bold text-burgundy-900 flex items-center gap-2">
            <Info className="w-4 h-4 text-burgundy-900" />
            <span>Scenario Overview</span>
          </h3>

          <div className="space-y-3 text-xs text-sage-800">
            <div className="p-3 rounded-xl bg-white/70 border border-white">
              <span className="font-bold text-burgundy-900 block mb-0.5">Selected Registry:</span>
              <span className="font-mono text-sage-700">{selectedConfig}</span>
            </div>

            {selectedConfig === 'active_runtime_benchmark' ? (
              <div className="p-3.5 rounded-xl bg-cream-50/80 border border-cream-200 text-xs text-sage-800 space-y-2">
                <div className="font-bold text-burgundy-900">Active Evaluation Dataset (shared/microgrid_data.csv):</div>
                <div>• Battery Capacity: <strong>100.0 kWh</strong></div>
                <div>• Inverter Maximum Power: <strong>±50.0 kW</strong></div>
                <div>• Safe SoC Bounds: <strong>[20%, 90%]</strong></div>
                <div>• Discrete Control Step: <strong>1.0 Hour</strong></div>
                <div>• Economic Currency: <strong>Indian Rupee (INR ₹)</strong></div>
              </div>
            ) : (
              <div className="p-3.5 rounded-xl bg-sage-50/80 border border-sage-200 text-xs text-sage-800 space-y-2">
                <div className="font-bold text-burgundy-900">Commercial Standard Spec (configs/{selectedConfig}.yaml):</div>
                <div>Parsed dynamically from authentic project configuration YAML.</div>
              </div>
            )}
          </div>
        </GlassCard>

        <GlassCard className="lg:col-span-7">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-burgundy-900 flex items-center gap-2">
              <FileCode className="w-4 h-4" />
              <span>Parsed Configuration Tree</span>
            </h3>
            <span className="text-[10px] font-mono text-sage-600 bg-white/80 px-2 py-0.5 rounded border border-white">
              YAML JSON representation
            </span>
          </div>

          <pre className="p-4 rounded-xl bg-sage-950 text-cream-200 text-xs font-mono overflow-x-auto max-h-[460px] leading-relaxed">
            {JSON.stringify(activeConf, null, 2)}
          </pre>
        </GlassCard>
      </div>
    </div>
  );
};

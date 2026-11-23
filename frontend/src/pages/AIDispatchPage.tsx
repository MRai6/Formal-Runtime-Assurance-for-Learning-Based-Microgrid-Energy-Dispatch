import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Cpu,
  Brain,
  TrendingDown,
  ShieldAlert,
  ShieldCheck,
  Award,
  Layers,
  ArrowRight,
  Database,
  BarChart4,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { fetchAIDispatch, AIDispatchResponse } from '../api';
import { GlassCard } from '../components/GlassCard';
import { KPICard } from '../components/KPICard';

export const AIDispatchPage: React.FC = () => {
  const [data, setData] = useState<AIDispatchResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAIDispatch()
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading || !data) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-28 rounded-2xl bg-white/40" />
        <div className="h-96 rounded-2xl bg-white/40" />
      </div>
    );
  }

  const { model_architecture, full_year_comparison, seasonal_heldout_blocks } = data;

  const costComparisonData = [
    { name: 'No Battery (Reference)', cost: 1481997, interventions: 0, violations: 0 },
    { name: 'Rule-Based Controller', cost: 1372329, interventions: 2740, violations: 8083 },
    { name: 'Trained SAC Agent (Ours)', cost: 1257757, interventions: 1808, violations: 2358 },
  ];

  return (
    <div className="space-y-6">
      {/* Overview Banner */}
      <GlassCard burgundy className="p-6 md:p-8">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-cream-200/20 text-cream-200 text-xs font-semibold mb-3 border border-cream-200/30">
              <Brain className="w-3.5 h-3.5" />
              <span>Soft Actor-Critic (SAC) Continuous Policy</span>
            </div>
            <h2 className="text-2xl md:text-3xl font-extrabold text-cream-100 tracking-tight">
              Learning-Based Economic Dispatch Policy
            </h2>
            <p className="text-sm text-cream-200/80 mt-1.5 max-w-2xl leading-relaxed">
              Trained via continuous deep reinforcement learning on 1-year telemetry with counterfactual policy relabeling.
              Wrapped by the formal runtime shield to guarantee zero physical constraint violations.
            </p>
          </div>

          <div className="text-right shrink-0">
            <div className="text-xs uppercase tracking-wider text-cream-300 font-semibold">
              Net Cost Improvement
            </div>
            <div className="text-3xl font-extrabold text-cream-100 font-mono">+8.3% Saved</div>
            <div className="text-xs text-cream-200/80">vs Heuristic Rule-Based Dispatch</div>
          </div>
        </div>
      </GlassCard>

      {/* KPI Comparisons */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="RL Algorithm"
          value="SAC"
          subValue="Soft Actor-Critic Continuous"
          badge="Member 2"
          icon={Cpu}
        />
        <KPICard
          label="Full-Year Shielded Cost"
          value="₹ 1,257,757"
          subValue="₹ 114,572 Cheaper than Heuristic"
          badge="-8.3% Cost"
          variant="safe"
          icon={TrendingDown}
        />
        <KPICard
          label="Shield Interventions"
          value="1,808"
          subValue="34.0% fewer interventions than Rule-based (2,740)"
          badge="Optimal Compliance"
          icon={ShieldCheck}
        />
        <KPICard
          label="Held-Out Test Block"
          value="7.0% ± 0.3"
          unit="%"
          subValue="Mean across 3 independent seeds"
          badge="Generalizable"
          variant="burgundy"
          icon={Award}
        />
      </div>

      {/* Annual Benchmark Table Comparison */}
      <GlassCard>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-burgundy-900">
              Full-Year Simulation Benchmark Comparison
            </h3>
            <p className="text-xs text-sage-600">
              Authentic experimental evaluation results from member2_rl_dispatch/results/table_full_year.csv
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-white/60 text-xs font-bold text-sage-700 uppercase bg-white/40">
                <th className="py-3 px-4">Controller Policy</th>
                <th className="py-3 px-4">Violation Hours (No Shield → Shield)</th>
                <th className="py-3 px-4">Cost with Shield</th>
                <th className="py-3 px-4">Saving vs Rule-Based</th>
                <th className="py-3 px-4">Saving vs No Battery</th>
                <th className="py-3 px-4">Shield Interventions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/40">
              {full_year_comparison.map((row, idx) => (
                <tr
                  key={idx}
                  className={`hover:bg-white/40 transition-colors ${
                    row.Controller === 'Trained SAC' ? 'font-semibold text-burgundy-900 bg-cream-50/50' : 'text-sage-900'
                  }`}
                >
                  <td className="py-3.5 px-4 flex items-center gap-2">
                    {row.Controller === 'Trained SAC' && (
                      <span className="w-2 h-2 rounded-full bg-burgundy-900" />
                    )}
                    <span>{row.Controller}</span>
                  </td>
                  <td className="py-3.5 px-4 font-mono">{row['Violation hours (no shield → shield)']}</td>
                  <td className="py-3.5 px-4 font-mono font-bold">{row['Cost with shield']}</td>
                  <td className="py-3.5 px-4 text-emerald-700 font-mono">{row['Saving vs rule-based']}</td>
                  <td className="py-3.5 px-4 text-emerald-700 font-mono">{row['Saving vs no battery']}</td>
                  <td className="py-3.5 px-4 font-mono">{row['Shield interventions']}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>

      {/* Chart: Annual Operating Cost Comparison & Seasonal Held-out Blocks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <GlassCard>
          <h3 className="text-base font-bold text-burgundy-900 mb-1">
            Annual Operating Cost by Controller (INR)
          </h3>
          <p className="text-xs text-sage-600 mb-4">
            Evaluating economic performance with formal shield active
          </p>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={costComparisonData} margin={{ top: 10, right: 10, left: 10, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" opacity={0.6} />
                <XAxis dataKey="name" stroke="#898b7e" fontSize={11} interval={0} />
                <YAxis
                  stroke="#898b7e"
                  fontSize={11}
                  domain={[1000000, 1600000]}
                  tickFormatter={(v) => `₹${(v / 100000).toFixed(1)}L`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    borderRadius: '12px',
                    border: '1px solid #E8D2B5',
                    fontSize: '12px',
                  }}
                  formatter={(val: any) => [`₹ ${Number(val).toLocaleString()}`, 'Cost']}
                />
                <Bar dataKey="cost" fill="#590907" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>

        {/* 4 Seasonal Held-Out Test Blocks (Generalization) */}
        <GlassCard>
          <h3 className="text-base font-bold text-burgundy-900 mb-1">
            Seasonal Held-Out Evaluation Blocks
          </h3>
          <p className="text-xs text-sage-600 mb-4">
            Generalization across 4 unseen seasonal test blocks (table_heldout.csv)
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-white/60 text-sage-700 font-bold uppercase bg-white/40">
                  <th className="py-2.5 px-3">Method</th>
                  <th className="py-2.5 px-3">Cost (INR)</th>
                  <th className="py-2.5 px-3">Savings</th>
                  <th className="py-2.5 px-3">Interventions</th>
                  <th className="py-2.5 px-3">Solar Used</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/40">
                {seasonal_heldout_blocks.map((b, idx) => (
                  <tr key={idx} className="hover:bg-white/40 transition-colors">
                    <td className="py-2.5 px-3 font-semibold text-burgundy-900">{b.Method}</td>
                    <td className="py-2.5 px-3 font-mono">₹ {b['Cost (INR)']}</td>
                    <td className="py-2.5 px-3 font-mono text-emerald-700">{b['Saving vs rule-based']}</td>
                    <td className="py-2.5 px-3 font-mono">{b['Interventions (rate)']}</td>
                    <td className="py-2.5 px-3 font-mono">{b['Solar used (kWh)']} kWh</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 p-3 rounded-xl bg-white/50 border border-white text-xs text-sage-700 space-y-1">
            <div>
              <strong>Observation Space:</strong> {model_architecture.observation_space.join(', ')}
            </div>
            <div>
              <strong>Action Space:</strong> {model_architecture.action_space}
            </div>
          </div>
        </GlassCard>
      </div>
    </div>
  );
};

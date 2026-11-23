import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  ShieldCheck,
  ShieldAlert,
  ArrowRight,
  Zap,
  Battery,
  Clock,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
} from 'lucide-react';
import { verifyShieldAction, ShieldVerifyResponse } from '../api';
import { GlassCard } from '../components/GlassCard';
import { KPICard } from '../components/KPICard';

export const SafetyShieldPage: React.FC = () => {
  // Real-time verification test inputs
  const [soc, setSoc] = useState(0.25);
  const [proposedKw, setProposedKw] = useState(40.0);
  const [batteryKwh, setBatteryKwh] = useState(100.0);
  const [maxPowerKw, setMaxPowerKw] = useState(50.0);
  const [socMin, setSocMin] = useState(0.20);
  const [socMax, setSocMax] = useState(0.90);

  const [verifyResult, setVerifyResult] = useState<ShieldVerifyResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const runVerify = () => {
    setLoading(true);
    verifyShieldAction({
      current_soc: soc,
      proposed_kw: proposedKw,
      battery_kwh: batteryKwh,
      max_power_kw: maxPowerKw,
      soc_min: socMin,
      soc_max: socMax,
    })
      .then((res) => {
        setVerifyResult(res);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    runVerify();
  }, [soc, proposedKw, batteryKwh, maxPowerKw, socMin, socMax]);

  return (
    <div className="space-y-6">
      {/* Formal Safety Pipeline Explanation Banner */}
      <GlassCard burgundy className="p-6 md:p-8">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-cream-200/20 text-cream-200 text-xs font-semibold mb-3 border border-cream-200/30">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Formal Mathematical Guarantee</span>
          </div>
          <h2 className="text-2xl md:text-3xl font-extrabold text-cream-100 tracking-tight">
            Convex Runtime Safety Shield
          </h2>
          <p className="text-sm text-cream-200/80 mt-1.5 leading-relaxed">
            Acts as a provably correct mathematical barrier inserted directly between the AI policy
            and the physical microgrid actuator. Projects any unsafe proposed power dispatch to the closest
            admissible action in the safe polyhedron.
          </p>
        </div>

        {/* 3-Step Pipeline Flow Diagram */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
          <div className="p-4 rounded-xl bg-white/10 border border-white/20">
            <div className="text-[11px] font-bold text-cream-300 uppercase">Stage 1</div>
            <div className="text-base font-bold text-cream-100 mt-1">RL Proposed Action</div>
            <div className="text-xs text-cream-200/70 mt-0.5">Unconstrained neural policy output</div>
          </div>

          <div className="p-4 rounded-xl bg-white/20 border border-white/30 text-center relative">
            <div className="text-[11px] font-bold text-cream-300 uppercase">Stage 2</div>
            <div className="text-base font-bold text-cream-100 mt-1">Convex Projection</div>
            <div className="text-xs text-cream-200/90 mt-0.5">Sub-millisecond mathematical clip</div>
          </div>

          <div className="p-4 rounded-xl bg-emerald-500/20 border border-emerald-400/40">
            <div className="text-[11px] font-bold text-emerald-300 uppercase">Stage 3</div>
            <div className="text-base font-bold text-cream-100 mt-1">Safe Executed Action</div>
            <div className="text-xs text-emerald-200 mt-0.5">Dispatched to inverter hardware</div>
          </div>
        </div>
      </GlassCard>

      {/* Real-time Interactive Testing Studio */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Controls Column (5 cols) */}
        <GlassCard className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between border-b border-white/60 pb-3">
            <h3 className="text-base font-bold text-burgundy-900 flex items-center gap-2">
              <Sliders className="w-4 h-4 text-burgundy-900" />
              <span>Real-Time What-If Sandbox</span>
            </h3>
            <button
              onClick={() => {
                setSoc(0.25);
                setProposedKw(40.0);
              }}
              className="text-xs font-semibold text-sage-700 hover:text-burgundy-900 flex items-center gap-1"
            >
              <RotateCcw className="w-3 h-3" />
              <span>Reset</span>
            </button>
          </div>

          {/* Slider 1: Current SoC */}
          <div>
            <div className="flex justify-between text-xs font-semibold text-sage-800 mb-1.5">
              <span>Current Battery SoC:</span>
              <span className="font-mono text-burgundy-900 font-bold">{(soc * 100).toFixed(0)}% ({soc.toFixed(2)})</span>
            </div>
            <input
              type="range"
              min="0.05"
              max="0.95"
              step="0.01"
              value={soc}
              onChange={(e) => setSoc(parseFloat(e.target.value))}
              className="w-full accent-burgundy-900 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-sage-500 mt-0.5">
              <span>5% (Deep)</span>
              <span>50% (Nominal)</span>
              <span>95% (Full)</span>
            </div>
          </div>

          {/* Slider 2: Proposed Action */}
          <div>
            <div className="flex justify-between text-xs font-semibold text-sage-800 mb-1.5">
              <span>AI Proposed Power Action (kW):</span>
              <span className="font-mono text-burgundy-900 font-bold">
                {proposedKw > 0 ? `+${proposedKw.toFixed(1)}` : proposedKw.toFixed(1)} kW
              </span>
            </div>
            <input
              type="range"
              min="-100.0"
              max="100.0"
              step="1.0"
              value={proposedKw}
              onChange={(e) => setProposedKw(parseFloat(e.target.value))}
              className="w-full accent-burgundy-900 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-sage-500 mt-0.5">
              <span>-100 kW (Charge)</span>
              <span>0 kW</span>
              <span>+100 kW (Discharge)</span>
            </div>
          </div>

          <div className="pt-3 border-t border-white/60 space-y-3">
            <div className="text-xs font-bold text-sage-800 uppercase tracking-wider">
              Boundary Parameters
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <label className="text-sage-600 block text-[11px] mb-1">Min SoC Threshold</label>
                <input
                  type="number"
                  value={socMin * 100}
                  onChange={(e) => setSocMin(parseFloat(e.target.value) / 100)}
                  className="w-full px-2.5 py-1.5 rounded-lg bg-white/70 border border-white text-burgundy-900 font-mono font-semibold"
                />
              </div>
              <div>
                <label className="text-sage-600 block text-[11px] mb-1">Max SoC Threshold</label>
                <input
                  type="number"
                  value={socMax * 100}
                  onChange={(e) => setSocMax(parseFloat(e.target.value) / 100)}
                  className="w-full px-2.5 py-1.5 rounded-lg bg-white/70 border border-white text-burgundy-900 font-mono font-semibold"
                />
              </div>
            </div>
          </div>
        </GlassCard>

        {/* Diagnostic Output Column (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          {verifyResult && (
            <>
              {/* Verification Status Card */}
              <GlassCard
                className={`border-2 ${
                  verifyResult.shield_intervened
                    ? 'border-amber-400 bg-amber-50/50'
                    : 'border-emerald-400 bg-emerald-50/50'
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-3">
                    {verifyResult.shield_intervened ? (
                      <div className="w-10 h-10 rounded-xl bg-amber-500/20 text-amber-800 flex items-center justify-center shrink-0">
                        <AlertTriangle className="w-5 h-5 text-amber-700" />
                      </div>
                    ) : (
                      <div className="w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-800 flex items-center justify-center shrink-0">
                        <CheckCircle2 className="w-5 h-5 text-emerald-700" />
                      </div>
                    )}
                    <div>
                      <h4
                        className={`text-base font-bold ${
                          verifyResult.shield_intervened ? 'text-amber-900' : 'text-emerald-900'
                        }`}
                      >
                        {verifyResult.shield_intervened
                          ? 'Shield Intervention Triggered'
                          : 'Proposed Action Is Formally Safe'}
                      </h4>
                      <p className="text-xs text-sage-700 mt-0.5">
                        {verifyResult.shield_intervened
                          ? 'Projected to closest boundary point in the safe polyhedron.'
                          : 'Action satisfies Rule 1 (SoC), Rule 2 (Power), and Rule 3 (Balance).'}
                      </p>
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="text-[11px] text-sage-600 block">Latency</span>
                    <span className="text-sm font-bold font-mono text-burgundy-900">
                      {verifyResult.computation_latency_us.toFixed(2)} µs
                    </span>
                  </div>
                </div>

                {verifyResult.violation_reasons.length > 0 && (
                  <div className="mt-3.5 p-3 rounded-xl bg-amber-100/70 border border-amber-200/80 text-xs text-amber-900 space-y-1">
                    <div className="font-bold">Violations Detected on Proposed Action:</div>
                    {verifyResult.violation_reasons.map((r, idx) => (
                      <div key={idx} className="flex items-center gap-1.5 font-mono text-[11px]">
                        <span>•</span>
                        <span>{r}</span>
                      </div>
                    ))}
                  </div>
                )}
              </GlassCard>

              {/* Action Projection Metrics */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3.5 rounded-xl bg-white/70 border border-white text-center">
                  <div className="text-[11px] uppercase text-sage-600 font-bold">Proposed</div>
                  <div className="text-lg font-bold text-burgundy-900 font-mono mt-1">
                    {verifyResult.proposed_action_kw.toFixed(1)} kW
                  </div>
                  <div className="text-[10px] text-sage-500">Unshielded AI</div>
                </div>

                <div className="p-3.5 rounded-xl bg-white/70 border border-white text-center">
                  <div className="text-[11px] uppercase text-sage-600 font-bold">Safe Interval</div>
                  <div className="text-sm font-bold text-sage-900 font-mono mt-1">
                    [{verifyResult.admissible_safe_interval[0].toFixed(1)},{' '}
                    {verifyResult.admissible_safe_interval[1].toFixed(1)}] kW
                  </div>
                  <div className="text-[10px] text-sage-500">[P_lo, P_hi]</div>
                </div>

                <div className="p-3.5 rounded-xl bg-burgundy-900 text-cream-100 text-center shadow-md">
                  <div className="text-[11px] uppercase text-cream-300 font-bold">Executed</div>
                  <div className="text-lg font-bold text-cream-100 font-mono mt-1">
                    {verifyResult.safe_executed_action_kw.toFixed(1)} kW
                  </div>
                  <div className="text-[10px] text-cream-200/80">Convex Projection</div>
                </div>

                <div className="p-3.5 rounded-xl bg-white/70 border border-white text-center">
                  <div className="text-[11px] uppercase text-sage-600 font-bold">Next SoC</div>
                  <div className="text-lg font-bold text-emerald-700 font-mono mt-1">
                    {verifyResult.next_soc_with_shield_pct.toFixed(1)}%
                  </div>
                  <div className="text-[10px] text-red-500 line-through">
                    {verifyResult.next_soc_without_shield_pct.toFixed(1)}%
                  </div>
                </div>
              </div>

              {/* Visual Action Polyhedron Projection Line */}
              <GlassCard>
                <div className="text-xs font-bold text-burgundy-900 mb-3">
                  1-Dimensional Action Convex Projection Visualizer
                </div>
                <div className="relative py-6">
                  {/* The continuous line from -100 to +100 */}
                  <div className="h-2 w-full bg-sage-200 rounded-full relative">
                    {/* Safe zone highlighting */}
                    <div
                      className="absolute top-0 h-full bg-emerald-400 rounded-full"
                      style={{
                        left: `${((verifyResult.admissible_safe_interval[0] + 100) / 200) * 100}%`,
                        width: `${
                          ((verifyResult.admissible_safe_interval[1] -
                            verifyResult.admissible_safe_interval[0]) /
                            200) *
                          100
                        }%`,
                      }}
                    />
                    {/* Proposed action pointer */}
                    <div
                      className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-red-600 border-2 border-white shadow-md z-10"
                      style={{
                        left: `${((verifyResult.proposed_action_kw + 100) / 200) * 100}%`,
                      }}
                      title={`Proposed: ${verifyResult.proposed_action_kw} kW`}
                    />
                    {/* Executed action pointer */}
                    <div
                      className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-burgundy-900 border-2 border-cream-200 shadow-md z-20"
                      style={{
                        left: `${((verifyResult.safe_executed_action_kw + 100) / 200) * 100}%`,
                      }}
                      title={`Executed: ${verifyResult.safe_executed_action_kw} kW`}
                    />
                  </div>
                  <div className="flex justify-between text-[10px] text-sage-600 font-mono mt-3">
                    <span>-100 kW</span>
                    <span className="text-emerald-700 font-bold">
                      Safe Interval [{verifyResult.admissible_safe_interval[0].toFixed(1)},{' '}
                      {verifyResult.admissible_safe_interval[1].toFixed(1)}]
                    </span>
                    <span>+100 kW</span>
                  </div>
                </div>
              </GlassCard>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

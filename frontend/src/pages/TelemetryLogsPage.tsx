import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Database,
  Search,
  Filter,
  Download,
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Info,
  Clock,
  ShieldCheck,
  ShieldAlert,
  X,
} from 'lucide-react';
import { fetchAuditLogs, AuditLogResponse, AuditLogRecord } from '../api';
import { GlassCard } from '../components/GlassCard';

export const TelemetryLogsPage: React.FC = () => {
  const [data, setData] = useState<AuditLogResponse | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [interventionsOnly, setInterventionsOnly] = useState(false);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [selectedRecord, setSelectedRecord] = useState<AuditLogRecord | null>(null);

  const loadLogs = () => {
    setLoading(true);
    fetchAuditLogs(page, pageSize, interventionsOnly, search)
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    loadLogs();
  }, [page, pageSize, interventionsOnly]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadLogs();
  };

  const exportCSV = () => {
    if (!data || data.records.length === 0) return;
    const headers = Object.keys(data.records[0]).join(',');
    const rows = data.records.map((r) => Object.values(r).map(v => `"${v}"`).join(',')).join('\n');
    const blob = new Blob([`${headers}\n${rows}`], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit_logs_page_${page}.csv`;
    a.click();
  };

  return (
    <div className="space-y-6">
      {/* Table Header & Controls */}
      <GlassCard className="space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Database className="w-5 h-5 text-burgundy-900" />
              <h3 className="text-base font-bold text-burgundy-900">
                PostgreSQL action_audit_log Telemetry Browser
              </h3>
            </div>
            <p className="text-xs text-sage-600 mt-0.5">
              Live TimescaleDB hypertable tracking every runtime verification decision
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={exportCSV}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white text-burgundy-900 font-semibold text-xs border border-white hover:bg-cream-100 transition-all shadow-sm"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export CSV</span>
            </button>
          </div>
        </div>

        {/* Filter and Search Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-white/60">
          <form onSubmit={handleSearchSubmit} className="relative w-full sm:w-72">
            <Search className="w-4 h-4 text-sage-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search violation reason..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 rounded-xl bg-white/70 border border-white text-xs text-burgundy-900 placeholder:text-sage-400 font-medium focus:outline-none focus:ring-2 focus:ring-burgundy-900/20"
            />
          </form>

          <div className="flex items-center gap-4 w-full sm:w-auto justify-between sm:justify-end">
            <label className="flex items-center gap-2 text-xs font-semibold text-sage-800 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={interventionsOnly}
                onChange={(e) => {
                  setInterventionsOnly(e.target.checked);
                  setPage(1);
                }}
                className="rounded accent-burgundy-900"
              />
              <span>Interventions Only</span>
            </label>

            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(parseInt(e.target.value));
                setPage(1);
              }}
              className="text-xs font-semibold text-sage-800 bg-white/70 px-2 py-1.5 rounded-lg border border-white"
            >
              <option value={10}>10 per page</option>
              <option value={25}>25 per page</option>
              <option value={50}>50 per page</option>
            </select>
          </div>
        </div>
      </GlassCard>

      {/* Main Records Table */}
      <GlassCard className="overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-white/60 bg-white/50 text-sage-700 font-bold uppercase tracking-wider">
                <th className="py-3 px-4">Timestamp (UTC)</th>
                <th className="py-3 px-4">SoC</th>
                <th className="py-3 px-4">RL Proposed</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Executed Action</th>
                <th className="py-3 px-4">Latency</th>
                <th className="py-3 px-4">Violation Details</th>
                <th className="py-3 px-4 text-center">Inspect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/40">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-sage-600">
                    Loading records from database...
                  </td>
                </tr>
              ) : !data || data.records.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-sage-600">
                    No matching audit records found.
                  </td>
                </tr>
              ) : (
                data.records.map((r, idx) => (
                  <tr
                    key={idx}
                    className={`hover:bg-white/40 transition-colors ${
                      r.shield_intervention_flag ? 'bg-amber-50/20' : ''
                    }`}
                  >
                    <td className="py-3 px-4 font-mono text-sage-800 whitespace-nowrap">
                      {new Date(r.time).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 font-mono font-semibold text-burgundy-900">
                      {(r.current_soc * 100).toFixed(1)}%
                    </td>
                    <td className="py-3 px-4 font-mono text-sage-800">{r.rl_proposed_action}</td>
                    <td className="py-3 px-4">
                      {r.shield_intervention_flag ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 text-[10px] font-bold border border-amber-200">
                          <ShieldAlert className="w-3 h-3 text-amber-600" />
                          <span>Intervened</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold border border-emerald-200">
                          <ShieldCheck className="w-3 h-3 text-emerald-600" />
                          <span>Pass</span>
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono font-bold text-burgundy-900">
                      {r.executed_action}
                    </td>
                    <td className="py-3 px-4 font-mono text-sage-600">
                      {r.computation_latency_ms.toFixed(4)} ms
                    </td>
                    <td className="py-3 px-4 text-sage-700 max-w-xs truncate">
                      {r.violation_reason || '—'}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <button
                        onClick={() => setSelectedRecord(r)}
                        className="px-2 py-1 rounded bg-white/70 hover:bg-white text-burgundy-900 font-semibold text-[11px] border border-white"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Server-side Pagination Bar */}
        {data && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-white/60 text-xs text-sage-700 bg-white/30">
            <div>
              Showing page <strong>{data.page}</strong> of <strong>{data.total_pages}</strong>{' '}
              ({data.total_records.toLocaleString()} total audit events)
            </div>

            <div className="flex items-center gap-1.5">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="p-1.5 rounded-lg bg-white/70 hover:bg-white text-sage-800 disabled:opacity-40 border border-white"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="px-2 font-mono font-bold">{page}</span>
              <button
                disabled={page >= data.total_pages}
                onClick={() => setPage((p) => p + 1)}
                className="p-1.5 rounded-lg bg-white/70 hover:bg-white text-sage-800 disabled:opacity-40 border border-white"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </GlassCard>

      {/* Record Inspection Modal */}
      <AnimatePresence>
        {selectedRecord && (
          <div className="fixed inset-0 bg-burgundy-950/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white/90 backdrop-blur-xl border border-white rounded-2xl p-6 max-w-lg w-full shadow-2xl space-y-4"
            >
              <div className="flex items-center justify-between border-b pb-3">
                <h4 className="text-base font-bold text-burgundy-900 flex items-center gap-2">
                  <Info className="w-4 h-4" />
                  <span>Audit Verification Record</span>
                </h4>
                <button
                  onClick={() => setSelectedRecord(null)}
                  className="p-1 rounded-lg hover:bg-sage-200 text-sage-700"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-2 text-xs font-mono">
                <div className="flex justify-between py-1 border-b border-sage-100">
                  <span className="text-sage-600 font-sans">Timestamp:</span>
                  <span className="text-burgundy-900 font-bold">{new Date(selectedRecord.time).toISOString()}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-sage-100">
                  <span className="text-sage-600 font-sans">State of Charge:</span>
                  <span>{(selectedRecord.current_soc * 100).toFixed(2)}%</span>
                </div>
                <div className="flex justify-between py-1 border-b border-sage-100">
                  <span className="text-sage-600 font-sans">RL Proposed Action:</span>
                  <span>{selectedRecord.rl_proposed_action}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-sage-100">
                  <span className="text-sage-600 font-sans">Intervention Flag:</span>
                  <span className={selectedRecord.shield_intervention_flag ? 'text-amber-700 font-bold' : 'text-emerald-700 font-bold'}>
                    {selectedRecord.shield_intervention_flag ? 'TRUE (Overridden)' : 'FALSE (Admissible)'}
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-sage-100">
                  <span className="text-sage-600 font-sans">Safe Fallback Action:</span>
                  <span>{selectedRecord.shield_fallback_action || 'N/A'}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-sage-100">
                  <span className="text-sage-600 font-sans">Dispatched Command:</span>
                  <span className="font-bold text-burgundy-900">{selectedRecord.executed_action}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-sage-100">
                  <span className="text-sage-600 font-sans">Verification Latency:</span>
                  <span>{selectedRecord.computation_latency_ms.toFixed(5)} ms</span>
                </div>
                <div className="py-2">
                  <span className="text-sage-600 font-sans block mb-1">Violation Explanation:</span>
                  <div className="p-2.5 rounded-lg bg-sage-50 text-sage-900 font-sans text-xs border border-sage-200">
                    {selectedRecord.violation_reason || 'No constraint violation detected.'}
                  </div>
                </div>
              </div>

              <button
                onClick={() => setSelectedRecord(null)}
                className="w-full py-2 rounded-xl bg-burgundy-900 text-cream-100 font-bold text-xs"
              >
                Close Inspector
              </button>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

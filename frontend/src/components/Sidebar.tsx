import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard,
  Zap,
  SunMedium,
  Cpu,
  ShieldCheck,
  BarChart3,
  Database,
  Settings,
  ChevronLeft,
  ChevronRight,
  Shield,
  Activity,
} from 'lucide-react';

export type NavItemKey =
  | 'overview'
  | 'energy-flow'
  | 'battery-solar'
  | 'ai-dispatch'
  | 'safety-shield'
  | 'simulation-results'
  | 'telemetry-logs'
  | 'system-configs';

interface SidebarProps {
  activeTab: NavItemKey;
  onSelectTab: (tab: NavItemKey) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

interface NavItemDef {
  key: NavItemKey;
  label: string;
  badge?: string;
  icon: React.ComponentType<{ className?: string }>;
}

const navItems: NavItemDef[] = [
  { key: 'overview', label: 'Overview Dashboard', icon: LayoutDashboard },
  { key: 'energy-flow', label: 'Energy Monitoring', badge: 'Live Flow', icon: Zap },
  { key: 'battery-solar', label: 'Solar & Battery Analytics', icon: SunMedium },
  { key: 'ai-dispatch', label: 'AI Dispatch Agent', badge: 'SAC', icon: Cpu },
  { key: 'safety-shield', label: 'Runtime Safety Shield', badge: 'Formal', icon: ShieldCheck },
  { key: 'simulation-results', label: 'Simulation & Benchmarks', icon: BarChart3 },
  { key: 'telemetry-logs', label: 'Telemetry & Audit Logs', icon: Database },
  { key: 'system-configs', label: 'System Configuration', icon: Settings },
];

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
}) => {
  const sidebarWidth = collapsed ? 'w-20' : 'w-72';

  const content = (
    <div className="flex flex-col h-full select-none">
      {/* Brand Header */}
      <div className="flex items-center justify-between p-5 border-b border-white/60">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="w-10 h-10 rounded-xl bg-burgundy-900 flex items-center justify-center text-cream-200 shadow-md shadow-burgundy-900/20 shrink-0">
            <Shield className="w-5 h-5 text-cream-200" />
          </div>
          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.15 }}
                className="overflow-hidden whitespace-nowrap"
              >
                <div className="font-bold text-base tracking-tight text-burgundy-900 flex items-center gap-1.5">
                  AURA<span className="text-sage-600 font-medium">GRID</span>
                  <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-burgundy-900/10 text-burgundy-900 border border-burgundy-900/20">
                    Formal
                  </span>
                </div>
                <div className="text-[11px] text-sage-600 font-medium">Microgrid Safety Assurance</div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Desktop Collapse Toggle */}
        <button
          onClick={onToggleCollapse}
          className="hidden md:flex items-center justify-center w-7 h-7 rounded-lg bg-white/70 hover:bg-white text-sage-700 hover:text-burgundy-900 border border-white/80 shadow-sm transition-colors"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation Items */}
      <div className="flex-1 py-4 px-3 space-y-1.5 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.key;

          return (
            <button
              key={item.key}
              onClick={() => {
                onSelectTab(item.key);
                onCloseMobile();
              }}
              className={`w-full flex items-center gap-3.5 px-3.5 py-3 rounded-xl text-sm font-semibold transition-all relative group ${
                isActive
                  ? 'bg-burgundy-900 text-cream-100 shadow-md shadow-burgundy-900/20'
                  : 'text-sage-800 hover:bg-white/60 hover:text-burgundy-900'
              }`}
              title={collapsed ? item.label : undefined}
            >
              <Icon
                className={`w-5 h-5 shrink-0 transition-colors ${
                  isActive ? 'text-cream-200' : 'text-sage-600 group-hover:text-burgundy-900'
                }`}
              />

              {!collapsed && (
                <div className="flex items-center justify-between flex-1 overflow-hidden whitespace-nowrap">
                  <span className="truncate">{item.label}</span>
                  {item.badge && (
                    <span
                      className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${
                        isActive
                          ? 'bg-cream-200/20 text-cream-200 border border-cream-200/30'
                          : 'bg-sage-200 text-sage-800 border border-sage-300'
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </div>
              )}

              {/* Tooltip for collapsed mode */}
              {collapsed && (
                <div className="absolute left-full ml-3.5 px-3 py-1.5 rounded-lg bg-burgundy-950 text-cream-100 text-xs font-medium whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-opacity shadow-lg z-50">
                  {item.label}
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* System Status Mini Badge */}
      <div className="p-3 border-t border-white/60">
        <div
          className={`rounded-xl p-3 bg-white/50 border border-white/80 transition-all ${
            collapsed ? 'text-center p-2' : ''
          }`}
        >
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
            </span>
            {!collapsed && (
              <span className="text-xs font-semibold text-sage-800 truncate">
                Provably Safe Policy
              </span>
            )}
          </div>
          {!collapsed && (
            <div className="text-[11px] text-sage-600 mt-1 font-mono">
              Zero Invariant Violations
            </div>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <aside
        className={`hidden md:block fixed top-0 left-0 h-screen ${sidebarWidth} glass-panel border-r border-white/60 transition-all duration-300 ease-in-out z-30`}
      >
        {content}
      </aside>

      {/* Mobile Drawer Backdrop */}
      {mobileOpen && (
        <div
          onClick={onCloseMobile}
          className="md:hidden fixed inset-0 bg-burgundy-950/40 backdrop-blur-sm z-40"
        />
      )}

      {/* Mobile Sidebar */}
      <aside
        className={`md:hidden fixed top-0 left-0 h-screen w-72 glass-panel border-r border-white/60 transition-transform duration-300 ease-in-out z-50 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {content}
      </aside>
    </>
  );
};

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sidebar, NavItemKey } from './components/Sidebar';
import { TopNav } from './components/TopNav';
import { fetchHealth } from './api';

// Pages
import { OverviewPage } from './pages/OverviewPage';
import { EnergyFlowPage } from './pages/EnergyFlowPage';
import { BatterySolarPage } from './pages/BatterySolarPage';
import { AIDispatchPage } from './pages/AIDispatchPage';
import { SafetyShieldPage } from './pages/SafetyShieldPage';
import { SimulationResultsPage } from './pages/SimulationResultsPage';
import { TelemetryLogsPage } from './pages/TelemetryLogsPage';
import { SystemConfigsPage } from './pages/SystemConfigsPage';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<NavItemKey>('overview');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [dbConnected, setDbConnected] = useState(false);
  const [lastUpdated, setLastUpdated] = useState('');

  // Initial and periodic health check
  useEffect(() => {
    const checkHealth = () => {
      fetchHealth()
        .then((res) => {
          setDbConnected(res.database.connected);
          setLastUpdated(res.timestamp);
        })
        .catch(() => {
          setDbConnected(false);
        });
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const renderActivePage = () => {
    switch (activeTab) {
      case 'overview':
        return <OverviewPage />;
      case 'energy-flow':
        return <EnergyFlowPage />;
      case 'battery-solar':
        return <BatterySolarPage />;
      case 'ai-dispatch':
        return <AIDispatchPage />;
      case 'safety-shield':
        return <SafetyShieldPage />;
      case 'simulation-results':
        return <SimulationResultsPage />;
      case 'telemetry-logs':
        return <TelemetryLogsPage />;
      case 'system-configs':
        return <SystemConfigsPage />;
      default:
        return <OverviewPage />;
    }
  };

  const mainPaddingLeft = sidebarCollapsed ? 'md:pl-20' : 'md:pl-72';

  return (
    <div className="min-h-screen flex flex-col antialiased">
      {/* Collapsible Glass Sidebar */}
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        mobileOpen={mobileMenuOpen}
        onCloseMobile={() => setMobileMenuOpen(false)}
      />

      {/* Main Content Area */}
      <div className={`flex-1 transition-all duration-300 ease-in-out ${mainPaddingLeft} flex flex-col`}>
        {/* Sticky Glass Top Navigation Bar */}
        <TopNav
          activeTab={activeTab}
          onOpenMobile={() => setMobileMenuOpen(true)}
          dbConnected={dbConnected}
          lastUpdated={lastUpdated}
        />

        {/* Page Content with 60 FPS Smooth Transitions */}
        <main className="flex-1 px-4 md:px-8 pb-12">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            >
              {renderActivePage()}
            </motion.div>
          </AnimatePresence>
        </main>

        {/* Footer */}
        <footer className="glass-panel border-t border-white/60 py-4 px-8 text-center text-xs text-sage-600">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-2 max-w-7xl mx-auto">
            <span>
              <strong>AURA-Grid</strong> • Formal Runtime Assurance for Learning-Based Microgrid Energy Dispatch
            </span>
            <span className="font-mono text-[11px] text-sage-500">
              PostgreSQL / TimescaleDB • FastAPI • React 19 • 60 FPS Glassmorphism
            </span>
          </div>
        </footer>
      </div>
    </div>
  );
};

export default App;

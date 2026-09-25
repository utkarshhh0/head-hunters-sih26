import React, { useState, useEffect } from 'react';
import { ShieldAlert, Server, RefreshCw } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { getHealth } from '../../api';

export const Header: React.FC = () => {
  const { session } = useAuth();
  const [backendStatus, setBackendStatus] = useState<'ONLINE' | 'OFFLINE' | 'CHECKING'>('CHECKING');
  const [latency, setLatency] = useState<number | null>(null);

  const checkBackendHealth = async () => {
    const start = performance.now();
    try {
      const res = await getHealth();
      const elapsed = Math.round(performance.now() - start);
      if (res.status === 'healthy') {
        setBackendStatus('ONLINE');
        setLatency(elapsed);
      } else {
        setBackendStatus('OFFLINE');
        setLatency(null);
      }
    } catch {
      setBackendStatus('OFFLINE');
      setLatency(null);
    }
  };

  useEffect(() => {
    checkBackendHealth();
    const interval = setInterval(checkBackendHealth, 30000); // 30s background heartbeat
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-14 bg-institutional-panel border-b border-institutional-border px-6 flex items-center justify-between shrink-0">
      {/* Active Case Context */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-institutional-textMuted">
            Active Workspace
          </span>
          <span className="text-xs font-mono font-semibold text-institutional-textPrimary tracking-tight">
            {session?.caseWorkspace || 'OPERATION HAWKEYE [CASE-2026-0814]'}
          </span>
        </div>

        <div className="hidden md:flex items-center gap-1.5 text-[11px] font-mono text-institutional-textMuted border-l border-institutional-borderMuted pl-4">
          <ShieldAlert className="w-3.5 h-3.5 text-amber-500/80" />
          <span>OFFICIAL USE ONLY · EVIDENTIARY AUDIT LOGGED</span>
        </div>
      </div>

      {/* Backend & Environment Live Status */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-xs font-mono">
          <button
            onClick={checkBackendHealth}
            title="Check backend status"
            className="flex items-center gap-1.5 px-2 py-1 rounded bg-slate-900/90 border border-slate-800 hover:border-slate-700 text-institutional-textSecondary transition-colors"
          >
            <Server className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-[11px]">API:</span>
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                backendStatus === 'ONLINE'
                  ? 'bg-emerald-400'
                  : backendStatus === 'OFFLINE'
                  ? 'bg-rose-500'
                  : 'bg-amber-400 animate-pulse'
              }`}
            />
            <span
              className={`text-[11px] font-semibold ${
                backendStatus === 'ONLINE'
                  ? 'text-emerald-400'
                  : backendStatus === 'OFFLINE'
                  ? 'text-rose-400'
                  : 'text-amber-400'
              }`}
            >
              {backendStatus}
            </span>
            {latency !== null && (
              <span className="text-[10px] text-slate-500 tabular-numbers">
                ({latency}ms)
              </span>
            )}
            <RefreshCw className="w-3 h-3 text-slate-500 hover:text-slate-300 ml-0.5" />
          </button>
        </div>

        {/* Clearance Level */}
        <div className="hidden lg:flex items-center gap-1.5 text-[10px] font-mono px-2 py-1 rounded bg-slate-950 border border-slate-800 text-slate-400">
          <span>CLEARANCE:</span>
          <span className="text-slate-200 font-semibold">LEVEL 4</span>
        </div>
      </div>
    </header>
  );
};

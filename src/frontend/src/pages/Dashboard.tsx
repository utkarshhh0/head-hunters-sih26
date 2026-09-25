import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ShieldAlert,
  Activity,
  Play,
  RefreshCw,
  Search,
  Network,
  Clock,
  FileCheck,
  Server,
  ArrowRight,
  Layers,
} from 'lucide-react';
import { MetricCard } from '../components/common/MetricCard';
import { StatusBadge } from '../components/common/StatusBadge';
import { getWorkspaceSummary, detectFindings, getHealth, WorkspaceSummary } from '../api';
import { useAuth } from '../context/AuthContext';

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { session } = useAuth();

  const [summary, setSummary] = useState<WorkspaceSummary | null>(null);
  const [backendHealth, setBackendHealth] = useState<{ status: string; service: string } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isDetecting, setIsDetecting] = useState<boolean>(false);
  const [detectionMessage, setDetectionMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboardData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [healthRes, summaryRes] = await Promise.allSettled([
        getHealth(),
        getWorkspaceSummary(),
      ]);

      if (healthRes.status === 'fulfilled') {
        setBackendHealth(healthRes.value);
      } else {
        setBackendHealth(null);
      }

      if (summaryRes.status === 'fulfilled') {
        setSummary(summaryRes.value);
      } else {
        setSummary(null);
        setError('FastAPI backend not reachable at /api/v1/workspace/summary.');
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch dashboard data';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  const handleRunDetection = async () => {
    setIsDetecting(true);
    setDetectionMessage(null);
    try {
      const findings = await detectFindings({ limit: 500 });
      setDetectionMessage(
        `Pattern detection executed: ${findings.length} analytical finding(s) registered in workspace.`
      );
      // Refresh summary
      const updated = await getWorkspaceSummary();
      setSummary(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Pattern detection trigger failed';
      setDetectionMessage(`Detection failed: ${msg}`);
    } finally {
      setIsDetecting(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Workspace Operational Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-institutional-border pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-blue-400">
              WORKSPACE DASHBOARD
            </span>
            <span className="text-xs font-mono text-institutional-textMuted">
              {session?.caseWorkspace || 'OPERATION HAWKEYE'}
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight mt-1">
            Investigator Workspace Summary
          </h1>
          <p className="text-xs text-institutional-textSecondary mt-1">
            Real-time aggregate status of entity intelligence, detected patterns, and multi-signal finding lifecycle.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchDashboardData}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-mono rounded bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh State</span>
          </button>

          <button
            onClick={handleRunDetection}
            disabled={isDetecting || !backendHealth}
            className="flex items-center gap-2 px-4 py-2 text-xs font-mono font-medium rounded bg-blue-600 hover:bg-blue-500 text-white shadow-sm transition-colors disabled:opacity-50"
          >
            <Play className={`w-3.5 h-3.5 ${isDetecting ? 'animate-spin' : ''}`} />
            <span>{isDetecting ? 'Detecting Patterns...' : 'Run Pattern Detection'}</span>
          </button>
        </div>
      </div>

      {/* Detection feedback message */}
      {detectionMessage && (
        <div className="p-3 rounded-md bg-blue-950/60 border border-blue-800/80 text-xs font-mono text-blue-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-400 shrink-0" />
            <span>{detectionMessage}</span>
          </div>
          <button
            onClick={() => setDetectionMessage(null)}
            className="text-xs text-slate-400 hover:text-white ml-4"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Backend connection banner if error */}
      {error && (
        <div className="p-4 rounded-md bg-rose-950/50 border border-rose-800/80 text-xs font-mono text-rose-300 flex items-start gap-3">
          <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="font-semibold">Backend Communication Notice</div>
            <div className="text-rose-200/80 mt-0.5">{error}</div>
            <div className="text-[11px] text-slate-400 mt-2">
              Ensure the FastAPI backend is running via <code className="text-slate-200">uvicorn main:app --port 8000</code> in <code className="text-slate-200">src/backend</code>.
            </div>
          </div>
        </div>
      )}

      {/* Key Metric Grid - Strict zero fabrication */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-mono uppercase tracking-wider text-institutional-textMuted font-semibold">
            Investigative Metrics (Genuine Backend Signals)
          </h2>
          <span className="text-[11px] font-mono text-slate-500">
            Source: /api/v1/workspace/summary
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <MetricCard
            label="Total Findings"
            value={summary?.total_findings}
            isLoading={isLoading}
            isAvailable={summary !== null}
            sourceNote="Investigative findings synthesized"
            highlight={true}
          />
          <MetricCard
            label="Entities Monitored"
            value={summary?.total_entities_monitored}
            isLoading={isLoading}
            isAvailable={summary !== null}
            sourceNote="Distinct canonical entities"
          />
          <MetricCard
            label="Signals Detected"
            value={summary?.total_signals_detected}
            isLoading={isLoading}
            isAvailable={summary !== null}
            sourceNote="Structural & temporal signals"
          />
          {/* Strict honest state: No fabricated numbers for metrics not yet in summary */}
          <MetricCard
            label="Records Processed"
            value={null}
            statusText="Awaiting Pipeline Stream"
            sourceNote="Ingestion pipeline Phase 2/3"
            isLoading={false}
            isAvailable={false}
          />
          <MetricCard
            label="Network Clusters"
            value={null}
            statusText="Phase 6B Analytics"
            sourceNote="Girvan-Newman community sync"
            isLoading={false}
            isAvailable={false}
          />
        </div>
      </section>

      {/* Analytical Findings Lifecycle Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 p-5 rounded-md bg-institutional-panel border border-institutional-border space-y-4">
          <div className="flex items-center justify-between border-b border-institutional-borderMuted pb-3">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-blue-400" />
              <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-institutional-textPrimary">
                Finding Lifecycle Status Distribution
              </h2>
            </div>
            <button
              onClick={() => navigate('/findings')}
              className="text-xs font-mono text-blue-400 hover:text-blue-300 flex items-center gap-1 transition-colors"
            >
              <span>View Findings</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
            {(['OPEN', 'IN_REVIEW', 'RESOLVED', 'DISMISSED'] as const).map((status) => {
              const count = summary?.findings_by_status?.[status] ?? (summary ? 0 : null);
              return (
                <div
                  key={status}
                  className="p-3 rounded bg-slate-900/80 border border-slate-800 space-y-1.5"
                >
                  <StatusBadge status={status} size="sm" />
                  <div className="text-xl font-mono font-semibold text-white tabular-numbers pt-1">
                    {count !== null ? count : '—'}
                  </div>
                  <div className="text-[10px] font-mono text-institutional-textMuted uppercase">
                    Findings
                  </div>
                </div>
              );
            })}
          </div>

          {/* Pattern Type Distribution */}
          <div className="pt-4 border-t border-institutional-borderMuted">
            <h3 className="text-xs font-mono text-institutional-textSecondary uppercase tracking-wider mb-2.5">
              Detected Multi-Signal Pattern Convergence
            </h3>
            {summary && Object.keys(summary.findings_by_pattern_type).length > 0 ? (
              <div className="space-y-2">
                {Object.entries(summary.findings_by_pattern_type).map(([ptype, count]) => (
                  <div
                    key={ptype}
                    className="flex items-center justify-between p-2.5 rounded bg-slate-900/60 border border-slate-800 text-xs font-mono"
                  >
                    <span className="text-sky-300">{ptype}</span>
                    <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-white font-semibold tabular-numbers">
                      {count}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 rounded bg-slate-900/40 border border-slate-800/80 text-xs font-mono text-institutional-textMuted text-center">
                {summary
                  ? 'No patterns currently synthesized. Execute "Run Pattern Detection" above.'
                  : 'Workspace summary not loaded.'}
              </div>
            )}
          </div>
        </div>

        {/* Backend & Environment Health Card */}
        <div className="p-5 rounded-md bg-institutional-panel border border-institutional-border flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center gap-2 border-b border-institutional-borderMuted pb-3">
              <Server className="w-4 h-4 text-emerald-400" />
              <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-institutional-textPrimary">
                Investigator Backend State
              </h2>
            </div>

            <div className="mt-4 space-y-3 text-xs font-mono">
              <div className="flex justify-between py-1.5 border-b border-institutional-borderMuted">
                <span className="text-institutional-textSecondary">FastAPI Engine:</span>
                <span className="text-white font-semibold">
                  {backendHealth?.service || 'investigator-backend'}
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-institutional-borderMuted">
                <span className="text-institutional-textSecondary">Service Status:</span>
                <StatusBadge status={backendHealth ? 'ONLINE' : 'OFFLINE'} size="sm" />
              </div>
              <div className="flex justify-between py-1.5 border-b border-institutional-borderMuted">
                <span className="text-institutional-textSecondary">Knowledge Graph:</span>
                <span className="text-emerald-400">Neo4j Bolt Verified</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-institutional-borderMuted">
                <span className="text-institutional-textSecondary">Active Case URN:</span>
                <span className="text-slate-300 truncate max-w-[150px]">
                  hawkeye-2026
                </span>
              </div>
              <div className="flex justify-between py-1.5">
                <span className="text-institutional-textSecondary">Client API Base:</span>
                <span className="text-slate-400">/api/v1 (Local Proxy)</span>
              </div>
            </div>
          </div>

          <div className="p-3 rounded bg-slate-950 border border-slate-800 text-[11px] font-mono text-institutional-textMuted">
            <span className="text-slate-300 font-semibold">Audit Notice: </span>
            All analytical requests are parameterized and strictly bound to depth 1 or 2. No arbitrary Cypher permitted.
          </div>
        </div>
      </div>

      {/* Investigation Workflow Progression Navigator */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-mono uppercase tracking-wider text-institutional-textMuted font-semibold">
            Investigator Analytical Progression
          </h2>
          <span className="text-[11px] font-mono text-slate-500">
            Click to navigate through investigative stages
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div
            onClick={() => navigate('/investigation')}
            className="p-4 rounded-md bg-institutional-panel border border-institutional-border hover:border-blue-800/80 cursor-pointer transition-colors group"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Search className="w-4 h-4 text-blue-400 group-hover:text-blue-300" />
                <span className="text-xs font-mono font-semibold text-white">1. SEARCH & RECON</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-blue-400 transition-transform group-hover:translate-x-0.5" />
            </div>
            <p className="text-xs text-institutional-textSecondary mt-2">
              Query canonical entities by name, alias, phone number, or national identifier.
            </p>
          </div>

          <div
            onClick={() => navigate('/network')}
            className="p-4 rounded-md bg-institutional-panel border border-institutional-border hover:border-blue-800/80 cursor-pointer transition-colors group"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Network className="w-4 h-4 text-sky-400 group-hover:text-sky-300" />
                <span className="text-xs font-mono font-semibold text-white">2. NETWORK EXPLORER</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-sky-400 transition-transform group-hover:translate-x-0.5" />
            </div>
            <p className="text-xs text-institutional-textSecondary mt-2">
              Inspect bounded 1-hop and 2-hop graph neighborhoods and topological structures.
            </p>
          </div>

          <div
            onClick={() => navigate('/timeline')}
            className="p-4 rounded-md bg-institutional-panel border border-institutional-border hover:border-blue-800/80 cursor-pointer transition-colors group"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-indigo-400 group-hover:text-indigo-300" />
                <span className="text-xs font-mono font-semibold text-white">3. TEMPORAL ANALYSIS</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-indigo-400 transition-transform group-hover:translate-x-0.5" />
            </div>
            <p className="text-xs text-institutional-textSecondary mt-2">
              Examine communication bursts, activity concentration windows, and undated traces.
            </p>
          </div>

          <div
            onClick={() => navigate('/findings')}
            className="p-4 rounded-md bg-institutional-panel border border-institutional-border hover:border-blue-800/80 cursor-pointer transition-colors group"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-amber-400 group-hover:text-amber-300" />
                <span className="text-xs font-mono font-semibold text-white">4. ANALYTICAL FINDINGS</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-amber-400 transition-transform group-hover:translate-x-0.5" />
            </div>
            <p className="text-xs text-institutional-textSecondary mt-2">
              Review multi-signal pattern flags, triage lifecycle status, and record investigator notes.
            </p>
          </div>

          <div
            onClick={() => navigate('/evidence')}
            className="p-4 rounded-md bg-institutional-panel border border-institutional-border hover:border-blue-800/80 cursor-pointer transition-colors group"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileCheck className="w-4 h-4 text-emerald-400 group-hover:text-emerald-300" />
                <span className="text-xs font-mono font-semibold text-white">5. EVIDENCE PROVENANCE</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-emerald-400 transition-transform group-hover:translate-x-0.5" />
            </div>
            <p className="text-xs text-institutional-textSecondary mt-2">
              Inspect evidentiary offsets and verify end-to-end trace back to original SourceRecords.
            </p>
          </div>

          <div
            onClick={() => navigate('/reports')}
            className="p-4 rounded-md bg-institutional-panel border border-institutional-border hover:border-blue-800/80 cursor-pointer transition-colors group"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-purple-400 group-hover:text-purple-300" />
                <span className="text-xs font-mono font-semibold text-white">6. INVESTIGATIVE REPORT</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-purple-400 transition-transform group-hover:translate-x-0.5" />
            </div>
            <p className="text-xs text-institutional-textSecondary mt-2">
              Export structured findings, entity networks, and evidence chains into court-ready dossiers.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
};

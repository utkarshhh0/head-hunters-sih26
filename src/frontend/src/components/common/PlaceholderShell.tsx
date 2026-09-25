import React from 'react';
import { LucideIcon, ArrowRight, ShieldCheck, Layers, Terminal } from 'lucide-react';

interface PlaceholderShellProps {
  moduleCode: string;
  title: string;
  subtitle: string;
  workflowStep: string;
  icon: LucideIcon;
  targetEndpoints: string[];
  capabilitiesPlanned: string[];
  architecturalContract: string;
}

const WORKFLOW_STEPS = [
  'SEARCH',
  'ENTITY CONTEXT',
  'RELATIONSHIPS',
  'NETWORK',
  'TIME',
  'FINDING',
  'EVIDENCE',
  'REPORT',
];

export const PlaceholderShell: React.FC<PlaceholderShellProps> = ({
  moduleCode,
  title,
  subtitle,
  workflowStep,
  icon: Icon,
  targetEndpoints,
  capabilitiesPlanned,
  architecturalContract,
}) => {
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="border-b border-institutional-border pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-blue-400">
              <Icon className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-slate-800/90 border border-slate-700 text-slate-300">
                  {moduleCode}
                </span>
                <span className="text-xs font-mono text-amber-400/90 uppercase tracking-wider">
                  Phase 6B Target
                </span>
              </div>
              <h1 className="text-xl font-semibold text-institutional-textPrimary tracking-tight mt-1">
                {title}
              </h1>
              <p className="text-xs text-institutional-textSecondary mt-0.5">
                {subtitle}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto text-xs font-mono px-3 py-1.5 rounded bg-slate-900 border border-slate-800 text-slate-400">
            <ShieldCheck className="w-4 h-4 text-slate-400" />
            <span>SHELL INITIALIZED (6A)</span>
          </div>
        </div>

        {/* Workflow Breadcrumb Strip */}
        <div className="mt-4 pt-3 border-t border-institutional-borderMuted">
          <div className="flex items-center gap-1 overflow-x-auto text-[11px] font-mono scrollbar-none py-1">
            <span className="text-institutional-textMuted uppercase mr-2 text-[10px] tracking-wider">
              Investigation Workflow:
            </span>
            {WORKFLOW_STEPS.map((step, idx) => {
              const isCurrent = step.toUpperCase() === workflowStep.toUpperCase();
              return (
                <React.Fragment key={step}>
                  {idx > 0 && <ArrowRight className="w-3 h-3 text-slate-700 shrink-0 mx-0.5" />}
                  <span
                    className={`px-2 py-0.5 rounded shrink-0 border ${
                      isCurrent
                        ? 'bg-blue-950/80 border-blue-700 text-blue-300 font-semibold'
                        : 'bg-slate-900/60 border-slate-800/80 text-slate-500'
                    }`}
                  >
                    {step}
                  </span>
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </div>

      {/* Institutional Readiness & Blueprint Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Module Operational Readiness Box */}
          <div className="p-6 rounded-md bg-institutional-panel border border-institutional-border">
            <div className="flex items-center gap-2 mb-3">
              <Layers className="w-4 h-4 text-blue-400" />
              <h2 className="text-sm font-semibold uppercase tracking-wider text-institutional-textPrimary">
                Component Foundation Status
              </h2>
            </div>
            <p className="text-xs text-institutional-textSecondary leading-relaxed">
              This module route is registered and mounted in the Phase 6A application shell.
              In accordance with Phase 6 scope isolation, no fabricated mock intelligence,
              synthetic nodes, or premature analytical visualizations have been injected into this workspace.
              Internal investigative functionality will be activated during Phase 6B using the centralized API layer.
            </p>

            <div className="mt-5 pt-4 border-t border-institutional-borderMuted">
              <h3 className="text-xs font-mono uppercase text-institutional-textMuted mb-2">
                Planned Functional Capabilities (Phase 6B)
              </h3>
              <ul className="space-y-1.5 text-xs text-slate-300 font-mono">
                {capabilitiesPlanned.map((cap, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-blue-400 select-none">▸</span>
                    <span>{cap}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Architectural Contract Note */}
          <div className="p-5 rounded-md bg-institutional-panel border border-institutional-border">
            <div className="flex items-center gap-2 mb-2">
              <Terminal className="w-4 h-4 text-emerald-400" />
              <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-institutional-textPrimary">
                Backend Domain Contract
              </h2>
            </div>
            <p className="text-xs text-institutional-textSecondary font-mono leading-relaxed">
              {architecturalContract}
            </p>
          </div>
        </div>

        {/* Sidebar API Endpoint Specifications */}
        <div className="space-y-6">
          <div className="p-5 rounded-md bg-institutional-panel border border-institutional-border">
            <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-institutional-textMuted mb-3">
              FastAPI Endpoint Target
            </h2>
            <div className="space-y-2">
              {targetEndpoints.map((ep, idx) => (
                <div
                  key={idx}
                  className="p-2 rounded bg-slate-900 border border-slate-800 text-xs font-mono text-sky-300 break-all"
                >
                  {ep}
                </div>
              ))}
            </div>
            <p className="text-[11px] text-institutional-textMuted mt-3 font-mono">
              Centralized API client wrappers are fully declared in <span className="text-slate-400">src/frontend/src/api</span> and ready for Phase 6B consumption.
            </p>
          </div>

          <div className="p-5 rounded-md bg-institutional-panel border border-institutional-border">
            <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-institutional-textMuted mb-2">
              Investigator Guardrails
            </h2>
            <p className="text-xs text-slate-400 leading-relaxed">
              All findings and topological structures rendered in this module are evidentiary and analytical representations. Guilt or criminality determination remains strictly with the human investigator.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

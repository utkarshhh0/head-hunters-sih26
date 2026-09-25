import React from 'react';

interface MetricCardProps {
  label: string;
  value?: number | string | null;
  statusText?: string;
  sourceNote?: string;
  isLoading?: boolean;
  isAvailable?: boolean;
  highlight?: boolean;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  statusText,
  sourceNote,
  isLoading = false,
  isAvailable = true,
  highlight = false,
}) => {
  return (
    <div
      className={`p-4 rounded-md border transition-colors ${
        highlight
          ? 'bg-institutional-panel border-blue-900/60 shadow-sm shadow-blue-950/20'
          : 'bg-institutional-panel border-institutional-border'
      }`}
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-institutional-textSecondary">
          {label}
        </span>
        {statusText && (
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-institutional-textMuted">
            {statusText}
          </span>
        )}
      </div>

      <div className="min-h-[2.25rem] flex items-baseline gap-2">
        {isLoading ? (
          <div className="h-7 w-20 bg-slate-800/80 animate-pulse rounded" />
        ) : !isAvailable || value === undefined || value === null ? (
          <div className="flex items-baseline gap-2">
            <span className="text-xl font-mono text-slate-500 font-medium">—</span>
            <span className="text-xs font-mono text-slate-500 italic">
              {statusText || 'Unconnected'}
            </span>
          </div>
        ) : (
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-mono font-semibold text-institutional-textPrimary tabular-numbers">
              {typeof value === 'number' ? value.toLocaleString() : value}
            </span>
          </div>
        )}
      </div>

      {sourceNote && (
        <div className="mt-2 pt-2 border-t border-institutional-borderMuted text-[11px] font-mono text-institutional-textMuted truncate">
          {sourceNote}
        </div>
      )}
    </div>
  );
};

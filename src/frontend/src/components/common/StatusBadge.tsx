import React from 'react';
import { FindingStatus } from '../../api/types';

interface StatusBadgeProps {
  status: FindingStatus | 'ONLINE' | 'OFFLINE' | 'CONNECTING' | 'PENDING' | 'ACTIVE' | string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const normalized = status.toUpperCase();

  let colorClasses = 'bg-slate-800 text-slate-300 border-slate-700';
  let dotColor = 'bg-slate-400';

  switch (normalized) {
    case 'OPEN':
    case 'DETECTED':
      colorClasses = 'bg-sky-950/70 text-sky-300 border-sky-800/80';
      dotColor = 'bg-sky-400';
      break;
    case 'IN_REVIEW':
    case 'TRIAGED':
      colorClasses = 'bg-amber-950/70 text-amber-300 border-amber-800/80';
      dotColor = 'bg-amber-400';
      break;
    case 'RESOLVED':
    case 'CONFIRMED':
      colorClasses = 'bg-emerald-950/70 text-emerald-300 border-emerald-800/80';
      dotColor = 'bg-emerald-400';
      break;
    case 'DISMISSED':
      colorClasses = 'bg-slate-900 text-slate-400 border-slate-800';
      dotColor = 'bg-slate-500';
      break;
    case 'ONLINE':
      colorClasses = 'bg-emerald-950/80 text-emerald-300 border-emerald-800';
      dotColor = 'bg-emerald-400 animate-pulse';
      break;
    case 'OFFLINE':
      colorClasses = 'bg-rose-950/80 text-rose-300 border-rose-800';
      dotColor = 'bg-rose-400';
      break;
    case 'CONNECTING':
      colorClasses = 'bg-amber-950/80 text-amber-300 border-amber-800';
      dotColor = 'bg-amber-400 animate-pulse';
      break;
    case 'ACTIVE':
      colorClasses = 'bg-blue-950/70 text-blue-300 border-blue-800/80';
      dotColor = 'bg-blue-400';
      break;
    default:
      colorClasses = 'bg-slate-800/80 text-slate-300 border-slate-700';
      dotColor = 'bg-slate-400';
      break;
  }

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs';

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-mono font-medium rounded border ${sizeClasses} ${colorClasses}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
      <span>{normalized.replace('_', ' ')}</span>
    </span>
  );
};

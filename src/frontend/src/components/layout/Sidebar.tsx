import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Search,
  Users,
  Network,
  Clock,
  Activity,
  FileCheck,
  FileSpreadsheet,
  Shield,
  LogOut,
  ChevronRight,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface NavItem {
  name: string;
  path: string;
  icon: React.ElementType;
  badge?: string;
}

interface NavGroup {
  groupName: string;
  items: NavItem[];
}

const NAVIGATION_GROUPS: NavGroup[] = [
  {
    groupName: 'APPLICATION',
    items: [
      { name: 'Dashboard', path: '/', icon: LayoutDashboard },
      { name: 'Investigation', path: '/investigation', icon: Search },
    ],
  },
  {
    groupName: 'ANALYSIS',
    items: [
      { name: 'Entity Intelligence', path: '/entities', icon: Users },
      { name: 'Network Explorer', path: '/network', icon: Network },
      { name: 'Timeline', path: '/timeline', icon: Clock },
      { name: 'Analytical Findings', path: '/findings', icon: Activity },
    ],
  },
  {
    groupName: 'EVIDENCE',
    items: [
      { name: 'Evidence', path: '/evidence', icon: FileCheck },
    ],
  },
  {
    groupName: 'OUTPUT',
    items: [
      { name: 'Reports', path: '/reports', icon: FileSpreadsheet },
    ],
  },
];

export const Sidebar: React.FC = () => {
  const { session, logout } = useAuth();

  return (
    <aside className="w-64 bg-institutional-panel border-r border-institutional-border flex flex-col shrink-0 min-h-screen">
      {/* Institutional System Header */}
      <div className="p-4 border-b border-institutional-border bg-slate-950/60">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-blue-950 border border-blue-800 flex items-center justify-center text-blue-400 shrink-0">
            <Shield className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-xs font-bold text-white tracking-wider">
                SIH26189
              </span>
              <span className="text-[10px] font-mono px-1 py-0.2 rounded bg-blue-950 border border-blue-800 text-blue-300">
                P-6A
              </span>
            </div>
            <div className="text-[11px] text-institutional-textSecondary font-medium tracking-tight">
              Criminal Network Analysis
            </div>
          </div>
        </div>
      </div>

      {/* Structured Navigation Groups */}
      <nav className="flex-1 py-4 px-2 space-y-6 overflow-y-auto">
        {NAVIGATION_GROUPS.map((group) => (
          <div key={group.groupName}>
            <div className="px-3 pb-2 text-[10px] font-mono font-semibold uppercase tracking-wider text-institutional-textMuted">
              {group.groupName}
            </div>
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    end={item.path === '/'}
                    className={({ isActive }) =>
                      `group flex items-center justify-between px-3 py-2 text-xs rounded transition-colors ${
                        isActive
                          ? 'bg-blue-950/60 border border-blue-900/80 text-white font-medium shadow-sm'
                          : 'text-institutional-textSecondary hover:text-white hover:bg-slate-900/60 border border-transparent'
                      }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <div className="flex items-center gap-2.5">
                          <Icon
                            className={`w-4 h-4 ${
                              isActive ? 'text-blue-400' : 'text-slate-400 group-hover:text-slate-300'
                            }`}
                          />
                          <span>{item.name}</span>
                        </div>
                        {isActive && <ChevronRight className="w-3.5 h-3.5 text-blue-400" />}
                      </>
                    )}
                  </NavLink>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Investigator Clearance / Session Footer */}
      <div className="p-3 border-t border-institutional-border bg-slate-950/60">
        <div className="p-2.5 rounded bg-slate-900/80 border border-institutional-border">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-institutional-textMuted uppercase">
              Investigator Clearance
            </span>
            <span className="text-[10px] font-mono text-emerald-400 font-semibold">
              ACTIVE
            </span>
          </div>
          <div className="text-xs font-mono font-medium text-white truncate mt-0.5">
            {session?.name || 'Authorized Investigator'}
          </div>
          <div className="text-[10px] font-mono text-institutional-textSecondary truncate">
            {session?.badgeId || 'INV-7842'} · {session?.station || 'SCB Intel'}
          </div>

          <button
            onClick={logout}
            className="w-full mt-3 flex items-center justify-center gap-1.5 px-2 py-1 text-xs font-mono rounded bg-slate-800/80 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/80 transition-colors"
          >
            <LogOut className="w-3 h-3 text-slate-400" />
            <span>End Session</span>
          </button>
        </div>
      </div>
    </aside>
  );
};

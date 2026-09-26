import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Lock, AlertCircle, ArrowRight, Server } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const Login: React.FC = () => {
  const { loginDemo, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [badgeId, setBadgeId] = useState('DEMO-USER');
  const [name, setName] = useState('Demo Investigator');

  React.useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loginDemo(badgeId, name);
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-[#0A0E17] flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6">
        {/* System Seal / Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex p-3 rounded-md bg-blue-950/70 border border-blue-800 text-blue-400 mb-1">
            <Shield className="w-8 h-8" />
          </div>
          <div className="flex items-center justify-center gap-2">
            <span className="text-xs font-mono font-bold tracking-widest px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
              SIH26189
            </span>
            <span className="text-xs font-mono text-blue-400 tracking-wider">
              INVESTIGATOR WORKSPACE
            </span>
          </div>
          <h1 className="text-lg font-semibold text-white tracking-tight">
            AI-Powered Criminal Network Analysis
          </h1>
          <p className="text-xs text-institutional-textSecondary max-w-sm mx-auto">
            Analytical intelligence, entity resolution, and topological pattern discovery workspace.
          </p>
        </div>

        {/* Access Box */}
        <div className="p-6 rounded-md bg-institutional-panel border border-institutional-border shadow-xl space-y-5">
          <div className="flex items-center gap-2 pb-3 border-b border-institutional-borderMuted">
            <Lock className="w-4 h-4 text-slate-400" />
            <h2 className="text-xs font-mono uppercase tracking-wider text-institutional-textPrimary font-semibold">
              Demo Workspace Access
            </h2>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-mono uppercase text-institutional-textSecondary mb-1.5">
                Demo User ID
              </label>
              <input
                type="text"
                value={badgeId}
                onChange={(e) => setBadgeId(e.target.value)}
                required
                className="w-full px-3 py-2 text-xs font-mono rounded bg-slate-900 border border-slate-800 focus:border-blue-700 focus:outline-none text-white transition-colors"
                placeholder="DEMO-USER"
              />
            </div>

            <div>
              <label className="block text-xs font-mono uppercase text-institutional-textSecondary mb-1.5">
                Display Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="w-full px-3 py-2 text-xs font-mono rounded bg-slate-900 border border-slate-800 focus:border-blue-700 focus:outline-none text-white transition-colors"
                placeholder="Demo Investigator"
              />
            </div>

            <div>
              <label className="block text-xs font-mono uppercase text-institutional-textMuted mb-1.5">
                Assigned Case Workspace
              </label>
              <div className="w-full px-3 py-2 text-xs font-mono rounded bg-slate-950 border border-slate-850 text-slate-400 select-none">
                OPERATION HAWKEYE [CASE-2026-0814]
              </div>
            </div>

            <button
              type="submit"
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-mono font-medium rounded bg-blue-600 hover:bg-blue-500 text-white shadow-sm transition-colors mt-2"
            >
              <span>Access Investigator Workspace</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </form>

          {/* Institutional clearance note */}
          <div className="pt-3 border-t border-institutional-borderMuted flex items-start gap-2 text-[11px] font-mono text-institutional-textMuted leading-relaxed">
            <AlertCircle className="w-3.5 h-3.5 text-amber-500/80 shrink-0 mt-0.5" />
            <span>
              Restricted analytical prototype. Access is logged. The human investigator remains the decision maker; analytical outputs represent evidentiary patterns rather than guilt determinations.
            </span>
          </div>
        </div>

          {/* Demonstration notice */}
          <div className="pt-3 border-t border-institutional-borderMuted flex items-start gap-2 text-[11px] font-mono text-institutional-textMuted leading-relaxed">
            <AlertCircle className="w-3.5 h-3.5 text-amber-500/80 shrink-0 mt-0.5" />
            <span>
              Controlled demonstration using synthetic data. Analytical findings are intended to support investigator review and do not determine guilt or criminal liability.
            </span>
          </div>

        {/* Backend Endpoint Notice */}
        <div className="text-center">
          <div className="inline-flex items-center gap-1.5 text-[11px] font-mono text-slate-500">
            <Server className="w-3 h-3 text-slate-600" />
            <span>Target Backend: FastAPI /api/v1 (Port 8000)</span>
          </div>
        </div>
      </div>
    </div>
  );
};

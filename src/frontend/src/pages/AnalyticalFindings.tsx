import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams, Link } from "react-router-dom";
import {
  Activity,
  Search,
  Filter,
  RefreshCw,
  Play,
  AlertCircle,
  CheckCircle2,
  Clock,
  FileCheck,
  Network,
  ExternalLink,
  Shield,
  Edit3,
} from 'lucide-react';
import {
  listFindings,
  getFinding,
  updateFindingStatus,
  detectFindings,
  InvestigativeFinding,
  FindingStatus,
} from '../api';
import { StatusBadge } from '../components/common/StatusBadge';

const ALL_STATUSES: FindingStatus[] = ['OPEN', 'IN_REVIEW', 'RESOLVED', 'DISMISSED'];

const VALID_TRANSITIONS: Record<FindingStatus, FindingStatus[]> = {
  OPEN: ['IN_REVIEW', 'DISMISSED'],
  IN_REVIEW: ['RESOLVED', 'DISMISSED', 'OPEN'],
  RESOLVED: ['IN_REVIEW', 'OPEN'],
  DISMISSED: ['OPEN', 'IN_REVIEW'],
};

export const AnalyticalFindings: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  // URL query params
  const activeFindingId = (searchParams.get('id') || '').trim();
  const entityFilter = (searchParams.get('entity_id') || '').trim();
  const statusFilterParam = searchParams.get('status') as FindingStatus | null;

  // Findings state
  const [findings, setFindings] = useState<InvestigativeFinding[]>([]);
  const [selectedFinding, setSelectedFinding] = useState<InvestigativeFinding | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Filter state
  const [selectedStatusFilter, setSelectedStatusFilter] = useState<string>(statusFilterParam || 'ALL');
  const [selectedPatternFilter, setSelectedPatternFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Triage update form state
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [updateSuccess, setUpdateSuccess] = useState<string | null>(null);
  const [targetStatus, setTargetStatus] = useState<FindingStatus>('OPEN');
  const [investigatorNotes, setInvestigatorNotes] = useState<string>('');

  // Detection pipeline execution state
  const [isDetecting, setIsDetecting] = useState<boolean>(false);
  const [detectionMessage, setDetectionMessage] = useState<string | null>(null);

  // --------------------------------------------------------------------------
  // Fetch Findings
  // --------------------------------------------------------------------------
  const fetchFindings = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params: { entity_id?: string; status?: FindingStatus } = {};
      if (entityFilter) {
        params.entity_id = entityFilter;
      }
      if (selectedStatusFilter !== 'ALL' && ALL_STATUSES.includes(selectedStatusFilter as FindingStatus)) {
        params.status = selectedStatusFilter as FindingStatus;
      }

      const records = await listFindings(params);
      setFindings(records);

      // Select active finding if ID in URL
      if (activeFindingId) {
        const found = records.find(f => f.finding_id === activeFindingId);
        if (found) {
          setSelectedFinding(found);
          setTargetStatus(found.status);
          setInvestigatorNotes(found.investigator_notes || '');
        } else {
          // If not in filtered list, try direct fetch
          try {
            const single = await getFinding(activeFindingId);
            setSelectedFinding(single);
            setTargetStatus(single.status);
            setInvestigatorNotes(single.investigator_notes || '');
          } catch {
            setSelectedFinding(null);
          }
        }
      } else if (records.length > 0 && !selectedFinding) {
        setSelectedFinding(records[0]);
        setTargetStatus(records[0].status);
        setInvestigatorNotes(records[0].investigator_notes || '');
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve analytical findings';
      setError(msg);
      setFindings([]);
    } finally {
      setIsLoading(false);
    }
  }, [entityFilter, selectedStatusFilter, activeFindingId]);

  useEffect(() => {
    fetchFindings();
  }, [fetchFindings]);

  // Sync selected finding notes and status when active item changes
  const handleSelectFinding = (finding: InvestigativeFinding) => {
    setSelectedFinding(finding);
    setTargetStatus(finding.status);
    setInvestigatorNotes(finding.investigator_notes || '');
    setUpdateError(null);
    setUpdateSuccess(null);
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      next.set('id', finding.finding_id);
      return next;
    });
  };

  // --------------------------------------------------------------------------
  // Execute Pattern Detection Pipeline
  // --------------------------------------------------------------------------
  const handleRunDetection = async () => {
    setIsDetecting(true);
    setDetectionMessage(null);
    try {
      const discovered = await detectFindings({
        entityId: entityFilter || undefined,
        limit: 500,
      });
      setDetectionMessage(
        `Analysis executed successfully: ${discovered.length} finding(s) discovered and registered in workspace.`
      );
      await fetchFindings();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Pattern detection orchestration failed';
      setDetectionMessage(`Detection error: ${msg}`);
    } finally {
      setIsDetecting(false);
    }
  };

  // --------------------------------------------------------------------------
  // Update Finding Status and Notes (PATCH /api/v1/findings/{id}/status)
  // --------------------------------------------------------------------------
  const handleStatusUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFinding) return;

    setIsUpdating(true);
    setUpdateError(null);
    setUpdateSuccess(null);

    try {
      const updated = await updateFindingStatus(selectedFinding.finding_id, {
        status: targetStatus,
        notes: investigatorNotes.trim() || null,
      });

      setSelectedFinding(updated);
      setFindings(prev => prev.map(f => f.finding_id === updated.finding_id ? updated : f));
      setUpdateSuccess(`Lifecycle status updated to ${updated.status} successfully.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update finding status';
      setUpdateError(msg);
    } finally {
      setIsUpdating(false);
    }
  };

  // --------------------------------------------------------------------------
  // Filtered Findings Computation
  // --------------------------------------------------------------------------
  const filteredFindings = useMemo(() => {
    return findings.filter(f => {
      if (selectedStatusFilter !== 'ALL' && f.status !== selectedStatusFilter) {
        return false;
      }
      if (selectedPatternFilter !== 'ALL' && f.pattern_type !== selectedPatternFilter) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchesTitle = f.title.toLowerCase().includes(q);
        const matchesId = f.finding_id.toLowerCase().includes(q);
        const matchesSummary = f.summary.toLowerCase().includes(q);
        const matchesEntity = f.entity_ids.some(eid => eid.toLowerCase().includes(q));
        if (!matchesTitle && !matchesId && !matchesSummary && !matchesEntity) {
          return false;
        }
      }
      return true;
    });
  }, [findings, selectedStatusFilter, selectedPatternFilter, searchQuery]);

  // Pattern types for filter dropdown
  const patternTypes = useMemo(() => {
    const types = new Set<string>();
    for (const f of findings) {
      if (f.pattern_type) types.add(f.pattern_type);
    }
    return Array.from(types);
  }, [findings]);

  // Counts by status
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { ALL: findings.length, OPEN: 0, IN_REVIEW: 0, RESOLVED: 0, DISMISSED: 0 };
    for (const f of findings) {
      counts[f.status] = (counts[f.status] || 0) + 1;
    }
    return counts;
  }, [findings]);

  // Allowed transitions for selected finding
  const allowedTransitions = selectedFinding ? VALID_TRANSITIONS[selectedFinding.status] || [] : [];

  return (
    <div className="space-y-6">
      {/* Module Bar */}
      <div className="border-b border-institutional-border pb-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950/80 border border-blue-800 text-blue-300 font-semibold tracking-wide">
              MOD-05-FND
            </span>
            <span className="text-xs font-mono text-slate-400">ANALYTICAL FINDINGS & TRIAGE</span>
            {entityFilter && (
              <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-[10px] font-mono text-slate-300">
                FILTERED BY: {entityFilter}
              </span>
            )}
          </div>
          <h1 className="text-xl font-mono font-semibold text-white tracking-tight mt-1 flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-400" />
            <span>Analytical Findings</span>
          </h1>
          <p className="text-xs font-mono text-slate-400 mt-1">
            Deterministic multi-signal pattern detections, investigator triage lifecycle, and evidence provenance links.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {entityFilter && (
            <button
              onClick={() => {
                setSearchParams({});
              }}
              className="px-2.5 py-1.5 rounded bg-slate-900 border border-slate-700 text-xs font-mono text-slate-300 hover:text-white transition-colors"
            >
              Clear Entity Filter
            </button>
          )}

          <button
            onClick={fetchFindings}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>

          <button
            onClick={handleRunDetection}
            disabled={isDetecting}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-medium rounded bg-blue-600 hover:bg-blue-500 text-white transition-colors shadow-sm disabled:opacity-50"
          >
            <Play className={`w-3.5 h-3.5 ${isDetecting ? 'animate-spin' : ''}`} />
            <span>{isDetecting ? 'Detecting...' : 'Run Detection Pipeline'}</span>
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-3 rounded-md bg-rose-950/40 border border-rose-800/70 text-xs font-mono text-rose-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="text-slate-400 hover:text-white"
          >
            ✕
          </button>
        </div>
      )}

      {/* Detection status message banner */}
      {detectionMessage && (
        <div className="p-3 rounded-md bg-blue-950/40 border border-blue-800/70 text-xs font-mono text-blue-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-400 shrink-0" />
            <span>{detectionMessage}</span>
          </div>
          <button
            onClick={() => setDetectionMessage(null)}
            className="text-slate-400 hover:text-white"
          >
            ✕
          </button>
        </div>
      )}

      {/* Status Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-institutional-border pb-3">
        {(['ALL', 'OPEN', 'IN_REVIEW', 'RESOLVED', 'DISMISSED'] as const).map((st) => (
          <button
            key={st}
            onClick={() => setSelectedStatusFilter(st)}
            className={`px-3 py-1.5 rounded text-xs font-mono transition-colors flex items-center gap-1.5 ${
              selectedStatusFilter === st
                ? 'bg-blue-600 text-white font-medium'
                : 'bg-slate-900/80 text-slate-400 hover:text-slate-200 border border-slate-800'
            }`}
          >
            <span>{st}</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-950/60 text-slate-300 font-bold">
              {statusCounts[st] || 0}
            </span>
          </button>
        ))}

        {patternTypes.length > 0 && (
          <div className="ml-auto flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-slate-500" />
            <select
              value={selectedPatternFilter}
              onChange={(e) => setSelectedPatternFilter(e.target.value)}
              className="bg-slate-900 text-slate-300 border border-slate-700 rounded px-2.5 py-1 text-xs font-mono focus:outline-none focus:border-blue-500"
            >
              <option value="ALL">All Pattern Types</option>
              {patternTypes.map((pt) => (
                <option key={pt} value={pt}>{pt}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Main Two-Column Layout */}
      {findings.length === 0 && !isLoading ? (
        <div className="p-12 rounded-md bg-institutional-panel border border-institutional-border text-center space-y-4">
          <Activity className="w-10 h-10 text-slate-600 mx-auto" />
          <div className="space-y-1">
            <h2 className="text-sm font-mono font-semibold text-slate-300">
              No Analytical Findings Registered in Workspace
            </h2>
            <p className="text-xs font-mono text-slate-500 max-w-md mx-auto">
              The investigator workspace currently has no active findings. Execute the multi-signal detection pipeline to identify structural hubs and temporal burst patterns.
            </p>
          </div>
          <div className="pt-2">
            <button
              onClick={handleRunDetection}
              disabled={isDetecting}
              className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-xs font-mono font-medium text-white transition-colors flex items-center justify-center gap-2 mx-auto disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5" />
              <span>{isDetecting ? 'Running Detection...' : 'Run Pattern Detection Pipeline'}</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Left Column: Findings Inventory List (5 cols) */}
          <div className="lg:col-span-5 space-y-3">
            {/* Search filter input */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search findings by title, ID, or entity..."
                className="w-full pl-8 pr-3 py-1.5 text-xs font-mono rounded bg-slate-900/90 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
            </div>

            {filteredFindings.length === 0 ? (
              <div className="p-6 rounded bg-institutional-panel border border-institutional-border text-center text-xs font-mono text-slate-500">
                No findings match the active filters.
              </div>
            ) : (
              <div className="space-y-2.5 max-h-[750px] overflow-y-auto pr-1">
                {filteredFindings.map((finding) => {
                  const isSelected = selectedFinding?.finding_id === finding.finding_id;
                  return (
                    <div
                      key={finding.finding_id}
                      onClick={() => handleSelectFinding(finding)}
                      className={`p-3.5 rounded-md border cursor-pointer transition-colors space-y-2 ${
                        isSelected
                          ? 'bg-slate-900 border-blue-500 shadow-sm'
                          : 'bg-institutional-panel border-institutional-border hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-950 border border-slate-800 text-sky-300 font-semibold truncate">
                          {finding.pattern_type || 'ANALYTICAL_PATTERN'}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <StatusBadge status={finding.status} />
                          <span className="text-[10px] font-mono text-slate-400">
                            {(finding.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                      </div>

                      <div className="text-xs font-mono font-bold text-white line-clamp-2">
                        {finding.title}
                      </div>

                      <p className="text-[11px] font-mono text-slate-400 line-clamp-2 leading-relaxed">
                        {finding.summary}
                      </p>

                      <div className="flex items-center justify-between text-[10px] font-mono text-slate-500 border-t border-slate-800/60 pt-2">
                        <span>{finding.entity_ids.length} Entities · {finding.evidence_ids.length} Evidence</span>
                        <span className="truncate max-w-[140px]">{finding.created_at?.slice(0, 10)}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Right Column: Finding Detail Dossier & Triage (7 cols) */}
          <div className="lg:col-span-7 bg-institutional-panel border border-institutional-border rounded-md p-5 space-y-5">
            {selectedFinding ? (
              <div className="space-y-5">
                {/* Dossier Header */}
                <div className="border-b border-institutional-border pb-4 space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950 border border-blue-800 text-blue-300 font-semibold">
                        {selectedFinding.pattern_type || 'FINDING'}
                      </span>
                      <StatusBadge status={selectedFinding.status} />
                    </div>
                    <span className="text-xs font-mono text-slate-400">
                      Confidence: <strong className="text-white">{(selectedFinding.confidence * 100).toFixed(0)}%</strong>
                    </span>
                  </div>

                  <h2 className="text-base font-mono font-bold text-white tracking-tight">
                    {selectedFinding.title}
                  </h2>

                  <div className="text-[11px] font-mono text-slate-500 select-all break-all">
                    {selectedFinding.finding_id}
                  </div>
                </div>

                {/* Primary Action Row: Provenance -> Evidence */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <Link
                    to={`/evidence?finding_id=${encodeURIComponent(selectedFinding.finding_id)}`}
                    className="p-2.5 rounded bg-blue-600 hover:bg-blue-500 text-white font-mono text-xs font-medium flex items-center justify-center gap-1.5 transition-colors shadow-sm"
                  >
                    <FileCheck className="w-3.5 h-3.5" />
                    <span>Inspect Evidence</span>
                  </Link>

                  {selectedFinding.entity_ids.length > 0 && (
                    <Link
                      to={`/network?focus=${encodeURIComponent(selectedFinding.entity_ids[0])}`}
                      className="p-2.5 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 font-mono text-xs flex items-center justify-center gap-1.5 transition-colors"
                    >
                      <Network className="w-3.5 h-3.5 text-sky-400" />
                      <span>Network Subgraph</span>
                    </Link>
                  )}

                  {selectedFinding.entity_ids.length > 0 && (
                    <Link
                      to={`/timeline?entity_id=${encodeURIComponent(selectedFinding.entity_ids[0])}`}
                      className="p-2.5 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 font-mono text-xs flex items-center justify-center gap-1.5 transition-colors"
                    >
                      <Clock className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Timeline Context</span>
                    </Link>
                  )}
                </div>

                {/* Analytical Explanation & Summary */}
                <div className="space-y-1.5 text-xs font-mono">
                  <div className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                    Analytical Summary
                  </div>
                  <div className="p-3 rounded bg-slate-900/60 border border-slate-800/80 text-slate-200 leading-relaxed">
                    {selectedFinding.summary}
                  </div>
                </div>

                {/* Observed Time Window */}
                {selectedFinding.time_window?.start_time && (
                  <div className="space-y-1 text-xs font-mono">
                    <div className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                      Observed Temporal Window
                    </div>
                    <div className="p-2.5 rounded bg-slate-900/60 border border-slate-800 text-slate-300 flex items-center gap-2">
                      <Clock className="w-3.5 h-3.5 text-sky-400" />
                      <span>
                        {selectedFinding.time_window.start_time} → {selectedFinding.time_window.end_time || 'Present'}
                      </span>
                    </div>
                  </div>
                )}

                {/* Caveats and Analytical Limitations */}
                {selectedFinding.caveats && selectedFinding.caveats.length > 0 && (
                  <div className="space-y-1.5 text-xs font-mono">
                    <div className="text-slate-400 font-semibold uppercase tracking-wider text-[10px] flex items-center gap-1">
                      <Shield className="w-3.5 h-3.5 text-amber-400" />
                      <span>Investigative Caveats & Limitations</span>
                    </div>
                    <ul className="space-y-1">
                      {selectedFinding.caveats.map((c, i) => (
                        <li key={i} className="text-slate-400 text-[11px] list-disc list-inside">
                          {c}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Involved Canonical Entities */}
                <div className="space-y-2 text-xs font-mono">
                  <div className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                    Involved Canonical Entities ({selectedFinding.entity_ids.length})
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {selectedFinding.entity_ids.map((eid) => (
                      <div
                        key={eid}
                        className="p-2 rounded bg-slate-900/70 border border-slate-800 flex items-center justify-between gap-2"
                      >
                        <span className="text-[11px] text-slate-200 truncate select-all">{eid}</span>
                        <div className="flex items-center gap-1">
                          <Link
                            to={`/entities?id=${encodeURIComponent(eid)}`}
                            className="p-1 rounded text-slate-400 hover:text-blue-400 hover:bg-slate-800"
                            title="Inspect Entity"
                          >
                            <ExternalLink className="w-3 h-3" />
                          </Link>
                          <Link
                            to={`/timeline?entity_id=${encodeURIComponent(eid)}`}
                            className="p-1 rounded text-slate-400 hover:text-emerald-400 hover:bg-slate-800"
                            title="View Timeline"
                          >
                            <Clock className="w-3 h-3" />
                          </Link>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Contributing Signals & Evidence References */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1 text-xs font-mono">
                  <div className="p-3 rounded bg-slate-900/50 border border-slate-800 space-y-1">
                    <span className="text-slate-500 uppercase text-[10px]">Contributing Signals</span>
                    <div className="text-white font-bold">{selectedFinding.signal_ids.length} signals</div>
                    <div className="text-[10px] text-slate-500 truncate">
                      {selectedFinding.signal_ids.join(', ')}
                    </div>
                  </div>

                  <div className="p-3 rounded bg-slate-900/50 border border-slate-800 space-y-1">
                    <span className="text-slate-500 uppercase text-[10px]">Evidence References</span>
                    <div className="text-white font-bold">{selectedFinding.evidence_ids.length} items</div>
                    <div className="text-[10px] text-slate-500 truncate">
                      {selectedFinding.evidence_ids.join(', ')}
                    </div>
                  </div>
                </div>

                {/* Triage & Lifecycle Status Management Form */}
                <div className="p-4 rounded-md bg-slate-950 border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                    <div className="text-xs font-mono font-semibold text-slate-300 flex items-center gap-1.5">
                      <Edit3 className="w-3.5 h-3.5 text-blue-400" />
                      <span>Investigator Triage & Lifecycle Management</span>
                    </div>
                    <span className="text-[10px] font-mono text-slate-500">
                      CURRENT: <strong className="text-slate-300">{selectedFinding.status}</strong>
                    </span>
                  </div>

                  {updateSuccess && (
                    <div className="p-2 rounded bg-emerald-950/60 border border-emerald-800 text-[11px] font-mono text-emerald-300">
                      {updateSuccess}
                    </div>
                  )}

                  {updateError && (
                    <div className="p-2 rounded bg-rose-950/60 border border-rose-800 text-[11px] font-mono text-rose-300">
                      {updateError}
                    </div>
                  )}

                  <form onSubmit={handleStatusUpdate} className="space-y-3 text-xs font-mono">
                    <div className="space-y-1">
                      <label className="text-[10px] text-slate-400 uppercase tracking-wider">
                        Transition Lifecycle Status:
                      </label>
                      <select
                        value={targetStatus}
                        onChange={(e) => setTargetStatus(e.target.value as FindingStatus)}
                        className="w-full bg-slate-900 text-white border border-slate-700 rounded px-3 py-1.5 focus:outline-none focus:border-blue-500"
                      >
                        <option value={selectedFinding.status}>
                          {selectedFinding.status} (Current)
                        </option>
                        {allowedTransitions.map((st) => (
                          <option key={st} value={st}>
                            → Transition to {st}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] text-slate-400 uppercase tracking-wider">
                        Investigator Assessment Notes:
                      </label>
                      <textarea
                        value={investigatorNotes}
                        onChange={(e) => setInvestigatorNotes(e.target.value)}
                        placeholder="Add investigative justification, corroboration details, or dismissal rationale..."
                        rows={3}
                        className="w-full bg-slate-900 text-white border border-slate-700 rounded p-2.5 text-xs font-mono focus:outline-none focus:border-blue-500 placeholder-slate-600"
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={isUpdating}
                      className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white font-mono text-xs font-medium transition-colors shadow-sm flex items-center gap-1.5 disabled:opacity-50"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>{isUpdating ? 'Saving...' : 'Update Finding Lifecycle'}</span>
                    </button>
                  </form>
                </div>
              </div>
            ) : (
              <div className="p-12 text-center text-xs font-mono text-slate-500 space-y-2">
                <Activity className="w-8 h-8 text-slate-700 mx-auto" />
                <div>Select a finding from the list to inspect details and perform triage.</div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

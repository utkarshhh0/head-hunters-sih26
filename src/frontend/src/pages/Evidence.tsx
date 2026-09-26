import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  FileCheck,
  FileText,
  Database,
  Search,
  ArrowLeft,
  ArrowRight,
  ExternalLink,
  Clock,
  Activity,
  AlertCircle,
  Layers,
  Network,
  Copy,
  Check,
  User,
  Phone,
  Car,
  MapPin,
  Building2,
  CreditCard,
  Fingerprint,
  ShieldCheck,
  Binary,
  RefreshCw,
} from 'lucide-react';
import {
  getFindingProvenance,
  listFindings,
  FindingProvenanceBundle,
  InvestigativeFinding,
  EvidenceRecord,
  SourceRecordItem,
} from '../api';
import { StatusBadge } from '../components/common/StatusBadge';

function getEntityIcon(type?: string) {
  switch (type?.toUpperCase()) {
    case 'PERSON':
      return <User className="w-3.5 h-3.5 text-blue-400" />;
    case 'PHONE':
      return <Phone className="w-3.5 h-3.5 text-emerald-400" />;
    case 'VEHICLE':
      return <Car className="w-3.5 h-3.5 text-amber-400" />;
    case 'LOCATION':
      return <MapPin className="w-3.5 h-3.5 text-rose-400" />;
    case 'ORGANIZATION':
      return <Building2 className="w-3.5 h-3.5 text-purple-400" />;
    case 'ACCOUNT':
      return <CreditCard className="w-3.5 h-3.5 text-cyan-400" />;
    default:
      return <Fingerprint className="w-3.5 h-3.5 text-slate-400" />;
  }
}

function getSourceTypeBadgeColor(sourceType?: string): string {
  switch (sourceType?.toUpperCase()) {
    case 'CALL_DETAIL_RECORD':
    case 'CDR':
      return 'bg-emerald-950/80 text-emerald-300 border-emerald-800';
    case 'VEHICLE_TOLL_LOG':
    case 'TOLL_LOG':
      return 'bg-amber-950/80 text-amber-300 border-amber-800';
    case 'BANK_TRANSACTION_LOG':
    case 'FINANCIAL':
      return 'bg-cyan-950/80 text-cyan-300 border-cyan-800';
    case 'POLICE_INCIDENT_REPORT':
    case 'FIR_REPORT':
      return 'bg-rose-950/80 text-rose-300 border-rose-800';
    default:
      return 'bg-slate-900 text-slate-300 border-slate-700';
  }
}

export const Evidence: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  // URL query params: support ?finding_id=... or fallback ?id=...
  const activeFindingId = (searchParams.get('finding_id') || searchParams.get('id') || '').trim();

  // Provenance bundle state
  const [bundle, setBundle] = useState<FindingProvenanceBundle | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Finding picker state (when activeFindingId is empty or invalid)
  const [availableFindings, setAvailableFindings] = useState<InvestigativeFinding[]>([]);
  const [isLoadingFindings, setIsLoadingFindings] = useState<boolean>(false);
  const [findingSearchQuery, setFindingSearchQuery] = useState<string>('');
  const [manualInputId, setManualInputId] = useState<string>('');

  // UI filters within provenance inspection
  const [activeTab, setActiveTab] = useState<'all' | 'evidence' | 'sources' | 'signals' | 'entities'>('all');
  const [evidenceFilterQuery, setEvidenceFilterQuery] = useState<string>('');
  const [selectedSourceType, setSelectedSourceType] = useState<string>('ALL');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [highlightedSourceId, setHighlightedSourceId] = useState<string | null>(null);

  // --------------------------------------------------------------------------
  // Copy to clipboard helper
  // --------------------------------------------------------------------------
  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // --------------------------------------------------------------------------
  // Fetch Available Findings (For Vault Index / Picker)
  // --------------------------------------------------------------------------
  useEffect(() => {
    if (!activeFindingId) {
      let isMounted = true;
      setIsLoadingFindings(true);
      listFindings({ limit: 100 })
        .then((records) => {
          if (isMounted) {
            setAvailableFindings(records);
          }
        })
        .catch(() => {
          if (isMounted) setAvailableFindings([]);
        })
        .finally(() => {
          if (isMounted) setIsLoadingFindings(false);
        });
      return () => {
        isMounted = false;
      };
    }
  }, [activeFindingId]);

  // --------------------------------------------------------------------------
  // Fetch Finding Provenance Bundle
  // --------------------------------------------------------------------------
  const fetchProvenance = useCallback(async (id: string) => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await getFindingProvenance(id);
      setBundle(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve finding provenance bundle';
      setError(msg);
      setBundle(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeFindingId) {
      fetchProvenance(activeFindingId);
    } else {
      setBundle(null);
    }
  }, [activeFindingId, fetchProvenance]);

  // Jump to Source Record helper
  const handleJumpToSource = (sourceId: string) => {
    setHighlightedSourceId(sourceId);
    setActiveTab('all');
    setTimeout(() => {
      const el = document.getElementById(`source-record-${sourceId}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 100);
  };

  // Filtered evidence items
  const filteredEvidence = useMemo(() => {
    if (!bundle?.evidence) return [];
    return bundle.evidence.filter((item: EvidenceRecord) => {
      const matchesType =
        selectedSourceType === 'ALL' ||
        item.source_type?.toUpperCase() === selectedSourceType.toUpperCase();
      const matchesQuery =
        !evidenceFilterQuery ||
        item.evidence_id?.toLowerCase().includes(evidenceFilterQuery.toLowerCase()) ||
        item.document_name?.toLowerCase().includes(evidenceFilterQuery.toLowerCase()) ||
        item.raw_snippet?.toLowerCase().includes(evidenceFilterQuery.toLowerCase()) ||
        item.source_record_id?.toLowerCase().includes(evidenceFilterQuery.toLowerCase());
      return matchesType && matchesQuery;
    });
  }, [bundle, evidenceFilterQuery, selectedSourceType]);

  // Unique source types in evidence
  const uniqueSourceTypes = useMemo(() => {
    if (!bundle?.evidence) return [];
    const set = new Set<string>();
    bundle.evidence.forEach((e) => {
      if (e.source_type) set.add(e.source_type);
    });
    return Array.from(set);
  }, [bundle]);

  // Filtered available findings in index
  const filteredAvailableFindings = useMemo(() => {
    if (!findingSearchQuery.trim()) return availableFindings;
    const q = findingSearchQuery.toLowerCase();
    return availableFindings.filter(
      (f) =>
        f.finding_id.toLowerCase().includes(q) ||
        f.title.toLowerCase().includes(q) ||
        (f.pattern_type && f.pattern_type.toLowerCase().includes(q))
    );
  }, [availableFindings, findingSearchQuery]);

  // --------------------------------------------------------------------------
  // Render: Finding Selector / Vault Index (When no finding_id is provided)
  // --------------------------------------------------------------------------
  if (!activeFindingId) {
    return (
      <div className="space-y-6">
        {/* Header Bar */}
        <div className="border-b border-institutional-border pb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950/80 border border-blue-800 text-blue-300 font-semibold tracking-wide">
                MOD-06-EVID
              </span>
              <span className="text-xs font-mono text-slate-400">EVIDENCE TRACEABILITY</span>
            </div>
            <h1 className="text-xl font-mono font-semibold text-white tracking-tight mt-1 flex items-center gap-2">
              <FileCheck className="w-5 h-5 text-blue-400" />
              <span>Evidence &amp; Source Records</span>
            </h1>
            <p className="text-xs font-mono text-slate-400 mt-1">
              Trace an analytical finding through supporting evidence back to its source record.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-400">
              SYNTHETIC DATA · TRACEABLE SOURCES
            </span>
          </div>
        </div>

        {/* Input Bar for Direct ID Query */}
        <div className="p-6 rounded-md bg-institutional-panel border border-institutional-border space-y-4">
          <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
            <Search className="w-4 h-4 text-blue-400" />
            <span className="font-semibold">INSPECT FINDING PROVENANCE BUNDLE</span>
          </div>
          <p className="text-xs font-mono text-slate-400 leading-relaxed max-w-2xl">
            Select an analytical finding to review its supporting signals, evidence records, and source records.
          </p>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (manualInputId.trim()) {
                setSearchParams({ finding_id: manualInputId.trim() });
              }
            }}
            className="flex flex-col sm:flex-row gap-2 max-w-xl"
          >
            <input
              type="text"
              value={manualInputId}
              onChange={(e) => setManualInputId(e.target.value)}
              placeholder="Enter Finding ID (e.g., finding-001)..."
              className="flex-1 px-3 py-2 text-xs font-mono rounded bg-slate-900/90 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
            <button
              type="submit"
              className="px-4 py-2 text-xs font-mono font-medium rounded bg-blue-600 hover:bg-blue-500 text-white transition-colors flex items-center justify-center gap-1.5"
            >
              <FileCheck className="w-3.5 h-3.5" />
              <span>Load Provenance</span>
            </button>
          </form>
        </div>

        {/* Available Findings List */}
        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <h2 className="text-xs font-mono uppercase tracking-wider text-institutional-textMuted font-semibold flex items-center gap-2">
              <Layers className="w-3.5 h-3.5 text-slate-400" />
              <span>Findings ({filteredAvailableFindings.length})</span>
            </h2>
            <div className="relative w-full sm:w-64">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
              <input
                type="text"
                value={findingSearchQuery}
                onChange={(e) => setFindingSearchQuery(e.target.value)}
                placeholder="Filter findings..."
                className="w-full pl-8 pr-3 py-1.5 text-xs font-mono rounded bg-slate-900 border border-slate-800 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          {isLoadingFindings ? (
            <div className="p-8 rounded-md bg-institutional-panel border border-institutional-border text-center space-y-2">
              <RefreshCw className="w-5 h-5 text-blue-400 animate-spin mx-auto" />
              <div className="text-xs font-mono text-slate-400">Loading findings from workspace...</div>
            </div>
          ) : filteredAvailableFindings.length === 0 ? (
            <div className="p-8 rounded-md bg-institutional-panel border border-institutional-border text-center space-y-2">
              <AlertCircle className="w-6 h-6 text-slate-500 mx-auto" />
              <div className="text-xs font-mono font-medium text-slate-300">No Findings Found</div>
              <p className="text-[11px] font-mono text-slate-500">
                Run pattern detection from Analytical Findings or Dashboard to synthesize findings.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {filteredAvailableFindings.map((f) => (
                <div
                  key={f.finding_id}
                  onClick={() => setSearchParams({ finding_id: f.finding_id })}
                  className="p-4 rounded-md bg-institutional-panel border border-institutional-border hover:border-blue-700/80 cursor-pointer transition-all space-y-3 group"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono text-sky-400 font-semibold px-2 py-0.5 rounded bg-sky-950/60 border border-sky-800/60">
                      {f.pattern_type || 'FINDING'}
                    </span>
                    <StatusBadge status={f.status} size="sm" />
                  </div>

                  <div className="space-y-1">
                    <h3 className="text-xs font-mono font-semibold text-white group-hover:text-blue-300 transition-colors line-clamp-1">
                      {f.title}
                    </h3>
                    <p className="text-[11px] font-mono text-slate-400 line-clamp-2 leading-relaxed">
                      {f.summary}
                    </p>
                  </div>

                  <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-[10px] font-mono text-slate-400">
                    <div className="flex items-center gap-2">
                      <span>{f.entity_ids.length} Entities</span>
                      <span>·</span>
                      <span className="text-amber-400">{f.evidence_ids.length} Evidence</span>
                    </div>
                    <div className="flex items-center gap-1 text-blue-400 group-hover:translate-x-0.5 transition-transform">
                      <span>View Evidence</span>
                      <ArrowRight className="w-3 h-3" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // --------------------------------------------------------------------------
  // Render: Loading State
  // --------------------------------------------------------------------------
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="border-b border-institutional-border pb-4 flex items-center justify-between">
          <button
            onClick={() => setSearchParams({})}
            className="p-1.5 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="text-xs font-mono text-slate-400">Loading provenance bundle...</span>
        </div>

        <div className="p-12 rounded-md bg-institutional-panel border border-institutional-border text-center space-y-3">
          <RefreshCw className="w-6 h-6 text-blue-400 animate-spin mx-auto" />
          <div className="text-xs font-mono text-slate-300 font-semibold">
            Querying typed provenance bundle from backend...
          </div>
          <div className="text-[11px] font-mono text-slate-500 truncate max-w-md mx-auto">
            {activeFindingId}
          </div>
        </div>
      </div>
    );
  }

  // --------------------------------------------------------------------------
  // Render: Error State
  // --------------------------------------------------------------------------
  if (error || !bundle) {
    return (
      <div className="space-y-6">
        <div className="border-b border-institutional-border pb-4 flex items-center justify-between">
          <button
            onClick={() => setSearchParams({})}
            className="p-1.5 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="text-xs font-mono text-rose-400">Provenance Retrieval Error</span>
        </div>

        <div className="p-6 rounded-md bg-rose-950/20 border border-rose-800/60 text-slate-200 space-y-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <div className="text-xs font-mono font-semibold text-rose-300 uppercase tracking-wide">
                Failed to Retrieve Provenance Bundle
              </div>
              <p className="text-xs font-mono text-slate-400">{error || 'Finding not found'}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 pt-2 border-t border-rose-900/40">
            <button
              onClick={() => fetchProvenance(activeFindingId)}
              className="px-3 py-1.5 rounded bg-rose-900/60 hover:bg-rose-900 border border-rose-700 text-xs font-mono text-white transition-colors flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry</span>
            </button>
            <button
              onClick={() => setSearchParams({})}
              className="px-3 py-1.5 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-mono text-slate-300 transition-colors"
            >
              Select Different Finding
            </button>
          </div>
        </div>
      </div>
    );
  }

  const { finding, signals, entities, relationships, evidence, source_records } = bundle;

  // --------------------------------------------------------------------------
  // Render: Provenance Audit View (Finding -> Evidence -> Source Record)
  // --------------------------------------------------------------------------
  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="border-b border-institutional-border pb-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="flex items-start sm:items-center gap-3">
          <button
            onClick={() => setSearchParams({})}
            className="p-1.5 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition-colors shrink-0 mt-1 sm:mt-0"
            title="Return to Finding Selector"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950/80 border border-blue-800 text-blue-300 font-semibold">
                MOD-06-EVID
              </span>
              <span className="text-xs font-mono text-slate-400">EVIDENCE TRACEABILITY</span>
              <StatusBadge status={finding.status} size="sm" />
            </div>
            <h1 className="text-lg font-mono font-bold text-white tracking-tight mt-1 flex items-center gap-2">
              <span>{finding.title}</span>
            </h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-[11px] font-mono text-slate-500 select-all">
                {finding.finding_id}
              </span>
              <button
                onClick={() => handleCopy(finding.finding_id, 'finding-id')}
                className="text-slate-500 hover:text-slate-300 p-0.5 transition-colors"
                title="Copy Finding ID"
              >
                {copiedId === 'finding-id' ? (
                  <Check className="w-3 h-3 text-emerald-400" />
                ) : (
                  <Copy className="w-3 h-3" />
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Pivot Links to Other Modules */}
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={`/findings?id=${encodeURIComponent(finding.finding_id)}`}
            className="px-2.5 py-1.5 rounded bg-slate-900 border border-slate-700 hover:bg-slate-800 text-slate-300 text-xs font-mono flex items-center gap-1.5 transition-colors"
          >
            <Activity className="w-3.5 h-3.5 text-sky-400" />
            <span>Finding Details</span>
          </Link>

          {finding.entity_ids.length > 0 && (
            <>
              <Link
                to={`/network?focus=${encodeURIComponent(finding.entity_ids[0])}`}
                className="px-2.5 py-1.5 rounded bg-slate-900 border border-slate-700 hover:bg-slate-800 text-slate-300 text-xs font-mono flex items-center gap-1.5 transition-colors"
              >
                <Network className="w-3.5 h-3.5 text-blue-400" />
                <span>Explore Network</span>
              </Link>
              <Link
                to={`/timeline?entity_id=${encodeURIComponent(finding.entity_ids[0])}`}
                className="px-2.5 py-1.5 rounded bg-slate-900 border border-slate-700 hover:bg-slate-800 text-slate-300 text-xs font-mono flex items-center gap-1.5 transition-colors"
              >
                <Clock className="w-3.5 h-3.5 text-amber-400" />
                <span>Timeline</span>
              </Link>
            </>
          )}
        </div>
      </div>

      {/* Visual Provenance Flow Bar */}
      <div className="p-4 rounded-md bg-slate-950/80 border border-slate-800 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider font-semibold">
            Finding → Evidence → Source Record
          </span>
          <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Trace Available</span>
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 text-xs font-mono">
          {/* Step 1: Finding */}
          <div className="p-2.5 rounded bg-slate-900/90 border border-blue-900/60 space-y-1">
            <div className="text-[9px] text-blue-400 uppercase font-semibold">Step 1: Finding</div>
            <div className="text-white font-medium truncate">{finding.pattern_type || 'Pattern'}</div>
            <div className="text-[10px] text-slate-400">
              {signals.length} supporting signal{signals.length === 1 ? '' : 's'}
            </div>
          </div>

          {/* Step 2: Signals & Entities */}
          <div className="p-2.5 rounded bg-slate-900/90 border border-slate-800 space-y-1">
            <div className="text-[9px] text-sky-400 uppercase font-semibold">Step 2: Analysis</div>
            <div className="text-white font-medium">{signals.length} Signals</div>
            <div className="text-[10px] text-slate-400">{entities.length} Entities · {relationships.length} Rels</div>
          </div>

          {/* Step 3: Evidence */}
          <div className="p-2.5 rounded bg-slate-900/90 border border-amber-900/60 space-y-1">
            <div className="text-[9px] text-amber-400 uppercase font-semibold">Step 3: Evidence</div>
            <div className="text-white font-medium">{evidence.length} Evidence Records</div>
            <div className="text-[10px] text-slate-400">{uniqueSourceTypes.length} Source Feeds</div>
          </div>

          {/* Step 4: Source Records */}
          <div className="p-2.5 rounded bg-slate-900/90 border border-emerald-900/60 space-y-1">
           <div className="text-[9px] text-emerald-400 uppercase font-semibold">Step 4: Source Records</div>
           <div className="text-white font-medium">{source_records.length} Source Records</div>
           <div className="text-[10px] text-slate-400">Original ingested records</div>
          </div>
        </div>
      </div>

      {/* Navigation Tabs for Auditing */}
      <div className="flex flex-wrap items-center gap-2 border-b border-institutional-border pb-2">
        <button
          onClick={() => setActiveTab('all')}
          className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-colors ${
            activeTab === 'all'
              ? 'bg-blue-600 text-white'
              : 'bg-slate-900 text-slate-400 hover:bg-slate-800'
          }`}
        >
          Full Provenance Chain
        </button>
        <button
          onClick={() => setActiveTab('evidence')}
          className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-colors flex items-center gap-1.5 ${
            activeTab === 'evidence'
              ? 'bg-amber-600 text-white'
              : 'bg-slate-900 text-slate-400 hover:bg-slate-800'
          }`}
        >
          <FileCheck className="w-3.5 h-3.5" />
          <span>Evidence Items ({evidence.length})</span>
        </button>
        <button
          onClick={() => setActiveTab('sources')}
          className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-colors flex items-center gap-1.5 ${
            activeTab === 'sources'
              ? 'bg-emerald-600 text-white'
              : 'bg-slate-900 text-slate-400 hover:bg-slate-800'
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          <span>Source Records ({source_records.length})</span>
        </button>
        <button
          onClick={() => setActiveTab('signals')}
          className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-colors flex items-center gap-1.5 ${
            activeTab === 'signals'
              ? 'bg-sky-600 text-white'
              : 'bg-slate-900 text-slate-400 hover:bg-slate-800'
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          <span>Signals ({signals.length})</span>
        </button>
        <button
          onClick={() => setActiveTab('entities')}
          className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-colors flex items-center gap-1.5 ${
            activeTab === 'entities'
              ? 'bg-purple-600 text-white'
              : 'bg-slate-900 text-slate-400 hover:bg-slate-800'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Entities &amp; Rels ({entities.length} / {relationships.length})</span>
        </button>
      </div>

      {/* ==================================================================== */}
      {/* SECTION 1: Finding & Analytical Context                              */}
      {/* ==================================================================== */}
      {(activeTab === 'all' || activeTab === 'signals' || activeTab === 'entities') && (
        <div className="p-5 rounded-md bg-institutional-panel border border-institutional-border space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <h2 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-semibold flex items-center gap-2">
              <Activity className="w-4 h-4 text-blue-400" />
              <span>Tier 1: Analytical Finding &amp; Derived Signals</span>
            </h2>
            <span className="text-[10px] font-mono text-slate-500">
               {signals.length} supporting signal{signals.length === 1 ? '' : 's'}
            </span>
          </div>

          <div className="space-y-2">
            <div className="text-xs font-mono font-medium text-slate-300">Finding Summary</div>
            <p className="text-xs font-mono text-slate-400 leading-relaxed bg-slate-950/60 p-3 rounded border border-slate-800">
              {finding.summary}
            </p>
          </div>

          {/* Time Window & Caveats */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
            {finding.time_window && (
              <div className="p-2.5 rounded bg-slate-900/60 border border-slate-800 space-y-1">
                <span className="text-[10px] text-slate-500 uppercase">Observed Time Window</span>
                <div className="text-slate-300">
                  {finding.time_window.start_time || 'unbounded'} → {finding.time_window.end_time || 'unbounded'}
                </div>
              </div>
            )}
            {finding.caveats && finding.caveats.length > 0 && (
              <div className="p-2.5 rounded bg-slate-900/60 border border-slate-800 space-y-1">
                <span className="text-[10px] text-amber-500 uppercase">Analysis Caveats</span>
                <ul className="text-slate-400 text-[11px] list-disc list-inside space-y-0.5">
                  {finding.caveats.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Contributing Signals */}
          <div className="space-y-2 pt-2 border-t border-slate-800">
            <div className="text-xs font-mono font-semibold text-slate-300 flex items-center gap-1.5">
              <Binary className="w-3.5 h-3.5 text-sky-400" />
              <span>Contributing Deterministic Signals ({signals.length})</span>
            </div>
            {signals.length === 0 ? (
              <div className="text-xs font-mono text-slate-500 italic p-2">
                No discrete signals attached to finding bundle.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                {signals.map((sig, idx) => {
                  const sigId = (sig.signal_id as string) || `sig-${idx}`;
                  const sigType = (sig.signal_type as string) || (sig.ref as string) || 'SIGNAL';
                  const evIds = (sig.evidence_ids as string[]) || [];

                  return (
                    <div
                      key={sigId}
                      className="p-2.5 rounded bg-slate-900/80 border border-slate-800 space-y-1.5 text-xs font-mono"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-semibold text-sky-300 px-1.5 py-0.5 rounded bg-sky-950 border border-sky-800">
                          {sigType}
                        </span>
                        <span className="text-[10px] text-slate-500">#{idx + 1}</span>
                      </div>
                      <div className="text-[11px] text-slate-300 truncate select-all">{sigId}</div>
                      {evIds.length > 0 && (
                        <div className="text-[10px] text-amber-400/90">
                          {evIds.length} evidence ref(s)
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Involved Entities & Relationships */}
          <div className="space-y-3 pt-2 border-t border-slate-800">
            <div className="text-xs font-mono font-semibold text-slate-300 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-purple-400" />
              <span>Involved Entities ({entities.length}) &amp; Relationships ({relationships.length})</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
              {entities.map((ent, idx) => {
                const eid = (ent.entity_id as string) || `ent-${idx}`;
                const name = (ent.canonical_name as string) || eid;
                const type = (ent.entity_type as string) || 'UNKNOWN';

                return (
                  <div
                    key={eid}
                    className="p-2.5 rounded bg-slate-900/60 border border-slate-800 space-y-1 text-xs font-mono"
                  >
                    <div className="flex items-center justify-between">
                      <span className="inline-flex items-center gap-1 text-[10px] text-slate-300">
                        {getEntityIcon(type)}
                        <span>{type}</span>
                      </span>
                      <Link
                        to={`/entities?id=${encodeURIComponent(eid)}`}
                        className="text-slate-400 hover:text-blue-400 p-0.5"
                        title="View Entity Intelligence"
                      >
                        <ExternalLink className="w-3 h-3" />
                      </Link>
                    </div>
                    <div className="font-medium text-white truncate">{name}</div>
                    <div className="text-[10px] text-slate-500 truncate select-all">{eid}</div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* SECTION 2: Supporting Evidence Vault Items                           */}
      {/* ==================================================================== */}
      {(activeTab === 'all' || activeTab === 'evidence') && (
        <div className="p-5 rounded-md bg-institutional-panel border border-institutional-border space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-800 pb-3">
            <div>
              <h2 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-semibold flex items-center gap-2">
                <FileCheck className="w-4 h-4 text-amber-400" />
                <span>Tier 2: Supporting Evidence Items ({filteredEvidence.length} of {evidence.length})</span>
              </h2>
              <p className="text-[11px] font-mono text-slate-500 mt-0.5">
                Extracted evidence items linked to the source records they came from.
              </p>
            </div>

            {/* Filter controls */}
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={selectedSourceType}
                onChange={(e) => setSelectedSourceType(e.target.value)}
                className="px-2 py-1 text-xs font-mono rounded bg-slate-900 border border-slate-800 text-slate-300 focus:outline-none focus:border-blue-500"
              >
                <option value="ALL">All Source Feeds</option>
                {uniqueSourceTypes.map((st) => (
                  <option key={st} value={st}>
                    {st}
                  </option>
                ))}
              </select>

              <div className="relative w-44">
                <Search className="w-3 h-3 text-slate-500 absolute left-2 top-2" />
                <input
                  type="text"
                  value={evidenceFilterQuery}
                  onChange={(e) => setEvidenceFilterQuery(e.target.value)}
                  placeholder="Filter snippets..."
                  className="w-full pl-7 pr-2 py-1 text-xs font-mono rounded bg-slate-900 border border-slate-800 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          </div>

          {/* Evidence List */}
          {evidence.length === 0 ? (
            <div className="p-8 rounded bg-slate-950/60 border border-slate-800 text-center space-y-2">
              <FileCheck className="w-8 h-8 text-slate-600 mx-auto" />
              <div className="text-xs font-mono font-semibold text-slate-300">
                No Supporting Evidence Records
              </div>
              <p className="text-[11px] font-mono text-slate-500 max-w-md mx-auto">
                No supporting evidence records are currently attached to this finding.
              </p>
            </div>
          ) : filteredEvidence.length === 0 ? (
            <div className="p-6 rounded bg-slate-950/60 border border-slate-800 text-center space-y-1">
              <div className="text-xs font-mono text-slate-400">No evidence records matched your filter.</div>
              <button
                onClick={() => {
                  setEvidenceFilterQuery('');
                  setSelectedSourceType('ALL');
                }}
                className="text-xs font-mono text-blue-400 hover:underline"
              >
                Clear Filters
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredEvidence.map((ev: EvidenceRecord) => {
                const isHighlight = highlightedSourceId === ev.source_record_id;

                return (
                  <div
                    key={ev.evidence_id}
                    className={`p-4 rounded-md bg-slate-900/80 border transition-colors space-y-3 ${
                      isHighlight
                        ? 'border-amber-500/80 bg-amber-950/10'
                        : 'border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    {/* Top Row: Evidence URN & Extractor */}
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-bold text-amber-300 tracking-tight select-all">
                          {ev.evidence_id}
                        </span>
                        <button
                          onClick={() => handleCopy(ev.evidence_id, ev.evidence_id)}
                          className="text-slate-500 hover:text-slate-300 p-0.5"
                          title="Copy Evidence URN"
                        >
                          {copiedId === ev.evidence_id ? (
                            <Check className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </button>
                      </div>

                      <div className="flex items-center gap-2">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-mono border ${getSourceTypeBadgeColor(
                            ev.source_type
                          )}`}
                        >
                          {ev.source_type}
                        </span>
                        {ev.extractor_name && (
                          <span className="text-[10px] font-mono text-slate-400">
                            Extractor: {ev.extractor_name}
                          </span>
                        )}
                        {ev.extracted_at && (
                          <span className="text-[10px] font-mono text-slate-500">
                            {ev.extracted_at}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Middle: Document Reference & Link to Source */}
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs font-mono">
                      <div className="flex items-center gap-2 text-slate-400">
                        <FileText className="w-3.5 h-3.5 text-blue-400" />
                        <span className="text-white font-medium">{ev.document_name}</span>
                        {ev.offset_start != null && ev.offset_end != null && (
                          <span className="text-[10px] text-slate-500">
                            [Offset {ev.offset_start} : {ev.offset_end}]
                          </span>
                        )}
                      </div>

                      {ev.source_record_id && (
                        <button
                          onClick={() => handleJumpToSource(ev.source_record_id)}
                          className="px-2.5 py-1 rounded bg-slate-950 hover:bg-slate-800 border border-slate-700 text-xs font-mono text-emerald-400 hover:text-emerald-300 transition-colors flex items-center gap-1.5 self-start sm:self-auto"
                        >
                          <Database className="w-3 h-3" />
                          <span>Source Record: {ev.source_record_id}</span>
                          <ArrowRight className="w-3 h-3" />
                        </button>
                      )}
                    </div>

                    {/* Raw Snippet Box */}
                    <div className="space-y-1">
                      <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                        Extracted Raw Text Snippet
                      </div>
                      <pre className="p-3 rounded bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 overflow-x-auto whitespace-pre-wrap leading-relaxed select-all">
                        {ev.raw_snippet || '(Empty snippet)'}
                      </pre>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ==================================================================== */}
      {/* SECTION 3: Original Source Record Traceability                       */}
      {/* ==================================================================== */}
      {(activeTab === 'all' || activeTab === 'sources') && (
        <div className="p-5 rounded-md bg-institutional-panel border border-institutional-border space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h2 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-semibold flex items-center gap-2">
                <Database className="w-4 h-4 text-emerald-400" />
                <span>Tier 3: Original Raw Source Documents ({source_records.length})</span>
              </h2>
              <p className="text-[11px] font-mono text-slate-500 mt-0.5">
                Original source records retained for traceability.
              </p>
            </div>
            <span className="text-[10px] font-mono text-emerald-400/90 font-semibold">
              SOURCE TRACE AVAILABLE
            </span>
          </div>

          {source_records.length === 0 ? (
            <div className="p-8 rounded bg-slate-950/60 border border-slate-800 text-center space-y-2">
              <Database className="w-8 h-8 text-slate-600 mx-auto" />
              <div className="text-xs font-mono font-semibold text-slate-300">
                No Raw Source Documents In Bundle
              </div>
              <p className="text-[11px] font-mono text-slate-500 max-w-md mx-auto">
                The evidence records referenced by this finding do not have parent source records cached in the workspace.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {source_records.map((src: SourceRecordItem) => {
                const sId = src.source_id || (src as unknown as { source_record_id?: string }).source_record_id || 'source';
                const isHighlighted = highlightedSourceId === sId;

                // Find any snippets from evidence that belong to this source record
                const matchingSnippets = evidence
                  .filter((e) => e.source_record_id === sId)
                  .map((e) => e.raw_snippet)
                  .filter(Boolean);

                return (
                  <div
                    key={sId}
                    id={`source-record-${sId}`}
                    className={`p-4 rounded-md bg-slate-900/90 border transition-all space-y-3 ${
                      isHighlighted
                        ? 'border-emerald-500 ring-1 ring-emerald-500/50 bg-emerald-950/10'
                        : 'border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    {/* Header Row */}
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-bold text-emerald-400 tracking-tight select-all">
                          {sId}
                        </span>
                        <button
                          onClick={() => handleCopy(sId, sId)}
                          className="text-slate-500 hover:text-slate-300 p-0.5"
                          title="Copy Source Record ID"
                        >
                          {copiedId === sId ? (
                            <Check className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </button>
                      </div>

                      <div className="flex items-center gap-2">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-mono border ${getSourceTypeBadgeColor(
                            src.source_type
                          )}`}
                        >
                          {src.source_type}
                        </span>
                        {src.ingested_at && (
                          <span className="text-[10px] font-mono text-slate-500">
                            Ingested: {src.ingested_at}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Metadata / Document Name */}
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs font-mono">
                      <div className="flex items-center gap-2">
                        <span className="text-slate-400">File/Document:</span>
                        <span className="text-white font-medium">{src.document_name}</span>
                      </div>
                      {matchingSnippets.length > 0 && (
                        <span className="text-[10px] font-mono text-amber-400">
                          Backs {matchingSnippets.length} evidence snippet(s)
                        </span>
                      )}
                    </div>

                    {/* Source Metadata Attributes (if present) */}
                    {src.metadata && Object.keys(src.metadata).length > 0 && (
                      <div className="p-2.5 rounded bg-slate-950/60 border border-slate-800/80 text-[11px] font-mono space-y-1">
                        <span className="text-[10px] text-slate-500 uppercase font-semibold">Source Metadata</span>
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                          {Object.entries(src.metadata).map(([k, v]) => (
                            <div key={k} className="truncate">
                              <span className="text-slate-500">{k}: </span>
                              <span className="text-slate-300">{String(v)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Full Raw Content Viewer */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                        <span>Original Raw Content</span>
                        <button
                          onClick={() => handleCopy(src.raw_content, `raw-${sId}`)}
                          className="text-slate-400 hover:text-white flex items-center gap-1 normal-case"
                        >
                          {copiedId === `raw-${sId}` ? (
                            <>
                              <Check className="w-3 h-3 text-emerald-400" />
                              <span className="text-emerald-400">Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3 h-3" />
                              <span>Copy Raw</span>
                            </>
                          )}
                        </button>
                      </div>

                      <pre className="p-3.5 rounded bg-slate-950 border border-slate-800/80 text-xs font-mono text-slate-200 overflow-x-auto max-h-64 whitespace-pre-wrap leading-relaxed select-all">
                        {src.raw_content || '(Empty content)'}
                      </pre>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Evidence;

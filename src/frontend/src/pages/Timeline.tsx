import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import {
  Clock,
  Calendar,
  Search,
  ArrowRight,
  ArrowLeft,
  ExternalLink,
  Network,
  Activity,
  AlertCircle,
  RefreshCw,
  Phone,
  Car,
  MapPin,
  Building2,
  CreditCard,
  User,
  Fingerprint,
  Layers,
  ArrowDownUp,
  FileCheck,
  ShieldAlert,
} from 'lucide-react';
import {
  getEntityNeighborhood,
  getEntityDetails,
  searchEntities,
  listFindings,
  EntityRecord,
  EntityDetails,
  NeighborhoodRelationship,
  InvestigativeFinding,
} from '../api';

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

function getRelationshipBadgeColor(type: string): string {
  switch (type?.toUpperCase()) {
    case 'COMMUNICATED_WITH':
      return 'bg-emerald-950/70 text-emerald-300 border-emerald-800/80';
    case 'OWNED_BY':
      return 'bg-blue-950/70 text-blue-300 border-blue-800/80';
    case 'ASSOCIATED_WITH':
      return 'bg-amber-950/70 text-amber-300 border-amber-800/80';
    case 'TRANSACTED_WITH':
      return 'bg-cyan-950/70 text-cyan-300 border-cyan-800/80';
    default:
      return 'bg-slate-900 text-slate-300 border-slate-800';
  }
}

interface RelationshipActivityItem {
  id: string;
  primaryTimestamp: string;
  firstSeen?: string | null;
  lastSeen?: string | null;
  relationshipType: string;
  sourceEntityId: string;
  targetEntityId: string;
  sourceName?: string | null;
  targetName?: string | null;
  counterpartId: string;
  counterpartName: string;
  counterpartType: string;
  isOutgoing: boolean;
  interactionCount: number;
  confidence: number;
  evidenceIds?: string[];
  rawRelationship: NeighborhoodRelationship;
}

export const Timeline: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const entityId = (searchParams.get('entity_id') || searchParams.get('focus') || '').trim();

  // State
  const [entityDetails, setEntityDetails] = useState<EntityDetails | null>(null);
  const [relationships, setRelationships] = useState<NeighborhoodRelationship[]>([]);
  const [neighborhoodEntities, setNeighborhoodEntities] = useState<EntityRecord[]>([]);
  const [relatedFindings, setRelatedFindings] = useState<InvestigativeFinding[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Sorting: 'asc' = earliest first, 'desc' = latest first
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  // Quick select sample entities when no entityId is set
  const [sampleEntities, setSampleEntities] = useState<EntityRecord[]>([]);
  const [manualInput, setManualInput] = useState<string>('');

  // --------------------------------------------------------------------------
  // Load Quick Select Samples
  // --------------------------------------------------------------------------
  useEffect(() => {
    let isMounted = true;
    async function loadSamples() {
      try {
        const records = await searchEntities({ limit: 12 });
        if (isMounted) {
          setSampleEntities(records);
        }
      } catch {
        // Soft fail on sample entities
      }
    }
    if (!entityId) {
      loadSamples();
    }
    return () => {
      isMounted = false;
    };
  }, [entityId]);

  // --------------------------------------------------------------------------
  // Fetch Temporal Data for Entity
  // --------------------------------------------------------------------------
  const fetchTemporalData = useCallback(async (id: string) => {
    if (!id) return;
    setIsLoading(true);
    setError(null);

    try {
      const [detailsData, neighborhoodData, findingsData] = await Promise.all([
        getEntityDetails(id).catch(() => null),
        getEntityNeighborhood(id, 2, 50),
        listFindings({ entity_id: id }).catch(() => []),
      ]);

      setEntityDetails(detailsData);
      setRelationships(neighborhoodData.relationships || []);
      setNeighborhoodEntities(neighborhoodData.entities || []);
      setRelatedFindings(findingsData);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve temporal telemetry';
      setError(msg);
      setRelationships([]);
      setNeighborhoodEntities([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (entityId) {
      fetchTemporalData(entityId);
    } else {
      setEntityDetails(null);
      setRelationships([]);
      setNeighborhoodEntities([]);
      setRelatedFindings([]);
    }
  }, [entityId, fetchTemporalData]);

  // --------------------------------------------------------------------------
  // Separate Dated Activity vs Undated Activity (Strict Zero Fabrication)
  // --------------------------------------------------------------------------
  const { datedActivities, undatedRelationships } = useMemo(() => {
    const dated: RelationshipActivityItem[] = [];
    const undated: NeighborhoodRelationship[] = [];

    const entityMap = new Map<string, EntityRecord>();
    for (const ent of neighborhoodEntities) {
      entityMap.set(ent.entity_id, ent);
    }

    for (let i = 0; i < relationships.length; i++) {
      const rel = relationships[i];
      const isOut = rel.source_entity_id === entityId;
      const counterpartId = isOut ? rel.target_entity_id : rel.source_entity_id;
      const counterpart = entityMap.get(counterpartId);
      const counterpartName = counterpart?.canonical_name || (isOut ? rel.target_name : rel.source_name) || counterpartId;
      const counterpartType = counterpart?.entity_type || 'UNKNOWN';

      const hasFirst = Boolean(rel.first_seen);
      const hasLast = Boolean(rel.last_seen);

      if (!hasFirst && !hasLast) {
        // Strictly undated record
        undated.push(rel);
        continue;
      }

      // Single relationship activity representing aggregated temporal bounds (first_seen / last_seen)
      const primaryTs = rel.first_seen || rel.last_seen!;
      dated.push({
        id: rel.relationship_id || `rel-act-${i}`,
        primaryTimestamp: primaryTs,
        firstSeen: rel.first_seen || null,
        lastSeen: rel.last_seen || null,
        relationshipType: rel.relationship_type,
        sourceEntityId: rel.source_entity_id,
        targetEntityId: rel.target_entity_id,
        sourceName: rel.source_name,
        targetName: rel.target_name,
        counterpartId,
        counterpartName,
        counterpartType,
        isOutgoing: isOut,
        interactionCount: rel.interaction_count,
        confidence: rel.confidence,
        evidenceIds: rel.evidence_ids,
        rawRelationship: rel,
      });
    }

    // Sort dated activities chronologically by observed timestamp bounds
    dated.sort((a, b) => {
      const timeA = new Date(a.primaryTimestamp).getTime();
      const timeB = new Date(b.primaryTimestamp).getTime();
      return sortOrder === 'asc' ? timeA - timeB : timeB - timeA;
    });

    return { datedActivities: dated, undatedRelationships: undated };
  }, [relationships, neighborhoodEntities, entityId, sortOrder]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (manualInput.trim()) {
      setSearchParams({ entity_id: manualInput.trim() });
    }
  };

  // --------------------------------------------------------------------------
  // Render: No Entity Selected State
  // --------------------------------------------------------------------------
  if (!entityId) {
    return (
      <div className="space-y-6">
        <div className="border-b border-institutional-border pb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950/80 border border-blue-800 text-blue-300 font-semibold tracking-wide">
                MOD-04-TIME
              </span>
              <span className="text-xs font-mono text-slate-400">RELATIONSHIP ACTIVITY SEQUENCE</span>
            </div>
            <h1 className="text-xl font-mono font-semibold text-white tracking-tight mt-1 flex items-center gap-2">
              <Clock className="w-5 h-5 text-blue-400" />
              <span>Timeline Explorer</span>
            </h1>
            <p className="text-xs font-mono text-slate-400 mt-1">
              Deterministic chronological interaction ordering across communication and transaction telemetry.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-400">
              ZERO TEMPORAL FABRICATION POLICY
            </span>
          </div>
        </div>

        {/* Entity Selector Bar */}
        <div className="p-6 rounded-md bg-institutional-panel border border-institutional-border space-y-4">
          <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
            <Search className="w-4 h-4 text-blue-400" />
            <span className="font-semibold">SELECT ENTITY FOR TIMELINE ANALYSIS</span>
          </div>
          <p className="text-xs font-mono text-slate-400 leading-relaxed max-w-2xl">
            Enter an entity identifier to trace its temporal interaction telemetry over time.
            Undated records are strictly segregated to uphold evidentiary standards.
          </p>

          <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row gap-2 max-w-xl">
            <input
              type="text"
              value={manualInput}
              onChange={(e) => setManualInput(e.target.value)}
              placeholder="Enter Entity ID (e.g., urn:entity:person:999773f5f992)..."
              className="flex-1 px-3 py-2 text-xs font-mono rounded bg-slate-900/90 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
            <button
              type="submit"
              className="px-4 py-2 text-xs font-mono font-medium rounded bg-blue-600 hover:bg-blue-500 text-white transition-colors flex items-center justify-center gap-1.5"
            >
              <Clock className="w-3.5 h-3.5" />
              <span>Load Timeline</span>
            </button>
          </form>
        </div>

        {/* Quick Select Grid */}
        {sampleEntities.length > 0 && (
          <div className="p-5 rounded-md bg-institutional-panel border border-institutional-border space-y-3">
            <h2 className="text-xs font-mono uppercase tracking-wider text-institutional-textMuted font-semibold flex items-center gap-2">
              <Layers className="w-3.5 h-3.5 text-slate-400" />
              <span>Knowledge Graph Entities (Quick Select)</span>
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {sampleEntities.map((ent) => (
                <div
                  key={ent.entity_id}
                  onClick={() => setSearchParams({ entity_id: ent.entity_id })}
                  className="p-3 rounded bg-slate-900/80 border border-slate-800 hover:border-blue-800/80 cursor-pointer transition-colors group space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-950 border border-slate-800 text-[10px] text-slate-300">
                      {getEntityIcon(ent.entity_type)}
                      <span>{ent.entity_type}</span>
                    </span>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-blue-400 transition-transform group-hover:translate-x-0.5" />
                  </div>
                  <div className="text-xs font-mono font-medium text-white truncate">
                    {ent.canonical_name || ent.entity_id}
                  </div>
                  <div className="text-[10px] font-mono text-institutional-textMuted truncate">
                    {ent.entity_id}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
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
          <span className="text-xs font-mono text-slate-400">Loading temporal telemetry...</span>
        </div>

        <div className="p-12 rounded-md bg-institutional-panel border border-institutional-border text-center space-y-3">
          <RefreshCw className="w-6 h-6 text-blue-400 animate-spin mx-auto" />
          <div className="text-xs font-mono text-slate-300 font-semibold">
            Querying timestamped observations from knowledge graph...
          </div>
          <div className="text-[11px] font-mono text-slate-500 truncate max-w-md mx-auto">
            {entityId}
          </div>
        </div>
      </div>
    );
  }

  // --------------------------------------------------------------------------
  // Render: Error State
  // --------------------------------------------------------------------------
  if (error) {
    return (
      <div className="space-y-6">
        <div className="border-b border-institutional-border pb-4 flex items-center justify-between">
          <button
            onClick={() => setSearchParams({})}
            className="p-1.5 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="text-xs font-mono text-rose-400">Timeline Retrieval Error</span>
        </div>

        <div className="p-6 rounded-md bg-rose-950/20 border border-rose-800/60 text-slate-200 space-y-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <div className="text-xs font-mono font-semibold text-rose-300 uppercase tracking-wide">
                Failed to Retrieve Timeline
              </div>
              <p className="text-xs font-mono text-slate-400">{error}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 pt-2 border-t border-rose-900/40">
            <button
              onClick={() => fetchTemporalData(entityId)}
              className="px-3 py-1.5 rounded bg-rose-900/60 hover:bg-rose-900 border border-rose-700 text-xs font-mono text-white transition-colors flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry</span>
            </button>
            <button
              onClick={() => setSearchParams({})}
              className="px-3 py-1.5 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-mono text-slate-300 transition-colors"
            >
              Choose Different Entity
            </button>
          </div>
        </div>
      </div>
    );
  }

  // --------------------------------------------------------------------------
  // Render: Timeline View
  // --------------------------------------------------------------------------
  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="border-b border-institutional-border pb-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setSearchParams({})}
            className="p-1.5 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition-colors"
            title="Choose different entity"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950/80 border border-blue-800 text-blue-300 font-semibold">
                MOD-04-TIME
              </span>
              <span className="text-xs font-mono text-slate-400">CHRONOLOGICAL SEQUENCE</span>
              {entityDetails && (
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-[10px] text-slate-300">
                  {getEntityIcon(entityDetails.entity_type)}
                  <span>{entityDetails.entity_type}</span>
                </span>
              )}
            </div>
            <h1 className="text-lg font-mono font-bold text-white tracking-tight mt-1 flex items-center gap-2">
              <span>{entityDetails?.canonical_name || entityId}</span>
            </h1>
            <p className="text-[11px] font-mono text-slate-500 truncate max-w-lg select-all">
              {entityId}
            </p>
          </div>
        </div>

        {/* Integration Actions */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')}
            className="px-2.5 py-1.5 rounded bg-slate-900 border border-slate-700 hover:bg-slate-800 text-slate-300 text-xs font-mono flex items-center gap-1.5 transition-colors"
            title="Toggle chronological order"
          >
            <ArrowDownUp className="w-3.5 h-3.5 text-blue-400" />
            <span>{sortOrder === 'asc' ? 'Oldest → Newest' : 'Newest → Oldest'}</span>
          </button>

          <Link
            to={`/network?focus=${encodeURIComponent(entityId)}`}
            className="px-2.5 py-1.5 rounded bg-slate-900 border border-slate-700 hover:bg-slate-800 text-slate-300 text-xs font-mono flex items-center gap-1.5 transition-colors"
          >
            <Network className="w-3.5 h-3.5 text-sky-400" />
            <span>Network</span>
          </Link>

          <Link
            to={`/entities?id=${encodeURIComponent(entityId)}`}
            className="px-2.5 py-1.5 rounded bg-slate-900 border border-slate-700 hover:bg-slate-800 text-slate-300 text-xs font-mono flex items-center gap-1.5 transition-colors"
          >
            <ExternalLink className="w-3.5 h-3.5 text-emerald-400" />
            <span>Entity Intelligence</span>
          </Link>

          <Link
            to={`/findings?entity_id=${encodeURIComponent(entityId)}`}
            className="px-2.5 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-medium flex items-center gap-1.5 transition-colors"
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Related Findings ({relatedFindings.length})</span>
          </Link>
        </div>
      </div>

      {/* Metrics Banner */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3 rounded bg-institutional-panel border border-institutional-border">
          <div className="text-[10px] font-mono text-slate-500 uppercase">Dated Activities</div>
          <div className="text-lg font-mono font-bold text-white mt-0.5">{datedActivities.length}</div>
        </div>
        <div className="p-3 rounded bg-institutional-panel border border-institutional-border">
          <div className="text-[10px] font-mono text-slate-500 uppercase">Undated Activities</div>
          <div className="text-lg font-mono font-bold text-amber-400 mt-0.5">{undatedRelationships.length}</div>
        </div>
        <div className="p-3 rounded bg-institutional-panel border border-institutional-border">
          <div className="text-[10px] font-mono text-slate-500 uppercase">Related Findings</div>
          <div className="text-lg font-mono font-bold text-sky-400 mt-0.5">{relatedFindings.length}</div>
        </div>
        <div className="p-3 rounded bg-institutional-panel border border-institutional-border">
          <div className="text-[10px] font-mono text-slate-500 uppercase">Connected Neighbors</div>
          <div className="text-lg font-mono font-bold text-slate-300 mt-0.5">{neighborhoodEntities.length}</div>
        </div>
      </div>

      {/* Correlated Findings Alert (if findings detected for entity) */}
      {relatedFindings.length > 0 && (
        <div className="p-4 rounded-md bg-blue-950/30 border border-blue-800/60 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-semibold text-blue-300 uppercase tracking-wide flex items-center gap-1.5">
              <Activity className="w-4 h-4 text-blue-400" />
              <span>Correlated Analytical Findings ({relatedFindings.length})</span>
            </span>
            <Link
              to={`/findings?entity_id=${encodeURIComponent(entityId)}`}
              className="text-[11px] font-mono text-blue-400 hover:text-blue-300 flex items-center gap-1"
            >
              <span>Inspect All in Findings</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1">
            {relatedFindings.map((f) => (
              <div
                key={f.finding_id}
                onClick={() => navigate(`/findings?id=${encodeURIComponent(f.finding_id)}`)}
                className="p-2.5 rounded bg-slate-900/80 border border-slate-800 hover:border-blue-700/80 cursor-pointer transition-colors space-y-1"
              >
                <div className="flex items-center justify-between text-[10px] font-mono">
                  <span className="text-sky-300 font-semibold">{f.pattern_type}</span>
                  <span className="text-slate-400">{(f.confidence * 100).toFixed(0)}% Conf</span>
                </div>
                <div className="text-xs font-mono font-medium text-white truncate">{f.title}</div>
                {f.time_window?.start_time && (
                  <div className="text-[10px] font-mono text-slate-500">
                    Window: {f.time_window.start_time} → {f.time_window.end_time || 'ongoing'}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Chronological Activity Feed */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-mono uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-2">
            <Calendar className="w-4 h-4 text-blue-400" />
            <span>Relationship Activity Stream ({datedActivities.length} activities)</span>
          </h2>
          <span className="text-[10px] font-mono text-slate-500">
            {sortOrder === 'asc' ? 'Oldest → Newest' : 'Newest → Oldest'}
          </span>
        </div>

        {datedActivities.length === 0 ? (
          <div className="p-8 rounded-md bg-institutional-panel border border-institutional-border text-center space-y-2">
            <Clock className="w-8 h-8 text-slate-600 mx-auto" />
            <div className="text-xs font-mono font-semibold text-slate-300">
              No Timestamped Activity Records Found
            </div>
            <p className="text-[11px] font-mono text-slate-500 max-w-md mx-auto">
              This entity has relationships recorded in the graph, but none contain timestamp bounds.
              See undated records section below.
            </p>
          </div>
        ) : (
          <div className="relative border-l-2 border-slate-800 ml-4 pl-6 space-y-6">
            {datedActivities.map((act) => (
              <div key={act.id} className="relative group">
                {/* Timeline node dot */}
                <div className="absolute -left-[31px] top-1.5 w-3 h-3 rounded-full bg-slate-950 border-2 border-blue-500 group-hover:scale-125 transition-transform" />

                <div className="p-4 rounded-md bg-institutional-panel border border-institutional-border hover:border-slate-700 transition-colors space-y-3">
                  {/* Activity Meta Header: Temporal Bounds */}
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-2">
                    <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
                      {act.firstSeen && act.lastSeen && act.firstSeen !== act.lastSeen ? (
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-[11px] text-slate-300">
                            <span className="text-[9px] text-slate-500 uppercase font-semibold">First Observed:</span>
                            <span className="text-sky-300 font-semibold">{act.firstSeen}</span>
                          </span>
                          <span className="text-slate-600">→</span>
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-[11px] text-slate-300">
                            <span className="text-[9px] text-slate-500 uppercase font-semibold">Last Observed:</span>
                            <span className="text-blue-300 font-semibold">{act.lastSeen}</span>
                          </span>
                        </div>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-[11px] text-slate-300">
                          <span className="text-[9px] text-slate-500 uppercase font-semibold">Observed:</span>
                          <span className="text-sky-300 font-semibold">{act.firstSeen || act.lastSeen}</span>
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono border ${getRelationshipBadgeColor(act.relationshipType)}`}>
                        {act.relationshipType}
                      </span>
                      <span className="text-[10px] font-mono text-slate-400 font-semibold">
                        {act.interactionCount}x interactions
                      </span>
                      <span className="text-[10px] font-mono text-slate-500">
                        {(act.confidence * 100).toFixed(0)}% conf
                      </span>
                    </div>
                  </div>

                  {/* Counterpart / Interaction Direction */}
                  <div className="flex items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                        {act.isOutgoing ? 'Target Counterpart' : 'Source Counterpart'}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-[10px] font-mono text-slate-300">
                          {getEntityIcon(act.counterpartType)}
                          <span>{act.counterpartType}</span>
                        </span>
                        <Link
                          to={`/entities?id=${encodeURIComponent(act.counterpartId)}`}
                          className="text-xs font-mono font-medium text-white hover:text-blue-400 transition-colors"
                        >
                          {act.counterpartName}
                        </Link>
                      </div>
                      <div className="text-[10px] font-mono text-slate-500 select-all">
                        {act.counterpartId}
                      </div>
                    </div>

                    {/* Quick Link to Counterpart Timeline */}
                    <div className="shrink-0 flex items-center gap-2">
                      <Link
                        to={`/timeline?entity_id=${encodeURIComponent(act.counterpartId)}`}
                        className="px-2 py-1 rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 text-[10px] font-mono text-slate-400 hover:text-slate-200 transition-colors flex items-center gap-1"
                        title="Pivot Timeline to this counterpart"
                      >
                        <Clock className="w-3 h-3" />
                        <span>Pivot Timeline</span>
                      </Link>

                      {act.evidenceIds && act.evidenceIds.length > 0 && (
                        <span className="px-2 py-1 rounded bg-slate-900 border border-slate-800 text-[10px] font-mono text-slate-400 flex items-center gap-1">
                          <FileCheck className="w-3 h-3 text-emerald-400" />
                          <span>{act.evidenceIds.length} Ev.</span>
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Undated Activity Section — Strict Zero Temporal Fabrication */}
      {undatedRelationships.length > 0 && (
        <div className="p-5 rounded-md bg-slate-950/90 border border-amber-900/50 space-y-3">
          <div className="flex items-center justify-between border-b border-amber-900/40 pb-2">
            <div className="flex items-center gap-2 text-xs font-mono font-semibold text-amber-300">
              <ShieldAlert className="w-4 h-4 text-amber-400" />
              <span>UNDATED RELATIONSHIP ACTIVITY ({undatedRelationships.length}) — ZERO TEMPORAL FABRICATION</span>
            </div>
            <span className="text-[10px] font-mono text-amber-500/80">NO SYNTHETIC TIMESTAMPS INJECTED</span>
          </div>

          <p className="text-[11px] font-mono text-slate-400 leading-relaxed">
            The following relationships exist in the verified knowledge graph without timestamp metadata in source records.
            In strict compliance with investigative forensic standards, mock dates have not been fabricated.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 pt-1">
            {undatedRelationships.map((rel, idx) => {
              const isOut = rel.source_entity_id === entityId;
              const neighborId = isOut ? rel.target_entity_id : rel.source_entity_id;
              const neighborName = (isOut ? rel.target_name : rel.source_name) || neighborId;

              return (
                <div
                  key={idx}
                  className="p-2.5 rounded bg-slate-900/60 border border-slate-800 space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono border ${getRelationshipBadgeColor(rel.relationship_type)}`}>
                      {rel.relationship_type}
                    </span>
                    <span className="text-[10px] font-mono text-slate-500">
                      {rel.interaction_count}x
                    </span>
                  </div>
                  <div className="text-xs font-mono font-medium text-slate-200 truncate">
                    <span className="text-slate-500">{isOut ? '→ ' : '← '}</span>
                    {neighborName}
                  </div>
                  <div className="text-[10px] font-mono text-slate-500 truncate select-all">
                    {neighborId}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

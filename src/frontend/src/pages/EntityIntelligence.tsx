import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams, useParams, Link } from 'react-router-dom';
import {
  Users,
  Search,
  Network,
  ArrowLeft,
  ArrowRight,
  Shield,
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
  FileText,
  Clock,
  ExternalLink,
} from 'lucide-react';
import {
  getEntityDetails,
  getEntityNeighborhood,
  searchEntities,
  EntityDetails,
  EntityNeighborhoodResponse,
  EntityRecord,
} from '../api';

function getEntityIcon(type?: string) {
  switch (type?.toUpperCase()) {
    case 'PERSON':
      return <User className="w-4 h-4 text-blue-400" />;
    case 'PHONE':
      return <Phone className="w-4 h-4 text-emerald-400" />;
    case 'VEHICLE':
      return <Car className="w-4 h-4 text-amber-400" />;
    case 'LOCATION':
      return <MapPin className="w-4 h-4 text-rose-400" />;
    case 'ORGANIZATION':
      return <Building2 className="w-4 h-4 text-purple-400" />;
    case 'ACCOUNT':
      return <CreditCard className="w-4 h-4 text-cyan-400" />;
    default:
      return <Fingerprint className="w-4 h-4 text-slate-400" />;
  }
}

function getRelationshipBadgeColor(type: string): string {
  switch (type) {
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

export const EntityIntelligence: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const routeParams = useParams<{ entityId?: string }>();

  const entityId = searchParams.get('id') || routeParams.entityId || '';

  const [details, setDetails] = useState<EntityDetails | null>(null);
  const [neighborhood, setNeighborhood] = useState<EntityNeighborhoodResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Fallback entity picker list when no entity is selected
  const [sampleEntities, setSampleEntities] = useState<EntityRecord[]>([]);
  const [manualIdInput, setManualIdInput] = useState<string>('');

  const fetchEntityContext = useCallback(async (id: string) => {
    if (!id.trim()) {
      setDetails(null);
      setNeighborhood(null);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const [detailsData, neighborhoodData] = await Promise.all([
        getEntityDetails(id.trim()),
        getEntityNeighborhood(id.trim(), 1, 50),
      ]);
      setDetails(detailsData);
      setNeighborhood(neighborhoodData);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve entity data from backend';
      setError(msg);
      setDetails(null);
      setNeighborhood(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (entityId) {
      fetchEntityContext(entityId);
    } else {
      // Load sample entities for quick selection
      searchEntities({ limit: 8 })
        .then(setSampleEntities)
        .catch(() => setSampleEntities([]));
    }
  }, [entityId, fetchEntityContext]);

  const handleManualLookup = (e: React.FormEvent) => {
    e.preventDefault();
    if (manualIdInput.trim()) {
      navigate(`/entities?id=${encodeURIComponent(manualIdInput.trim())}`);
    }
  };

  // --------------------------------------------------------------------------
  // Render: No Entity Selected (Selector Mode)
  // --------------------------------------------------------------------------
  if (!entityId) {
    return (
      <div className="space-y-6">
        <div className="border-b border-institutional-border pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-blue-400">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-slate-800/90 border border-slate-700 text-slate-300">
                  MOD-02-ENT
                </span>
                <span className="text-xs font-mono text-emerald-400 uppercase tracking-wider">
                  Operational (Phase 6B.1)
                </span>
              </div>
              <h1 className="text-xl font-semibold text-institutional-textPrimary tracking-tight mt-1">
                Entity Intelligence Context
              </h1>
              <p className="text-xs text-institutional-textSecondary mt-0.5">
                Select a resolved canonical entity to inspect attributes, direct relationships, and neighborhood topology.
              </p>
            </div>
          </div>
        </div>

        {/* Manual lookup input */}
        <div className="p-5 rounded-md bg-institutional-panel border border-institutional-border space-y-4">
          <h2 className="text-xs font-mono uppercase tracking-wider text-institutional-textSecondary font-semibold">
            Inspect Entity by Identifier / URN
          </h2>
          <form onSubmit={handleManualLookup} className="flex gap-3">
            <input
              type="text"
              value={manualIdInput}
              onChange={(e) => setManualIdInput(e.target.value)}
              placeholder="e.g. urn:entity:person:999773f5f992 or +91-9900000101"
              className="flex-1 px-3 py-2 text-xs font-mono rounded bg-slate-900 border border-slate-800 focus:border-blue-700 focus:outline-none text-white placeholder:text-slate-500"
            />
            <button
              type="submit"
              className="px-4 py-2 text-xs font-mono font-medium rounded bg-blue-600 hover:bg-blue-500 text-white shadow-sm transition-colors"
            >
              Load Intelligence
            </button>
            <Link
              to="/investigation"
              className="px-4 py-2 text-xs font-mono rounded bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1.5"
            >
              <Search className="w-3.5 h-3.5" />
              <span>Open Search</span>
            </Link>
          </form>
        </div>

        {/* Sample entities from live graph */}
        {sampleEntities.length > 0 && (
          <div className="p-5 rounded-md bg-institutional-panel border border-institutional-border space-y-3">
            <h2 className="text-xs font-mono uppercase tracking-wider text-institutional-textMuted font-semibold">
              Available Knowledge Graph Entities (Quick Select)
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {sampleEntities.map((ent) => (
                <div
                  key={ent.entity_id}
                  onClick={() => navigate(`/entities?id=${encodeURIComponent(ent.entity_id)}`)}
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
          <div className="flex items-center gap-2">
            <Link
              to="/investigation"
              className="p-1.5 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <span className="text-xs font-mono text-slate-400">Loading entity context...</span>
          </div>
        </div>

        <div className="p-12 rounded-md bg-institutional-panel border border-institutional-border text-center space-y-3">
          <RefreshCw className="w-6 h-6 text-blue-400 animate-spin mx-auto" />
          <div className="text-xs font-mono text-slate-400">
            Fetching entity properties and neighborhood traversal from backend...
          </div>
          <div className="text-[11px] font-mono text-slate-600 truncate max-w-md mx-auto">
            {entityId}
          </div>
        </div>
      </div>
    );
  }

  // --------------------------------------------------------------------------
  // Render: Error State
  // --------------------------------------------------------------------------
  if (error || !details) {
    return (
      <div className="space-y-6">
        <div className="border-b border-institutional-border pb-4 flex items-center justify-between">
          <Link
            to="/investigation"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-900 border border-slate-800 text-xs font-mono text-slate-300 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Return to Search</span>
          </Link>
        </div>

        <div className="p-6 rounded-md bg-rose-950/60 border border-rose-800/80 text-xs font-mono text-rose-300 space-y-2">
          <div className="flex items-center gap-2 font-semibold">
            <AlertCircle className="w-4 h-4 text-rose-400" />
            <span>Entity Retrieval Failed</span>
          </div>
          <div className="text-rose-200/90">{error || `Entity ${entityId} not found in knowledge graph.`}</div>
          <div className="pt-2 text-[11px] text-slate-400">
            Target Endpoint: <code className="text-slate-200">GET /api/v1/entities/{entityId}</code>
          </div>
        </div>
      </div>
    );
  }

  // --------------------------------------------------------------------------
  // Render: Full Entity Intelligence Dossier
  // --------------------------------------------------------------------------
  const attributesEntries = details.attributes
    ? Object.entries(details.attributes).filter(([k]) => k !== 'attributes_json')
    : [];

  return (
    <div className="space-y-6">
      {/* Entity Context Navigation & Action Bar */}
      <div className="border-b border-institutional-border pb-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link
              to="/investigation"
              title="Return to Entity Search"
              className="p-2 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
            </Link>

            <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-blue-400">
              {getEntityIcon(details.entity_type)}
            </div>

            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 font-semibold">
                  {details.entity_type}
                </span>
                <span className="text-[11px] font-mono text-institutional-textMuted truncate max-w-sm">
                  {details.entity_id}
                </span>
              </div>
              <h1 className="text-xl font-bold text-white tracking-tight mt-1">
                {details.canonical_name || details.entity_id}
              </h1>
            </div>
          </div>

          {/* Primary Progression Actions: Network Explorer & Timeline */}
          <div className="flex items-center gap-2 self-start md:self-auto">
            <button
              onClick={() => navigate(`/timeline?entity_id=${encodeURIComponent(details.entity_id)}`)}
              className="flex items-center gap-1.5 px-3 py-2 text-xs font-mono rounded bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 transition-colors"
            >
              <Clock className="w-3.5 h-3.5 text-blue-400" />
              <span>Timeline</span>
            </button>
            <button
              onClick={() => navigate(`/network?focus=${encodeURIComponent(details.entity_id)}`)}
              className="flex items-center gap-2 px-4 py-2 text-xs font-mono font-medium rounded bg-blue-600 hover:bg-blue-500 text-white shadow-sm transition-colors"
            >
              <Network className="w-3.5 h-3.5" />
              <span>Explore in Network Explorer</span>
              <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </button>
          </div>
        </div>

        {/* Workflow breadcrumb notice */}
        <div className="mt-3 flex items-center justify-between text-[11px] font-mono text-institutional-textMuted border-t border-institutional-borderMuted pt-2">
          <span>
            Workflow Stage: <strong className="text-slate-300">ENTITY CONTEXT</strong> → Next: <strong className="text-sky-300">NETWORK EXPLORER</strong>
          </span>
          <span className="text-slate-500">
            Audited Graph Read: Live Neo4j Query Layer
          </span>
        </div>
      </div>

      {/* Top Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-3.5 rounded-md bg-institutional-panel border border-institutional-border space-y-1">
          <div className="text-[10px] font-mono uppercase text-institutional-textSecondary font-semibold">
            Direct Relationships
          </div>
          <div className="text-2xl font-mono font-bold text-white tabular-numbers">
            {details.direct_relationship_count}
          </div>
          <div className="text-[10px] font-mono text-institutional-textMuted">
            Connected edges in graph
          </div>
        </div>

        <div className="p-3.5 rounded-md bg-institutional-panel border border-institutional-border space-y-1">
          <div className="text-[10px] font-mono uppercase text-institutional-textSecondary font-semibold">
            Possible Match Pairs
          </div>
          <div className="text-2xl font-mono font-bold text-amber-400 tabular-numbers">
            {details.possible_match_count}
          </div>
          <div className="text-[10px] font-mono text-institutional-textMuted">
            [:EVALUATED_PAIR] unmerged
          </div>
        </div>

        <div className="p-3.5 rounded-md bg-institutional-panel border border-institutional-border space-y-1">
          <div className="text-[10px] font-mono uppercase text-institutional-textSecondary font-semibold">
            Neighborhood Nodes
          </div>
          <div className="text-2xl font-mono font-bold text-sky-400 tabular-numbers">
            {neighborhood?.total_nodes ?? 0}
          </div>
          <div className="text-[10px] font-mono text-institutional-textMuted">
            Bounded 1-hop radius
          </div>
        </div>

        <div className="p-3.5 rounded-md bg-institutional-panel border border-institutional-border space-y-1">
          <div className="text-[10px] font-mono uppercase text-institutional-textSecondary font-semibold">
            Neighborhood Edges
          </div>
          <div className="text-2xl font-mono font-bold text-indigo-400 tabular-numbers">
            {neighborhood?.total_edges ?? 0}
          </div>
          <div className="text-[10px] font-mono text-institutional-textMuted">
            Interconnecting relationships
          </div>
        </div>
      </div>

      {/* Main Intelligence Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Properties, Identifiers & Source Records */}
        <div className="space-y-6">
          {/* Canonical Properties Box */}
          <div className="p-5 rounded-md bg-institutional-panel border border-institutional-border space-y-4">
            <div className="flex items-center gap-2 border-b border-institutional-borderMuted pb-2.5">
              <Fingerprint className="w-4 h-4 text-blue-400" />
              <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-institutional-textPrimary">
                Entity Identifiers & Properties
              </h2>
            </div>

            <div className="space-y-2 text-xs font-mono">
              <div className="flex justify-between py-1.5 border-b border-institutional-borderMuted">
                <span className="text-institutional-textSecondary">Canonical Name:</span>
                <span className="text-white font-medium">{details.canonical_name || '—'}</span>
              </div>

              {details.full_name && (
                <div className="flex justify-between py-1.5 border-b border-institutional-borderMuted">
                  <span className="text-institutional-textSecondary">Full Name:</span>
                  <span className="text-slate-200">{details.full_name}</span>
                </div>
              )}

              {details.national_id && (
                <div className="flex justify-between py-1.5 border-b border-institutional-borderMuted">
                  <span className="text-institutional-textSecondary">National ID:</span>
                  <span className="text-amber-300 font-semibold">{details.national_id}</span>
                </div>
              )}

              {details.phone_number && (
                <div className="flex justify-between py-1.5 border-b border-institutional-borderMuted">
                  <span className="text-institutional-textSecondary">Phone MSISDN:</span>
                  <span className="text-emerald-300 font-semibold">{details.phone_number}</span>
                </div>
              )}

              {details.registration_number && (
                <div className="flex justify-between py-1.5 border-b border-institutional-borderMuted">
                  <span className="text-institutional-textSecondary">Plate Number:</span>
                  <span className="text-amber-300 font-semibold">{details.registration_number}</span>
                </div>
              )}

              {details.account_number && (
                <div className="flex justify-between py-1.5 border-b border-institutional-borderMuted">
                  <span className="text-institutional-textSecondary">Account No:</span>
                  <span className="text-cyan-300 font-semibold">{details.account_number}</span>
                </div>
              )}

              {details.address && (
                <div className="flex justify-between py-1.5 border-b border-institutional-borderMuted">
                  <span className="text-institutional-textSecondary">Address:</span>
                  <span className="text-slate-200">{details.address}</span>
                </div>
              )}

              {details.org_name && (
                <div className="flex justify-between py-1.5 border-b border-institutional-borderMuted">
                  <span className="text-institutional-textSecondary">Org Name:</span>
                  <span className="text-purple-300">{details.org_name}</span>
                </div>
              )}

              {details.labels && details.labels.length > 0 && (
                <div className="flex justify-between py-1.5 border-b border-institutional-borderMuted">
                  <span className="text-institutional-textSecondary">Graph Labels:</span>
                  <div className="flex gap-1 flex-wrap justify-end">
                    {details.labels.map((l) => (
                      <span key={l} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
                        {l}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {details.created_at && (
                <div className="flex justify-between py-1.5">
                  <span className="text-institutional-textSecondary">Ingested / Recorded:</span>
                  <span className="text-slate-400 text-[11px]">
                    {new Date(details.created_at).toLocaleDateString()}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Resolved Attributes Table */}
          {attributesEntries.length > 0 && (
            <div className="p-5 rounded-md bg-institutional-panel border border-institutional-border space-y-3">
              <div className="flex items-center gap-2 border-b border-institutional-borderMuted pb-2.5">
                <Layers className="w-4 h-4 text-emerald-400" />
                <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-institutional-textPrimary">
                  Extracted Attributes
                </h2>
              </div>
              <div className="space-y-1.5 text-xs font-mono">
                {attributesEntries.map(([key, val]) => (
                  <div
                    key={key}
                    className="flex items-center justify-between p-2 rounded bg-slate-900/60 border border-slate-800"
                  >
                    <span className="text-institutional-textSecondary">{key}:</span>
                    <span className="text-slate-200 font-medium">
                      {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Source Records & Evidence Provenance */}
          <div className="p-5 rounded-md bg-institutional-panel border border-institutional-border space-y-3">
            <div className="flex items-center gap-2 border-b border-institutional-borderMuted pb-2.5">
              <FileText className="w-4 h-4 text-purple-400" />
              <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-institutional-textPrimary">
                Source Record Provenance
              </h2>
            </div>

            {details.source_record_ids && details.source_record_ids.length > 0 ? (
              <div className="space-y-2 text-xs font-mono">
                {details.source_record_ids.map((srcId) => (
                  <div
                    key={srcId}
                    className="p-2 rounded bg-slate-900 border border-slate-800 text-[11px] text-sky-300 break-all flex items-start gap-2"
                  >
                    <span className="text-slate-500 select-none">↳</span>
                    <span>{srcId}</span>
                  </div>
                ))}
                <p className="text-[11px] text-institutional-textMuted pt-1">
                  Traces directly to raw source document in Phase 2 ingestion store.
                </p>
              </div>
            ) : (
              <div className="p-3 rounded bg-slate-900/50 border border-slate-800 text-xs font-mono text-institutional-textMuted text-center">
                Zero source records directly linked.
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Direct Relationships and Bounded Neighborhood */}
        <div className="lg:col-span-2 space-y-6">
          {/* Direct Relationships Table */}
          <div className="rounded-md bg-institutional-panel border border-institutional-border overflow-hidden">
            <div className="p-3.5 border-b border-institutional-border flex items-center justify-between bg-slate-950/40">
              <div className="flex items-center gap-2">
                <Network className="w-4 h-4 text-blue-400" />
                <span className="text-xs font-mono uppercase tracking-wider text-institutional-textPrimary font-semibold">
                  Direct Relationships & Connected Entities ({neighborhood?.relationships.length ?? 0})
                </span>
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                Depth: 1 Hop · Limit: 50
              </span>
            </div>

            {neighborhood && neighborhood.relationships.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono border-collapse">
                  <thead>
                    <tr className="border-b border-institutional-border bg-slate-900/60 text-institutional-textMuted uppercase text-[10px] tracking-wider">
                      <th className="py-2.5 px-4 font-semibold">Connected Target</th>
                      <th className="py-2.5 px-4 font-semibold">Relationship Type</th>
                      <th className="py-2.5 px-4 font-semibold text-center">Count</th>
                      <th className="py-2.5 px-4 font-semibold">Time Window</th>
                      <th className="py-2.5 px-4 font-semibold text-right">Inspect</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-institutional-borderMuted">
                    {neighborhood.relationships.map((rel, idx) => {
                      // Determine opposite entity ID
                      const isSource = rel.source_entity_id === details.entity_id;
                      const otherEntityId = isSource ? rel.target_entity_id : rel.source_entity_id;
                      const otherName = isSource ? (rel.target_name || rel.target_entity_id) : (rel.source_name || rel.source_entity_id);

                      const hasTime = rel.first_seen || rel.last_seen;
                      const timeStr = hasTime
                        ? `${rel.first_seen ? new Date(rel.first_seen).toLocaleDateString() : '—'} → ${
                            rel.last_seen ? new Date(rel.last_seen).toLocaleDateString() : '—'
                          }`
                        : 'Undated';

                      return (
                        <tr
                          key={rel.relationship_id || idx}
                          className="hover:bg-slate-900/50 transition-colors"
                        >
                          <td className="py-3 px-4">
                            <div className="font-medium text-white">{otherName}</div>
                            <div className="text-[10px] text-institutional-textMuted truncate max-w-xs">
                              {otherEntityId}
                            </div>
                          </td>

                          <td className="py-3 px-4 whitespace-nowrap">
                            <span
                              className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold border ${getRelationshipBadgeColor(
                                rel.relationship_type
                              )}`}
                            >
                              {rel.relationship_type}
                            </span>
                          </td>

                          <td className="py-3 px-4 text-center tabular-numbers text-slate-300">
                            {rel.interaction_count}
                          </td>

                          <td className="py-3 px-4 text-institutional-textSecondary whitespace-nowrap text-[11px]">
                            <div className="flex items-center gap-1.5">
                              <Clock className="w-3 h-3 text-slate-500" />
                              <span>{timeStr}</span>
                            </div>
                          </td>

                          <td className="py-3 px-4 text-right whitespace-nowrap">
                            <button
                              onClick={() => navigate(`/entities?id=${encodeURIComponent(otherEntityId)}`)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700 text-xs transition-colors"
                            >
                              <span>Context</span>
                              <ExternalLink className="w-3 h-3 text-slate-400" />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 text-center space-y-2">
                <Network className="w-6 h-6 text-slate-600 mx-auto" />
                <div className="text-xs font-mono text-slate-400">
                  Zero direct relationships connected to this entity in the knowledge graph.
                </div>
              </div>
            )}
          </div>

          {/* Neighborhood Topological Overview & Next Step */}
          <div className="p-5 rounded-md bg-institutional-panel border border-institutional-border space-y-4">
            <div className="flex items-center justify-between border-b border-institutional-borderMuted pb-3">
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-emerald-400" />
                <h2 className="text-xs font-mono font-semibold uppercase tracking-wider text-institutional-textPrimary">
                  Topological Analysis & Network Progression
                </h2>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950 border border-blue-800 text-blue-300">
                Phase 6B.2 Destination
              </span>
            </div>

            <p className="text-xs text-institutional-textSecondary leading-relaxed">
              This entity possesses <strong className="text-white">{details.direct_relationship_count}</strong> direct connection(s) and <strong className="text-amber-400">{details.possible_match_count}</strong> possible match resolution candidate(s) in the active case knowledge graph.
              Proceed to <strong className="text-slate-200">Network Explorer</strong> to visually inspect the multi-hop graph neighborhood, bridge centralities, and clustered structures using interactive topology tooling.
            </p>

            <div className="pt-2 flex items-center justify-between">
              <div className="text-[11px] font-mono text-institutional-textMuted">
                Endpoint: <code className="text-slate-300">GET /api/v1/entities/{details.entity_id}/neighborhood?depth=1</code>
              </div>

              <button
                onClick={() => navigate(`/network?focus=${encodeURIComponent(details.entity_id)}`)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-900 hover:bg-slate-800 text-blue-400 hover:text-blue-300 border border-slate-700 text-xs font-mono transition-colors"
              >
                <span>Launch in Network Explorer</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Search,
  Users,
  Filter,
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
} from 'lucide-react';
import { searchEntities, EntityRecord } from '../api';

const ENTITY_TYPES = [
  { label: 'All Entity Types', value: '' },
  { label: 'Person', value: 'PERSON' },
  { label: 'Phone', value: 'PHONE' },
  { label: 'Vehicle', value: 'VEHICLE' },
  { label: 'Location', value: 'LOCATION' },
  { label: 'Organization', value: 'ORGANIZATION' },
  { label: 'Account', value: 'ACCOUNT' },
];

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

export const Investigation: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const initialQuery = searchParams.get('q') || '';
  const initialType = searchParams.get('type') || '';

  const [query, setQuery] = useState(initialQuery);
  const [selectedType, setSelectedType] = useState(initialType);
  const [results, setResults] = useState<EntityRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const executeSearch = useCallback(async (searchQuery: string, typeFilter: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await searchEntities({
        query: searchQuery.trim() || undefined,
        entity_type: typeFilter.trim() || undefined,
        limit: 100,
      });
      setResults(data);
      setHasSearched(true);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to query entities from backend';
      setError(message);
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial search on mount
  useEffect(() => {
    executeSearch(initialQuery, initialType);
  }, [executeSearch, initialQuery, initialType]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newParams: Record<string, string> = {};
    if (query.trim()) newParams.q = query.trim();
    if (selectedType.trim()) newParams.type = selectedType.trim();
    setSearchParams(newParams);
    executeSearch(query, selectedType);
  };

  const handleSelectEntity = (entityId: string) => {
    navigate(`/entities?id=${encodeURIComponent(entityId)}`);
  };

  const extractKeyIdentifier = (entity: EntityRecord): string => {
    if (entity.phone_number) return entity.phone_number;
    if (entity.national_id) return `ID: ${entity.national_id}`;
    if (entity.registration_number) return `Reg: ${entity.registration_number}`;
    if (entity.account_number) return `Acc: ${entity.account_number}`;
    if (entity.address) return entity.address;
    if (entity.org_name) return entity.org_name;
    if (entity.attributes && Object.keys(entity.attributes).length > 0) {
      const firstEntry = Object.entries(entity.attributes)[0];
      return `${firstEntry[0]}: ${String(firstEntry[1])}`;
    }
    return '—';
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="border-b border-institutional-border pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-blue-400">
              <Search className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-slate-800/90 border border-slate-700 text-slate-300">
                  MOD-01-SRCH
                </span>
                <span className="text-xs font-mono text-emerald-400 uppercase tracking-wider">
                  Operational (Phase 6B.1)
                </span>
              </div>
              <h1 className="text-xl font-semibold text-institutional-textPrimary tracking-tight mt-1">
                Investigation / Entity Search
              </h1>
              <p className="text-xs text-institutional-textSecondary mt-0.5">
                Query canonical entities by name, alias, phone, vehicle plate, account, or national identifier.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto text-xs font-mono px-3 py-1.5 rounded bg-slate-900 border border-slate-800 text-slate-400">
            <Shield className="w-4 h-4 text-blue-400" />
            <span>KNOWLEDGE GRAPH SEARCH</span>
          </div>
        </div>
      </div>

      {/* Search and Filter Panel */}
      <div className="p-4 rounded-md bg-institutional-panel border border-institutional-border">
        <form onSubmit={handleSubmit} className="flex flex-col md:flex-row items-stretch gap-3">
          <div className="flex-1 relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by name, phone (+91...), plate (DL-...), ID (IND-...), or account..."
              className="w-full pl-9 pr-3 py-2 text-xs font-mono rounded bg-slate-900 border border-slate-800 focus:border-blue-700 focus:outline-none text-white placeholder:text-slate-500 transition-colors"
            />
          </div>

          <div className="w-full md:w-56 relative">
            <Filter className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <select
              value={selectedType}
              onChange={(e) => {
                setSelectedType(e.target.value);
              }}
              className="w-full pl-8 pr-3 py-2 text-xs font-mono rounded bg-slate-900 border border-slate-800 focus:border-blue-700 focus:outline-none text-white appearance-none cursor-pointer"
            >
              {ENTITY_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="flex items-center justify-center gap-2 px-4 py-2 text-xs font-mono font-medium rounded bg-blue-600 hover:bg-blue-500 text-white shadow-sm transition-colors disabled:opacity-50 shrink-0"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Search Entities</span>
          </button>
        </form>

        <div className="mt-3 pt-3 border-t border-institutional-borderMuted flex items-center justify-between text-[11px] font-mono text-institutional-textMuted">
          <span>Target Endpoint: GET /api/v1/entities (Max Limit: 100)</span>
          {hasSearched && (
            <span className="text-slate-400">
              Found <strong className="text-white tabular-numbers">{results.length}</strong> matching canonical entities
            </span>
          )}
        </div>
      </div>

      {/* Error Notice */}
      {error && (
        <div className="p-4 rounded-md bg-rose-950/60 border border-rose-800/80 text-xs font-mono text-rose-300 flex items-start gap-3">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold">Entity Search Failed</div>
            <div className="text-rose-200/90 mt-0.5">{error}</div>
          </div>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="p-8 rounded-md bg-institutional-panel border border-institutional-border text-center space-y-3">
          <RefreshCw className="w-5 h-5 text-blue-400 animate-spin mx-auto" />
          <div className="text-xs font-mono text-slate-400">
            Querying knowledge graph entities from Neo4j...
          </div>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && hasSearched && results.length === 0 && (
        <div className="p-8 rounded-md bg-institutional-panel border border-institutional-border text-center space-y-2">
          <Users className="w-8 h-8 text-slate-600 mx-auto" />
          <h2 className="text-sm font-mono font-semibold text-slate-300">
            No Entities Found
          </h2>
          <p className="text-xs text-institutional-textSecondary max-w-md mx-auto">
            Zero canonical entities matched query criteria. Clear filters or verify if data has been ingested into the graph database.
          </p>
        </div>
      )}

      {/* Real Entities Results Table */}
      {!isLoading && results.length > 0 && (
        <div className="rounded-md bg-institutional-panel border border-institutional-border overflow-hidden">
          <div className="p-3 border-b border-institutional-border flex items-center justify-between bg-slate-950/40">
            <span className="text-xs font-mono uppercase tracking-wider text-institutional-textSecondary font-semibold">
              Canonical Entities Ledger
            </span>
            <span className="text-[11px] font-mono text-slate-400">
              Deterministic Knowledge Graph Slice
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono border-collapse">
              <thead>
                <tr className="border-b border-institutional-border bg-slate-900/60 text-institutional-textMuted uppercase text-[10px] tracking-wider">
                  <th className="py-2.5 px-4 font-semibold">Entity Type</th>
                  <th className="py-2.5 px-4 font-semibold">Canonical Name / Value</th>
                  <th className="py-2.5 px-4 font-semibold">Key Identifier</th>
                  <th className="py-2.5 px-4 font-semibold">Entity URN</th>
                  <th className="py-2.5 px-4 font-semibold text-right">Investigation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-institutional-borderMuted">
                {results.map((entity) => {
                  const keyId = extractKeyIdentifier(entity);
                  return (
                    <tr
                      key={entity.entity_id}
                      onClick={() => handleSelectEntity(entity.entity_id)}
                      className="hover:bg-slate-900/50 cursor-pointer transition-colors group"
                    >
                      <td className="py-3 px-4 whitespace-nowrap">
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300 text-[11px]">
                          {getEntityIcon(entity.entity_type)}
                          <span>{entity.entity_type}</span>
                        </span>
                      </td>

                      <td className="py-3 px-4 font-medium text-white whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <span>{entity.canonical_name || entity.entity_id}</span>
                          {entity.aliases && entity.aliases.length > 0 && (
                            <span className="text-[10px] px-1 rounded bg-slate-800 text-slate-400">
                              alias: {entity.aliases[0]}
                            </span>
                          )}
                        </div>
                      </td>

                      <td className="py-3 px-4 text-institutional-textSecondary whitespace-nowrap">
                        {keyId}
                      </td>

                      <td className="py-3 px-4 text-institutional-textMuted text-[11px] font-mono truncate max-w-xs">
                        {entity.entity_id}
                      </td>

                      <td className="py-3 px-4 text-right whitespace-nowrap">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSelectEntity(entity.entity_id);
                          }}
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-blue-950/60 hover:bg-blue-900 text-blue-300 border border-blue-800/80 text-xs transition-colors"
                        >
                          <span>Inspect</span>
                          <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import cytoscape, { Core, ElementDefinition, NodeSingular, EdgeSingular } from 'cytoscape';
import {
  Network,
  Maximize2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Search,
  ArrowRight,
  ArrowLeft,
  ExternalLink,
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
  X,
  Clock,
  ChevronRight,
} from 'lucide-react';
import {
  getEntityNeighborhood,
  searchEntities,
  EntityRecord,
  NeighborhoodRelationship,
  EntityNeighborhoodResponse,
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

interface SelectedNodeData {
  id: string;
  label: string;
  entityType: string;
  isCenter: boolean;
  rawEntity: EntityRecord;
}

interface SelectedEdgeData {
  id: string;
  source: string;
  target: string;
  label: string;
  interactionCount: number;
  confidence: number;
  rawRelationship: NeighborhoodRelationship;
}

type LayoutType = 'cose' | 'concentric' | 'breadthfirst';

export const NetworkExplorer: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const focusEntityId = (searchParams.get('focus') || '').trim();

  // Neighborhood Graph State
  const [neighborhood, setNeighborhood] = useState<EntityNeighborhoodResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Fallback / Initial Quick Select Entities
  const [sampleEntities, setSampleEntities] = useState<EntityRecord[]>([]);
  const [manualIdInput, setManualIdInput] = useState<string>('');

  // Cytoscape DOM container & Instance reference
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  // Inspector state
  const [selectedNode, setSelectedNode] = useState<SelectedNodeData | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<SelectedEdgeData | null>(null);
  const [layoutName, setLayoutName] = useState<LayoutType>('cose');

  // --------------------------------------------------------------------------
  // Fetch sample entities for quick select when no focus is set
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
        // Soft fail on sample entities list
      }
    }
    if (!focusEntityId) {
      loadSamples();
    }
    return () => {
      isMounted = false;
    };
  }, [focusEntityId]);

  // --------------------------------------------------------------------------
  // Fetch 2-hop bounded neighborhood from backend
  // --------------------------------------------------------------------------
  const fetchNeighborhood = useCallback(async (entityId: string) => {
    if (!entityId) {
      setNeighborhood(null);
      return;
    }

    setIsLoading(true);
    setError(null);
    setSelectedNode(null);
    setSelectedEdge(null);

    try {
      // Strictly depth=2, limit=50 as required by institutional bounded graph contract
      const data = await getEntityNeighborhood(entityId, 2, 50);
      setNeighborhood(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve neighborhood graph from backend';
      setError(msg);
      setNeighborhood(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (focusEntityId) {
      fetchNeighborhood(focusEntityId);
    } else {
      setNeighborhood(null);
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
    }
  }, [focusEntityId, fetchNeighborhood]);

  // --------------------------------------------------------------------------
  // Run Cytoscape Layout
  // --------------------------------------------------------------------------
  const runLayout = useCallback((cy: Core, type: LayoutType, centerId: string) => {
    let layoutConfig: cytoscape.LayoutOptions;

    if (type === 'concentric') {
      layoutConfig = {
        name: 'concentric',
        concentric: (node: NodeSingular) => (node.data('isCenter') ? 2 : 1),
        levelWidth: () => 1,
        padding: 50,
        animate: false,
      } as cytoscape.LayoutOptions;
    } else if (type === 'breadthfirst') {
      layoutConfig = {
        name: 'breadthfirst',
        roots: centerId ? `node[id = "${centerId}"]` : undefined,
        directed: true,
        padding: 50,
        animate: false,
      } as cytoscape.LayoutOptions;
    } else {
      // 'cose' physics-directed layout
      layoutConfig = {
        name: 'cose',
        animate: false,
        padding: 50,
        nodeRepulsion: () => 700000,
        idealEdgeLength: () => 140,
        edgeElasticity: () => 100,
        nestingFactor: 1.2,
        gravity: 1,
        numIter: 1000,
        initialTemp: 1000,
        coolingFactor: 0.99,
        minTemp: 1.0,
      } as cytoscape.LayoutOptions;
    }

    const layout = cy.layout(layoutConfig);
    layout.run();
  }, []);

  // --------------------------------------------------------------------------
  // Cytoscape Mount & Update Lifecycle
  // --------------------------------------------------------------------------
  useEffect(() => {
    if (!containerRef.current || !neighborhood) return;

    // Destroy existing instance to guarantee clean DOM attachment
    if (cyRef.current) {
      cyRef.current.destroy();
      cyRef.current = null;
    }

    // Build elements
    const elements: ElementDefinition[] = [];
    const nodeIds = new Set<string>();

    const centerId = neighborhood.center_entity_id;

    // 1. Nodes
    for (const ent of neighborhood.entities) {
      if (!ent.entity_id) continue;
      nodeIds.add(ent.entity_id);
      const isCenter = ent.entity_id === centerId;
      const label = ent.canonical_name || ent.entity_id;

      elements.push({
        group: 'nodes',
        data: {
          id: ent.entity_id,
          label: label,
          entityType: (ent.entity_type || 'UNKNOWN').toUpperCase(),
          isCenter: isCenter,
          rawEntity: ent,
        },
      });
    }

    // Ensure center entity is always represented even if missing from entities array
    if (centerId && !nodeIds.has(centerId)) {
      nodeIds.add(centerId);
      elements.push({
        group: 'nodes',
        data: {
          id: centerId,
          label: centerId,
          entityType: 'UNKNOWN',
          isCenter: true,
          rawEntity: { entity_id: centerId, entity_type: 'UNKNOWN' },
        },
      });
    }

    // 2. Edges
    const edgeIds = new Set<string>();
    const relationships = neighborhood.relationships || [];
    for (let i = 0; i < relationships.length; i++) {
      const rel = relationships[i];
      const src = rel.source_entity_id;
      const tgt = rel.target_entity_id;

      // Ensure both source and target nodes exist in Cytoscape
      if (!src || !tgt || !nodeIds.has(src) || !nodeIds.has(tgt)) {
        continue;
      }

      const edgeId = rel.relationship_id || `rel-${src}-${rel.relationship_type}-${tgt}-${i}`;
      if (edgeIds.has(edgeId)) continue;
      edgeIds.add(edgeId);

      elements.push({
        group: 'edges',
        data: {
          id: edgeId,
          source: src,
          target: tgt,
          label: rel.relationship_type,
          interactionCount: rel.interaction_count || 1,
          confidence: rel.confidence,
          rawRelationship: rel,
        },
      });
    }

    // Institutional Dark Cytoscape Stylesheet
    const cy = cytoscape({
      container: containerRef.current,
      elements: elements,
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'shape': 'round-rectangle',
            'width': 44,
            'height': 44,
            'background-color': '#1e293b',
            'border-width': 2,
            'border-color': '#475569',
            'color': '#cbd5e1',
            'font-family': 'ui-monospace, SFMono-Regular, Menlo, monospace',
            'font-size': '10px',
            'text-valign': 'bottom',
            'text-margin-y': 6,
            'text-max-width': '120px',
            'text-wrap': 'ellipsis',
            'text-background-color': '#0a0e17',
            'text-background-opacity': 0.88,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'text-border-color': '#1e293b',
            'text-border-width': 1,
            'text-border-opacity': 0.8,
          } as unknown as cytoscape.Css.Node,
        },
        {
          selector: 'node[entityType = "PERSON"]',
          style: {
            'background-color': '#1e3a5f',
            'border-color': '#3b82f6',
          } as unknown as cytoscape.Css.Node,
        },
        {
          selector: 'node[entityType = "PHONE"]',
          style: {
            'background-color': '#064e3b',
            'border-color': '#10b981',
          } as unknown as cytoscape.Css.Node,
        },
        {
          selector: 'node[entityType = "VEHICLE"]',
          style: {
            'background-color': '#78350f',
            'border-color': '#f59e0b',
          } as unknown as cytoscape.Css.Node,
        },
        {
          selector: 'node[entityType = "LOCATION"]',
          style: {
            'background-color': '#881337',
            'border-color': '#f43f5e',
          } as unknown as cytoscape.Css.Node,
        },
        {
          selector: 'node[entityType = "ORGANIZATION"]',
          style: {
            'background-color': '#4c1d95',
            'border-color': '#a855f7',
          } as unknown as cytoscape.Css.Node,
        },
        {
          selector: 'node[entityType = "ACCOUNT"]',
          style: {
            'background-color': '#0e7490',
            'border-color': '#06b6d4',
          } as unknown as cytoscape.Css.Node,
        },
        {
          selector: 'node[?isCenter]',
          style: {
            'width': 54,
            'height': 54,
            'border-width': 4,
            'border-color': '#38bdf8',
            'border-style': 'solid',
            'font-weight': 'bold',
            'color': '#38bdf8',
          } as unknown as cytoscape.Css.Node,
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 4,
            'border-color': '#ffffff',
            'overlay-color': '#38bdf8',
            'overlay-opacity': 0.15,
            'overlay-padding': 6,
          } as unknown as cytoscape.Css.Node,
        },
        {
          selector: 'edge',
          style: {
            'label': 'data(label)',
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#475569',
            'line-color': '#334155',
            'width': 2,
            'arrow-scale': 1.1,
            'font-family': 'ui-monospace, SFMono-Regular, Menlo, monospace',
            'font-size': '8px',
            'color': '#94a3b8',
            'text-rotation': 'autorotate',
            'text-background-color': '#0a0e17',
            'text-background-opacity': 0.88,
            'text-background-padding': '2px',
            'text-background-shape': 'roundrectangle',
            'text-border-color': '#1e293b',
            'text-border-width': 1,
            'text-border-opacity': 0.8,
          } as unknown as cytoscape.Css.Edge,
        },
        {
          selector: 'edge[label = "COMMUNICATED_WITH"]',
          style: {
            'line-color': '#065f46',
            'target-arrow-color': '#10b981',
          } as unknown as cytoscape.Css.Edge,
        },
        {
          selector: 'edge[label = "OWNED_BY"]',
          style: {
            'line-color': '#1e40af',
            'target-arrow-color': '#3b82f6',
          } as unknown as cytoscape.Css.Edge,
        },
        {
          selector: 'edge[label = "ASSOCIATED_WITH"]',
          style: {
            'line-color': '#92400e',
            'target-arrow-color': '#f59e0b',
          } as unknown as cytoscape.Css.Edge,
        },
        {
          selector: 'edge[label = "TRANSACTED_WITH"]',
          style: {
            'line-color': '#155e75',
            'target-arrow-color': '#06b6d4',
          } as unknown as cytoscape.Css.Edge,
        },
        {
          selector: 'edge:selected',
          style: {
            'line-color': '#60a5fa',
            'target-arrow-color': '#60a5fa',
            'width': 3,
            'color': '#ffffff',
          } as unknown as cytoscape.Css.Edge,
        },
      ],
      minZoom: 0.15,
      maxZoom: 3.5,
      wheelSensitivity: 0.25,
      boxSelectionEnabled: false,
    });

    cyRef.current = cy;

    // Node selection
    cy.on('tap', 'node', (evt) => {
      const node = evt.target as NodeSingular;
      setSelectedNode(node.data() as SelectedNodeData);
      setSelectedEdge(null);
    });

    // Edge selection
    cy.on('tap', 'edge', (evt) => {
      const edge = evt.target as EdgeSingular;
      setSelectedEdge(edge.data() as SelectedEdgeData);
      setSelectedNode(null);
    });

    // Canvas background tap deselects
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        setSelectedNode(null);
        setSelectedEdge(null);
      }
    });

    // Double tap node opens Entity Intelligence directly
    cy.on('dbltap', 'node', (evt) => {
      const node = evt.target as NodeSingular;
      const data = node.data() as SelectedNodeData;
      if (data?.id) {
        navigate(`/entities?id=${encodeURIComponent(data.id)}`);
      }
    });

    // Run layout and fit
    runLayout(cy, layoutName, centerId);
    cy.fit(undefined, 50);

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [neighborhood, layoutName, navigate, runLayout]);

  // Window resize handler
  useEffect(() => {
    const handleResize = () => {
      cyRef.current?.resize();
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // --------------------------------------------------------------------------
  // Canvas Control Handlers
  // --------------------------------------------------------------------------
  const handleFit = () => {
    cyRef.current?.fit(undefined, 50);
  };

  const handleZoomIn = () => {
    if (cyRef.current) {
      cyRef.current.zoom(cyRef.current.zoom() * 1.25);
      cyRef.current.center();
    }
  };

  const handleZoomOut = () => {
    if (cyRef.current) {
      cyRef.current.zoom(cyRef.current.zoom() * 0.8);
      cyRef.current.center();
    }
  };

  const handleResetLayout = () => {
    if (cyRef.current && neighborhood) {
      runLayout(cyRef.current, layoutName, neighborhood.center_entity_id);
      cyRef.current.fit(undefined, 50);
    }
  };

  const handleLayoutChange = (newLayout: LayoutType) => {
    setLayoutName(newLayout);
    if (cyRef.current && neighborhood) {
      runLayout(cyRef.current, newLayout, neighborhood.center_entity_id);
      cyRef.current.fit(undefined, 50);
    }
  };

  const handleFormSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (manualIdInput.trim()) {
      setSearchParams({ focus: manualIdInput.trim() });
    }
  };

  // Find center entity metadata
  const centerEntity = neighborhood?.entities.find(
    (e) => e.entity_id === neighborhood.center_entity_id
  );

  // Connected edges for selected node
  const selectedNodeConnectedRels = selectedNode && neighborhood
    ? neighborhood.relationships.filter(
        (r) => r.source_entity_id === selectedNode.id || r.target_entity_id === selectedNode.id
      )
    : [];

  // Entity type counts for graph overview
  const entityTypeCounts = neighborhood
    ? neighborhood.entities.reduce<Record<string, number>>((acc, ent) => {
        const t = (ent.entity_type || 'UNKNOWN').toUpperCase();
        acc[t] = (acc[t] || 0) + 1;
        return acc;
      }, {})
    : {};

  // --------------------------------------------------------------------------
  // Empty State: No focus entity specified
  // --------------------------------------------------------------------------
  if (!focusEntityId) {
    return (
      <div className="space-y-6">
        {/* Module Header */}
        <div className="border-b border-institutional-border pb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950/80 border border-blue-800 text-blue-300 font-semibold tracking-wide">
                MOD-03-NET
              </span>
              <span className="text-xs font-mono text-slate-400">GRAPH TOPOLOGY & NEIGHBORHOOD</span>
            </div>
            <h1 className="text-xl font-mono font-semibold text-white tracking-tight mt-1 flex items-center gap-2">
              <Network className="w-5 h-5 text-blue-400" />
              <span>Network Explorer</span>
            </h1>
            <p className="text-xs font-mono text-slate-400 mt-1">
              Interactive topological graph visualization of bounded 2-hop neighborhoods from Neo4j.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-400">
              DEPTH: <strong className="text-slate-200">2 HOPS</strong>
            </span>
            <span className="px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-400">
              LIMIT: <strong className="text-slate-200">50 EDGES</strong>
            </span>
          </div>
        </div>

        {/* Entity Lookup Form */}
        <div className="p-6 rounded-md bg-institutional-panel border border-institutional-border space-y-4">
          <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
            <Search className="w-4 h-4 text-blue-400" />
            <span className="font-semibold">SELECT CENTER ENTITY FOR GRAPH TRAVERSAL</span>
          </div>
          <p className="text-xs font-mono text-slate-400 leading-relaxed max-w-2xl">
            Specify a canonical entity identifier to render its bounded 2-hop network neighborhood.
            Node topology, direct relationships, and interaction edges will be fetched directly from the knowledge graph.
          </p>

          <form onSubmit={handleFormSearch} className="flex flex-col sm:flex-row gap-2 max-w-xl">
            <input
              type="text"
              value={manualIdInput}
              onChange={(e) => setManualIdInput(e.target.value)}
              placeholder="Enter Entity ID (e.g., ent-vikram-singh-001)..."
              className="flex-1 px-3 py-2 text-xs font-mono rounded bg-slate-900/90 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
            <button
              type="submit"
              className="px-4 py-2 text-xs font-mono font-medium rounded bg-blue-600 hover:bg-blue-500 text-white transition-colors flex items-center justify-center gap-1.5"
            >
              <Network className="w-3.5 h-3.5" />
              <span>Explore Neighborhood</span>
            </button>
          </form>
        </div>

        {/* Available Knowledge Graph Entities Quick Select */}
        {sampleEntities.length > 0 && (
          <div className="p-5 rounded-md bg-institutional-panel border border-institutional-border space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-mono uppercase tracking-wider text-institutional-textMuted font-semibold flex items-center gap-2">
                <Layers className="w-3.5 h-3.5 text-slate-400" />
                <span>Available Knowledge Graph Entities (Quick Select)</span>
              </h2>
              <Link
                to="/investigation"
                className="text-[11px] font-mono text-blue-400 hover:text-blue-300 flex items-center gap-1"
              >
                <span>Full Ledger Search</span>
                <ChevronRight className="w-3 h-3" />
              </Link>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {sampleEntities.map((ent) => (
                <div
                  key={ent.entity_id}
                  onClick={() => setSearchParams({ focus: ent.entity_id })}
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
  // Loading State
  // --------------------------------------------------------------------------
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="border-b border-institutional-border pb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSearchParams({})}
              className="p-1.5 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition-colors"
              title="Return to Entity Selector"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <span className="text-xs font-mono text-slate-400">Loading graph topology...</span>
          </div>
        </div>

        <div className="p-12 rounded-md bg-institutional-panel border border-institutional-border text-center space-y-3">
          <RefreshCw className="w-6 h-6 text-blue-400 animate-spin mx-auto" />
          <div className="text-xs font-mono text-slate-300 font-semibold">
            Querying bounded 2-hop neighborhood from Neo4j knowledge graph...
          </div>
          <div className="text-[11px] font-mono text-slate-500">
            Center Entity: <span className="text-blue-400">{focusEntityId}</span> · Traversal Depth: 2 · Limit: 50
          </div>
        </div>
      </div>
    );
  }

  // --------------------------------------------------------------------------
  // Error State
  // --------------------------------------------------------------------------
  if (error) {
    return (
      <div className="space-y-6">
        <div className="border-b border-institutional-border pb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSearchParams({})}
              className="p-1.5 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <span className="text-xs font-mono text-rose-400">Graph Exploration Error</span>
          </div>
        </div>

        <div className="p-6 rounded-md bg-rose-950/20 border border-rose-800/60 text-slate-200 space-y-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <div className="text-xs font-mono font-semibold text-rose-300 uppercase tracking-wide">
                Failed to Retrieve Network Neighborhood
              </div>
              <p className="text-xs font-mono text-slate-400">{error}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 pt-2 border-t border-rose-900/40">
            <button
              onClick={() => fetchNeighborhood(focusEntityId)}
              className="px-3 py-1.5 rounded bg-rose-900/60 hover:bg-rose-900 border border-rose-700 text-xs font-mono text-white transition-colors flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry Query</span>
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
  // Empty Neighborhood State (0 nodes returned)
  // --------------------------------------------------------------------------
  if (neighborhood && neighborhood.entities.length === 0) {
    return (
      <div className="space-y-6">
        <div className="border-b border-institutional-border pb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSearchParams({})}
              className="p-1.5 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <span className="text-xs font-mono text-slate-400">Empty Graph Neighborhood</span>
          </div>
        </div>

        <div className="p-8 rounded-md bg-institutional-panel border border-institutional-border text-center space-y-4">
          <Network className="w-8 h-8 text-slate-600 mx-auto" />
          <div className="space-y-1">
            <div className="text-sm font-mono font-semibold text-slate-300">
              No Network Neighborhood Discovered
            </div>
            <p className="text-xs font-mono text-slate-500 max-w-md mx-auto">
              Entity <span className="text-slate-300">{focusEntityId}</span> has no recorded relationships
              within 2 hops or does not exist in the knowledge graph.
            </p>
          </div>
          <div className="flex justify-center gap-2 pt-2">
            <button
              onClick={() => setSearchParams({})}
              className="px-4 py-2 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-mono text-slate-300 transition-colors"
            >
              Select Another Entity
            </button>
            <Link
              to="/investigation"
              className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-xs font-mono text-white transition-colors"
            >
              Back to Investigation Search
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // --------------------------------------------------------------------------
  // Graph Canvas View
  // --------------------------------------------------------------------------
  return (
    <div className="space-y-4 flex flex-col h-[calc(100vh-6rem)]">
      {/* Module Bar & Focus Entity Context */}
      <div className="border-b border-institutional-border pb-3 flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-3">
          <Link
            to={`/entities?id=${encodeURIComponent(focusEntityId)}`}
            className="p-1.5 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition-colors flex items-center gap-1 text-xs font-mono"
            title="Return to Entity Intelligence"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Entity Context</span>
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-950/80 border border-blue-800 text-blue-300 font-semibold">
                MOD-03-NET
              </span>
              <span className="text-xs font-mono text-slate-400">NEIGHBORHOOD GRAPH</span>
              <span className="text-slate-600">·</span>
              <span className="text-xs font-mono font-semibold text-white truncate max-w-xs">
                {centerEntity?.canonical_name || focusEntityId}
              </span>
              {centerEntity && (
                <span className="inline-flex items-center gap-1 px-1.5 py-0.2 rounded bg-slate-900 border border-slate-800 text-[10px] text-slate-400">
                  {getEntityIcon(centerEntity.entity_type)}
                  <span>{centerEntity.entity_type}</span>
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Quick Pivot Input & Bounded Contract Badges */}
        <div className="flex items-center gap-2">
          <form onSubmit={handleFormSearch} className="flex items-center gap-1.5">
            <input
              type="text"
              value={manualIdInput}
              onChange={(e) => setManualIdInput(e.target.value)}
              placeholder="Pivot entity ID..."
              className="w-36 sm:w-48 px-2.5 py-1 text-xs font-mono rounded bg-slate-900/90 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
            <button
              type="submit"
              className="p-1.5 rounded bg-slate-900 border border-slate-700 text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
              title="Pivot Network"
            >
              <Search className="w-3.5 h-3.5" />
            </button>
          </form>

          <span className="px-2 py-1 rounded bg-slate-900 border border-slate-800 text-[10px] font-mono text-slate-400 hidden md:inline">
            DEPTH: <strong className="text-slate-200">2 HOPS</strong>
          </span>
          <span className="px-2 py-1 rounded bg-slate-900 border border-slate-800 text-[10px] font-mono text-slate-400 hidden md:inline">
            LIMIT: <strong className="text-slate-200">50 EDGES</strong>
          </span>
        </div>
      </div>

      {/* Main Canvas + Inspector Grid */}
      <div className="flex-1 flex flex-col lg:flex-row gap-3 min-h-0 overflow-hidden">
        {/* Cytoscape Graph Canvas Area */}
        <div className="flex-1 flex flex-col bg-institutional-panel border border-institutional-border rounded-md overflow-hidden relative">
          {/* Graph Toolbar */}
          <div className="h-10 px-3 border-b border-institutional-border bg-slate-950/70 flex items-center justify-between shrink-0">
            {/* Left: Metrics & Layout Selector */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
                <span className="inline-flex items-center gap-1 text-slate-300">
                  <strong className="text-white">{neighborhood?.total_nodes || 0}</strong> Nodes
                </span>
                <span className="text-slate-600">·</span>
                <span className="inline-flex items-center gap-1 text-slate-300">
                  <strong className="text-white">{neighborhood?.total_edges || 0}</strong> Edges
                </span>
              </div>

              <div className="h-4 w-px bg-slate-800" />

              {/* Layout Switcher */}
              <div className="flex items-center gap-1 text-xs font-mono">
                <span className="text-slate-500 text-[11px] hidden sm:inline">Layout:</span>
                <select
                  value={layoutName}
                  onChange={(e) => handleLayoutChange(e.target.value as LayoutType)}
                  className="bg-slate-900 text-slate-300 border border-slate-700 rounded px-2 py-0.5 text-xs font-mono focus:outline-none focus:border-blue-500"
                >
                  <option value="cose">Force-Directed (COSE)</option>
                  <option value="concentric">Concentric Rings</option>
                  <option value="breadthfirst">Hierarchical (Tree)</option>
                </select>
              </div>
            </div>

            {/* Right: Zoom / Pan / Reset Controls */}
            <div className="flex items-center gap-1">
              <button
                onClick={handleZoomIn}
                className="p-1.5 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 hover:text-white transition-colors"
                title="Zoom In"
              >
                <ZoomIn className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={handleZoomOut}
                className="p-1.5 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 hover:text-white transition-colors"
                title="Zoom Out"
              >
                <ZoomOut className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={handleFit}
                className="p-1.5 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 hover:text-white transition-colors"
                title="Fit to Screen"
              >
                <Maximize2 className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={handleResetLayout}
                className="p-1.5 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 hover:text-white transition-colors"
                title="Reset Layout"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Cytoscape Container */}
          <div
            ref={containerRef}
            className="flex-1 w-full h-full bg-[#0A0E17] cursor-grab active:cursor-grabbing"
            style={{ minHeight: '400px' }}
          />

          {/* Legend Overlay */}
          <div className="absolute bottom-3 left-3 bg-slate-950/90 border border-slate-800 rounded p-2 text-[10px] font-mono space-y-1.5 pointer-events-none backdrop-blur-sm max-w-xs hidden sm:block">
            <div className="text-slate-400 font-semibold tracking-wider uppercase text-[9px]">
              Entity Type Legend
            </div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-slate-300">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-[#1e3a5f] border border-[#3b82f6]" />
                <span>PERSON</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-[#064e3b] border border-[#10b981]" />
                <span>PHONE</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-[#78350f] border border-[#f59e0b]" />
                <span>VEHICLE</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-[#881337] border border-[#f43f5e]" />
                <span>LOCATION</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-[#4c1d95] border border-[#a855f7]" />
                <span>ORGANIZATION</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-[#0e7490] border border-[#06b6d4]" />
                <span>ACCOUNT</span>
              </span>
            </div>
          </div>
        </div>

        {/* Right Docked Inspector Panel */}
        <div className="w-full lg:w-80 xl:w-96 bg-institutional-panel border border-institutional-border rounded-md flex flex-col shrink-0 overflow-hidden">
          {/* Selected Node Inspector */}
          {selectedNode ? (
            <div className="flex-1 flex flex-col overflow-y-auto">
              {/* Header */}
              <div className="p-3 border-b border-institutional-border bg-slate-950/60 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-[10px] font-mono text-slate-300">
                    {getEntityIcon(selectedNode.entityType)}
                    <span>{selectedNode.entityType}</span>
                  </span>
                  {selectedNode.isCenter && (
                    <span className="px-1.5 py-0.5 rounded bg-sky-950/80 border border-sky-700 text-[10px] font-mono text-sky-300 font-semibold">
                      FOCUS CENTER
                    </span>
                  )}
                </div>
                <button
                  onClick={() => setSelectedNode(null)}
                  className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                  title="Close Inspector"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Entity Identity & Primary Action */}
              <div className="p-4 space-y-3 border-b border-institutional-border">
                <div className="space-y-1">
                  <div className="text-sm font-mono font-bold text-white break-words">
                    {selectedNode.label}
                  </div>
                  <div className="text-[11px] font-mono text-institutional-textMuted break-all select-all">
                    {selectedNode.id}
                  </div>
                </div>

                {/* Primary Action: Link to Entity Intelligence */}
                <div className="space-y-2 pt-1">
                  <Link
                    to={`/entities?id=${encodeURIComponent(selectedNode.id)}`}
                    className="w-full py-2 px-3 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-mono font-medium flex items-center justify-center gap-2 shadow-sm transition-colors"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>Open Entity Intelligence</span>
                  </Link>

                  {/* Secondary Action: Re-center network on this node */}
                  {!selectedNode.isCenter && (
                    <button
                      onClick={() => setSearchParams({ focus: selectedNode.id })}
                      className="w-full py-2 px-3 bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 rounded text-xs font-mono flex items-center justify-center gap-2 transition-colors"
                    >
                      <Network className="w-3.5 h-3.5 text-blue-400" />
                      <span>Re-Center Network Here</span>
                    </button>
                  )}

                  {/* Tertiary Action: Trace Chronology in Timeline */}
                  <Link
                    to={`/timeline?entity_id=${encodeURIComponent(selectedNode.id)}`}
                    className="w-full py-2 px-3 bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 rounded text-xs font-mono flex items-center justify-center gap-2 transition-colors"
                  >
                    <Clock className="w-3.5 h-3.5 text-blue-400" />
                    <span>View Timeline Activity</span>
                  </Link>
                </div>
              </div>

              {/* Entity Attributes & Known Identifiers */}
              <div className="p-4 space-y-3 border-b border-institutional-border text-xs font-mono">
                <div className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                  Attributes & Identifiers
                </div>
                <div className="space-y-1.5">
                  {selectedNode.rawEntity.national_id && (
                    <div className="flex justify-between border-b border-slate-800/60 pb-1">
                      <span className="text-slate-500">National ID:</span>
                      <span className="text-slate-200 select-all">{selectedNode.rawEntity.national_id}</span>
                    </div>
                  )}
                  {selectedNode.rawEntity.phone_number && (
                    <div className="flex justify-between border-b border-slate-800/60 pb-1">
                      <span className="text-slate-500">Phone:</span>
                      <span className="text-slate-200 select-all">{selectedNode.rawEntity.phone_number}</span>
                    </div>
                  )}
                  {selectedNode.rawEntity.registration_number && (
                    <div className="flex justify-between border-b border-slate-800/60 pb-1">
                      <span className="text-slate-500">Registration:</span>
                      <span className="text-slate-200 select-all">{selectedNode.rawEntity.registration_number}</span>
                    </div>
                  )}
                  {selectedNode.rawEntity.address && (
                    <div className="flex justify-between border-b border-slate-800/60 pb-1">
                      <span className="text-slate-500">Address:</span>
                      <span className="text-slate-200 truncate max-w-[180px]">{selectedNode.rawEntity.address}</span>
                    </div>
                  )}
                  {selectedNode.rawEntity.account_number && (
                    <div className="flex justify-between border-b border-slate-800/60 pb-1">
                      <span className="text-slate-500">Account:</span>
                      <span className="text-slate-200 select-all">{selectedNode.rawEntity.account_number}</span>
                    </div>
                  )}
                  {selectedNode.rawEntity.aliases && selectedNode.rawEntity.aliases.length > 0 && (
                    <div className="space-y-1 border-b border-slate-800/60 pb-1">
                      <span className="text-slate-500">Aliases:</span>
                      <div className="flex flex-wrap gap-1">
                        {selectedNode.rawEntity.aliases.map((a, i) => (
                          <span key={i} className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-[10px] text-slate-300">
                            {a}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {selectedNode.rawEntity.source_record_ids && selectedNode.rawEntity.source_record_ids.length > 0 && (
                    <div className="flex justify-between border-b border-slate-800/60 pb-1">
                      <span className="text-slate-500">Sources:</span>
                      <span className="text-slate-300">{selectedNode.rawEntity.source_record_ids.length} records</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Connected Relationships in Graph Slice */}
              <div className="p-4 space-y-2 text-xs font-mono flex-1 overflow-y-auto">
                <div className="flex items-center justify-between text-[10px] uppercase text-slate-400 font-semibold tracking-wider">
                  <span>Neighborhood Links ({selectedNodeConnectedRels.length})</span>
                </div>
                {selectedNodeConnectedRels.length === 0 ? (
                  <div className="text-[11px] text-slate-500 italic">No direct links in current slice.</div>
                ) : (
                  <div className="space-y-1.5">
                    {selectedNodeConnectedRels.map((rel, idx) => {
                      const isOut = rel.source_entity_id === selectedNode.id;
                      const neighborId = isOut ? rel.target_entity_id : rel.source_entity_id;
                      const neighbor = neighborhood?.entities.find((e) => e.entity_id === neighborId);
                      const neighborName = neighbor?.canonical_name || neighborId;

                      return (
                        <div
                          key={idx}
                          onClick={() => {
                            if (neighborId) {
                              // Select the neighbor node
                              const ent = neighborhood?.entities.find((e) => e.entity_id === neighborId);
                              if (ent) {
                                setSelectedNode({
                                  id: ent.entity_id,
                                  label: ent.canonical_name || ent.entity_id,
                                  entityType: (ent.entity_type || 'UNKNOWN').toUpperCase(),
                                  isCenter: ent.entity_id === neighborhood?.center_entity_id,
                                  rawEntity: ent,
                                });
                              }
                            }
                          }}
                          className="p-2 rounded bg-slate-900/70 border border-slate-800 hover:border-slate-700 cursor-pointer space-y-1"
                        >
                          <div className="flex items-center justify-between">
                            <span className={`px-1.5 py-0.5 rounded text-[9px] border ${getRelationshipBadgeColor(rel.relationship_type)}`}>
                              {rel.relationship_type}
                            </span>
                            <span className="text-[10px] text-slate-500">
                              {rel.interaction_count}x
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-300 truncate">
                            <span className="text-slate-500">{isOut ? '→ ' : '← '}</span>
                            {neighborName}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          ) : selectedEdge ? (
            /* Selected Edge Inspector */
            <div className="flex-1 flex flex-col overflow-y-auto">
              <div className="p-3 border-b border-institutional-border bg-slate-950/60 flex items-center justify-between">
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-300 font-semibold">
                  RELATIONSHIP INSPECTION
                </span>
                <button
                  onClick={() => setSelectedEdge(null)}
                  className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                  title="Close Inspector"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="p-4 space-y-3 border-b border-institutional-border text-xs font-mono">
                <span className={`inline-block px-2 py-0.5 rounded border text-[11px] font-mono font-medium ${getRelationshipBadgeColor(selectedEdge.label)}`}>
                  {selectedEdge.label}
                </span>

                <div className="space-y-2 pt-2">
                  <div className="p-2 rounded bg-slate-900/80 border border-slate-800 space-y-1">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider">Source Entity</span>
                    <div className="text-slate-200 font-medium truncate">
                      {selectedEdge.rawRelationship.source_name || selectedEdge.source}
                    </div>
                    <div className="text-[10px] text-slate-500 truncate">{selectedEdge.source}</div>
                  </div>

                  <div className="p-2 rounded bg-slate-900/80 border border-slate-800 space-y-1">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider">Target Entity</span>
                    <div className="text-slate-200 font-medium truncate">
                      {selectedEdge.rawRelationship.target_name || selectedEdge.target}
                    </div>
                    <div className="text-[10px] text-slate-500 truncate">{selectedEdge.target}</div>
                  </div>
                </div>
              </div>

              <div className="p-4 space-y-3 text-xs font-mono">
                <div className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                  Observed Telemetry
                </div>
                <div className="space-y-1.5">
                  <div className="flex justify-between border-b border-slate-800/60 pb-1">
                    <span className="text-slate-500">Interactions:</span>
                    <span className="text-slate-200 font-bold">{selectedEdge.interactionCount}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-800/60 pb-1">
                    <span className="text-slate-500">Confidence:</span>
                    <span className="text-slate-200">{(selectedEdge.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-800/60 pb-1">
                    <span className="text-slate-500">First Seen:</span>
                    <span className="text-slate-200">{selectedEdge.rawRelationship.first_seen || 'Not observed'}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-800/60 pb-1">
                    <span className="text-slate-500">Last Seen:</span>
                    <span className="text-slate-200">{selectedEdge.rawRelationship.last_seen || 'Not observed'}</span>
                  </div>
                  {selectedEdge.rawRelationship.evidence_ids && (
                    <div className="flex justify-between border-b border-slate-800/60 pb-1">
                      <span className="text-slate-500">Evidence Provenance:</span>
                      <span className="text-slate-300">{selectedEdge.rawRelationship.evidence_ids.length} records</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            /* Default: Graph Slice Overview */
            <div className="flex-1 flex flex-col p-4 space-y-4 text-xs font-mono overflow-y-auto">
              <div className="border-b border-institutional-border pb-3">
                <div className="text-[10px] uppercase font-semibold text-slate-400 tracking-wider">
                  Graph Slice Overview
                </div>
                <div className="text-sm font-bold text-white mt-1 truncate">
                  {centerEntity?.canonical_name || focusEntityId}
                </div>
                <div className="text-[11px] text-slate-500 truncate">{focusEntityId}</div>
              </div>

              {/* Bounded Configuration Summary */}
              <div className="p-3 rounded bg-slate-900/60 border border-slate-800 space-y-2">
                <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">
                  Bounded Exploration Contract
                </div>
                <div className="space-y-1 text-[11px]">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Traversal Depth:</span>
                    <span className="text-slate-300 font-bold">2 Hops (Bounded)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Relationship Limit:</span>
                    <span className="text-slate-300 font-bold">50 Edges (Strict)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Total Nodes:</span>
                    <span className="text-slate-300 font-bold">{neighborhood?.total_nodes}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Total Relationships:</span>
                    <span className="text-slate-300 font-bold">{neighborhood?.total_edges}</span>
                  </div>
                </div>
              </div>

              {/* Entity Breakdown */}
              <div className="space-y-2">
                <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">
                  Discovered Entity Types
                </div>
                <div className="space-y-1">
                  {Object.entries(entityTypeCounts).map(([type, count]) => (
                    <div
                      key={type}
                      className="flex items-center justify-between p-1.5 rounded bg-slate-900/40 border border-slate-800/60 text-[11px]"
                    >
                      <span className="flex items-center gap-1.5 text-slate-300">
                        {getEntityIcon(type)}
                        <span>{type}</span>
                      </span>
                      <span className="text-slate-400 font-bold">{count}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Direct Links to Center Entity Intelligence & Timeline */}
              <div className="pt-2 space-y-2">
                <Link
                  to={`/entities?id=${encodeURIComponent(focusEntityId)}`}
                  className="w-full py-2 px-3 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-mono font-medium flex items-center justify-center gap-2 transition-colors"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  <span>Inspect Center Entity Intelligence</span>
                </Link>

                <Link
                  to={`/timeline?entity_id=${encodeURIComponent(focusEntityId)}`}
                  className="w-full py-2 px-3 bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 rounded text-xs font-mono flex items-center justify-center gap-2 transition-colors"
                >
                  <Clock className="w-3.5 h-3.5 text-blue-400" />
                  <span>View Timeline Activity</span>
                </Link>
              </div>

              {/* Instructions */}
              <div className="p-3 rounded bg-slate-950 border border-slate-800/80 text-slate-400 text-[11px] leading-relaxed">
                <span className="text-slate-300 font-semibold">Investigator Controls:</span> Click any node to inspect attributes and open Entity Intelligence. Click an edge to inspect interaction frequency and confidence. Double-click any node to immediately navigate. Drag nodes or canvas to explore topology.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

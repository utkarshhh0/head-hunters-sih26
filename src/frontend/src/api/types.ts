/**
 * Domain and API contracts for Investigator Frontend.
 * Perfectly mirrors backend Pydantic models from src/backend/app/schemas/.
 */

export type FindingStatus = 'OPEN' | 'IN_REVIEW' | 'RESOLVED' | 'DISMISSED';

export type PatternType = 'INTERMEDIARY_HUB_BURST' | 'DENSE_COMMUNITY_BURST' | string;

export interface TimeWindow {
  start_time?: string | null;
  end_time?: string | null;
}

export interface InvestigativeFinding {
  finding_id: string;
  title: string;
  summary: string;
  entity_ids: string[];
  relationship_ids: string[];
  signal_ids: string[];
  evidence_ids: string[];
  confidence: number;
  caveats: string[];
  created_at: string;
  status: FindingStatus;
  pattern_id?: string | null;
  pattern_type?: string | null;
  time_window?: TimeWindow | null;
  investigator_notes?: string | null;
}

export interface FindingStatusUpdate {
  status: FindingStatus;
  notes?: string | null;
}

export interface EvidenceRecord {
  evidence_id: string;
  source_record_id: string;
  source_type: string;
  document_name: string;
  raw_snippet: string;
  offset_start?: number | null;
  offset_end?: number | null;
  extractor_name: string;
  extracted_at: string;
  [key: string]: unknown;
}

export interface SourceRecordItem {
  source_id: string;
  source_type: string;
  document_name: string;
  raw_content: string;
  metadata?: Record<string, unknown>;
  ingested_at: string;
  [key: string]: unknown;
}

export interface FindingProvenanceBundle {
  finding: InvestigativeFinding;
  pattern?: Record<string, unknown> | null;
  signals: Record<string, unknown>[];
  entities: Record<string, unknown>[];
  relationships: Record<string, unknown>[];
  evidence: EvidenceRecord[];
  source_records: SourceRecordItem[];
}

export interface WorkspaceSummary {
  total_findings: number;
  findings_by_status: Record<string, number>;
  findings_by_pattern_type: Record<string, number>;
  total_entities_monitored: number;
  total_signals_detected: number;
}

export interface EntityRecord {
  entity_id: string;
  canonical_name?: string | null;
  entity_type: string;
  aliases?: string[];
  attributes?: Record<string, unknown>;
  labels?: string[];
  national_id?: string | null;
  phone_number?: string | null;
  registration_number?: string | null;
  address?: string | null;
  org_name?: string | null;
  account_number?: string | null;
  full_name?: string | null;
  source_record_ids?: string[];
  created_at?: string | null;
  updated_at?: string | null;
  [key: string]: unknown;
}

export interface EntityDetails extends EntityRecord {
  direct_relationship_count: number;
  possible_match_count: number;
}

export interface NeighborhoodRelationship {
  relationship_id?: string;
  relationship_type: string;
  source_entity_id: string;
  target_entity_id: string;
  source_name?: string | null;
  target_name?: string | null;
  interaction_count: number;
  first_seen?: string | null;
  last_seen?: string | null;
  confidence: number;
  origin?: string;
  evidence_ids?: string[];
  attributes?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface EntityNeighborhoodResponse {
  center_entity_id: string;
  depth: number;
  entities: EntityRecord[];
  relationships: NeighborhoodRelationship[];
  total_nodes: number;
  total_edges: number;
}

export interface HealthResponse {
  status: string;
  service: string;
}

export interface ApiError {
  detail: string;
  status?: number;
}

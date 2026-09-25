"""Investigator Workspace Service for Phase 5.

Orchestrates:
- Pattern detection and finding synthesis
- Finding lifecycle management (in-memory state for Round 2)
- Finding status transitions: OPEN -> IN_REVIEW -> RESOLVED / DISMISSED
- Investigator assessment notes
- End-to-end typed FindingProvenanceBundle assembly:
  Finding -> Pattern / Signals -> Entities / Relationships -> Evidence -> SourceRecord
- Bounded entity exploration (strictly depth 1 or 2, parameterized)
- Workspace dashboard summary metrics

No arbitrary Cypher execution. Bounded and validated queries only.
"""

from typing import Any, Dict, List, Optional, Set
from neo4j import Driver

from app.schemas.finding import FindingStatus, InvestigativeFinding
from app.schemas.analytics import MultiSignalPattern, StructuralSignal, TemporalSignal
from app.schemas.workspace import (
    FindingProvenanceBundle,
    WorkspaceSummary,
    EntityNeighborhoodResponse,
)
from app.graph.config import Neo4jConfig
from app.graph.query import Neo4jGraphQuery
from app.analytics.patterns import PatternDetector
from app.services.finding_service import FindingSynthesizer


VALID_STATUS_TRANSITIONS: Dict[FindingStatus, Set[FindingStatus]] = {
    FindingStatus.OPEN: {FindingStatus.IN_REVIEW, FindingStatus.DISMISSED},
    FindingStatus.IN_REVIEW: {FindingStatus.RESOLVED, FindingStatus.DISMISSED, FindingStatus.OPEN},
    FindingStatus.RESOLVED: {FindingStatus.IN_REVIEW, FindingStatus.OPEN},
    FindingStatus.DISMISSED: {FindingStatus.OPEN, FindingStatus.IN_REVIEW},
}


class WorkspaceService:
    """Service layer managing the investigator workspace, findings, and provenance."""

    def __init__(
        self,
        query: Optional[Neo4jGraphQuery] = None,
        driver: Optional[Driver] = None,
        config: Optional[Neo4jConfig] = None,
        detector: Optional[PatternDetector] = None,
        synthesizer: Optional[FindingSynthesizer] = None,
    ):
        self.query = query or Neo4jGraphQuery(driver=driver, config=config)
        self.detector = detector or PatternDetector(query=self.query, driver=driver, config=config)
        self.synthesizer = synthesizer or FindingSynthesizer()

        # In-memory storage for Round 2 prototype lifecycle state
        self._findings: Dict[str, InvestigativeFinding] = {}
        self._patterns: Dict[str, MultiSignalPattern] = {}
        self._signals: Dict[str, Any] = {}

    def close(self) -> None:
        """Closes query and detector resources."""
        self.detector.close()
        self.query.close()

    def __enter__(self) -> "WorkspaceService":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # -------------------------------------------------------------------------
    # Finding Lifecycle & Storage
    # -------------------------------------------------------------------------

    def register_finding(
        self,
        finding: InvestigativeFinding,
        pattern: Optional[MultiSignalPattern] = None,
    ) -> InvestigativeFinding:
        """Registers a finding into the workspace in-memory state."""
        self._findings[finding.finding_id] = finding
        if pattern:
            self._patterns[pattern.pattern_id] = pattern
        return finding

    def detect_and_register_findings(
        self,
        entity_id: Optional[str] = None,
        subgraph: Optional[Dict[str, Any]] = None,
        limit: int = 500,
    ) -> List[InvestigativeFinding]:
        """Orchestrates PatternDetector -> FindingSynthesizer -> Workspace registration.

        Preserves existing status and notes if a finding with the same ID was previously registered.
        """
        patterns = self.detector.detect_patterns(
            entity_id=entity_id,
            subgraph=subgraph,
            limit=limit,
        )

        synthesized_findings: List[InvestigativeFinding] = []
        for pat in patterns:
            self._patterns[pat.pattern_id] = pat
            existing = self._findings.get(f"urn:finding:{pat.pattern_type.value.lower()}:{pat.pattern_id}")

            current_status = existing.status if existing else FindingStatus.OPEN
            current_notes = existing.investigator_notes if existing else None

            finding = self.synthesizer.synthesize_finding(
                pattern=pat,
                status=current_status,
                notes=current_notes,
            )

            # Check if this exact finding_id is already registered
            if finding.finding_id in self._findings:
                prior = self._findings[finding.finding_id]
                finding = finding.model_copy(
                    update={
                        "status": prior.status,
                        "investigator_notes": prior.investigator_notes,
                    }
                )

            self._findings[finding.finding_id] = finding
            synthesized_findings.append(finding)

        return sorted(synthesized_findings, key=lambda f: f.finding_id)

    def list_findings(
        self,
        status: Optional[FindingStatus] = None,
        entity_id: Optional[str] = None,
        pattern_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[InvestigativeFinding]:
        """Lists findings with optional filtering by status, entity ID, or pattern type."""
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500.")

        results = list(self._findings.values())

        if status is not None:
            results = [f for f in results if f.status == status]

        if entity_id is not None:
            eid_clean = entity_id.strip()
            results = [f for f in results if eid_clean in f.entity_ids]

        if pattern_type is not None:
            pt_clean = pattern_type.strip().upper()
            results = [f for f in results if f.pattern_type and f.pattern_type.upper() == pt_clean]

        # Sort deterministically by finding_id
        results.sort(key=lambda f: f.finding_id)
        return results[:limit]

    def get_finding(self, finding_id: str) -> Optional[InvestigativeFinding]:
        """Retrieves a single finding by its finding ID."""
        if not finding_id or not finding_id.strip():
            raise ValueError("finding_id must be a non-empty string.")
        return self._findings.get(finding_id.strip())

    def update_finding_status(
        self,
        finding_id: str,
        status: FindingStatus,
        notes: Optional[str] = None,
    ) -> InvestigativeFinding:
        """Updates the status and optional notes of an existing finding.

        Follows lifecycle transitions: OPEN -> IN_REVIEW -> RESOLVED / DISMISSED.
        """
        clean_id = finding_id.strip()
        finding = self._findings.get(clean_id)
        if not finding:
            raise KeyError(f"Finding not found: {clean_id}")

        allowed = VALID_STATUS_TRANSITIONS.get(finding.status, set())
        if status != finding.status and status not in allowed:
            raise ValueError(
                f"Invalid status transition from {finding.status.value} to {status.value}. "
                f"Allowed transitions: {sorted([s.value for s in allowed])}"
            )

        updated_notes = notes if notes is not None else finding.investigator_notes
        updated_finding = finding.model_copy(
            update={
                "status": status,
                "investigator_notes": updated_notes,
            }
        )
        self._findings[clean_id] = updated_finding
        return updated_finding

    # -------------------------------------------------------------------------
    # End-to-End Provenance Bundle Assembly
    # -------------------------------------------------------------------------

    def get_finding_provenance_bundle(self, finding_id: str) -> FindingProvenanceBundle:
        """Assembles the complete typed provenance bundle for an investigative finding:

        Finding -> Pattern / Signals -> Entities / Relationships -> Evidence -> SourceRecord
        """
        clean_id = finding_id.strip()
        finding = self._findings.get(clean_id)
        if not finding:
            raise KeyError(f"Finding not found: {clean_id}")

        # 1. Pattern Reference
        pattern = self._patterns.get(finding.pattern_id) if finding.pattern_id else None

        # 2. Contributing Signals
        signals: List[Dict[str, Any]] = []
        if pattern:
            for sig_id in pattern.contributing_signal_ids:
                if sig_id in self._signals:
                    signals.append(self._signals[sig_id])
                else:
                    signals.append({"signal_id": sig_id, "ref": "contributing_signal"})
        else:
            for sig_id in finding.signal_ids:
                if sig_id in self._signals:
                    signals.append(self._signals[sig_id])
                else:
                    signals.append({"signal_id": sig_id, "ref": "finding_signal"})

        # 3. Entities
        entities: List[Dict[str, Any]] = []
        for eid in finding.entity_ids:
            try:
                edata = self.query.get_entity_details(eid)
                if edata:
                    entities.append(edata)
                else:
                    entities.append({"entity_id": eid, "canonical_name": eid})
            except Exception:
                entities.append({"entity_id": eid, "canonical_name": eid})

        # 4. Relationships
        relationships: List[Dict[str, Any]] = []
        # Attempt to retrieve direct relationships for finding entities
        if finding.entity_ids:
            try:
                for eid in finding.entity_ids:
                    direct_rels = self.query.get_direct_relationships(entity_id=eid, limit=100)
                    for r in direct_rels:
                        if (
                            not finding.relationship_ids
                            or r.get("relationship_id") in finding.relationship_ids
                        ):
                            if r not in relationships:
                                relationships.append(r)
            except Exception:
                pass

        # If relationship_ids were not populated from direct_rels, preserve stub references
        found_rel_ids = {r.get("relationship_id") for r in relationships}
        for rid in finding.relationship_ids:
            if rid not in found_rel_ids:
                relationships.append({"relationship_id": rid, "ref": "referenced_relationship"})

        # 5. Evidence & Source Records via query.get_evidence_by_id
        evidence_list: List[Dict[str, Any]] = []
        source_records_dict: Dict[str, Dict[str, Any]] = {}

        evidence_ids_to_fetch = set(finding.evidence_ids)
        for r in relationships:
            for ev_id in r.get("evidence_ids", []):
                evidence_ids_to_fetch.add(ev_id)

        for ev_id in sorted(list(evidence_ids_to_fetch)):
            try:
                ev_res = self.query.get_evidence_by_id(ev_id)
                if ev_res:
                    if ev_res.get("evidence"):
                        evidence_list.append(ev_res["evidence"])
                    if ev_res.get("source_record"):
                        s_rec = ev_res["source_record"]
                        s_id = s_rec.get("source_id") or s_rec.get("source_record_id")
                        if s_id:
                            source_records_dict[s_id] = s_rec
                else:
                    evidence_list.append({"evidence_id": ev_id, "ref": "unresolved_evidence"})
            except Exception:
                evidence_list.append({"evidence_id": ev_id, "ref": "unresolved_evidence"})

        source_records = [source_records_dict[k] for k in sorted(source_records_dict.keys())]

        return FindingProvenanceBundle(
            finding=finding,
            pattern=pattern,
            signals=signals,
            entities=entities,
            relationships=relationships,
            evidence=evidence_list,
            source_records=source_records,
        )

    # -------------------------------------------------------------------------
    # Workspace Overview & Exploration
    # -------------------------------------------------------------------------

    def get_workspace_summary(self) -> WorkspaceSummary:
        """Calculates aggregate metrics across all registered findings."""
        findings = list(self._findings.values())

        by_status: Dict[str, int] = {s.value: 0 for s in FindingStatus}
        by_pattern: Dict[str, int] = {}
        all_eids: Set[str] = set()
        all_sids: Set[str] = set()

        for f in findings:
            by_status[f.status.value] = by_status.get(f.status.value, 0) + 1
            if f.pattern_type:
                by_pattern[f.pattern_type] = by_pattern.get(f.pattern_type, 0) + 1
            for eid in f.entity_ids:
                all_eids.add(eid)
            for sid in f.signal_ids:
                all_sids.add(sid)

        return WorkspaceSummary(
            total_findings=len(findings),
            findings_by_status=by_status,
            findings_by_pattern_type=by_pattern,
            total_entities_monitored=len(all_eids),
            total_signals_detected=len(all_sids),
        )

    def search_entities(
        self,
        query: Optional[str] = None,
        entity_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Searches canonical entities via the graph query layer."""
        return self.query.search_entities(query=query, entity_type=entity_type, limit=limit)

    def get_entity_details(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves entity details and connectivity metrics via the graph query layer."""
        return self.query.get_entity_details(entity_id=entity_id)

    def get_entity_neighborhood(
        self,
        entity_id: str,
        depth: int = 1,
        limit: int = 50,
    ) -> EntityNeighborhoodResponse:
        """Retrieves a strictly bounded 1-hop or 2-hop network graph neighborhood for an entity.

        Enforces strict limits: depth in {1, 2}, limit in [1, 200].
        Unbounded traversals or depth > 2 are strictly prohibited.
        """
        if not entity_id or not entity_id.strip():
            raise ValueError("entity_id must be a non-empty string.")

        if depth not in (1, 2):
            raise ValueError(f"Traversal depth must be 1 or 2, got {depth}.")

        if limit < 1 or limit > 200:
            raise ValueError("limit must be between 1 and 200.")

        clean_eid = entity_id.strip()
        data = self.query.traverse_network(
            start_entity_id=clean_eid,
            hops=depth,
            limit=limit,
        )

        nodes = data.get("entities", [])
        edges = data.get("relationships", [])

        return EntityNeighborhoodResponse(
            center_entity_id=clean_eid,
            depth=depth,
            entities=nodes,
            relationships=edges,
            total_nodes=len(nodes),
            total_edges=len(edges),
        )

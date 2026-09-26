"""Report Generation Service for Phase 6C-A Backend.

Transforms FindingProvenanceBundle into deterministic, audit-ready PDF reports:
FindingProvenanceBundle -> deterministic report view data -> Jinja2 HTML -> WeasyPrint PDF.

Strict Language and Determinism Constraints:
- Neutral analytical wording only (no subjective or legally conclusive claims).
- Zero fabrication: no invented statistics, entities, relationships, evidence, or timestamps.
- Zero LLM dependence: pure deterministic templating.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# Ensure Windows environment variable WEASYPRINT_DLL_DIRECTORIES is picked up from user/system registry
# if not already present in os.environ (without hardcoding any machine-specific paths).
if sys.platform == "win32" and "WEASYPRINT_DLL_DIRECTORIES" not in os.environ:
    try:
        import winreg

        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(root, r"Environment") as key:
                    val, _ = winreg.QueryValueEx(key, "WEASYPRINT_DLL_DIRECTORIES")
                    if val:
                        os.environ["WEASYPRINT_DLL_DIRECTORIES"] = val
                        break
            except OSError:
                continue
    except Exception:
        pass

import jinja2
from weasyprint import HTML

from app.schemas.workspace import FindingProvenanceBundle


class ReportService:
    """Service orchestrating deterministic HTML and PDF report generation."""

    def __init__(self, template_dir: Optional[Path] = None):
        if template_dir is None:
            self.template_dir = Path(__file__).resolve().parent.parent / "templates"
        else:
            self.template_dir = Path(template_dir)

        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.template_dir)),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
        )

        css_path = self.template_dir / "report.css"
        if css_path.exists():
            self._css_content = css_path.read_text(encoding="utf-8")
        else:
            self._css_content = ""

    def build_report_data(
        self,
        bundle: FindingProvenanceBundle,
        generated_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Builds a deterministic, sorted view model from the provenance bundle.

        Zero fabrication: only uses data present in the bundle.
        """
        f = bundle.finding
        ts_now = generated_at or datetime.now(timezone.utc)
        generated_at_str = ts_now.strftime("%Y-%m-%d %H:%M:%S UTC")

        # 1. Header View Data
        header_data = {
            "title": "Investigative Analytical Report",
            "finding_id": f.finding_id,
            "status": f.status.value if hasattr(f.status, "value") else str(f.status),
            "pattern_type": (
                f.pattern_type
                or (
                    bundle.pattern.pattern_type.value
                    if bundle.pattern and hasattr(bundle.pattern.pattern_type, "value")
                    else "N/A"
                )
            ),
            "generated_at": generated_at_str,
            "synthetic_notice": (
                "SYNTHETIC / CONTROLLED DEMONSTRATION NOTICE: This report was generated in a "
                "controlled research and demonstration environment using synthetic or anonymized data. "
                "Not for operational or evidentiary use."
            ),
        }

        # 2. Executive Summary View Data
        time_window_text = "Not temporally bounded"
        if f.time_window:
            start_s = (
                f.time_window.start_time.isoformat()
                if hasattr(f.time_window.start_time, "isoformat")
                else str(f.time_window.start_time)
            )
            end_s = (
                f.time_window.end_time.isoformat()
                if hasattr(f.time_window.end_time, "isoformat")
                else str(f.time_window.end_time)
            )
            time_window_text = f"{start_s} to {end_s}"

        summary_data = {
            "title": f.title,
            "summary": f.summary,
            "status": f.status.value if hasattr(f.status, "value") else str(f.status),
            "pattern_type": f.pattern_type or "N/A",
            "time_window_text": time_window_text,
            "caveats": list(f.caveats),
        }

        # 3. Entity Profile (from provenance.entities ONLY)
        processed_entities: List[Dict[str, Any]] = []
        for e in bundle.entities:
            eid = e.get("entity_id") or e.get("id") or ""
            cname = e.get("canonical_name") or e.get("name") or eid
            etype = e.get("entity_type") or e.get("type") or "UNKNOWN"

            # Filter remaining attributes
            ignored_keys = {"entity_id", "id", "canonical_name", "name", "entity_type", "type"}
            attrs = {k: v for k, v in e.items() if k not in ignored_keys and v is not None}

            processed_entities.append(
                {
                    "entity_id": eid,
                    "canonical_name": cname,
                    "entity_type": etype,
                    "attributes": attrs,
                }
            )
        processed_entities.sort(key=lambda item: item["entity_id"])

        # 4. Network Overview (from provenance.relationships ONLY)
        processed_relationships: List[Dict[str, Any]] = []
        for r in bundle.relationships:
            rid = r.get("relationship_id") or ""
            src = r.get("source_entity_id") or r.get("source") or ""
            tgt = r.get("target_entity_id") or r.get("target") or ""
            rtype = r.get("relationship_type") or r.get("type") or ""
            count = r.get("interaction_count")
            first_seen = r.get("first_seen")
            last_seen = r.get("last_seen")
            ev_ids = sorted(list(r.get("evidence_ids") or []))

            first_seen_str = first_seen.isoformat() if hasattr(first_seen, "isoformat") else str(first_seen) if first_seen else None
            last_seen_str = last_seen.isoformat() if hasattr(last_seen, "isoformat") else str(last_seen) if last_seen else None

            processed_relationships.append(
                {
                    "relationship_id": rid,
                    "source_entity_id": src,
                    "target_entity_id": tgt,
                    "relationship_type": rtype,
                    "interaction_count": count,
                    "first_seen": first_seen_str,
                    "last_seen": last_seen_str,
                    "evidence_ids": ev_ids,
                }
            )
        processed_relationships.sort(key=lambda item: item["relationship_id"])

        # 5. Timeline / Activity (ONLY observed time_window and relationship temporal fields)
        timeline_events: List[Dict[str, Any]] = []
        if f.time_window:
            start_str = (
                f.time_window.start_time.isoformat()
                if hasattr(f.time_window.start_time, "isoformat")
                else str(f.time_window.start_time)
            )
            end_str = (
                f.time_window.end_time.isoformat()
                if hasattr(f.time_window.end_time, "isoformat")
                else str(f.time_window.end_time)
            )
            timeline_events.append(
                {
                    "timestamp": start_str,
                    "event_type": "Observation Window Start",
                    "description": "Beginning of analytical observation window for detected pattern",
                }
            )
            timeline_events.append(
                {
                    "timestamp": end_str,
                    "event_type": "Observation Window End",
                    "description": "Conclusion of analytical observation window for detected pattern",
                }
            )

        for r in processed_relationships:
            if r["first_seen"]:
                timeline_events.append(
                    {
                        "timestamp": r["first_seen"],
                        "event_type": "Relationship First Observed",
                        "description": (
                            f"First recorded interaction ({r['relationship_type']}) "
                            f"between {r['source_entity_id']} and {r['target_entity_id']}"
                        ),
                    }
                )
            if r["last_seen"] and r["last_seen"] != r["first_seen"]:
                timeline_events.append(
                    {
                        "timestamp": r["last_seen"],
                        "event_type": "Relationship Last Observed",
                        "description": (
                            f"Latest recorded interaction ({r['relationship_type']}) "
                            f"between {r['source_entity_id']} and {r['target_entity_id']}"
                        ),
                    }
                )

        timeline_events.sort(key=lambda item: (item["timestamp"], item["event_type"], item["description"]))

        # 6. Analytical Findings
        pattern_data = None
        if bundle.pattern:
            ptype = (
                bundle.pattern.pattern_type.value
                if hasattr(bundle.pattern.pattern_type, "value")
                else str(bundle.pattern.pattern_type)
            )
            pattern_data = {
                "pattern_id": bundle.pattern.pattern_id,
                "pattern_type": ptype,
                "detection_method": bundle.pattern.detection_method,
                "explanation": bundle.pattern.explanation,
                "limitations": list(bundle.pattern.limitations),
            }
        elif f.pattern_id or f.pattern_type:
            pattern_data = {
                "pattern_id": f.pattern_id or "N/A",
                "pattern_type": f.pattern_type or "N/A",
                "detection_method": "Deterministic Rule Trigger",
                "explanation": f.summary,
                "limitations": list(f.caveats),
            }

        processed_signals: List[Dict[str, Any]] = []
        for s in bundle.signals:
            sid = s.get("signal_id") or ""
            stype = s.get("signal_type") or ""
            mval = s.get("metric_value", 0.0)
            rdesc = s.get("rule_description") or ""
            eids = sorted(list(s.get("entity_ids") or []))
            rids = sorted(list(s.get("relationship_ids") or []))

            processed_signals.append(
                {
                    "signal_id": sid,
                    "signal_type": stype,
                    "metric_value": mval,
                    "rule_description": rdesc,
                    "entity_ids": eids,
                    "relationship_ids": rids,
                }
            )
        processed_signals.sort(key=lambda item: item["signal_id"])

        # 7. Supporting Evidence (Preserving chain: Finding -> Evidence -> Source Record)
        source_map: Dict[str, Dict[str, Any]] = {}
        for s in bundle.source_records:
            s_id = s.get("source_id") or s.get("source_record_id")
            if s_id:
                ingested = s.get("ingested_at")
                ingested_str = ingested.isoformat() if hasattr(ingested, "isoformat") else str(ingested) if ingested else "N/A"
                source_map[s_id] = {
                    "source_id": s_id,
                    "source_type": s.get("source_type", "UNKNOWN"),
                    "document_name": s.get("document_name", "UNKNOWN"),
                    "ingested_at": ingested_str,
                    "raw_content": s.get("raw_content"),
                }

        processed_evidence: List[Dict[str, Any]] = []
        linked_source_ids = set()
        for ev in bundle.evidence:
            ev_id = ev.get("evidence_id") or ""
            ext_type = ev.get("extraction_type") or "ANALYTICAL_EXTRACTION"
            ext_val = ev.get("extracted_value") or ev.get("snippet") or ev.get("details") or ""
            conf = ev.get("confidence")
            src_id = ev.get("source_id") or ev.get("source_record_id")
            src_rec = source_map.get(src_id) if src_id else None
            if src_id and src_rec:
                linked_source_ids.add(src_id)

            processed_evidence.append(
                {
                    "evidence_id": ev_id,
                    "extraction_type": ext_type,
                    "extracted_value": ext_val,
                    "confidence": conf,
                    "source_id": src_id,
                    "source_record": src_rec,
                }
            )
        processed_evidence.sort(key=lambda item: item["evidence_id"])

        # Any source records not directly linked by evidence records
        standalone_sources = [
            src_rec for s_id, src_rec in source_map.items() if s_id not in linked_source_ids
        ]
        standalone_sources.sort(key=lambda item: item["source_id"])

        # 8. Investigator Notes
        notes = f.investigator_notes if f.investigator_notes and f.investigator_notes.strip() else None

        # 9. Methodology / Limitations
        all_limitations: List[str] = []
        if pattern_data and pattern_data.get("limitations"):
            all_limitations.extend(pattern_data["limitations"])
        for c in f.caveats:
            if c not in all_limitations:
                all_limitations.append(c)

        methodology_data = {
            "statement": (
                "This report reflects automated, deterministic graph and temporal analytical observations "
                "intended exclusively to assist qualified human investigators. It does not establish culpability, "
                "criminal intent, or legal determination. All automated pattern flags require independent "
                "verification against authoritative source records."
            ),
            "limitations": all_limitations,
        }

        return {
            "header": header_data,
            "summary": summary_data,
            "entities": processed_entities,
            "relationships": processed_relationships,
            "timeline_events": timeline_events,
            "pattern": pattern_data,
            "signals": processed_signals,
            "evidence_items": processed_evidence,
            "standalone_source_records": standalone_sources,
            "investigator_notes": notes,
            "methodology": methodology_data,
            "css_content": self._css_content,
        }

    def render_html(
        self,
        bundle: FindingProvenanceBundle,
        generated_at: Optional[datetime] = None,
    ) -> str:
        """Renders the HTML template deterministically for the given provenance bundle."""
        data = self.build_report_data(bundle, generated_at=generated_at)
        template = self.jinja_env.get_template("report.html")
        return template.render(**data)

    def generate_pdf(
        self,
        bundle: FindingProvenanceBundle,
        generated_at: Optional[datetime] = None,
    ) -> bytes:
        """Generates PDF bytes using WeasyPrint from the rendered HTML report."""
        html_content = self.render_html(bundle, generated_at=generated_at)
        html_doc = HTML(string=html_content, base_url=str(self.template_dir))
        return html_doc.write_pdf()

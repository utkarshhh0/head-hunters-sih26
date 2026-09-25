"""Deterministic Finding Synthesizer Service for Phase 5.

Converts Phase 4 MultiSignalPattern instances into canonical InvestigativeFinding domain models.

Key Invariants:
1. Determinism: Identical pattern inputs produce identical finding IDs, titles, and summaries.
2. Neutral Language: Findings represent objective analytical observations for human investigation.
   Never infers guilt, criminal liability, illicit intent, or mastermind status.
3. Zero LLM Dependencies: All titles, summaries, and limitations are deterministic interpolations
   of observed graph metrics and heuristics.
4. Complete Provenance Preservation: Preserves all entity IDs, relationship IDs, contributing signal IDs,
   and evidence provenance IDs.
5. Zero Timestamp Fabrication: Preserves the observed time window strictly from the pattern.
6. Nominal Confidence: Preserves the backward-compatible confidence field at 1.0 (unweighted nominal)
   without inventing arbitrary decimals (e.g. 0.85/0.75) or introducing risk scores.
"""

import hashlib
from typing import List, Optional

from app.schemas.finding import FindingStatus, InvestigativeFinding
from app.schemas.analytics import MultiSignalPattern, PatternType


def _deterministic_hash(val: str, length: int = 12) -> str:
    """Generates a deterministic hex hash prefix from an input string."""
    return hashlib.sha256(val.encode("utf-8")).hexdigest()[:length]


class FindingSynthesizer:
    """Deterministic synthesizer translating MultiSignalPattern into InvestigativeFinding."""

    def synthesize_finding(
        self,
        pattern: MultiSignalPattern,
        status: FindingStatus = FindingStatus.OPEN,
        notes: Optional[str] = None,
    ) -> InvestigativeFinding:
        """Transforms a single MultiSignalPattern into an InvestigativeFinding."""
        ptype_str = (
            pattern.pattern_type.value
            if hasattr(pattern.pattern_type, "value")
            else str(pattern.pattern_type)
        )

        # Deterministic finding ID derived from pattern URN
        finding_hash = _deterministic_hash(f"{pattern.pattern_id}:{ptype_str}")
        finding_id = f"urn:finding:{ptype_str.lower()}:{finding_hash}"

        # Standard neutral title
        title = f"Investigative Finding: {pattern.title}"

        # Summary derived from observed analytical explanation and detection method
        summary = (
            f"{pattern.explanation} "
            f"[Detection Method: {pattern.detection_method}]"
        )

        # Combine pattern limitations with standard investigative neutrality caveats
        caveats = list(pattern.limitations)
        standard_caveat = (
            "Analytical observation flagged for human investigative assessment; "
            "does not constitute a legal determination of wrongdoing, liability, or intent."
        )
        if standard_caveat not in caveats:
            caveats.append(standard_caveat)

        return InvestigativeFinding(
            finding_id=finding_id,
            title=title,
            summary=summary,
            entity_ids=sorted(list(pattern.entity_ids)),
            relationship_ids=sorted(list(pattern.relationship_ids)),
            signal_ids=sorted(list(pattern.contributing_signal_ids)),
            evidence_ids=sorted(list(pattern.evidence_ids)),
            confidence=1.0,  # Nominal unweighted confidence per contract; no arbitrary scoring
            caveats=caveats,
            status=status,
            pattern_id=pattern.pattern_id,
            pattern_type=ptype_str,
            time_window=pattern.time_window,
            investigator_notes=notes,
        )

    def synthesize_findings(
        self,
        patterns: List[MultiSignalPattern],
        status: FindingStatus = FindingStatus.OPEN,
    ) -> List[InvestigativeFinding]:
        """Transforms a list of MultiSignalPattern instances into InvestigativeFinding models.

        Results are sorted deterministically by finding_id.
        """
        findings = [
            self.synthesize_finding(pattern, status=status)
            for pattern in patterns
        ]
        return sorted(findings, key=lambda f: f.finding_id)

import React from 'react';
import { FileCheck } from 'lucide-react';
import { PlaceholderShell } from '../components/common/PlaceholderShell';

export const Evidence: React.FC = () => {
  return (
    <PlaceholderShell
      moduleCode="MOD-06-EVID"
      title="Evidence"
      subtitle="Verifiable traceability from analytical patterns and signals back to raw source records."
      workflowStep="EVIDENCE"
      icon={FileCheck}
      targetEndpoints={[
        'GET /api/v1/findings/{finding_id}/provenance',
      ]}
      capabilitiesPlanned={[
        'Visual end-to-end provenance tree: Finding → Pattern → Signals → Relationships → Evidence → SourceRecord',
        'Exact character offset highlighting within raw textual snippets and structured record bodies',
        'Cryptographic record verification using deterministic SHA-256 source identifiers',
        'Chain-of-custody audit view for evidentiary compliance in court proceedings',
      ]}
      architecturalContract="Consumes get_finding_provenance(). Strictly binds to FindingProvenanceBundle domain schema. Zero synthetic evidence or orphan edges."
    />
  );
};

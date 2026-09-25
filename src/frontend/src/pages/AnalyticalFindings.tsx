import React from 'react';
import { Activity } from 'lucide-react';
import { PlaceholderShell } from '../components/common/PlaceholderShell';

export const AnalyticalFindings: React.FC = () => {
  return (
    <PlaceholderShell
      moduleCode="MOD-05-FND"
      title="Analytical Findings"
      subtitle="Multi-signal pattern discoveries, investigator triage workflow, and lifecycle state management."
      workflowStep="FINDING"
      icon={Activity}
      targetEndpoints={[
        'GET /api/v1/findings?status={status}&pattern_type={type}&limit=50',
        'GET /api/v1/findings/{finding_id}',
        'PATCH /api/v1/findings/{finding_id}/status',
      ]}
      capabilitiesPlanned={[
        'Filterable findings inventory by status (DETECTED, TRIAGED, CONFIRMED, DISMISSED)',
        'Detailed breakdown of contributing structural bridge, high-degree, and temporal burst signals',
        'Investigator triage controls with mandatory rationale notes for dismissed items',
        'Direct link to end-to-end provenance verification chain',
      ]}
      architecturalContract="Consumes FindingService and WorkspaceService. Enforces valid lifecycle state transitions (DETECTED -> TRIAGED -> CONFIRMED/DISMISSED). Finding status updates are stored prototype-local."
    />
  );
};

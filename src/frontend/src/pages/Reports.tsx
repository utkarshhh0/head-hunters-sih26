import React from 'react';
import { FileSpreadsheet } from 'lucide-react';
import { PlaceholderShell } from '../components/common/PlaceholderShell';

export const Reports: React.FC = () => {
  return (
    <PlaceholderShell
      moduleCode="MOD-07-REP"
      title="Reports"
      subtitle="Court-ready investigative dossiers, evidentiary exhibits, and analytical briefing summaries."
      workflowStep="REPORT"
      icon={FileSpreadsheet}
      targetEndpoints={[
        'GET /api/v1/workspace/summary',
        'GET /api/v1/findings',
        'Phase 7 Report Generation API',
      ]}
      capabilitiesPlanned={[
        'Automated generation of formal court-admissible Investigative Dossiers',
        'Executive analytical summary compilation with multi-signal pattern breakdowns',
        'Evidentiary provenance appendix containing exact source records and character offsets',
        'PDF export and standardized JSON case transfer format',
      ]}
      architecturalContract="Scheduled for Phase 7. Will consume Phase 5 WorkspaceService and typed FindingProvenanceBundle directly without generative hallucinations or unverified assertions."
    />
  );
};

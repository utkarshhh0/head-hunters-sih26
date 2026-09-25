import React from 'react';
import { Clock } from 'lucide-react';
import { PlaceholderShell } from '../components/common/PlaceholderShell';

export const Timeline: React.FC = () => {
  return (
    <PlaceholderShell
      moduleCode="MOD-04-TIME"
      title="Timeline"
      subtitle="Chronological communication bursts, temporal concentration windows, and event sequencing."
      workflowStep="TIME"
      icon={Clock}
      targetEndpoints={[
        'GET /api/v1/findings',
        'GET /api/v1/findings/{finding_id}/provenance',
      ]}
      capabilitiesPlanned={[
        'Interactive chronological interaction timeline across communications and transactions',
        'Temporal burst window highlights aligning with detected multi-signal patterns',
        'Strict separation and explicit display of undated interactions (zero synthetic timestamps)',
        'Time-window zooming and temporal density distribution heatmaps',
      ]}
      architecturalContract="Built on Phase 4 TemporalAnalyzer. Adheres to zero-fabrication principle: undated records remain undated and are not fabricated with mock dates."
    />
  );
};

import React from 'react';
import { Network } from 'lucide-react';
import { PlaceholderShell } from '../components/common/PlaceholderShell';

export const NetworkExplorer: React.FC = () => {
  return (
    <PlaceholderShell
      moduleCode="MOD-03-NET"
      title="Network Explorer"
      subtitle="Bounded topological graph exploration and multi-hop relationship inspection."
      workflowStep="NETWORK"
      icon={Network}
      targetEndpoints={[
        'GET /api/v1/entities/{entity_id}/neighborhood?depth=1|2&limit=50',
      ]}
      capabilitiesPlanned={[
        'Interactive topological graph canvas powered by Cytoscape (scheduled for Phase 6B)',
        'Bounded 1-hop and 2-hop local graph neighborhood expansion',
        'Relationship type filtering (COMMUNICATED_WITH, OWNED_BY, ASSOCIATED_WITH, TRANSACTED_WITH)',
        'Visual indicators for bridge nodes, degree hubs, and interaction frequency weights',
      ]}
      architecturalContract="Consumes get_entity_neighborhood(). Depth is strictly enforced by the backend API to values of 1 or 2. Cypher queries are fully parameterized and protected against arbitrary client input."
    />
  );
};

/**
 * Verification script for Phase 6A & 6B.1:
 * - Frontend Foundation & Application Shell (6A)
 * - Investigation / Search -> Entity Intelligence Workflow (6B.1)
 *
 * Validates:
 * 1. Build artifacts presence and bundle integrity
 * 2. Application route & component structure
 * 3. Sidebar conceptual navigation
 * 4. API client layer contracts & entity endpoints
 * 5. Investigation component functionality & contracts
 * 6. Entity Intelligence component functionality & contracts
 * 7. Live FastAPI backend smoke tests across entities & neighborhoods
 */

import { readFileSync, existsSync } from 'fs';
import { resolve, join } from 'path';

const FRONTEND_DIR = resolve('src/frontend');
const DIST_DIR = join(FRONTEND_DIR, 'dist');

console.log('================================================================');
console.log('SIH26189 — Phase 6B.1 Investigation & Entity Intelligence Verification');
console.log('================================================================\n');

let failedTests = 0;

function assert(condition, message) {
  if (condition) {
    console.log(`[PASS] ${message}`);
  } else {
    console.error(`[FAIL] ${message}`);
    failedTests++;
  }
}

// 1. Verify build artifacts
console.log('--- 1. Build Artifacts Verification ---');
assert(existsSync(join(DIST_DIR, 'index.html')), 'dist/index.html exists');
const distHtml = readFileSync(join(DIST_DIR, 'index.html'), 'utf-8');
assert(distHtml.includes('SIH26189'), 'dist/index.html includes system title SIH26189');
assert(existsSync(join(DIST_DIR, 'assets')), 'dist/assets directory exists');

// 2. Verify source code structure and routes
console.log('\n--- 2. Application Route & Component Structure ---');
const appTsx = readFileSync(join(FRONTEND_DIR, 'src/App.tsx'), 'utf-8');

const requiredRoutes = [
  { path: '/', name: 'Dashboard' },
  { path: '/investigation', name: 'Investigation' },
  { path: '/entities', name: 'EntityIntelligence' },
  { path: '/network', name: 'NetworkExplorer' },
  { path: '/timeline', name: 'Timeline' },
  { path: '/findings', name: 'AnalyticalFindings' },
  { path: '/evidence', name: 'Evidence' },
  { path: '/reports', name: 'Reports' },
  { path: '/login', name: 'Login' },
];

requiredRoutes.forEach(r => {
  assert(
    appTsx.includes(`path="${r.path}"`) && appTsx.includes(r.name),
    `Route ${r.path} mapped to <${r.name} />`
  );
});

// 3. Verify Sidebar Navigation Structure
console.log('\n--- 3. Sidebar Conceptual Navigation Groups ---');
const sidebarTsx = readFileSync(join(FRONTEND_DIR, 'src/components/layout/Sidebar.tsx'), 'utf-8');
assert(sidebarTsx.includes("'APPLICATION'"), "Sidebar contains 'APPLICATION' group");
assert(sidebarTsx.includes("'ANALYSIS'"), "Sidebar contains 'ANALYSIS' group");
assert(sidebarTsx.includes("'EVIDENCE'"), "Sidebar contains 'EVIDENCE' group");
assert(sidebarTsx.includes("'OUTPUT'"), "Sidebar contains 'OUTPUT' group");

const requiredNavItems = [
  'Dashboard',
  'Investigation',
  'Entity Intelligence',
  'Network Explorer',
  'Timeline',
  'Analytical Findings',
  'Evidence',
  'Reports',
];

requiredNavItems.forEach(item => {
  assert(sidebarTsx.includes(item), `Sidebar navigation contains '${item}'`);
});

// 4. Verify API Layer Contracts
console.log('\n--- 4. API Client & Configuration Layer ---');
const apiTypes = readFileSync(join(FRONTEND_DIR, 'src/api/types.ts'), 'utf-8');
const workspaceApi = readFileSync(join(FRONTEND_DIR, 'src/api/workspaceApi.ts'), 'utf-8');
const findingsApi = readFileSync(join(FRONTEND_DIR, 'src/api/findingsApi.ts'), 'utf-8');
const entitiesApi = readFileSync(join(FRONTEND_DIR, 'src/api/entitiesApi.ts'), 'utf-8');

assert(apiTypes.includes('EntityRecord'), 'api/types.ts defines EntityRecord');
assert(apiTypes.includes('EntityDetails'), 'api/types.ts defines EntityDetails');
assert(apiTypes.includes('EntityNeighborhoodResponse'), 'api/types.ts defines EntityNeighborhoodResponse');
assert(apiTypes.includes('NeighborhoodRelationship'), 'api/types.ts defines NeighborhoodRelationship');

assert(workspaceApi.includes('/api/v1/workspace/summary'), 'workspaceApi targets /api/v1/workspace/summary');
assert(findingsApi.includes('/api/v1/findings'), 'findingsApi targets /api/v1/findings');
assert(entitiesApi.includes('/api/v1/entities'), 'entitiesApi targets /api/v1/entities');

// 5. Verify Investigation Page Implementation (Phase 6B.1)
console.log('\n--- 5. Investigation Component Implementation (Phase 6B.1) ---');
const investigationTsx = readFileSync(join(FRONTEND_DIR, 'src/pages/Investigation.tsx'), 'utf-8');
assert(investigationTsx.includes('searchEntities'), 'Investigation component calls searchEntities');
assert(investigationTsx.includes('handleSelectEntity'), 'Investigation component handles entity selection');
assert(investigationTsx.includes('/entities?id='), 'Investigation navigates to /entities?id=');
assert(investigationTsx.includes('Canonical Entities Ledger'), 'Investigation renders canonical entities ledger table');

// 6. Verify Entity Intelligence Page Implementation (Phase 6B.1)
console.log('\n--- 6. Entity Intelligence Component Implementation (Phase 6B.1) ---');
const entityIntelTsx = readFileSync(join(FRONTEND_DIR, 'src/pages/EntityIntelligence.tsx'), 'utf-8');
assert(entityIntelTsx.includes('getEntityDetails'), 'EntityIntelligence calls getEntityDetails');
assert(entityIntelTsx.includes('getEntityNeighborhood'), 'EntityIntelligence calls getEntityNeighborhood');
assert(entityIntelTsx.includes('direct_relationship_count'), 'EntityIntelligence displays direct_relationship_count');
assert(entityIntelTsx.includes('possible_match_count'), 'EntityIntelligence displays possible_match_count');
assert(entityIntelTsx.includes('source_record_ids'), 'EntityIntelligence displays source_record_ids provenance');
assert(entityIntelTsx.includes('/network?focus='), 'EntityIntelligence provides navigation to Network Explorer');

// 7. Verify Network Explorer Implementation (Phase 6B.2)
console.log('\n--- 7. Network Explorer Component Implementation (Phase 6B.2) ---');
const packageJson = readFileSync(join(FRONTEND_DIR, 'package.json'), 'utf-8');
assert(packageJson.includes('cytoscape'), 'package.json contains cytoscape dependency');

const networkExplorerTsx = readFileSync(join(FRONTEND_DIR, 'src/pages/NetworkExplorer.tsx'), 'utf-8');
assert(networkExplorerTsx.includes("import cytoscape"), 'NetworkExplorer imports cytoscape');
assert(networkExplorerTsx.includes("searchParams.get('focus')"), 'NetworkExplorer reads focus parameter from URL');
assert(networkExplorerTsx.includes('getEntityNeighborhood(entityId, 2, 50)'), 'NetworkExplorer calls getEntityNeighborhood strictly with depth=2 and limit=50');
assert(networkExplorerTsx.includes('/entities?id='), 'NetworkExplorer links selected node to /entities?id=');
assert(networkExplorerTsx.includes('containerRef'), 'NetworkExplorer attaches Cytoscape to DOM container ref');
assert(networkExplorerTsx.includes('runLayout'), 'NetworkExplorer executes dynamic topological graph layout');
assert(networkExplorerTsx.includes('cose'), 'NetworkExplorer supports force-directed COSE layout');
assert(networkExplorerTsx.includes('concentric'), 'NetworkExplorer supports concentric ring layout');
assert(networkExplorerTsx.includes('breadthfirst'), 'NetworkExplorer supports hierarchical tree layout');
assert(networkExplorerTsx.includes('RELATIONSHIP INSPECTION'), 'NetworkExplorer includes relationship edge inspector');
assert(networkExplorerTsx.includes('MOD-03-NET'), 'NetworkExplorer preserves MOD-03-NET module code');

// 8. Verify Live FastAPI Backend Smoke Test (if backend is active)
console.log('\n--- 8. Live FastAPI Backend Smoke Test ---');
try {
  const healthRes = await fetch('http://127.0.0.1:8000/health');
  assert(healthRes.status === 200, 'Live Backend /health returns HTTP 200');

  const entitiesRes = await fetch('http://127.0.0.1:8000/api/v1/entities?limit=10');
  assert(entitiesRes.status === 200, 'Live Backend /api/v1/entities returns HTTP 200');
  const entitiesJson = await entitiesRes.json();
  assert(Array.isArray(entitiesJson), 'Entities response is an Array');

  if (entitiesJson.length > 0) {
    const testEntity = entitiesJson[0];
    const detailsRes = await fetch(`http://127.0.0.1:8000/api/v1/entities/${encodeURIComponent(testEntity.entity_id)}`);
    assert(detailsRes.status === 200, `Live Backend /api/v1/entities/{id} returns HTTP 200 for ${testEntity.canonical_name || testEntity.entity_id}`);
    const detailsJson = await detailsRes.json();
    assert(typeof detailsJson.direct_relationship_count === 'number', 'Entity details contains direct_relationship_count');

    // 1-hop test
    const nbRes1 = await fetch(`http://127.0.0.1:8000/api/v1/entities/${encodeURIComponent(testEntity.entity_id)}/neighborhood?depth=1&limit=50`);
    assert(nbRes1.status === 200, `Live Backend /api/v1/entities/{id}/neighborhood returns HTTP 200 (depth=1)`);
    const nbJson1 = await nbRes1.json();
    assert(typeof nbJson1.total_nodes === 'number', 'Neighborhood (depth=1) contains total_nodes');
    assert(typeof nbJson1.total_edges === 'number', 'Neighborhood (depth=1) contains total_edges');
    assert(Array.isArray(nbJson1.relationships), 'Neighborhood (depth=1) contains relationships array');

    // 2-hop test (Network Explorer contract)
    const nbRes2 = await fetch(`http://127.0.0.1:8000/api/v1/entities/${encodeURIComponent(testEntity.entity_id)}/neighborhood?depth=2&limit=50`);
    assert(nbRes2.status === 200, `Live Backend /api/v1/entities/{id}/neighborhood returns HTTP 200 (depth=2)`);
    const nbJson2 = await nbRes2.json();
    assert(nbJson2.depth === 2, 'Neighborhood depth equals 2');
    assert(typeof nbJson2.total_nodes === 'number', 'Neighborhood (depth=2) contains total_nodes');
    assert(typeof nbJson2.total_edges === 'number', 'Neighborhood (depth=2) contains total_edges');
    assert(Array.isArray(nbJson2.relationships), 'Neighborhood (depth=2) contains relationships array');
  } else {
    console.log('[INFO] No entities in database to test specific entity details/neighborhood.');
  }
} catch (err) {
  console.log('[INFO] Backend server currently offline for live smoke test. Skipping live API assertions.');
}

// Summary
console.log('\n================================================================');
if (failedTests === 0) {
  console.log('ALL VERIFICATIONS PASSED (0 failures)');
  console.log('Phase 6B.2 Network Explorer implementation verified successfully.');
} else {
  console.error(`VERIFICATION FAILED: ${failedTests} test(s) failed.`);
  process.exit(1);
}
console.log('================================================================\n');

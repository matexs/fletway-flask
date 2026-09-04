import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export function renderEndpointTest(endpoint) {
  const serialized = JSON.stringify({ id: endpoint.id, role: endpoint.auth_role, mutation: endpoint.mutates_data }, null, 2);
  return `import http from 'k6/http';
import execution from 'k6/execution';
import { check } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { adapterFor, buildRequestBody, resolvePath } from '../../k6/adapters/endpoint-adapters.js';
import { buildScenarios, buildThresholds, metricName, profileIdsFor } from '../../k6/config/performance.config.js';
import { captureResponseIds, emitLedgerEvent, isTimeout, pause, requestOptions, requestTags, setupEndpoint, solicitationFor, tokenForRole } from '../../templates/endpoint.template.js';

const endpoint = ${serialized};
const adapter = adapterFor(endpoint);
// Contract marker: resolvePath(adapter.path) remains the single path boundary.
const BASE_URL = String(__ENV.BASE_URL || '').replace(/[\\\\/,]+$/, '');
const PROFILE = __ENV.PROFILE || 'smoke';

export const options = { scenarios: buildScenarios(PROFILE), thresholds: buildThresholds(profileIdsFor(PROFILE), [{ key: endpoint.id }]), setupTimeout: __ENV.K6_SETUP_TIMEOUT || '10m', summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'count'] };
const metrics = Object.fromEntries(profileIdsFor(PROFILE).map((profileId) => [profileId, {
  duration: new Trend(metricName(profileId, 'duration_ms', endpoint.id), true),
  success: new Rate(metricName(profileId, 'success_rate', endpoint.id)),
  errors: new Rate(metricName(profileId, 'error_rate', endpoint.id)),
  timeouts: new Rate(metricName(profileId, 'timeout_rate', endpoint.id)),
}]));

export function setup() { return setupEndpoint(endpoint); }

export function runFlow(data) {
  const fixture = solicitationFor(data.pool);
  const context = { runId: __ENV.RUN_ID, vu: __VU, iteration: __ITER, solicitudId: fixture && fixture.solicitudId, localidadOrigenId: (fixture && fixture.localidadOrigenId) || (data.localities && data.localities.origin), localidadDestinoId: (fixture && fixture.localidadDestinoId) || (data.localities && data.localities.destination) };
  const body = buildRequestBody(adapter, context);
  const scenario = execution.scenario.name;
  const tags = requestTags({ endpointId: endpoint.id, profile: PROFILE, stage: scenario, role: endpoint.role });
  const payload = body === undefined ? null : JSON.stringify(body);
  const response = http.request(adapter.method, BASE_URL + resolvePath(adapter.path, context), payload, requestOptions(tokenForRole(endpoint.role, data.auth), tags));
  const successful = response.status === adapter.expectedStatus;
  const timedOut = isTimeout(response);
  const current = metrics[scenario] || metrics[PROFILE];
  current.duration.add(response.timings.duration, tags);
  current.success.add(successful, tags);
  current.errors.add(!successful, tags);
  current.timeouts.add(timedOut, tags);
  if (!successful) console.log(\`FLETWAY_RESULT \${JSON.stringify({ run_id: __ENV.RUN_ID || 'run', endpoint_id: endpoint.id, profile: PROFILE, status: response.status, error: response.error || null, timed_out: timedOut })}\`);
  check(response, { [endpoint.id + ' expected status']: () => successful, [endpoint.id + ' no timeout']: () => !timedOut }, tags);
  if (endpoint.mutation) emitLedgerEvent({ endpoint_id: endpoint.id, method: adapter.method, path: resolvePath(adapter.path, context), status: response.status, response_ids: captureResponseIds(response), resource_action: 'create', created_by_test: true });
  pause();
}

export default function (data) { runFlow(data); }
`;
}

function loadManifest(manifestPath) {
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  if (!Array.isArray(manifest.endpoints)) throw new Error('manifest.endpoints must be an array');
  return manifest.endpoints;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const manifestPath = process.argv[2] || path.join(root, 'config', 'endpoints.manifest.json');
  for (const endpoint of loadManifest(manifestPath)) {
    const directory = endpoint.module.includes('presupuesto') ? path.join(root, 'endpoints', 'presupuestos') : path.join(root, 'endpoints', 'solicitudes');
    fs.mkdirSync(directory, { recursive: true });
    fs.writeFileSync(path.join(directory, `${endpoint.id}.js`), renderEndpointTest(endpoint));
  }
}

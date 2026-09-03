import http from 'k6/http';
import { check } from 'k6';
import execution from 'k6/execution';
import { Rate, Trend } from 'k6/metrics';
import { captureResponseIds, emitLedgerEvent, isTimeout, requestOptions, requestTags, setupAuth, tokenForRole } from '../../templates/endpoint.template.js';
import { adapterFor, resolvePath } from '../../k6/adapters/endpoint-adapters.js';
import { buildScenarios, buildThresholds, metricName, profileIdsFor } from '../../k6/config/performance.config.js';

const endpoint = { "id": "presupuestos-completo-batch", "role": "client", "mutation": false };
const adapter = adapterFor(endpoint);
const BASE_URL = String(__ENV.BASE_URL || '').replace(/[\/,]+$/, '');
const PROFILE = __ENV.PROFILE || 'smoke';
export const options = { scenarios: buildScenarios(PROFILE), thresholds: buildThresholds(profileIdsFor(PROFILE), [{ key: endpoint.id }]) };
const metrics = Object.fromEntries(profileIdsFor(PROFILE).map((profileId) => [profileId, {
  overall: { duration: new Trend(metricName(profileId, 'duration_ms'), true), success: new Rate(metricName(profileId, 'success_rate')), errors: new Rate(metricName(profileId, 'error_rate')), timeouts: new Rate(metricName(profileId, 'timeout_rate')) },
  endpoint: { duration: new Trend(metricName(profileId, 'duration_ms', endpoint.id), true), success: new Rate(metricName(profileId, 'success_rate', endpoint.id)), errors: new Rate(metricName(profileId, 'error_rate', endpoint.id)), timeouts: new Rate(metricName(profileId, 'timeout_rate', endpoint.id)) },
}]));
export function setup() { return setupAuth(endpoint.role); }
export function runFlow(auth) {
  const body = adapter.body ? adapter.body() : undefined;
  const tags = requestTags({ endpointId: endpoint.id, profile: PROFILE, stage: __ENV.STAGE || 'measure', role: endpoint.role });
  const response = http.request(adapter.method, BASE_URL + resolvePath(adapter.path), body === undefined ? null : JSON.stringify(body), requestOptions(tokenForRole(endpoint.role, auth), tags));
  const timedOut = isTimeout(response, __ENV.REQUEST_TIMEOUT || '10s');
  const successful = response.status >= 200 && response.status < 400;
  const metricSet = metrics[execution.scenario.name] || metrics[PROFILE];
  for (const scope of [metricSet.overall, metricSet.endpoint]) { scope.duration.add(response.timings.duration, tags); scope.success.add(successful, tags); scope.errors.add(!successful, tags); scope.timeouts.add(timedOut, tags); }
  check(response, { [endpoint.id + ' status is successful']: () => successful, [endpoint.id + ' does not time out']: () => !timedOut }, tags);
  if (endpoint.mutation) emitLedgerEvent({ endpoint_id: endpoint.id, method: adapter.method, path: adapter.path, status: response.status, response_ids: captureResponseIds(response), resource_action: 'update', created_by_test: false });
}
export default function (auth) { return runFlow(auth); }

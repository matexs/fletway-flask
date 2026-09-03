import http from 'k6/http';
import { check } from 'k6';
import execution from 'k6/execution';
import { Rate, Trend } from 'k6/metrics';
import { captureResponseIds, emitLedgerEvent, isTimeout, requestOptions, requestTags, setupAuth, tokenForRole } from '../../templates/endpoint.template.js';
import { adapterFor, resolvePath } from '../../k6/adapters/endpoint-adapters.js';
import { buildScenarios, buildThresholds, metricName, profileIdsFor } from '../../k6/config/performance.config.js';

const endpoint = {
  "id": "detalle-solicitud",
  "role": "client",
  "mutation": false
};
// Path IDs come from environment variables: REQUEST_ID.
const adapter = adapterFor(endpoint);
const BASE_URL = String(__ENV.BASE_URL || '').replace(/[\/,]+$/, '');
const PROFILE = __ENV.PROFILE || 'smoke';

export const options = { scenarios: buildScenarios(PROFILE), thresholds: buildThresholds(profileIdsFor(PROFILE), [{ key: endpoint.id }]) };
const metrics = Object.fromEntries(profileIdsFor(PROFILE).map((profileId) => [profileId, {
  overall: {
    duration: new Trend(metricName(profileId, 'duration_ms'), true),
    success: new Rate(metricName(profileId, 'success_rate')),
    errors: new Rate(metricName(profileId, 'error_rate')),
    timeouts: new Rate(metricName(profileId, 'timeout_rate')),
  },
  endpoint: {
    duration: new Trend(metricName(profileId, 'duration_ms', endpoint.id), true),
    success: new Rate(metricName(profileId, 'success_rate', endpoint.id)),
    errors: new Rate(metricName(profileId, 'error_rate', endpoint.id)),
    timeouts: new Rate(metricName(profileId, 'timeout_rate', endpoint.id)),
  },
}]));
export function setup() { return setupAuth(endpoint.role); }
export function runFlow(auth) {
  const body = adapter.body ? adapter.body() : undefined;
  const tags = requestTags({ endpointId: endpoint.id, profile: PROFILE, stage: __ENV.STAGE || 'measure', role: endpoint.role });
  const token = tokenForRole(endpoint.role, auth);
  const requestBody = adapter.transport?.type === 'multipart'
    ? { [adapter.transport.field]: http.file(open(__ENV[adapter.transport.fixtureEnv], 'b'), __ENV[adapter.transport.filenameEnv] || 'upload.bin', __ENV[adapter.transport.contentTypeEnv] || 'application/octet-stream') }
    : (body === undefined ? null : JSON.stringify(body));
  const response = http.request(adapter.method, BASE_URL + resolvePath(adapter.path), requestBody, requestOptions(token, tags, undefined, { multipart: adapter.transport?.type === 'multipart' }));
  const timedOut = isTimeout(response, __ENV.REQUEST_TIMEOUT || '10s');
  const successful = response.status >= 200 && response.status < 400;
  const metricSet = metrics[execution.scenario.name] || metrics[PROFILE];
  metricSet.overall.duration.add(response.timings.duration, tags);
  metricSet.overall.success.add(successful, tags);
  metricSet.overall.errors.add(!successful, tags);
  metricSet.overall.timeouts.add(timedOut, tags);
  metricSet.endpoint.duration.add(response.timings.duration, tags);
  metricSet.endpoint.success.add(successful, tags);
  metricSet.endpoint.errors.add(!successful, tags);
  metricSet.endpoint.timeouts.add(timedOut, tags);
  check(response, { [endpoint.id + ' status is successful']: () => response.status >= 200 && response.status < 400, [endpoint.id + ' does not time out']: () => !timedOut }, tags);
  const responseIds = endpoint.mutation ? captureResponseIds(response) : {};
  endpoint.mutation && emitLedgerEvent({ endpoint_id: endpoint.id, method: adapter.method, path: adapter.path, status: response.status, response_ids: responseIds, resource_action: 'update', created_by_test: false });
}

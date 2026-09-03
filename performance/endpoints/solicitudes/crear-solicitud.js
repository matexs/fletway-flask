import http from 'k6/http';
import { check } from 'k6';
import { captureResponseIds, emitLedgerEvent, isTimeout, requestOptions, requestTags, setupAuth, tokenForRole } from '../../templates/endpoint.template.js';
import { adapterFor, resolvePath } from '../../k6/adapters/endpoint-adapters.js';
import { buildScenarios, buildThresholds, profileIdsFor } from '../../k6/config/performance.config.js';

const endpoint = {
  "id": "crear-solicitud",
  "role": "client",
  "mutation": true
};
const adapter = adapterFor(endpoint);
const BASE_URL = String(__ENV.BASE_URL || '').replace(/[\/,]+$/, '');
const PROFILE = __ENV.PROFILE || 'smoke';

export const options = { scenarios: buildScenarios(PROFILE), thresholds: buildThresholds(profileIdsFor(PROFILE), [{ key: endpoint.id }]) };
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
  check(response, { [endpoint.id + ' status is successful']: () => response.status >= 200 && response.status < 400, [endpoint.id + ' does not time out']: () => !timedOut }, tags);
  const responseIds = endpoint.mutation ? captureResponseIds(response) : {};
  endpoint.mutation && emitLedgerEvent({ endpoint_id: endpoint.id, method: adapter.method, path: adapter.path, status: response.status, response_ids: responseIds });
}

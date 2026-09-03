import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { endpointForIteration, selectEndpoint } from '../k6/lib/endpoint-selection.js';

const endpoints = [
  { key: 'health', manifestId: 'health', weight: 5 },
  { key: 'buscar_localidades', manifestId: 'buscar-localidades', weight: 10 },
];

test('selects exactly the requested manifest endpoint', () => {
  assert.equal(selectEndpoint(endpoints, 'buscar-localidades').key, 'buscar_localidades');
  assert.equal(selectEndpoint(endpoints, 'buscar-localidades', 99).key, 'buscar_localidades');
});

test('rejects an unknown endpoint instead of falling back to weights', () => {
  assert.throws(() => selectEndpoint(endpoints, 'not-in-manifest', 0), /unknown endpoint/i);
});

test('never uses weighted fallback when an endpoint is selected', () => {
  assert.equal(endpointForIteration(endpoints, 'health', 99).manifestId, 'health');
});

test('k6 flow uses the exact selector and manifest endpoint tag', () => {
  const script = fs.readFileSync(path.resolve('performance/k6/scripts/fletway-api.js'), 'utf8');
  assert.match(script, /selectEndpointForIteration\(endpoints, ENDPOINT_ID/);
  assert.match(script, /endpointId: endpoint\.manifestId/);
  assert.equal((script.match(/const selectedEndpoint/g) || []).length, 1);
});

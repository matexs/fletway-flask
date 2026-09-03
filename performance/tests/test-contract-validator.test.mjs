import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { validateTestContract } from '../scripts/validate-test-contract.mjs';

function file(contents) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'fletway-contract-'));
  const target = path.join(directory, 'endpoint.js');
  fs.writeFileSync(target, contents, 'utf8');
  return target;
}

test('accepts generated endpoint contract without stages, thresholds, or secrets', () => {
  const result = validateTestContract(file("import { setupAuth } from '../templates/endpoint.template.js';\nimport { adapterFor } from '../k6/adapters/endpoint-adapters.js';\nconst endpoint = { id: 'localidades' };\nsetupAuth; adapterFor(endpoint);"));
  assert.equal(result.valid, true);
});

test('rejects hardcoded stages and thresholds in endpoint scripts', () => {
  assert.throws(() => validateTestContract(file("export const options = { stages: [{ duration: '1m', target: 10 }], thresholds: { p95: ['p(95)<500'] } };")), /stages|thresholds/i);
});

test('rejects credentials, JWTs, and concrete path IDs', () => {
  assert.throws(() => validateTestContract(file("const password = 'super-secret'; const token = 'literal-token'; const jwt = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def'; const path = '/api/solicitudes/123';")), /secret|credential|jwt|hardcoded.*id/i);
});

test('rejects secrets hidden in object properties, bearer headers, UUIDs, queries, and paths', () => {
  const source = "const config = { password: 'x', apiKey: 'y' }; const headers = { Authorization: 'Bearer abc.def.ghi' }; const path = '/api/items/550e8400-e29b-41d4-a716-446655440000?q=123';";
  assert.throws(() => validateTestContract(file(source)), /secret|bearer|uuid|query|id/i);
});

test('requires executable imports and calls instead of comments or strings', () => {
  assert.throws(() => validateTestContract(file("// adapterFor and endpoint.template.js\nconst text = 'adapterFor';")), /import|usage|adapter/i);
});

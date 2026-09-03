import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const template = fs.readFileSync(path.resolve('performance/templates/endpoint.template.js'), 'utf8');

test('exposes a named structured ledger hook and role-aware setupAuth', () => {
  assert.match(template, /export function emitLedgerEvent\(/);
  assert.match(template, /event_type:\s*['"]performance_response['"]/);
  assert.match(template, /export function setupAuth\(requiredRole\s*=\s*null\)/);
  assert.match(template, /requiredRole/);
  assert.match(template, /requiredRole === 'public'/);
  assert.match(template, /requiredRole === 'public'\) return \['BASE_URL'\]/);
});

test('uses timeout status, k6 error code, and timing-aware detection', () => {
  assert.match(template, /export \{ isTimeout \} from/);
});

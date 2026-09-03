import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { validateTestContract } from '../../scripts/validate-test-contract.mjs';

const directory = path.dirname(fileURLToPath(import.meta.url));
const manifestPath = path.resolve(directory, '../../config/endpoints.manifest.json');
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const endpointIds = manifest.endpoints
  .filter(({ module, priority }) => module === 'routes/solicitud_routes.py' && priority === 'P0')
  .map(({ id }) => id);

test('contains every Solicitudes P0 endpoint script with the shared contract', () => {
  assert.ok(endpointIds.length, 'canonical manifest contains no Solicitudes P0 endpoints');
  for (const endpointId of endpointIds) {
    const filePath = path.join(directory, `${endpointId}.js`);
    assert.equal(fs.existsSync(filePath), true, `canonical manifest P0 endpoint lacks script: ${endpointId}`);
    assert.deepEqual(validateTestContract(filePath), { valid: true, filePath, violations: [] });
  }
});

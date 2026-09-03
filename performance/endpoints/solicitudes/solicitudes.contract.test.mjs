import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { validateTestContract } from '../../scripts/validate-test-contract.mjs';

const directory = path.dirname(fileURLToPath(import.meta.url));
const endpointIds = [
  'mis-pedidos',
  'mis-pedidos-optimizado',
  'dashboard-transportista',
  'historial-transportista',
  'crear-solicitud',
  'actualizar-solicitud',
  'detalle-solicitud',
];

test('contains every Solicitudes P0 endpoint script with the shared contract', () => {
  for (const endpointId of endpointIds) {
    const filePath = path.join(directory, `${endpointId}.js`);
    assert.equal(fs.existsSync(filePath), true, `missing endpoint script: ${endpointId}`);
    assert.deepEqual(validateTestContract(filePath), { valid: true, filePath, violations: [] });
  }
});

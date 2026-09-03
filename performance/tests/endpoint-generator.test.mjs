import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { generateEndpointTest } from '../scripts/generate-endpoint-test.mjs';

const manifestPath = path.resolve('performance/config/endpoints.manifest.json');

test('generates a manifest endpoint with shared setup and adapter request metadata', () => {
  const output = generateEndpointTest(manifestPath, 'crear-solicitud');
  assert.match(output, /from ['"].*templates[\\/]endpoint\.template\.js/);
  assert.match(output, /adapterFor\(endpoint\)/);
  assert.match(output, /adapter\.body/);
  assert.match(output, /captureResponseIds/);
  assert.doesNotMatch(output, /stages\s*:/);
  assert.doesNotMatch(output, /thresholds\s*:\s*\{/);
});

test('captures path IDs from environment without hardcoding a concrete ID', () => {
  const output = generateEndpointTest(manifestPath, 'detalle-solicitud');
  assert.match(output, /resolvePath/);
  assert.match(output, /REQUEST_ID/);
  assert.doesNotMatch(output, /\/api\/solicitudes\/\d+/);
});

test('uses adapter method and path at runtime and calls the ledger hook for mutations', () => {
  const output = generateEndpointTest(manifestPath, 'crear-solicitud');
  assert.match(output, /http\.request\(adapter\.method/);
  assert.match(output, /resolvePath\(adapter\.path\)/);
  assert.doesNotMatch(output, /method:\s*['"]POST['"]/);
  assert.doesNotMatch(output, /path:\s*['"]\/api\/solicitudes['"]/);
  assert.match(output, /endpoint\.mutation\s*&&\s*emitLedgerEvent/);
  assert.match(output, /setupAuth\(endpoint\.role\)/);
});

test('writes one generated endpoint file and refuses unknown manifest IDs', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'fletway-generator-'));
  const outputPath = path.join(directory, 'crear-solicitud.js');
  const result = generateEndpointTest(manifestPath, 'crear-solicitud', outputPath);
  assert.equal(result.outputPath, outputPath);
  assert.equal(fs.existsSync(outputPath), true);
  assert.throws(() => generateEndpointTest(manifestPath, 'missing-endpoint'), /unknown endpoint/i);
});

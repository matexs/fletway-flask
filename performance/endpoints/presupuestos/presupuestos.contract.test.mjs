import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const directory = path.dirname(fileURLToPath(import.meta.url));
const localManifestPath = path.resolve(directory, '../../config/endpoints.manifest.json');
const siblingManifestPath = path.resolve(directory, '../../../../fletway-flask-performance/performance/config/endpoints.manifest.json');
const manifestPath = process.env.PERFORMANCE_MANIFEST_PATH || (fs.existsSync(localManifestPath) ? localManifestPath : siblingManifestPath);
const endpointIds = [
  'mis-presupuestos',
  'presupuestos-completo-batch',
  'presupuestos-solicitud',
];

function loadManifest() {
  assert.equal(fs.existsSync(manifestPath), true, `missing canonical manifest: ${manifestPath}`);
  return JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
}

test('contains every Presupuestos P0 endpoint declared in the canonical manifest', () => {
  const manifest = loadManifest();
  const endpoints = manifest.endpoints.filter((endpoint) => endpoint.module === 'routes/presupuesto_routes.py' && endpoint.priority === 'P0');
  assert.deepEqual(endpoints.map((endpoint) => endpoint.id), endpointIds);

  for (const endpoint of endpoints) {
    const filePath = path.join(directory, `${endpoint.id}.js`);
    assert.equal(fs.existsSync(filePath), true, `missing endpoint script: ${endpoint.id}`);
    const source = fs.readFileSync(filePath, 'utf8');
    assert.match(source, new RegExp(`"id": "${endpoint.id}"`));
    assert.match(source, /adapterFor\(endpoint\)/);
    assert.match(source, /resolvePath\(adapter\.path\)/);
    assert.match(source, /http\.request\(adapter\.method/);
    assert.match(source, /export default function/);
    assert.match(source, /new Trend\(metricName/);
    assert.match(source, /new Rate\(metricName/);
    assert.match(source, /requestTags\(/);
    assert.doesNotMatch(source, /(password|jwt|Bearer\s+[A-Za-z0-9._-]{20,})\s*[:=]/i);
  }
});

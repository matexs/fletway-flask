import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { metricName } from '../k6/config/performance.config.js';

const performanceRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const manifestPath = path.join(performanceRoot, 'config', 'endpoints.manifest.json');

const requested = [
  ['GET', '/api/presupuestos/completo-batch', 'client', ['load', 'stress', 'spike']],
  ['GET', '/api/presupuestos/mis-presupuestos', 'driver', ['load', 'stress', 'spike']],
  ['GET', '/api/presupuestos/solicitud/<solicitud_id>', 'client', ['smoke', 'load', 'stress', 'spike']],
  ['GET', '/api/solicitudes/<id>', 'client', ['smoke', 'load', 'stress', 'spike']],
  ['GET', '/api/solicitudes/mis-pedidos', 'client', ['load', 'stress', 'spike']],
  ['GET', '/api/transportista/dashboard', 'driver', ['load', 'stress', 'spike']],
  ['GET', '/api/transportista/historial', 'driver', ['load', 'stress', 'spike']],
  ['GET', '/solicitudes/mis-pedidos-optimizado', 'client', ['load', 'stress', 'spike']],
  ['PATCH', '/api/solicitudes/<id>', 'client', ['smoke', 'load', 'stress', 'spike']],
  ['POST', '/api/solicitudes', 'client', ['smoke', 'load', 'stress', 'spike']],
];

test('manifest contains exactly the requested endpoints and profiles', () => {
  assert.equal(fs.existsSync(manifestPath), true);
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  assert.equal(manifest.endpoints.length, requested.length);
  assert.deepEqual(manifest.endpoints.map((e) => [e.method, e.path, e.auth_role, e.enabled_profiles]), requested);
  assert.equal(new Set(manifest.endpoints.map((e) => e.id)).size, requested.length);
  assert.ok(manifest.endpoints.every((e) => typeof e.objective === 'string' && e.objective.length > 0));
});

test('mutating endpoints are explicitly marked', () => {
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const mutations = manifest.endpoints.filter((e) => e.mutates_data);
  assert.deepEqual(mutations.map((e) => e.method), ['PATCH', 'POST']);
});

test('metric names normalize endpoint ids for k6', () => {
  assert.equal(metricName('smoke', 'duration_ms', 'crear-solicitud'), 'fletway_smoke_crear_solicitud_duration_ms');
});

test('preflight does not probe mutating routes with GET', () => {
  const source = fs.readFileSync(path.join(performanceRoot, 'runners', 'preflight.ps1'), 'utf8');
  assert.match(source, /endpoint\.method\s+-eq\s*['"]GET['"]/i);
});

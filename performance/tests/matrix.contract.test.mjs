import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const matrixScript = path.join(root, 'scripts', 'build-general-matrix.ps1');
const manifest = path.join(root, 'config', 'endpoints.manifest.json');

test('matrix builder emits the exact canonical shape for every requested profile', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'fletway-matrix-'));
  const result = spawnSync('pwsh', ['-NoProfile', '-File', matrixScript, '-CampaignDirectory', directory, '-ManifestPath', manifest], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const rows = JSON.parse(fs.readFileSync(path.join(directory, 'matrix_general.json'), 'utf8'));
  const csv = fs.readFileSync(path.join(directory, 'matrix_general.csv'), 'utf8').trim().split(/\r?\n/);
  assert.equal(rows.length, 34);
  assert.equal(csv.length, 35);
  assert.match(csv[1], /GET \/api\/presupuestos\/completo-batch/);
  assert.deepEqual(Object.keys(rows[0]), ['endpoint', 'test', 'objetivo', 'carga_vu_min', 'carga_vu_max', 'p95_ms', 'error_pct', 'capacidad_rps', 'resultado', 'usuarios']);
  assert.ok(rows.every((row) => row.resultado === 'NO_EJECUTADA'));
});

test('matrix builder reads k6 summary metrics at the exported top level', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'fletway-matrix-values-'));
  fs.mkdirSync(path.join(directory, 'raw'));
  fs.writeFileSync(path.join(directory, 'raw', 'presupuestos-completo-batch-load.json'), JSON.stringify({
    result: 'EJECUTADA',
    metrics: {
      fletway_load_presupuestos_completo_batch_duration_ms: { 'p(95)': 1234, count: 90 },
      fletway_load_presupuestos_completo_batch_error_rate: { rate: 0.06 },
      fletway_load_presupuestos_completo_batch_timeout_rate: { rate: 0 },
    },
  }));
  const result = spawnSync('pwsh', ['-NoProfile', '-File', matrixScript, '-CampaignDirectory', directory, '-ManifestPath', manifest], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const rows = JSON.parse(fs.readFileSync(path.join(directory, 'matrix_general.json'), 'utf8'));
  const row = rows.find((candidate) => candidate.endpoint === 'GET /api/presupuestos/completo-batch' && candidate.test === 'load');
  assert.equal(row.p95_ms, '1234');
  assert.equal(row.error_pct, '6');
  assert.equal(row.capacidad_rps, '1');
  assert.equal(row.resultado, 'ADVERTENCIA');
});

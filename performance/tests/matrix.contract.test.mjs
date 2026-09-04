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
  assert.equal(rows.length, 34);
  assert.deepEqual(Object.keys(rows[0]), ['endpoint', 'test', 'objetivo', 'carga_vu_min', 'carga_vu_max', 'p95_ms', 'error_pct', 'capacidad_rps', 'resultado', 'usuarios']);
  assert.ok(rows.every((row) => row.resultado === 'NO_EJECUTADA'));
});

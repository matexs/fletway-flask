import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import {
  calculateScore,
  classifyScore,
  errorScore,
  latencyScore,
  testScore,
} from '../config/scoring.js';

const profiles = ['smoke', 'load', 'stress', 'spike'];

const thresholds = {
  profiles: {
    smoke: { p95_ms: 1000, error_pct: 1 },
    load: { p95_ms: 2000, error_pct: 5 },
    stress: { p95_ms: 3000, error_pct: 10 },
    spike: { p95_ms: 5000, error_pct: 20 },
  },
  hard: { p95_ms: 5000, error_pct: 20 },
};

function row(endpoint, test, p95 = 100, error = 0) {
  return {
    endpoint,
    test,
    objetivo: 'objective',
    carga_vu_min: 1,
    carga_vu_max: 3,
    p95_ms: p95,
    error_pct: error,
    capacidad_rps: 10,
    resultado: 'APROBADA',
    usuarios: '1→3 VUs',
  };
}

function manifest(...items) {
  return { endpoints: items.map(({ id, weight, priority = 'P0' }) => ({
    id,
    method: 'GET',
    path: `/${id}`,
    objective: 'objective',
    priority,
    traffic_weight: weight,
    enabled_profiles: profiles,
  })) };
}

test('calculates bounded latency, error, test, endpoint, and general scores', () => {
  assert.equal(latencyScore(1000, 900), 100);
  assert.equal(latencyScore(1000, 2000), 50);
  assert.equal(errorScore(1, 20, 1), 100);
  assert.equal(errorScore(1, 20, 10.5), 50);
  assert.equal(errorScore(1, 20, 20), 0);
  assert.equal(testScore(50, 100), 65);

  const result = calculateScore({
    thresholds,
    manifest: manifest({ id: 'orders', weight: 2 }),
    matrix: profiles.map((profile) => row('GET /orders', profile)),
  });
  assert.equal(result.coverage_pct, 100);
  assert.equal(result.general_score, 100);
  assert.equal(result.classification, 'EXCELENTE');
  assert.equal(result.representative, true);
  assert.equal(result.endpoints[0].score, 100);
  assert.deepEqual(result.profile_weights, { smoke: 0.1, load: 0.4, stress: 0.3, spike: 0.2 });
});

test('uses only fully executed endpoints and preserves an explicit incomplete reason', () => {
  const matrix = profiles.map((profile) => row('GET /complete', profile));
  matrix[3] = { ...matrix[3], resultado: 'NO_EJECUTADA', carga_vu_min: '', carga_vu_max: '', p95_ms: '', error_pct: '', capacidad_rps: '' };
  const result = calculateScore({
    thresholds,
    manifest: manifest({ id: 'complete', weight: 3 }, { id: 'missing', weight: 2 }),
    matrix,
  });
  assert.equal(result.general_score, null);
  assert.equal(result.endpoints[0].score, null);
  assert.equal(result.endpoints[0].included_in_general, false);
  assert.match(result.endpoints[0].reason, /missing executed profiles: spike/);
  assert.equal(result.coverage_pct, 0);
  assert.equal(result.representative, false);
  assert.equal(result.representative_reason.code, 'COVERAGE_BELOW_TARGET');
});

test('uses all prioritized P0/P1/P2 traffic in coverage denominator', () => {
  const result = calculateScore({
    thresholds,
    manifest: manifest({ id: 'a', weight: 4 }, { id: 'b', weight: 6 }, { id: 'p1', weight: 100, priority: 'P1' }, { id: 'p2', weight: 50, priority: 'P2' }),
    matrix: profiles.flatMap((profile) => [row('GET /a', profile), row('GET /p1', profile)]),
  });
  assert.equal(result.coverage_pct, 2.5);
  assert.equal(result.general_score, 100);
  assert.equal(result.classification, null);
  assert.equal(result.classification_blocked, true);
  assert.equal(result.representative, false);
});

test('handles zero p95 and rejects invalid denominators, contradictions, and malformed numeric values', () => {
  const zeroP95Result = calculateScore({
    thresholds,
    manifest: manifest({ id: 'zero-p95', weight: 1 }),
    matrix: profiles.map((profile) => row('GET /zero-p95', profile, 0)),
  });
  assert.equal(zeroP95Result.endpoints[0].scores.smoke.latency_score, 100);
  assert.equal(errorScore(20, 20, 20), 0);
  assert.throws(() => errorScore(20, 1, 5), /hard error/);
  assert.throws(() => calculateScore({
    thresholds,
    manifest: manifest({ id: 'orders', weight: 1 }),
    matrix: profiles.map((profile) => ({ ...row('GET /orders', profile), p95_ms: 'not-a-number' })),
  }), /p95_ms/);
  assert.throws(() => calculateScore({
    thresholds,
    manifest: manifest({ id: 'orders', weight: 1 }),
    matrix: profiles.map((profile) => row('GET /orders', profile)).concat(row('GET /orders', 'smoke')),
  }), /duplicate/);
});

test('classifies score ranges and blocks representativeness below 80 percent', () => {
  assert.equal(classifyScore(90), 'EXCELENTE');
  assert.equal(classifyScore(80), 'BUENO');
  assert.equal(classifyScore(70), 'ACEPTABLE');
  assert.equal(classifyScore(60), 'MEJORABLE');
  assert.equal(classifyScore(59.99), 'CRITICO');
  assert.throws(() => classifyScore(Number.NaN), /finite/);
});

test('CLI emits reproducible JSON from the canonical matrix and manifest files', () => {
  const root = mkdtempSync(join(tmpdir(), 'fletway-task10-'));
  try {
    const manifestPath = join(root, 'manifest.json');
    const thresholdsPath = join(root, 'thresholds.json');
    const matrixPath = join(root, 'matrix.csv');
    const firstOutput = join(root, 'first.json');
    const secondOutput = join(root, 'second.json');
    writeFileSync(manifestPath, JSON.stringify(manifest({ id: 'orders', weight: 1 })));
    writeFileSync(thresholdsPath, JSON.stringify(thresholds));
    writeFileSync(matrixPath, [
      'endpoint,test,objetivo,carga_vu_min,carga_vu_max,p95_ms,error_pct,capacidad_rps,resultado,usuarios',
      ...profiles.map((profile) => `GET /orders,${profile},objective,1,3,100,0,10,APROBADA,1→3 VUs`),
    ].join('\n'));
    for (const output of [firstOutput, secondOutput]) {
      const run = spawnSync(process.execPath, ['performance/scripts/calculate-score.js', '--matrix', matrixPath, '--manifest', manifestPath, '--thresholds', thresholdsPath, '--output', output], { encoding: 'utf8' });
      assert.equal(run.status, 0, run.stderr || run.stdout);
    }
    assert.equal(readFileSync(firstOutput, 'utf8'), readFileSync(secondOutput, 'utf8'));
    assert.equal(JSON.parse(readFileSync(firstOutput, 'utf8')).general_score, 100);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('rejects invalid threshold error percentages before incomplete endpoints are scored', () => {
  const incompleteMatrix = profiles.map((profile) => ({
    ...row('GET /orders', profile),
    resultado: 'NO_EJECUTADA',
    carga_vu_min: '',
    carga_vu_max: '',
    p95_ms: '',
    error_pct: '',
    capacidad_rps: '',
  }));
  const calculateIncomplete = (thresholdVariant) => calculateScore({
    thresholds: thresholdVariant,
    manifest: manifest({ id: 'orders', weight: 1 }),
    matrix: incompleteMatrix,
  });
  const variant = (mutate) => {
    const copy = JSON.parse(JSON.stringify(thresholds));
    mutate(copy);
    return copy;
  };

  assert.throws(() => calculateIncomplete(variant((value) => { value.profiles.smoke.error_pct = -0.1; })), /smoke\.error_pct/);
  assert.throws(() => calculateIncomplete(variant((value) => { value.profiles.load.error_pct = 100.1; })), /load\.error_pct/);
  assert.throws(() => calculateIncomplete(variant((value) => { value.profiles.stress.error_pct = 'NaN'; })), /stress\.error_pct/);
  assert.throws(() => calculateIncomplete(variant((value) => { value.hard.error_pct = 100.1; })), /hard\.error_pct/);
  assert.throws(() => calculateIncomplete(variant((value) => { value.profiles.spike.error_pct = 21; value.hard.error_pct = 20; })), /spike.*hard|target.*hard/);
});

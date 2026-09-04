import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { buildScenarios, profiles } from '../k6/config/performance.config.js';
import { parseLedgerMarkers } from '../fixtures/resource-ledger.js';

test('profiles preserve the approved five-minute endpoint schedule', () => {
  assert.deepEqual(profiles, {
    smoke: { minVus: 1, maxVus: 3, durationSeconds: 40 },
    load: { minVus: 0, maxVus: 10, durationSeconds: 90 },
    stress: { minVus: 10, maxVus: 30, durationSeconds: 105 },
    spike: { minVus: 3, maxVus: 30, durationSeconds: 60 },
  });
  assert.equal(buildScenarios('stress').stress_30.vus, 30);
  assert.equal(buildScenarios('spike').spike.stages[2].target, 30);
});

test('ledger parser accepts only sanitized FLETWAY markers', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'fletway-ledger-'));
  const logPath = path.join(directory, 'run.log');
  fs.writeFileSync(logPath, [
    'normal k6 output',
    'FLETWAY_LEDGER {"run_id":"r1","created_at":"2026-09-04T00:00:00Z","endpoint_id":"crear-solicitud","method":"POST","path":"/api/solicitudes","status":201,"response_ids":{"solicitud_id":42},"resource_action":"create","created_by_test":true}',
    'FLETWAY_LEDGER {"run_id":"r1","created_at":"2026-09-04T00:00:01Z","endpoint_id":"crear-solicitud","method":"POST","path":"/api/solicitudes","status":500,"response_ids":{},"resource_action":"create","created_by_test":true}',
  ].join('\n'));
  assert.deepEqual(parseLedgerMarkers(logPath), [{
    run_id: 'r1', created_at: '2026-09-04T00:00:00Z', endpoint_id: 'crear-solicitud',
    method: 'POST', path: '/api/solicitudes', status: 201, response_ids: { solicitud_id: 42 },
    resource_action: 'create', created_by_test: true,
  }]);
});


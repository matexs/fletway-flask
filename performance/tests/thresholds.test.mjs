import assert from 'node:assert/strict';
import test from 'node:test';
import { buildThresholds, metricName } from '../config/thresholds.js';

test('normalizes endpoint IDs into valid k6 metric names without changing suffixes', () => {
  assert.equal(metricName('smoke', 'success_rate', 'mis-pedidos'), 'fletway_smoke_mis_pedidos_success_rate');
  assert.deepEqual(Object.keys(buildThresholds(['smoke'], [{ key: 'mis-pedidos' }])).sort(), [
    'fletway_smoke_duration_ms',
    'fletway_smoke_error_rate',
    'fletway_smoke_mis_pedidos_duration_ms',
    'fletway_smoke_mis_pedidos_error_rate',
    'fletway_smoke_mis_pedidos_success_rate',
    'fletway_smoke_mis_pedidos_timeout_rate',
    'fletway_smoke_success_rate',
    'fletway_smoke_timeout_rate',
  ]);
});

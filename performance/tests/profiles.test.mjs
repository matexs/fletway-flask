import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildScenarios,
  profileIdsFor,
  profileLabels,
  spikeRecovery,
  stressStages,
} from '../config/profiles.js';

test('defines canonical smoke and load ramp boundaries', () => {
  assert.deepEqual(buildScenarios('smoke').smoke.stages.map(({ target }) => target), [1, 3, 0]);
  assert.deepEqual(buildScenarios('load').load.stages.map(({ target }) => target), [10, 10, 0]);
});

test('keeps standard stress levels independently addressable', () => {
  assert.deepEqual(profileIdsFor('stress'), ['stress_10', 'stress_20', 'stress_30']);
  const scenarios = buildScenarios('stress');
  for (const [id, vus] of [['stress_10', 10], ['stress_20', 20], ['stress_30', 30]]) {
    assert.equal(scenarios[id].vus, vus);
    assert.equal(scenarios[id].startTime, '0s');
  }
});

test('supports configurable extended P0 stress stages', () => {
  assert.deepEqual(stressStages('p0'), [20, 40, 60, 80, 100]);
  assert.deepEqual(profileIdsFor('stress_p0'), ['stress_p0_20', 'stress_p0_40', 'stress_p0_60', 'stress_p0_80', 'stress_p0_100']);
  const scenarios = buildScenarios('stress_p0', { vus: [25, 50] });
  assert.deepEqual(Object.keys(scenarios), ['stress_p0_25', 'stress_p0_50']);
  assert.equal(scenarios.stress_p0_50.vus, 50);
});

test('provides an abrupt configurable spike with recovery metadata', () => {
  assert.equal(profileLabels.spike, 'Spike');
  const defaults = buildScenarios('spike').spike;
  assert.deepEqual(defaults.stages.map(({ target }) => target), [3, 30, 3, 0]);
  assert.deepEqual(spikeRecovery(), { target: 3, duration: '30s' });
  const scenario = buildScenarios('spike', { baselineVus: 2, spikeVus: 25, recoveryVus: 2 }).spike;
  assert.deepEqual(scenario.stages.map(({ target }) => target), [2, 25, 2, 0]);
  assert.deepEqual(spikeRecovery({ baselineVus: 2, recoveryVus: 2 }), { target: 2, duration: '30s' });
});

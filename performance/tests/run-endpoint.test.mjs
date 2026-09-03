import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const runner = path.resolve('performance/runners/run-endpoint.ps1');

test('builds a dry-run command with endpoint and measurable stage metadata', () => {
  const output = execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', runner,
    '-EndpointId', 'health', '-Profile', 'stress', '-Stage', 'stress_20',
    '-VuMin', '10', '-VuMax', '20', '-WhatIf'], { encoding: 'utf8' });
  assert.match(output, /ENDPOINT_ID=health/);
  assert.match(output, /STAGE=stress_20/);
  assert.match(output, /VU_MIN=10/);
  assert.match(output, /VU_MAX=20/);
});

test('preserves raw summary data and adds stage and spike recovery metadata', () => {
  assert.match(fs.readFileSync(runner, 'utf8'), /recovery/);
  const output = execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', runner,
    '-EndpointId', 'health', '-Profile', 'spike', '-Stage', 'spike',
    '-VuMin', '2', '-VuMax', '25', '-RecoveryVus', '2', '-RecoveryDuration', '30s', '-WhatIf'], { encoding: 'utf8' });
  assert.match(output, /RECOVERY_VUS=2/);
  assert.match(output, /RECOVERY_DURATION=30s/);
});

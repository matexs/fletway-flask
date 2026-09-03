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
  assert.match(output, /PROFILE=stress_20/);
  assert.doesNotMatch(output, /PROFILE=stress /);
});

test('derives canonical VU bounds when they are omitted', () => {
  const output = execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', runner,
    '-EndpointId', 'health', '-Profile', 'load', '-WhatIf'], { encoding: 'utf8' });
  assert.match(output, /VU_MIN=0/);
  assert.match(output, /VU_MAX=10/);
});

test('preserves raw summary data and adds stage and spike recovery metadata', () => {
  assert.match(fs.readFileSync(runner, 'utf8'), /recovery/);
  const output = execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', runner,
    '-EndpointId', 'health', '-Profile', 'spike', '-Stage', 'spike',
    '-VuMin', '2', '-VuMax', '25', '-RecoveryVus', '2', '-RecoveryDuration', '30s', '-WhatIf'], { encoding: 'utf8' });
  assert.match(output, /RECOVERY_VUS=2/);
  assert.match(output, /RECOVERY_DURATION=30s/);
});

test('exposes configurable spike controls and records canonical recovery defaults', () => {
  const output = execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', runner,
    '-EndpointId', 'health', '-Profile', 'spike', '-BaselineVus', '4', '-SpikeVus', '50', '-WhatIf'], { encoding: 'utf8' });
  assert.match(output, /VU_MIN=4/);
  assert.match(output, /VU_MAX=50/);
  assert.match(output, /RECOVERY_VUS=4/);
  assert.match(output, /RECOVERY_DURATION=30s/);
});

test('uses the plan spike defaults when controls are omitted', () => {
  const output = execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', runner,
    '-EndpointId', 'health', '-Profile', 'spike', '-WhatIf'], { encoding: 'utf8' });
  assert.match(output, /VU_MIN=3/);
  assert.match(output, /VU_MAX=30/);
  assert.match(output, /BASELINE_VUS=3/);
  assert.match(output, /SPIKE_VUS=30/);
  assert.match(output, /RECOVERY_VUS=3/);
  assert.match(output, /RECOVERY_DURATION=30s/);
});

test('rejects output traversal and existing output without explicit overwrite', () => {
  assert.throws(() => execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', runner,
    '-EndpointId', 'health', '-OutputPath', '..\\escaped.json', '-WhatIf'], { encoding: 'utf8', stdio: 'pipe' }), /results|path|ruta/i);
});

test('refuses to overwrite an existing result unless forced', () => {
  const source = fs.readFileSync(runner, 'utf8');
  assert.match(source, /Test-Path -LiteralPath \$rawPath/);
  assert.match(source, /Output already exists/);
  assert.match(source, /-not \$Force/);
});

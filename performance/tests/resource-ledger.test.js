const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');

const { createLedger, mergeRun, compareCodeUnits, encodePathPart } = require('../fixtures/resource-ledger');

async function temporaryDirectory() {
  return fs.mkdtemp(path.join(os.tmpdir(), 'fletway-ledger-'));
}

test('writes each agent run to its own append-only JSONL file', async () => {
  const root = await temporaryDirectory();
  const ledger = createLedger({ directory: root, runId: '2026-09-03T153000', agent: 'solicitudes' });

  await ledger.append({
    resource_type: 'solicitud',
    id: 123,
    created_by_test: 'POST /api/solicitudes',
  });
  await ledger.append({
    resource_type: 'solicitud',
    id: 124,
    created_by_test: 'POST /api/solicitudes',
  });

  const file = path.join(root, encodePathPart('2026-09-03T153000', 'runId'), `${encodePathPart('solicitudes', 'agent')}.jsonl`);
  const records = (await fs.readFile(file, 'utf8')).trim().split('\n').map(JSON.parse);
  assert.deepEqual(records.map((record) => record.id), [123, 124]);
  assert.equal(records[0].run_id, '2026-09-03T153000');
  assert.equal(records[0].agent, 'solicitudes');
  assert.match(records[0].created_at, /^\d{4}-\d{2}-\d{2}T/);
});

test('merges all agent ledgers without changing source files', async () => {
  const root = await temporaryDirectory();
  const first = createLedger({ directory: root, runId: 'run-1', agent: 'solicitudes' });
  const second = createLedger({ directory: root, runId: 'run-1', agent: 'presupuestos' });
  await first.append({ resource_type: 'solicitud', id: 123, created_by_test: 'solicitudes test' });
  await second.append({ resource_type: 'presupuesto', id: 456, created_by_test: 'presupuestos test' });

  const mergedPath = await mergeRun({ directory: root, runId: 'run-1' });
  const records = (await fs.readFile(mergedPath, 'utf8')).trim().split('\n').map(JSON.parse);
  assert.deepEqual(records.map((record) => record.id), [456, 123]);
  assert.equal(await fs.readFile(path.join(root, encodePathPart('run-1', 'runId'), `${encodePathPart('solicitudes', 'agent')}.jsonl`), 'utf8').then((value) => value.split('\n').filter(Boolean).length), 1);
  assert.equal(await fs.readFile(path.join(root, encodePathPart('run-1', 'runId'), `${encodePathPart('presupuestos', 'agent')}.jsonl`), 'utf8').then((value) => value.split('\n').filter(Boolean).length), 1);
});

test('rejects records without a positive integer ID', async () => {
  const root = await temporaryDirectory();
  const ledger = createLedger({ directory: root, runId: 'run-1', agent: 'test' });
  await assert.rejects(() => ledger.append({ resource_type: 'solicitud', id: '123', created_by_test: 'test' }), /positive integer ID/);
  await assert.rejects(() => ledger.append({ resource_type: 'solicitud', id: 0, created_by_test: 'test' }), /positive integer ID/);
});

test('uses collision-free paths for distinct run and agent identifiers', async () => {
  const root = await temporaryDirectory();
  const slash = createLedger({ directory: root, runId: 'a/b', agent: 'x-y' });
  const dash = createLedger({ directory: root, runId: 'a-b', agent: 'x/y' });
  await slash.append({ resource_type: 'solicitud', id: 1, created_by_test: 'test' });
  await dash.append({ resource_type: 'solicitud', id: 2, created_by_test: 'test' });
  assert.notEqual(slash.filePath, dash.filePath);
});

test('orders ledger files with explicit code-unit comparison', async () => {
  assert.equal(compareCodeUnits('z', 'ä') < 0, true);
  assert.equal(compareCodeUnits('b', 'a') > 0, true);
});

test('ignores unregistered JSONL files and rejects inconsistent registered records', async () => {
  const root = await temporaryDirectory();
  const ledger = createLedger({ directory: root, runId: 'run-1', agent: 'solicitudes' });
  await ledger.append({ resource_type: 'solicitud', id: 123, created_by_test: 'test' });
  await fs.writeFile(path.join(root, encodePathPart('run-1', 'runId'), 'intruder.jsonl'), '{"run_id":"run-1","agent":"intruder","resource_type":"solicitud","id":999,"created_by_test":"bad","created_at":"2026-09-03T15:30:00Z"}\n');
  const mergedPath = await mergeRun({ directory: root, runId: 'run-1' });
  const merged = (await fs.readFile(mergedPath, 'utf8')).trim().split('\n').map(JSON.parse);
  assert.deepEqual(merged.map((record) => record.id), [123]);

  const inconsistent = createLedger({ directory: root, runId: 'run-2', agent: 'solicitudes' });
  await inconsistent.append({ resource_type: 'solicitud', id: 456, created_by_test: 'test' });
  const inconsistentPath = inconsistent.filePath;
  const tampered = JSON.parse((await fs.readFile(inconsistentPath, 'utf8')).trim());
  tampered.run_id = 'other-run';
  await fs.writeFile(inconsistentPath, `${JSON.stringify(tampered)}\n`);
  await assert.rejects(() => mergeRun({ directory: root, runId: 'run-2' }), /run_id consistency/);
});

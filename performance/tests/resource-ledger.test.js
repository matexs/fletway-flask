const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');

const { createLedger, mergeRun } = require('../fixtures/resource-ledger');

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

  const file = path.join(root, '2026-09-03T153000', 'solicitudes.jsonl');
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
  assert.equal(await fs.readFile(path.join(root, 'run-1', 'solicitudes.jsonl'), 'utf8').then((value) => value.split('\n').filter(Boolean).length), 1);
  assert.equal(await fs.readFile(path.join(root, 'run-1', 'presupuestos.jsonl'), 'utf8').then((value) => value.split('\n').filter(Boolean).length), 1);
});

test('rejects records without a positive integer ID', async () => {
  const root = await temporaryDirectory();
  const ledger = createLedger({ directory: root, runId: 'run-1', agent: 'test' });
  await assert.rejects(() => ledger.append({ resource_type: 'solicitud', id: '123', created_by_test: 'test' }), /positive integer ID/);
  await assert.rejects(() => ledger.append({ resource_type: 'solicitud', id: 0, created_by_test: 'test' }), /positive integer ID/);
});

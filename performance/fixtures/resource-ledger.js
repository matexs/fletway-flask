const fs = require('node:fs/promises');
const path = require('node:path');

function encodePathPart(value, label) {
  if (typeof value !== 'string' || !value.trim()) throw new TypeError(`${label} must be a non-empty string`);
  return Buffer.from(value, 'utf8').toString('hex');
}

function compareCodeUnits(left, right) {
  const length = Math.min(left.length, right.length);
  for (let index = 0; index < length; index += 1) {
    const difference = left.charCodeAt(index) - right.charCodeAt(index);
    if (difference) return difference;
  }
  return left.length - right.length;
}

function validateRecord(record, expected) {
  if (!record || !Number.isInteger(record.id) || record.id <= 0) {
    throw new TypeError('resource record requires a positive integer ID');
  }
  if (typeof record.resource_type !== 'string' || !record.resource_type.trim()) {
    throw new TypeError('resource record requires resource_type');
  }
  if (typeof record.created_by_test !== 'string' || !record.created_by_test.trim()) {
    throw new TypeError('resource record requires created_by_test');
  }
  if (record.created_at !== undefined && (typeof record.created_at !== 'string' || Number.isNaN(Date.parse(record.created_at)))) {
    throw new TypeError('resource record requires a valid created_at');
  }
  if (expected && (record.run_id !== expected.runId || record.agent !== expected.agent)) {
    throw new TypeError('resource record failed run_id consistency or agent consistency');
  }
}

function createLedger({ directory, runId, agent }) {
  const runPart = encodePathPart(runId, 'runId');
  const agentPart = encodePathPart(agent, 'agent');
  const runDirectory = path.join(directory, runPart);
  const filePath = path.join(runDirectory, `${agentPart}.jsonl`);
  const metadataPath = path.join(runDirectory, `${agentPart}.ledger.json`);

  return {
    filePath,
    async append(record) {
      validateRecord(record);
      await fs.mkdir(runDirectory, { recursive: true });
      const metadata = { format: 'fletway-resource-ledger-v1', run_id: runId, agent, ledger_file: path.basename(filePath) };
      try {
        await fs.writeFile(metadataPath, `${JSON.stringify(metadata)}\n`, { encoding: 'utf8', flag: 'wx' });
      } catch (error) {
        if (error.code !== 'EEXIST') throw error;
        const existing = JSON.parse(await fs.readFile(metadataPath, 'utf8'));
        if (JSON.stringify(existing) !== JSON.stringify(metadata)) throw new Error('ledger metadata does not match this run or agent');
      }
      const completeRecord = {
        run_id: runId,
        agent,
        resource_type: record.resource_type,
        id: record.id,
        created_by_test: record.created_by_test,
        created_at: record.created_at || new Date().toISOString(),
      };
      validateRecord(completeRecord, { runId, agent });
      // Concurrent append callers share one JSONL stream; their relative order is intentionally unspecified.
      await fs.appendFile(filePath, `${JSON.stringify(completeRecord)}\n`, { encoding: 'utf8' });
      return completeRecord;
    },
  };
}

async function mergeRun({ directory, runId }) {
  const runDirectory = path.join(directory, encodePathPart(runId, 'runId'));
  const entries = (await fs.readdir(runDirectory, { withFileTypes: true }))
    .filter((entry) => entry.isFile() && entry.name.endsWith('.jsonl') && entry.name !== 'merged.jsonl')
    .sort((a, b) => compareCodeUnits(a.name, b.name));
  const records = [];
  for (const entry of entries) {
    const metadataPath = path.join(runDirectory, entry.name.replace(/\.jsonl$/, '.ledger.json'));
    let metadata;
    try { metadata = JSON.parse(await fs.readFile(metadataPath, 'utf8')); } catch (error) {
      if (error.code === 'ENOENT') continue;
      throw error;
    }
    if (metadata.format !== 'fletway-resource-ledger-v1' || metadata.run_id !== runId || metadata.ledger_file !== entry.name || typeof metadata.agent !== 'string' || !metadata.agent) {
      throw new TypeError(`invalid ledger metadata for ${entry.name}`);
    }
    const lines = (await fs.readFile(path.join(runDirectory, entry.name), 'utf8')).split(/\r?\n/).filter(Boolean);
    for (const line of lines) {
      const record = JSON.parse(line);
      validateRecord(record, { runId, agent: metadata.agent });
      records.push(record);
    }
  }
  const outputPath = path.join(runDirectory, 'merged.jsonl');
  await fs.writeFile(outputPath, records.map((record) => JSON.stringify(record)).concat(records.length ? [''] : []).join('\n'), { encoding: 'utf8', flag: 'wx' });
  return outputPath;
}

module.exports = { createLedger, mergeRun, compareCodeUnits, encodePathPart };

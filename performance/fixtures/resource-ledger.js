const fs = require('node:fs/promises');
const path = require('node:path');

function safePathPart(value, label) {
  if (typeof value !== 'string' || !value.trim()) throw new TypeError(`${label} must be a non-empty string`);
  return value.replace(/[<>:"/\\|?*\x00-\x1f]/g, '-');
}

function validateRecord(record) {
  if (!record || !Number.isInteger(record.id) || record.id <= 0) {
    throw new TypeError('resource record requires a positive integer ID');
  }
  if (typeof record.resource_type !== 'string' || !record.resource_type.trim()) {
    throw new TypeError('resource record requires resource_type');
  }
  if (typeof record.created_by_test !== 'string' || !record.created_by_test.trim()) {
    throw new TypeError('resource record requires created_by_test');
  }
}

function createLedger({ directory, runId, agent }) {
  const runPart = safePathPart(runId, 'runId');
  const agentPart = safePathPart(agent, 'agent');
  const runDirectory = path.join(directory, runPart);
  const filePath = path.join(runDirectory, `${agentPart}.jsonl`);

  return {
    filePath,
    async append(record) {
      validateRecord(record);
      await fs.mkdir(runDirectory, { recursive: true });
      const completeRecord = {
        run_id: runId,
        agent,
        resource_type: record.resource_type,
        id: record.id,
        created_by_test: record.created_by_test,
        created_at: record.created_at || new Date().toISOString(),
      };
      await fs.appendFile(filePath, `${JSON.stringify(completeRecord)}\n`, { encoding: 'utf8' });
      return completeRecord;
    },
  };
}

async function mergeRun({ directory, runId }) {
  const runDirectory = path.join(directory, safePathPart(runId, 'runId'));
  const entries = (await fs.readdir(runDirectory, { withFileTypes: true }))
    .filter((entry) => entry.isFile() && entry.name.endsWith('.jsonl') && entry.name !== 'merged.jsonl')
    .sort((a, b) => a.name.localeCompare(b.name));
  const records = [];
  for (const entry of entries) {
    const lines = (await fs.readFile(path.join(runDirectory, entry.name), 'utf8')).split(/\r?\n/).filter(Boolean);
    for (const line of lines) records.push(JSON.parse(line));
  }
  const outputPath = path.join(runDirectory, 'merged.jsonl');
  await fs.writeFile(outputPath, records.map((record) => JSON.stringify(record)).concat(records.length ? [''] : []).join('\n'), { encoding: 'utf8', flag: 'wx' });
  return outputPath;
}

module.exports = { createLedger, mergeRun };

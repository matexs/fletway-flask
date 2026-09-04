import fs from 'node:fs';
import path from 'node:path';

export function parseLedgerMarkers(logPath) {
  const result = [];
  if (!fs.existsSync(logPath)) return result;
  for (const line of fs.readFileSync(logPath, 'utf8').split(/\r?\n/)) {
    if (!line.startsWith('FLETWAY_LEDGER ')) continue;
    try {
      const value = JSON.parse(line.slice('FLETWAY_LEDGER '.length));
      if (value.status >= 200 && value.status < 300 && value.response_ids?.solicitud_id) {
        result.push({
          run_id: String(value.run_id),
          created_at: String(value.created_at),
          endpoint_id: String(value.endpoint_id),
          method: String(value.method),
          path: String(value.path),
          status: Number(value.status),
          response_ids: { solicitud_id: Number(value.response_ids.solicitud_id) },
          resource_action: String(value.resource_action),
          created_by_test: Boolean(value.created_by_test),
        });
      }
    } catch (_) {
      // Ignore non-JSON console output and malformed markers.
    }
  }
  return result;
}

if (process.argv[2] === 'parse') {
  const entries = parseLedgerMarkers(process.argv[3]);
  const outputPath = process.argv[4];
  if (!outputPath) throw new Error('Usage: resource-ledger.js parse <log> <output.jsonl>');
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, entries.map((entry) => JSON.stringify(entry)).join('\n') + (entries.length ? '\n' : ''));
}

#!/usr/bin/env node
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { calculateScore } from '../config/scoring.js';

function usage() {
  throw new Error('Usage: calculate-score.js --matrix <matrix.csv> --manifest <manifest.json> [--thresholds <thresholds.json>] --output <score.json>');
}

function argumentsFrom(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    if (!flag.startsWith('--') || !argv[index + 1] || argv[index + 1].startsWith('--')) usage();
    options[flag.slice(2)] = argv[index + 1];
    index += 1;
  }
  if (!options.matrix || !options.manifest || !options.output) usage();
  return options;
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = '';
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (quoted) {
      if (character === '"' && text[index + 1] === '"') { field += '"'; index += 1; }
      else if (character === '"') quoted = false;
      else field += character;
    } else if (character === '"' && field === '') quoted = true;
    else if (character === ',') { row.push(field); field = ''; }
    else if (character === '\n') { row.push(field.replace(/\r$/, '')); rows.push(row); row = []; field = ''; }
    else field += character;
  }
  if (quoted) throw new Error('matrix CSV contains an unterminated quoted field.');
  if (field !== '' || row.length > 0) { row.push(field); rows.push(row); }
  if (rows.length < 2) throw new Error('matrix CSV must contain a header and at least one row.');
  const header = rows.shift();
  return rows.filter((values) => values.some((value) => value !== '')).map((values) => {
    if (values.length !== header.length) throw new Error('matrix CSV row has the wrong number of columns.');
    return Object.fromEntries(header.map((name, index) => [name, values[index]]));
  });
}

function readJson(path) {
  return JSON.parse(readFileSync(resolve(path), 'utf8'));
}

function main() {
  const options = argumentsFrom(process.argv.slice(2));
  const thresholdsPath = options.thresholds ?? fileURLToPath(new URL('../config/thresholds.json', import.meta.url));
  const result = calculateScore({
    matrix: parseCsv(readFileSync(resolve(options.matrix), 'utf8')),
    manifest: readJson(options.manifest),
    thresholds: readJson(thresholdsPath),
  });
  const output = resolve(options.output);
  mkdirSync(dirname(output), { recursive: true });
  writeFileSync(output, `${JSON.stringify(result, null, 2)}\n`, 'utf8');
  process.stdout.write(`Calculated score: ${output}\n`);
}

try { main(); }
catch (error) { process.stderr.write(`${error.message}\n`); process.exitCode = 1; }

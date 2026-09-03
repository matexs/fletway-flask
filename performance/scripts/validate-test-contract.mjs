import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const forbidden = [
  { pattern: /\bstages\s*:\s*\[/i, message: 'hardcoded stages' },
  { pattern: /\bthresholds\s*:\s*\{/i, message: 'hardcoded thresholds' },
  { pattern: /(?:password|secret|api[_-]?key|token|credential)\s*=\s*['"`][^'"`]+['"`]/i, message: 'literal secret or credential' },
  { pattern: /['"]eyJ[a-zA-Z0-9_.-]{12,}['"]/i, message: 'literal JWT' },
  { pattern: /\/api\/[^'"`\n]*\/\d+(?:\/|['"`])/i, message: 'hardcoded path ID' },
];

export function validateTestContract(filePath) {
  const source = fs.readFileSync(filePath, 'utf8');
  const violations = forbidden.filter(({ pattern }) => pattern.test(source)).map(({ message }) => message);
  if (!/endpoint\.template\.js/.test(source)) violations.push('missing shared endpoint template import');
  if (!/adapterFor/.test(source)) violations.push('missing endpoint adapter');
  if (violations.length) throw new Error(`${path.basename(filePath)} violates endpoint contract: ${violations.join(', ')}`);
  return { valid: true, filePath, violations: [] };
}

function main() { const files = process.argv.slice(2); if (!files.length) throw new Error('Usage: node validate-test-contract.mjs <endpoint-script> [...]'); for (const file of files) console.log(JSON.stringify(validateTestContract(file))); }
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();

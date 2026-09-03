import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const forbidden = [
  { pattern: /\bstages\s*:\s*\[/i, message: 'hardcoded stages' },
  { pattern: /\bthresholds\s*:\s*\{/i, message: 'hardcoded thresholds' },
  { pattern: /(?:password|secret|api[_-]?key|token|credential)\s*=\s*['"`][^'"`]+['"`]/i, message: 'literal secret or credential' },
  { pattern: /(?:password|secret|api[_-]?key|token|credential|authorization)\s*:\s*['"`][^'"`]+['"`]/i, message: 'secret object property' },
  { pattern: /Bearer\s+[A-Za-z0-9._~-]{8,}/i, message: 'literal bearer credential' },
  { pattern: /['"]eyJ[a-zA-Z0-9_.-]{12,}['"]/i, message: 'literal JWT' },
  { pattern: /[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/i, message: 'hardcoded UUID' },
  { pattern: /\/[^'"`\n]*\/\d+(?:\/|['"`])/i, message: 'hardcoded path ID' },
  { pattern: /[?&][A-Za-z0-9_-]+=%?\d+/i, message: 'hardcoded query ID' },
];

function withoutComments(source) {
  return source.replace(/\/\/[^\n]*|\/\*[\s\S]*?\*\//g, '');
}

export function validateTestContract(filePath) {
  const source = fs.readFileSync(filePath, 'utf8');
  const executable = withoutComments(source);
  const violations = forbidden.filter(({ pattern }) => pattern.test(source)).map(({ message }) => message);
  if (!/import\s+\{[^}]*\b(?:setupAuth|requestOptions)\b[^}]*\}\s+from\s+['"][^'"]*endpoint\.template\.js['"]/.test(executable)) violations.push('missing executable shared template import');
  if (!/import\s+\{[^}]*\badapterFor\b[^}]*\}\s+from\s+['"][^'"]*endpoint-adapters\.js['"]/.test(executable) || !/\badapterFor\s*\(/.test(executable)) violations.push('missing executable endpoint adapter usage');
  if (violations.length) throw new Error(`${path.basename(filePath)} violates endpoint contract: ${violations.join(', ')}`);
  return { valid: true, filePath, violations: [] };
}

function main() { const files = process.argv.slice(2); if (!files.length) throw new Error('Usage: node validate-test-contract.mjs <endpoint-script> [...]'); for (const file of files) console.log(JSON.stringify(validateTestContract(file))); }
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();

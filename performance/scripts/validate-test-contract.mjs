import fs from 'node:fs';

export function validateTestContract(filePath) {
  const text = fs.readFileSync(filePath, 'utf8');
  const errors = [];
  if (!/http\.request\(adapter\.method/.test(text)) errors.push('missing adapter request');
  if (!/requestTags\(/.test(text)) errors.push('missing request tags');
  if (!/export default function/.test(text)) errors.push('missing default function');
  if (/(password|jwt|Bearer\s+[A-Za-z0-9._-]{20,})\s*[:=]/i.test(text)) errors.push('possible secret');
  return { valid: errors.length === 0, filePath, violations: errors };
}

if (process.argv[2]) process.exit(validateTestContract(process.argv[2]).valid ? 0 : 1);

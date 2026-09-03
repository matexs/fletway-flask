const K6_TIMEOUT_CODES = new Set([1050, 1051, 1052]);

function timeoutMilliseconds(value) {
  const match = String(value || '').trim().match(/^(\d+(?:\.\d+)?)(ms|s|m)$/i);
  if (!match) return 0;
  return Number(match[1]) * ({ ms: 1, s: 1000, m: 60000 }[match[2].toLowerCase()]);
}

export function isTimeout(response, configuredTimeout = '10s') {
  const code = Number(response?.error_code ?? response?.errorCode ?? 0);
  if (K6_TIMEOUT_CODES.has(code)) return true;
  if (/timeout|timed out|deadline exceeded/i.test(String(response?.error || ''))) return true;
  const duration = Number(response?.timings?.duration || 0);
  const limit = timeoutMilliseconds(configuredTimeout);
  return limit > 0 && duration >= limit;
}

import http from 'k6/http';

export function normalizeUrl(value) {
  return String(value || '').trim().replace(/[\\/,]+$/, '');
}

export function requiredEnvironment(requiredRole = null) {
  const common = ['BASE_URL', 'SUPABASE_URL', 'SUPABASE_ANON_KEY'];
  if (requiredRole === 'public') return ['BASE_URL'];
  if (requiredRole === 'client') return [...common, 'CLIENT_EMAIL', 'CLIENT_PASSWORD'];
  if (requiredRole === 'driver') return [...common, 'DRIVER_EMAIL', 'DRIVER_PASSWORD'];
  return [...common, 'CLIENT_EMAIL', 'CLIENT_PASSWORD', 'DRIVER_EMAIL', 'DRIVER_PASSWORD'];
}

export function requireEnvironment(env = __ENV, requiredRole = null) {
  const missing = requiredEnvironment(requiredRole).filter((name) => !env[name]);
  if (missing.length) throw new Error(`Faltan variables requeridas: ${missing.join(', ')}`);
}

export function authHeaders(token) {
  return { Authorization: `Bearer ${token}`, Accept: 'application/json' };
}

export function login(role, email, password, { supabaseUrl, anonKey, timeout }) {
  const response = http.post(`${normalizeUrl(supabaseUrl)}/auth/v1/token?grant_type=password`, JSON.stringify({ email, password }), {
    headers: { apikey: anonKey, Authorization: `Bearer ${anonKey}`, 'Content-Type': 'application/json' },
    responseType: 'text',
    tags: { endpoint_id: 'supabase_login', profile: 'setup', stage: 'auth', role },
    timeout,
  });
  if (response.status !== 200) throw new Error(`No se pudo autenticar el rol ${role}. HTTP ${response.status}.`);
  const token = response.json('access_token');
  if (!token) throw new Error(`Supabase no devolvió access_token para ${role}.`);
  return token;
}

export function requestTags({ endpointId, profile, stage, role }) {
  return { endpoint_id: endpointId, profile, stage, role };
}

export function setupAuth(requiredRole = null) {
  requireEnvironment(__ENV, requiredRole);
  const options = { supabaseUrl: __ENV.SUPABASE_URL, anonKey: __ENV.SUPABASE_ANON_KEY, timeout: __ENV.SETUP_REQUEST_TIMEOUT || '60s' };
  return {
    clientToken: requiredRole === 'driver' || requiredRole === 'public' ? null : login('client', __ENV.CLIENT_EMAIL, __ENV.CLIENT_PASSWORD, options),
    driverToken: requiredRole === 'client' || requiredRole === 'public' ? null : login('driver', __ENV.DRIVER_EMAIL, __ENV.DRIVER_PASSWORD, options),
  };
}

export function tokenForRole(role, auth) {
  return role === 'client' ? auth.clientToken : role === 'driver' ? auth.driverToken : null;
}

export function captureResponseIds(response) {
  const ids = {};
  if (!response || !response.body) return ids;
  let payload;
  try { payload = response.json(); } catch (_) { return ids; }
  const visit = (value) => {
    if (!value || typeof value !== 'object') return;
    for (const [key, item] of Object.entries(value)) {
      if (item !== null && typeof item === 'object') visit(item);
      else if (/(^|_)(id|ids)$/i.test(key) && item !== undefined && item !== null) ids[key] = item;
    }
  };
  visit(payload);
  return ids;
}

export function emitLedgerEvent(event, sink = console.log) {
  const ledgerEvent = { ledger_event_version: 1, event_type: 'performance_response', ...event };
  sink(JSON.stringify(ledgerEvent));
  return ledgerEvent;
}

export function requestOptions(token, tags, body, { multipart = false } = {}) {
  return {
    headers: token ? { ...authHeaders(token), ...(multipart ? {} : { 'Content-Type': 'application/json' }) } : { Accept: 'application/json', ...(multipart ? {} : { 'Content-Type': 'application/json' }) },
    tags, timeout: __ENV.REQUEST_TIMEOUT || '10s', ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  };
}

export { isTimeout } from '../k6/lib/timeout.js';

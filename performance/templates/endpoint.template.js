import http from 'k6/http';

export function normalizeUrl(value) {
  return String(value || '').trim().replace(/[\\/,]+$/, '');
}

export function requiredEnvironment() {
  return ['BASE_URL', 'SUPABASE_URL', 'SUPABASE_ANON_KEY', 'CLIENT_EMAIL', 'CLIENT_PASSWORD', 'DRIVER_EMAIL', 'DRIVER_PASSWORD'];
}

export function requireEnvironment(env = __ENV) {
  const missing = requiredEnvironment().filter((name) => !env[name]);
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

export function setupAuth() {
  requireEnvironment();
  const options = { supabaseUrl: __ENV.SUPABASE_URL, anonKey: __ENV.SUPABASE_ANON_KEY, timeout: __ENV.SETUP_REQUEST_TIMEOUT || '60s' };
  return { clientToken: login('client', __ENV.CLIENT_EMAIL, __ENV.CLIENT_PASSWORD, options), driverToken: login('driver', __ENV.DRIVER_EMAIL, __ENV.DRIVER_PASSWORD, options) };
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

export function requestOptions(token, tags, body) {
  return {
    headers: token ? { ...authHeaders(token), 'Content-Type': 'application/json' } : { Accept: 'application/json', 'Content-Type': 'application/json' },
    tags, timeout: __ENV.REQUEST_TIMEOUT || '10s', ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  };
}

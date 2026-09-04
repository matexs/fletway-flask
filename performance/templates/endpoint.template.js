import http from 'k6/http';
import { sleep } from 'k6';

const BASE_URL = String(__ENV.BASE_URL || '').replace(/[\\/,]+$/, '');
const SETUP_TIMEOUT = __ENV.SETUP_REQUEST_TIMEOUT || '60s';
const REQUEST_TIMEOUT = __ENV.REQUEST_TIMEOUT || '10s';

function authHeaders(token) {
  return { Authorization: `Bearer ${token}`, Accept: 'application/json', 'Content-Type': 'application/json' };
}

function login(role, email, password) {
  const response = http.post(`${String(__ENV.SUPABASE_URL || '').replace(/[\\/,]+$/, '')}/auth/v1/token?grant_type=password`, JSON.stringify({ email, password }), {
    headers: { apikey: __ENV.SUPABASE_ANON_KEY, Authorization: `Bearer ${__ENV.SUPABASE_ANON_KEY}`, 'Content-Type': 'application/json' },
    timeout: SETUP_TIMEOUT,
    tags: { kind: 'setup-auth', role },
  });
  if (response.status !== 200) throw new Error(`No se pudo autenticar ${role}: HTTP ${response.status}`);
  const token = response.json('access_token');
  if (!token) throw new Error(`Supabase no devolvió token para ${role}`);
  return token;
}

export function setupAuth(role) {
  const clientToken = login('client', __ENV.CLIENT_EMAIL, __ENV.CLIENT_PASSWORD);
  const driverToken = role === 'driver' ? login('driver', __ENV.DRIVER_EMAIL, __ENV.DRIVER_PASSWORD) : null;
  return { clientToken, driverToken };
}

export function tokenForRole(role, auth) {
  return role === 'driver' ? auth.driverToken : auth.clientToken;
}

export function requestOptions(token, tags) {
  return { headers: authHeaders(token), timeout: REQUEST_TIMEOUT, tags };
}

export function setupRequestOptions(token, tags) {
  return { headers: authHeaders(token), timeout: SETUP_TIMEOUT, tags };
}

export function requestTags({ endpointId, profile, stage, role }) {
  return { kind: 'api', endpoint_id: endpointId, profile, stage, role };
}

export function isTimeout(response) {
  return String(response.error || '').toLowerCase().includes('timeout');
}

export function captureResponseIds(response) {
  try {
    const body = response.json();
    const result = {};
    if (body && body.solicitud_id) result.solicitud_id = Number(body.solicitud_id);
    if (body && body.presupuesto_id) result.presupuesto_id = Number(body.presupuesto_id);
    return result;
  } catch (_) {
    return {};
  }
}

export function emitLedgerEvent(event) {
  if (event.status >= 200 && event.status < 300 && Object.keys(event.response_ids || {}).length > 0) {
    console.log(`FLETWAY_LEDGER ${JSON.stringify({ run_id: __ENV.RUN_ID || 'run', created_at: new Date().toISOString(), ...event })}`);
  }
}

function localityIds(token) {
  const configuredOrigin = Number(__ENV.LOCALIDAD_ORIGEN_ID);
  const configuredDestination = Number(__ENV.LOCALIDAD_DESTINO_ID);
  if (configuredOrigin > 0 && configuredDestination > 0) return { origin: configuredOrigin, destination: configuredDestination };
  const response = http.get(`${BASE_URL}/api/localidades`, setupRequestOptions(token, { kind: 'fixture-localities', role: 'client' }));
  if (response.status !== 200) throw new Error(`No se pudieron obtener localidades: HTTP ${response.status}`);
  const values = response.json();
  const rows = Array.isArray(values) ? values : (values.localidades || values.data || []);
  if (rows.length < 2) throw new Error('Se necesitan al menos dos localidades para crear fixtures');
  return { origin: Number(rows[0].localidad_id), destination: Number(rows[1].localidad_id) };
}

export function createSolicitation(auth, context, endpointId = 'fixture') {
  const ids = localityIds(auth.clientToken);
  const suffix = `${context.runId || __ENV.RUN_ID || 'run'}-${context.seed || 'fixture'}`;
  const body = {
    direccion_origen: `Fixture origen ${suffix}`,
    direccion_destino: `Fixture destino ${suffix}`,
    localidad_origen_id: ids.origin,
    localidad_destino_id: ids.destination,
    detalles_carga: `Fixture k6 ${suffix}`,
    medidas: '1x1x1',
    peso: 10,
    hora_recogida: new Date(Date.now() + 86400000).toISOString(),
  };
  const response = http.post(`${BASE_URL}/api/solicitudes`, JSON.stringify(body), setupRequestOptions(auth.clientToken, { kind: 'fixture', endpoint_id: endpointId, role: 'client' }));
  if (response.status !== 201) throw new Error(`No se pudo crear fixture de solicitud: HTTP ${response.status}`);
  const solicitudId = Number(response.json('solicitud_id'));
  if (!solicitudId) throw new Error('Fixture POST no devolvió solicitud_id');
  emitLedgerEvent({ endpoint_id: endpointId, method: 'POST', path: '/api/solicitudes', status: response.status, response_ids: { solicitud_id: solicitudId }, resource_action: 'create', created_by_test: true });
  return { solicitudId, localidadOrigenId: ids.origin, localidadDestinoId: ids.destination };
}

function discoverSolicitations(token, editableOnly) {
  const response = http.get(`${BASE_URL}/api/solicitudes/mis-pedidos`, setupRequestOptions(token, { kind: 'fixture-discovery', role: 'client' }));
  if (response.status !== 200) return [];
  try {
    const rows = response.json();
    const values = Array.isArray(rows) ? rows : (rows.solicitudes || rows.data || []);
    return values
      .filter((row) => row && row.solicitud_id && (!editableOnly || row.estado === 'sin transportista'))
      .map((row) => ({ solicitudId: Number(row.solicitud_id), localidadOrigenId: Number(row.localidad_origen_id), localidadDestinoId: Number(row.localidad_destino_id) }));
  } catch (_) {
    return [];
  }
}

export function setupEndpoint(endpoint) {
  if (!__ENV.SUPABASE_URL || !__ENV.SUPABASE_ANON_KEY || !__ENV.CLIENT_EMAIL || !__ENV.CLIENT_PASSWORD) throw new Error('Faltan credenciales de cliente');
  if (endpoint.role === 'driver' && (!__ENV.DRIVER_EMAIL || !__ENV.DRIVER_PASSWORD)) throw new Error('Faltan credenciales de driver');
  const auth = setupAuth(endpoint.role);
  const requiresSolicitation = ['presupuestos-solicitud', 'detalle-solicitud', 'actualizar-solicitud'].includes(endpoint.id);
  const requiredPoolSize = !requiresSolicitation ? 0 : (endpoint.id === 'actualizar-solicitud' ? Math.max(30, Number(__ENV.MAX_SETUP_VUS || 30)) : 1);
  const pool = requiresSolicitation ? discoverSolicitations(auth.clientToken, endpoint.id === 'actualizar-solicitud') : [];
  if (__ENV.SOLICITUD_ID) pool.unshift({ solicitudId: Number(__ENV.SOLICITUD_ID) });
  for (let index = pool.length; index < requiredPoolSize; index += 1) {
    pool.push(createSolicitation(auth, { runId: __ENV.RUN_ID, seed: `${endpoint.id}-${index}` }, endpoint.id));
  }
  return { auth, pool };
}

export function solicitationFor(pool) {
  if (!pool || pool.length === 0) return null;
  const index = Math.max(0, (Number(__VU) || 1) - 1) % pool.length;
  return pool[index];
}

export function pause() {
  const seconds = Number(__ENV.THINK_TIME_SECONDS || 0.2);
  if (seconds > 0) sleep(seconds);
}

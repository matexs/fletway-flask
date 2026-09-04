const BASE_URL = String(__ENV.BASE_URL || '').replace(/[\\/,]+$/, '');

function numberEnv(name) {
  const value = Number(__ENV[name]);
  return Number.isInteger(value) && value > 0 ? value : null;
}

export function solicitationBody(context = {}) {
  const suffix = `${context.runId || __ENV.RUN_ID || 'run'}-${context.vu || 0}-${context.iteration || 0}`;
  return {
    direccion_origen: `Performance origen ${suffix}`,
    direccion_destino: `Performance destino ${suffix}`,
    localidad_origen_id: context.localidadOrigenId || numberEnv('LOCALIDAD_ORIGEN_ID'),
    localidad_destino_id: context.localidadDestinoId || numberEnv('LOCALIDAD_DESTINO_ID'),
    detalles_carga: `Carga de prueba k6 ${suffix}`,
    medidas: '1x1x1',
    peso: 10,
    hora_recogida: new Date(Date.now() + 86400000).toISOString(),
  };
}

const adapters = {
  'presupuestos-completo-batch': { method: 'GET', path: () => '/api/presupuestos/completo-batch', expectedStatus: 200 },
  'mis-presupuestos': { method: 'GET', path: () => '/api/presupuestos/mis-presupuestos', expectedStatus: 200 },
  'presupuestos-solicitud': { method: 'GET', path: (ctx) => `/api/presupuestos/solicitud/${ctx.solicitudId}`, expectedStatus: 200 },
  'detalle-solicitud': { method: 'GET', path: (ctx) => `/api/solicitudes/${ctx.solicitudId}`, expectedStatus: 200 },
  'mis-pedidos': { method: 'GET', path: () => '/api/solicitudes/mis-pedidos', expectedStatus: 200 },
  'dashboard-transportista': { method: 'GET', path: () => '/api/transportista/dashboard', expectedStatus: 200 },
  'historial-transportista': { method: 'GET', path: () => '/api/transportista/historial', expectedStatus: 200 },
  'mis-pedidos-optimizado': { method: 'GET', path: () => '/solicitudes/mis-pedidos-optimizado', expectedStatus: 200 },
  'actualizar-solicitud': { method: 'PATCH', path: (ctx) => `/api/solicitudes/${ctx.solicitudId}`, expectedStatus: 200, body: (ctx) => ({ detalles_carga: `Actualización k6 ${ctx.runId}-${ctx.vu}-${ctx.iteration}` }) },
  'crear-solicitud': { method: 'POST', path: () => '/api/solicitudes', expectedStatus: 201, body: solicitationBody },
};

export function adapterFor(endpoint) {
  const adapter = adapters[endpoint.id];
  if (!adapter) throw new Error(`No adapter registered for ${endpoint.id}`);
  return adapter;
}

export function resolvePath(pathOrFactory, context = {}) {
  return typeof pathOrFactory === 'function' ? pathOrFactory(context) : pathOrFactory;
}

export function buildRequestBody(adapter, context) {
  return adapter.body ? adapter.body(context) : undefined;
}

export function getBaseUrl() {
  return BASE_URL;
}

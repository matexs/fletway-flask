const PLACEHOLDER_ENV = { id: 'REQUEST_ID', solicitud_id: 'SOLICITUD_ID', presupuesto_id: 'PRESUPUESTO_ID', transportista_id: 'TRANSPORTISTA_ID', filename: 'FILENAME' };

function required(name) {
  const value = __ENV[name];
  if (value === undefined || value === '') throw new Error(`Missing ${name} for endpoint adapter.`);
  return value;
}

function bodyFromEnv(fields) {
  return () => Object.fromEntries(Object.entries(fields).map(([field, source]) => [field, typeof source === 'function' ? source() : required(source)]));
}

// Adapters own transport/body behavior only. Method and path always come from the manifest.
const endpointAdapters = {
  'crear-solicitud': { body: bodyFromEnv({ direccion_origen: 'ORIGIN_ADDRESS', direccion_destino: 'DESTINATION_ADDRESS', detalles_carga: 'CARGO_DETAILS', peso: 'WEIGHT', hora_recogida: 'PICKUP_TIME' }) },
  'actualizar-solicitud': { body: bodyFromEnv({ detalles_carga: 'CARGO_DETAILS', peso: 'WEIGHT' }) },
  'aceptar-presupuesto-solicitud': { body: bodyFromEnv({ presupuesto_id: 'PRESUPUESTO_ID' }) },
  'crear-presupuesto': { body: bodyFromEnv({ solicitud_id: 'SOLICITUD_ID', precio_estimado: 'ESTIMATED_PRICE', comentario: 'QUOTE_COMMENT' }) },
  'actualizar-presupuesto': { body: bodyFromEnv({ precio_estimado: 'ESTIMATED_PRICE', comentario: 'QUOTE_COMMENT' }) },
  'resumenes-presupuestos-batch': { body: bodyFromEnv({ solicitud_ids: () => JSON.parse(required('SOLICITUD_IDS_JSON')) }) },
  'crear-calificacion': { body: bodyFromEnv({ solicitud_id: 'SOLICITUD_ID', puntuacion: 'RATING_SCORE', comentario: 'RATING_COMMENT' }) },
  'enviar-reporte': { body: bodyFromEnv({ usuario_id: 'REPORT_USER_ID', solicitud_id: 'SOLICITUD_ID', motivo: 'REPORT_REASON', mensaje: 'REPORT_MESSAGE' }) },
  'subir-foto-solicitud': { body: () => undefined, transport: { type: 'multipart', field: 'foto', fixtureEnv: 'PHOTO_FIXTURE_PATH', filenameEnv: 'PHOTO_FILENAME', contentTypeEnv: 'PHOTO_CONTENT_TYPE' } },
};

export function resolvePath(path) {
  return String(path).replace(/<([^>]+)>/g, (_, placeholder) => encodeURIComponent(required(PLACEHOLDER_ENV[placeholder] || placeholder.toUpperCase())));
}

export function adapterFor(endpoint) {
  if (!endpoint || !endpoint.id || !endpoint.method || !endpoint.path) throw new Error('Manifest endpoint with id, method, and path is required.');
  return { method: endpoint.method, path: endpoint.path, ...(endpointAdapters[endpoint.id] || {}) };
}

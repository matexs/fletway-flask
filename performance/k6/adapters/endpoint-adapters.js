const PLACEHOLDER_ENV = { id: 'REQUEST_ID', solicitud_id: 'SOLICITUD_ID', presupuesto_id: 'PRESUPUESTO_ID', transportista_id: 'TRANSPORTISTA_ID', filename: 'FILENAME' };

function required(name) {
  const value = __ENV[name];
  if (value === undefined || value === '') throw new Error(`Missing ${name} for endpoint adapter.`);
  return value;
}

function bodyFromEnv(fields) {
  return () => Object.fromEntries(Object.entries(fields).map(([field, source]) => [field, typeof source === 'function' ? source() : required(source)]));
}

const endpointDefinitions = {
  'crear-solicitud': { method: 'POST', path: '/api/solicitudes', body: bodyFromEnv({ direccion_origen: 'ORIGIN_ADDRESS', direccion_destino: 'DESTINATION_ADDRESS', detalles_carga: 'CARGO_DETAILS', peso: 'WEIGHT', hora_recogida: 'PICKUP_TIME' }) },
  'actualizar-solicitud': { method: 'PATCH', path: '/api/solicitudes/<id>', body: bodyFromEnv({ detalles_carga: 'CARGO_DETAILS', peso: 'WEIGHT' }) },
  'aceptar-presupuesto-solicitud': { method: 'POST', path: '/api/solicitudes/<id>/aceptar-presupuesto', body: bodyFromEnv({ presupuesto_id: 'PRESUPUESTO_ID' }) },
  'crear-presupuesto': { method: 'POST', path: '/api/presupuestos', body: bodyFromEnv({ solicitud_id: 'SOLICITUD_ID', precio_estimado: 'ESTIMATED_PRICE', comentario: 'QUOTE_COMMENT' }) },
  'actualizar-presupuesto': { method: 'PUT', path: '/api/presupuestos/<presupuesto_id>', body: bodyFromEnv({ precio_estimado: 'ESTIMATED_PRICE', comentario: 'QUOTE_COMMENT' }) },
  'resumenes-presupuestos-batch': { method: 'POST', path: '/api/presupuestos/resumenes-batch', body: bodyFromEnv({ solicitud_ids: () => JSON.parse(required('SOLICITUD_IDS_JSON')) }) },
  'crear-calificacion': { method: 'POST', path: '/api/calificaciones', body: bodyFromEnv({ solicitud_id: 'SOLICITUD_ID', puntuacion: 'RATING_SCORE', comentario: 'RATING_COMMENT' }) },
};

const readOnlyDefinitions = {
  health: ['GET', '/'], localidades: ['GET', '/api/localidades'], 'buscar-localidades': ['GET', '/api/localidades/buscar'], 'mis-pedidos': ['GET', '/api/solicitudes/mis-pedidos'],
  'mis-pedidos-optimizado': ['GET', '/solicitudes/mis-pedidos-optimizado'], 'dashboard-transportista': ['GET', '/api/transportista/dashboard'], 'historial-transportista': ['GET', '/api/transportista/historial'],
  'mis-presupuestos': ['GET', '/api/presupuestos/mis-presupuestos'], 'presupuestos-completo-batch': ['GET', '/api/presupuestos/completo-batch'], 'detalle-solicitud': ['GET', '/api/solicitudes/<id>'],
  'mis-pedidos-optimizado-v': ['GET', '/solicitudes/mis-pedidos-optimizadov'], 'archivo-upload': ['GET', '/uploads/<filename>'], 'fotos-solicitud': ['GET', '/api/solicitudes/<id>/fotos'],
  'mis-viajes-fletero': ['GET', '/mis-viajes-fletero'], 'mis-pedidos-cliente': ['GET', '/mis-pedidos-cliente'], 'presupuestos-solicitud': ['GET', '/api/presupuestos/solicitud/<solicitud_id>'],
  'resumen-presupuesto': ['GET', '/api/presupuestos/resumen/<solicitud_id>'], 'detalle-transportista': ['GET', '/api/transportistas/<transportista_id>'],
  'estadisticas-transportista': ['GET', '/api/calificaciones/transportista/<transportista_id>/estadisticas'], 'calificaciones-transportista': ['GET', '/api/calificaciones/transportista/<transportista_id>'],
  'calificacion-solicitud': ['GET', '/api/calificaciones/solicitud/<solicitud_id>'], 'puede-calificar-solicitud': ['GET', '/api/calificaciones/puede-calificar/<solicitud_id>'],
  'puede-calificar-solicitud-duplicado': ['GET', '/api/calificaciones/puede-calificar/<solicitud_id>'],
};

for (const [id, [method, path]] of Object.entries(readOnlyDefinitions)) endpointDefinitions[id] ||= { method, path };
for (const id of ['cancelar-solicitud', 'cancelar-solicitud-fletero', 'comenzar-viaje', 'completar-solicitud', 'aceptar-presupuesto', 'rechazar-presupuesto', 'eliminar-presupuesto', 'enviar-reporte', 'subir-foto-solicitud']) {
  endpointDefinitions[id] ||= { method: id === 'eliminar-presupuesto' ? 'DELETE' : id === 'subir-foto-solicitud' || id === 'enviar-reporte' || id === 'aceptar-presupuesto' || id === 'rechazar-presupuesto' || id === 'comenzar-viaje' || id === 'completar-solicitud' ? 'POST' : 'PATCH', path: '/api/solicitudes/<id>' };
}
endpointDefinitions['cancelar-solicitud'].path = '/api/solicitudes/<id>/cancelar';
endpointDefinitions['cancelar-solicitud-fletero'].path = '/api/solicitudes/<id>/cancelar-fletero';
endpointDefinitions['comenzar-viaje'].path = '/api/solicitudes/<id>/comenzar-viaje';
endpointDefinitions['completar-solicitud'].path = '/api/solicitudes/<id>/completar';
endpointDefinitions['aceptar-presupuesto'].path = '/api/presupuestos/<presupuesto_id>/aceptar';
endpointDefinitions['rechazar-presupuesto'].path = '/api/presupuestos/<presupuesto_id>/rechazar';
endpointDefinitions['eliminar-presupuesto'].path = '/api/presupuestos/<presupuesto_id>';
endpointDefinitions['enviar-reporte'].path = '/enviar-reporte';
endpointDefinitions['subir-foto-solicitud'].path = '/api/solicitudes/<id>/foto';

export function resolvePath(path) {
  return String(path).replace(/<([^>]+)>/g, (_, placeholder) => encodeURIComponent(required(PLACEHOLDER_ENV[placeholder] || placeholder.toUpperCase())));
}

export function adapterFor(endpoint) {
  if (!endpoint || !endpoint.id) throw new Error('Endpoint manifest entry is required.');
  const definition = endpointDefinitions[endpoint.id];
  if (!definition) throw new Error(`No adapter registered for endpoint: ${endpoint.id}`);
  return { ...definition };
}

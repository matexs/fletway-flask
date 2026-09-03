import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
globalThis.open = (name) => fs.readFileSync(path.resolve('performance/k6/adapters', name), 'utf8');
const { adapterFor } = await import('../k6/adapters/endpoint-adapters.js');

globalThis.__ENV = {
  REQUEST_BODY_JSON: '{"should_not":"be_used"}',
  ORIGIN_ADDRESS: 'Origin from env', DESTINATION_ADDRESS: 'Destination from env',
  CARGO_DETAILS: 'Boxes from env', WEIGHT: '12', PICKUP_TIME: '2026-09-03T12:00:00Z',
  SOLICITUD_ID: 'request-from-env', ESTIMATED_PRICE: '99.50', QUOTE_COMMENT: 'Careful',
  REPORT_USER_ID: 'user-from-env', REPORT_REASON: 'reason-from-env', REPORT_MESSAGE: 'message-from-env',
  PHOTO_FIXTURE_PATH: 'fixture-from-env.jpg', PHOTO_FILENAME: 'photo-from-env.jpg', PHOTO_CONTENT_TYPE: 'image/jpeg',
};

test('maps create request body from endpoint-specific environment fields', () => {
  const body = adapterFor({ id: 'crear-solicitud', method: 'POST', path: '/api/solicitudes' }).body();
  assert.deepEqual(body, { direccion_origen: 'Origin from env', direccion_destino: 'Destination from env', detalles_carga: 'Boxes from env', peso: '12', hora_recogida: '2026-09-03T12:00:00Z' });
});

test('maps create quote body independently and never falls back to generic JSON', () => {
  const body = adapterFor({ id: 'crear-presupuesto', method: 'POST', path: '/api/presupuestos' }).body();
  assert.deepEqual(body, { solicitud_id: 'request-from-env', precio_estimado: '99.50', comentario: 'Careful' });
});

test('maps enviar-reporte to its required JSON fields from environment', () => {
  const body = adapterFor({ id: 'enviar-reporte', method: 'POST', path: '/enviar-reporte' }).body();
  assert.deepEqual(body, { usuario_id: 'user-from-env', solicitud_id: 'request-from-env', motivo: 'reason-from-env', mensaje: 'message-from-env' });
});

test('provides a non-empty multipart fixture contract for subir-foto-solicitud', () => {
  const adapter = adapterFor({ id: 'subir-foto-solicitud', method: 'POST', path: '/api/solicitudes/<id>/foto' });
  assert.deepEqual(adapter.transport, { type: 'multipart', field: 'foto', fixtureEnv: 'PHOTO_FIXTURE_PATH', filenameEnv: 'PHOTO_FILENAME', contentTypeEnv: 'PHOTO_CONTENT_TYPE' });
  assert.equal(adapter.body(), undefined);
});

test('derives method and path from the manifest endpoint, preventing adapter drift', () => {
  assert.throws(() => adapterFor({ id: 'crear-solicitud', method: 'PUT', path: '/manifest-owned-path' }), /drift/i);
});

test('accepts the generated endpoint shape and resolves its canonical route', () => {
  const adapter = adapterFor({ id: 'crear-solicitud', role: 'client', mutation: true });
  assert.equal(adapter.method, 'POST');
  assert.equal(adapter.path, '/api/solicitudes');
});

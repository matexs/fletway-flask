import assert from 'node:assert/strict';
import test from 'node:test';
import { adapterFor } from '../k6/adapters/endpoint-adapters.js';

globalThis.__ENV = {
  REQUEST_BODY_JSON: '{"should_not":"be_used"}',
  ORIGIN_ADDRESS: 'Origin from env', DESTINATION_ADDRESS: 'Destination from env',
  CARGO_DETAILS: 'Boxes from env', WEIGHT: '12', PICKUP_TIME: '2026-09-03T12:00:00Z',
  SOLICITUD_ID: 'request-from-env', ESTIMATED_PRICE: '99.50', QUOTE_COMMENT: 'Careful',
};

test('maps create request body from endpoint-specific environment fields', () => {
  const body = adapterFor({ id: 'crear-solicitud', method: 'POST', path: '/api/solicitudes' }).body();
  assert.deepEqual(body, { direccion_origen: 'Origin from env', direccion_destino: 'Destination from env', detalles_carga: 'Boxes from env', peso: '12', hora_recogida: '2026-09-03T12:00:00Z' });
});

test('maps create quote body independently and never falls back to generic JSON', () => {
  const body = adapterFor({ id: 'crear-presupuesto', method: 'POST', path: '/api/presupuestos' }).body();
  assert.deepEqual(body, { solicitud_id: 'request-from-env', precio_estimado: '99.50', comentario: 'Careful' });
});

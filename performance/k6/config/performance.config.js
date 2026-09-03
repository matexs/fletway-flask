/* Compatibility entry point for existing k6 scripts. */
export { softLimits, hardLimits, metricName, buildThresholds } from '../../config/thresholds.js';
export { profileLabels, profileIdsFor, buildScenarios } from '../../config/profiles.js';

export const endpoints = [
  { key: 'health', label: 'Health check', role: 'public', path: '/', weight: 5 },
  { key: 'localidades', label: 'Localidades', role: 'client', path: '/api/localidades', weight: 10 },
  { key: 'buscar_localidades', label: 'Buscar localidades', role: 'client', path: '/api/localidades/buscar', weight: 10 },
  { key: 'mis_pedidos', label: 'Pedidos del cliente', role: 'client', path: '/api/solicitudes/mis-pedidos', weight: 20 },
  { key: 'mis_pedidos_optimizado', label: 'Pedidos optimizados', role: 'client', path: '/solicitudes/mis-pedidos-optimizado', weight: 15 },
  { key: 'dashboard_transportista', label: 'Dashboard del fletero', role: 'driver', path: '/api/transportista/dashboard', weight: 15 },
  { key: 'historial_transportista', label: 'Historial del fletero', role: 'driver', path: '/api/transportista/historial', weight: 10 },
  { key: 'mis_presupuestos', label: 'Presupuestos del fletero', role: 'driver', path: '/api/presupuestos/mis-presupuestos', weight: 10 },
  { key: 'presupuestos_batch', label: 'Presupuestos batch del cliente', role: 'client', path: '/api/presupuestos/completo-batch', weight: 5 },
];

export const softLimits = {
  smoke: { p95Ms: 1000, successRate: 0.99, errorRate: 0.01, timeoutRate: 0 },
  default: { p95Ms: 2000, successRate: 0.95, errorRate: 0.05, timeoutRate: 0.01 },
};

export const hardLimits = {
  p95Ms: 5000,
  successRate: 0.80,
  errorRate: 0.20,
  timeoutRate: 0.10,
};

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

export const profileLabels = {
  smoke: 'Smoke',
  load: 'Carga',
  stress_10: 'Estrés 10 VU',
  stress_20: 'Estrés 20 VU',
  stress_30: 'Estrés 30 VU',
};

export function profileIdsFor(profile) {
  if (profile === 'stress') return ['stress_10', 'stress_20', 'stress_30'];
  return [profile];
}

export function buildScenarios(profile) {
  if (profile === 'smoke') {
    return {
      smoke: {
        executor: 'ramping-vus',
        exec: 'runFlow',
        startVUs: 0,
        stages: [
          { duration: '10s', target: 1 },
          { duration: '20s', target: 3 },
          { duration: '10s', target: 0 },
        ],
        gracefulRampDown: '5s',
      },
    };
  }

  if (profile === 'load') {
    return {
      load: {
        executor: 'ramping-vus',
        exec: 'runFlow',
        startVUs: 0,
        stages: [
          { duration: '15s', target: 10 },
          { duration: '60s', target: 10 },
          { duration: '15s', target: 0 },
        ],
        gracefulRampDown: '5s',
      },
    };
  }

  if (profile === 'stress') {
    return {
      stress_10: { executor: 'constant-vus', exec: 'runFlow', vus: 10, duration: '30s', startTime: '0s', gracefulStop: '5s' },
      stress_20: { executor: 'constant-vus', exec: 'runFlow', vus: 20, duration: '30s', startTime: '35s', gracefulStop: '5s' },
      stress_30: { executor: 'constant-vus', exec: 'runFlow', vus: 30, duration: '30s', startTime: '70s', gracefulStop: '5s' },
    };
  }

  throw new Error(`PROFILE inválido: ${profile}. Valores permitidos: smoke, load, stress.`);
}

export function metricName(profileId, kind, endpointKey = '') {
  const suffix = endpointKey ? `_${endpointKey}` : '';
  return `fletway_${profileId}${suffix}_${kind}`;
}

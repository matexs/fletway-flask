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
  if (profile === 'smoke') return { smoke: { executor: 'ramping-vus', exec: 'runFlow', startVUs: 0, stages: [{ duration: '10s', target: 1 }, { duration: '20s', target: 3 }, { duration: '10s', target: 0 }], gracefulRampDown: '5s' } };
  if (profile === 'load') return { load: { executor: 'ramping-vus', exec: 'runFlow', startVUs: 0, stages: [{ duration: '15s', target: 10 }, { duration: '60s', target: 10 }, { duration: '15s', target: 0 }], gracefulRampDown: '5s' } };
  if (profile === 'stress') return {
    stress_10: { executor: 'constant-vus', exec: 'runFlow', vus: 10, duration: '30s', startTime: '0s', gracefulStop: '5s' },
    stress_20: { executor: 'constant-vus', exec: 'runFlow', vus: 20, duration: '30s', startTime: '35s', gracefulStop: '5s' },
    stress_30: { executor: 'constant-vus', exec: 'runFlow', vus: 30, duration: '30s', startTime: '70s', gracefulStop: '5s' },
  };
  throw new Error(`PROFILE inválido: ${profile}. Valores permitidos: smoke, load, stress.`);
}

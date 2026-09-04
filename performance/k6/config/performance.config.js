export const softLimits = {
  smoke: { p95Ms: 1000, successRate: 0.99, errorRate: 0.01, timeoutRate: 0 },
  load: { p95Ms: 2000, successRate: 0.95, errorRate: 0.05, timeoutRate: 0.01 },
  stress: { p95Ms: 3000, successRate: 0.90, errorRate: 0.10, timeoutRate: 0.10 },
  spike: { p95Ms: 5000, successRate: 0.80, errorRate: 0.20, timeoutRate: 0.10 },
};

export const hardLimits = {
  p95Ms: 5000,
  successRate: 0.80,
  errorRate: 0.20,
  timeoutRate: 0.10,
};

export const profiles = {
  smoke: { minVus: 1, maxVus: 3, durationSeconds: 40 },
  load: { minVus: 0, maxVus: 10, durationSeconds: 90 },
  stress: { minVus: 10, maxVus: 30, durationSeconds: 105 },
  spike: { minVus: 3, maxVus: 30, durationSeconds: 60 },
};

export function profileIdsFor(profile) {
  return profile === 'stress' ? ['stress_10', 'stress_20', 'stress_30'] : [profile];
}

export function buildScenarios(profile) {
  if (profile === 'smoke') {
    return { smoke: { executor: 'ramping-vus', exec: 'runFlow', startVUs: 0, stages: [
      { duration: '10s', target: 1 }, { duration: '20s', target: 3 }, { duration: '10s', target: 0 },
    ], gracefulRampDown: '5s' } };
  }
  if (profile === 'load') {
    return { load: { executor: 'ramping-vus', exec: 'runFlow', startVUs: 0, stages: [
      { duration: '15s', target: 10 }, { duration: '60s', target: 10 }, { duration: '15s', target: 0 },
    ], gracefulRampDown: '5s' } };
  }
  if (profile === 'stress') {
    return {
      stress_10: { executor: 'constant-vus', exec: 'runFlow', vus: 10, duration: '30s', startTime: '0s', gracefulStop: '5s' },
      stress_20: { executor: 'constant-vus', exec: 'runFlow', vus: 20, duration: '30s', startTime: '35s', gracefulStop: '5s' },
      stress_30: { executor: 'constant-vus', exec: 'runFlow', vus: 30, duration: '30s', startTime: '70s', gracefulStop: '5s' },
    };
  }
  if (profile === 'spike') {
    return { spike: { executor: 'ramping-vus', exec: 'runFlow', startVUs: 0, stages: [
      { duration: '10s', target: 3 }, { duration: '5s', target: 30 }, { duration: '25s', target: 30 },
      { duration: '5s', target: 3 }, { duration: '15s', target: 3 },
    ], gracefulRampDown: '5s' } };
  }
  throw new Error(`PROFILE inválido: ${profile}. Valores permitidos: smoke, load, stress, spike.`);
}

export function metricName(profileId, kind, endpointKey = '') {
  return `fletway_${profileId}${endpointKey ? `_${endpointKey}` : ''}_${kind}`;
}

export function buildThresholds(profileIds, endpointEntries = []) {
  const thresholds = {};
  for (const profileId of profileIds) {
    thresholds[metricName(profileId, 'duration_ms')] = ['p(95)<5000'];
    thresholds[metricName(profileId, 'success_rate')] = ['rate>0.8'];
    thresholds[metricName(profileId, 'error_rate')] = ['rate<0.2'];
    thresholds[metricName(profileId, 'timeout_rate')] = ['rate<0.1'];
    for (const entry of endpointEntries) {
      thresholds[metricName(profileId, 'duration_ms', entry.key)] = ['p(95)<5000'];
      thresholds[metricName(profileId, 'success_rate', entry.key)] = ['rate>0.8'];
      thresholds[metricName(profileId, 'error_rate', entry.key)] = ['rate<0.2'];
      thresholds[metricName(profileId, 'timeout_rate', entry.key)] = ['rate<0.1'];
    }
  }
  return thresholds;
}

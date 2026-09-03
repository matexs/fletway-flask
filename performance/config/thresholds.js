export const softLimits = {
  smoke: { p95Ms: 1000, successRate: 0.99, errorRate: 0.01, timeoutRate: 0 },
  default: { p95Ms: 2000, successRate: 0.95, errorRate: 0.05, timeoutRate: 0.01 },
};

export const hardLimits = { p95Ms: 5000, successRate: 0.80, errorRate: 0.20, timeoutRate: 0.10 };

export function metricName(profileId, kind, endpointKey = '') {
  return `fletway_${profileId}${endpointKey ? `_${endpointKey}` : ''}_${kind}`;
}

export function buildThresholds(profileIds, endpoints = []) {
  const thresholds = {};
  for (const profileId of profileIds) {
    const metricScopes = [{ endpointKey: '' }, ...endpoints.map(({ key }) => ({ endpointKey: key }))];
    for (const { endpointKey } of metricScopes) {
      thresholds[metricName(profileId, 'duration_ms', endpointKey)] = [`p(95)<${hardLimits.p95Ms}`];
      thresholds[metricName(profileId, 'success_rate', endpointKey)] = [`rate>${hardLimits.successRate}`];
      thresholds[metricName(profileId, 'error_rate', endpointKey)] = [`rate<${hardLimits.errorRate}`];
      thresholds[metricName(profileId, 'timeout_rate', endpointKey)] = [`rate<${hardLimits.timeoutRate}`];
    }
  }
  return thresholds;
}

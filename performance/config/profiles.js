export const profileLabels = {
  smoke: 'Smoke',
  load: 'Carga',
  stress_10: 'Estrés 10 VU',
  stress_20: 'Estrés 20 VU',
  stress_30: 'Estrés 30 VU',
  stress_p0_20: 'Estrés P0 20 VU',
  stress_p0_40: 'Estrés P0 40 VU',
  stress_p0_60: 'Estrés P0 60 VU',
  stress_p0_80: 'Estrés P0 80 VU',
  stress_p0_100: 'Estrés P0 100 VU',
  spike: 'Spike',
};

const STANDARD_STRESS_VUS = [10, 20, 30];
const P0_STRESS_VUS = [20, 40, 60, 80, 100];

export function stressStages(kind = 'standard', configuredVus) {
  if (configuredVus !== undefined) {
    if (!Array.isArray(configuredVus) || configuredVus.length === 0 || configuredVus.some((vus) => !Number.isInteger(vus) || vus <= 0)) {
      throw new Error('Stress VU stages must be a non-empty array of positive integers.');
    }
    return [...configuredVus];
  }
  if (kind === 'standard') return [...STANDARD_STRESS_VUS];
  if (kind === 'p0') return [...P0_STRESS_VUS];
  throw new Error(`Unknown stress stage set: ${kind}.`);
}

export function profileIdsFor(profile, configuredVus) {
  if (profile === 'stress') return stressStages('standard', configuredVus).map((vus) => `stress_${vus}`);
  if (profile === 'stress_p0') return stressStages('p0', configuredVus).map((vus) => `stress_p0_${vus}`);
  return [profile];
}

function stressScenario(id, vus, options = {}) {
  return {
    executor: 'constant-vus', exec: 'runFlow', vus,
    duration: options.duration || '30s', startTime: '0s', gracefulStop: options.gracefulStop || '5s',
  };
}

export function spikeRecovery(options = {}) {
  return { target: options.recoveryVus ?? options.baselineVus ?? 3, duration: options.recoveryDuration || '30s' };
}

export function buildScenarios(profile, options = {}) {
  if (profile === 'smoke') return { smoke: { executor: 'ramping-vus', exec: 'runFlow', startVUs: 0, stages: [{ duration: '10s', target: 1 }, { duration: '20s', target: 3 }, { duration: '10s', target: 0 }], gracefulRampDown: '5s' } };
  if (profile === 'load') return { load: { executor: 'ramping-vus', exec: 'runFlow', startVUs: 0, stages: [{ duration: '15s', target: 10 }, { duration: '60s', target: 10 }, { duration: '15s', target: 0 }], gracefulRampDown: '5s' } };
  if (profile === 'stress' || profile === 'stress_p0') {
    const vus = stressStages(profile === 'stress_p0' ? 'p0' : 'standard', options.vus);
    return Object.fromEntries(vus.map((level) => {
      const id = `${profile}_${level}`;
      return [id, stressScenario(id, level, { ...options, vuMin: options.vuMin ?? level, vuMax: options.vuMax ?? level })];
    }));
  }
  const individualStress = /^(stress|stress_p0)_\d+$/.exec(profile);
  if (individualStress) {
    const vus = Number(profile.split('_').pop());
    return { [profile]: stressScenario(profile, vus, options) };
  }
  if (profile === 'spike') {
    const baselineVus = options.baselineVus ?? 3;
    const spikeVus = options.spikeVus ?? 30;
    const recoveryVus = options.recoveryVus ?? baselineVus;
    const recovery = spikeRecovery({ ...options, recoveryVus });
    return { spike: {
      executor: 'ramping-vus', exec: 'runFlow', startVUs: baselineVus,
      stages: [
        { duration: options.baselineDuration || '30s', target: baselineVus },
        { duration: options.spikeDuration || '10s', target: spikeVus },
        recovery,
        { duration: options.cooldownDuration || '10s', target: 0 },
      ],
      gracefulRampDown: '5s',
    } };
  }
  throw new Error(`PROFILE inválido: ${profile}. Valores permitidos: smoke, load, stress, stress_p0, spike.`);
}

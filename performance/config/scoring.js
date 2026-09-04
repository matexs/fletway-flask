const PROFILES = Object.freeze(['smoke', 'load', 'stress', 'spike']);
const PROFILE_WEIGHTS = Object.freeze({ smoke: 0.10, load: 0.40, stress: 0.30, spike: 0.20 });
const CANONICAL_COLUMNS = Object.freeze([
  'endpoint', 'test', 'objetivo', 'carga_vu_min', 'carga_vu_max',
  'p95_ms', 'error_pct', 'capacidad_rps', 'resultado', 'usuarios',
]);
const EXECUTED_RESULTS = new Set(['APROBADA', 'ADVERTENCIA', 'FALLIDA']);

function finite(value, name, { minimum = -Infinity, exclusiveMinimum = false } = {}) {
  if (typeof value === 'boolean' || value === null || value === undefined || String(value).trim() === '') {
    throw new Error(`${name} must be a finite numeric value.`);
  }
  const number = Number(value);
  if (!Number.isFinite(number) || (exclusiveMinimum ? number <= minimum : number < minimum)) {
    throw new Error(`${name} must be a finite numeric value${exclusiveMinimum ? ` greater than ${minimum}` : ` >= ${minimum}`}.`);
  }
  return number;
}

function requiredText(value, name) {
  if (typeof value !== 'string' || value.trim() === '') throw new Error(`${name} must be non-empty text.`);
  return value;
}

function percentage(value, name) {
  const number = finite(value, name, { minimum: 0 });
  if (number > 100) throw new Error(`${name} must be between 0 and 100.`);
  return number;
}

export function latencyScore(targetP95Ms, observedP95Ms) {
  const target = finite(targetP95Ms, 'target p95', { minimum: 0, exclusiveMinimum: true });
  const observed = finite(observedP95Ms, 'observed p95', { minimum: 0 });
  return observed <= target ? 100 : Math.min(100, (target / observed) * 100);
}

export function errorScore(targetErrorPct, hardErrorPct, observedErrorPct) {
  const target = finite(targetErrorPct, 'target error', { minimum: 0 });
  const hard = finite(hardErrorPct, 'hard error', { minimum: 0 });
  const observed = finite(observedErrorPct, 'observed error', { minimum: 0 });
  if (hard < target) throw new Error('hard error must be greater than or equal to target error.');
  if (observed >= hard) return 0;
  if (observed <= target) return 100;
  return ((hard - observed) / (hard - target)) * 100;
}

export function testScore(latency, error) {
  const latencyValue = finite(latency, 'latency score', { minimum: 0 });
  const errorValue = finite(error, 'error score', { minimum: 0 });
  if (latencyValue > 100 || errorValue > 100) throw new Error('metric scores must be between 0 and 100.');
  return (0.70 * latencyValue) + (0.30 * errorValue);
}

export function classifyScore(score) {
  const value = finite(score, 'score', { minimum: 0 });
  if (value > 100) throw new Error('score must be between 0 and 100.');
  if (value >= 90) return 'EXCELENTE';
  if (value >= 80) return 'BUENO';
  if (value >= 70) return 'ACEPTABLE';
  if (value >= 60) return 'MEJORABLE';
  return 'CRITICO';
}

function validateThresholds(thresholds) {
  if (!thresholds || typeof thresholds !== 'object' || !thresholds.profiles || !thresholds.hard) {
    throw new Error('thresholds requires profiles and hard.');
  }
  const profiles = {};
  for (const profile of PROFILES) {
    const source = thresholds.profiles[profile];
    if (!source) throw new Error(`thresholds missing profile: ${profile}.`);
    profiles[profile] = {
      p95_ms: finite(source.p95_ms, `${profile}.p95_ms`, { minimum: 0, exclusiveMinimum: true }),
      error_pct: percentage(source.error_pct, `${profile}.error_pct`),
    };
  }
  const hardErrorPct = percentage(thresholds.hard.error_pct, 'hard.error_pct');
  for (const profile of PROFILES) {
    if (profiles[profile].error_pct > hardErrorPct) throw new Error(`${profile}.error_pct must be <= hard.error_pct.`);
  }
  return {
    profiles,
    hard: { error_pct: hardErrorPct },
  };
}

function manifestEntries(manifest) {
  const entries = Array.isArray(manifest) ? manifest : manifest?.endpoints;
  if (!Array.isArray(entries) || entries.length === 0) throw new Error('manifest endpoints cannot be empty.');
  const seen = new Set();
  return entries.map((entry) => {
    const id = requiredText(entry.id, 'manifest endpoint id');
    if (seen.has(id)) throw new Error(`duplicate manifest endpoint id: ${id}.`);
    seen.add(id);
    const method = requiredText(entry.method, `${id}.method`).toUpperCase();
    const path = requiredText(entry.path, `${id}.path`);
    const priority = requiredText(entry.priority, `${id}.priority`);
    if (!['P0', 'P1', 'P2'].includes(priority)) throw new Error(`invalid priority for ${id}.`);
    const enabled = entry.enabled_profiles ?? PROFILES;
    if (!Array.isArray(enabled) || enabled.length === 0 || enabled.some((p) => !PROFILES.includes(p)) || new Set(enabled).size !== enabled.length) {
      throw new Error(`invalid enabled_profiles for ${id}.`);
    }
    return { id, endpoint: `${method} ${path}`, objective: requiredText(entry.objective, `${id}.objective`), priority,
      traffic_weight: finite(entry.traffic_weight, `${id}.traffic_weight`, { minimum: 0, exclusiveMinimum: true }), enabled_profiles: enabled };
  });
}

function validateMatrix(matrix, entries) {
  if (!Array.isArray(matrix)) throw new Error('matrix must be an array.');
  const entryEndpoints = new Set(entries.map((entry) => entry.endpoint));
  const entryByEndpoint = new Map(entries.map((entry) => [entry.endpoint, entry]));
  const seen = new Set();
  for (const row of matrix) {
    const keys = Object.keys(row);
    if (keys.length !== CANONICAL_COLUMNS.length || keys.some((key, index) => key !== CANONICAL_COLUMNS[index])) {
      throw new Error('matrix schema does not match canonical columns.');
    }
    requiredText(row.endpoint, 'matrix endpoint');
    if (!entryEndpoints.has(row.endpoint)) throw new Error(`matrix references unknown endpoint: ${row.endpoint}.`);
    if (!PROFILES.includes(row.test)) throw new Error(`matrix has unsupported profile: ${row.test}.`);
    const key = `${row.endpoint}|${row.test}`;
    if (seen.has(key)) throw new Error(`duplicate matrix row: ${key}.`);
    seen.add(key);
    if (row.objetivo !== entryByEndpoint.get(row.endpoint).objective) throw new Error(`${key}.objetivo contradicts manifest objective.`);
    if (!EXECUTED_RESULTS.has(row.resultado) && row.resultado !== 'NO_EJECUTADA') throw new Error(`invalid matrix resultado: ${row.resultado}.`);
    if (row.resultado === 'NO_EJECUTADA') {
      for (const field of ['carga_vu_min', 'carga_vu_max', 'p95_ms', 'error_pct', 'capacidad_rps']) {
        if (String(row[field]).trim() !== '') throw new Error(`${key} NO_EJECUTADA row must leave ${field} blank.`);
      }
      continue;
    }
    const vuMin = finite(row.carga_vu_min, `${key}.carga_vu_min`, { minimum: 0 });
    const vuMax = finite(row.carga_vu_max, `${key}.carga_vu_max`, { minimum: 0 });
    if (!Number.isInteger(vuMin) || !Number.isInteger(vuMax) || vuMin > vuMax) throw new Error(`${key} has contradictory VU values.`);
    finite(row.p95_ms, `${key}.p95_ms`, { minimum: 0 });
    finite(row.error_pct, `${key}.error_pct`, { minimum: 0 });
    if (finite(row.error_pct, `${key}.error_pct`) > 100) throw new Error(`${key}.error_pct must be <= 100.`);
    finite(row.capacidad_rps, `${key}.capacidad_rps`, { minimum: 0 });
  }
  return seen;
}

function endpointResult(entry, rows, thresholds) {
  const byProfile = new Map(rows.filter((row) => row.endpoint === entry.endpoint).map((row) => [row.test, row]));
  const missing = PROFILES.filter((profile) => !byProfile.has(profile) || byProfile.get(profile).resultado === 'NO_EJECUTADA');
  if (missing.length) return { id: entry.id, endpoint: entry.endpoint, traffic_weight: entry.traffic_weight, score: null, included_in_general: false,
    reason: `missing executed profiles: ${missing.join(', ')}` };
  const scores = {};
  for (const profile of PROFILES) {
    const row = byProfile.get(profile);
    const target = thresholds.profiles[profile];
    const latency = latencyScore(target.p95_ms, row.p95_ms);
    const error = errorScore(target.error_pct, thresholds.hard.error_pct, row.error_pct);
    scores[profile] = { latency_score: latency, error_score: error, test_score: testScore(latency, error) };
  }
  const score = PROFILES.reduce((sum, profile) => sum + (scores[profile].test_score * PROFILE_WEIGHTS[profile]), 0);
  return { id: entry.id, endpoint: entry.endpoint, traffic_weight: entry.traffic_weight, score, included_in_general: true, scores };
}

export function calculateScore({ manifest, matrix, thresholds }) {
  const config = validateThresholds(thresholds);
  const entries = manifestEntries(manifest);
  validateMatrix(matrix, entries);
  const prioritized = entries.filter((entry) => entry.priority === 'P0');
  const coverageDenominator = entries
    .filter((entry) => ['P0', 'P1', 'P2'].includes(entry.priority))
    .reduce((sum, entry) => sum + entry.traffic_weight, 0);
  if (!(coverageDenominator > 0)) throw new Error('prioritized traffic weight denominator must be greater than zero.');
  const endpoints = prioritized.map((entry) => endpointResult(entry, matrix, config));
  for (const endpoint of endpoints) endpoint.normalized_traffic_weight = endpoint.traffic_weight / coverageDenominator;
  const complete = endpoints.filter((endpoint) => endpoint.included_in_general);
  const executedWeight = complete.reduce((sum, endpoint) => sum + endpoint.traffic_weight, 0);
  for (const endpoint of complete) endpoint.executed_normalized_traffic_weight = endpoint.traffic_weight / executedWeight;
  const generalScore = executedWeight > 0 ? complete.reduce((sum, endpoint) => sum + endpoint.score * (endpoint.traffic_weight / executedWeight), 0) : null;
  const coveragePct = (executedWeight / coverageDenominator) * 100;
  const representative = coveragePct >= 80 && complete.length > 0;
  const representativeReason = representative
    ? { code: 'COVERAGE_MEETS_TARGET', message: `coverage_pct ${coveragePct} meets the 80% target.` }
    : { code: 'COVERAGE_BELOW_TARGET', message: `coverage_pct ${coveragePct} is below the 80% target; representative classification is blocked.` };
  return { profile_weights: { ...PROFILE_WEIGHTS }, coverage_pct: coveragePct, general_score: generalScore,
    classification: representative && generalScore !== null ? classifyScore(generalScore) : null,
    classification_blocked: !representative, representative, representative_reason: representativeReason, endpoints };
}

export { CANONICAL_COLUMNS, PROFILE_WEIGHTS, PROFILES };

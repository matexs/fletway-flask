import { endpoints, hardLimits, metricName, profileIdsFor, profileLabels, softLimits } from '../config/performance.config.js';

function metricValues(data, name) {
  return data.metrics[name]?.values || {};
}

function number(value, fallback = 0) {
  return Number.isFinite(value) ? value : fallback;
}

function evaluateMetricSet(data, profileId, endpointKey = '') {
  const duration = metricValues(data, metricName(profileId, 'duration_ms', endpointKey));
  const success = metricValues(data, metricName(profileId, 'success_rate', endpointKey));
  const errors = metricValues(data, metricName(profileId, 'error_rate', endpointKey));
  const timeouts = metricValues(data, metricName(profileId, 'timeout_rate', endpointKey));
  const requests = number(duration.count);
  const p95Ms = number(duration['p(95)']);
  const successRate = number(success.rate);
  const errorRate = number(errors.rate);
  const timeoutRate = number(timeouts.rate);
  const soft = profileId === 'smoke' ? softLimits.smoke : softLimits.default;

  const hardFailure =
    p95Ms >= hardLimits.p95Ms ||
    successRate <= hardLimits.successRate ||
    errorRate >= hardLimits.errorRate ||
    timeoutRate >= hardLimits.timeoutRate;

  const softFailure =
    p95Ms >= soft.p95Ms ||
    successRate <= soft.successRate ||
    errorRate >= soft.errorRate ||
    (soft.timeoutRate === 0 ? timeoutRate > 0 : timeoutRate >= soft.timeoutRate);

  return {
    requests,
    p95Ms,
    averageMs: number(duration.avg),
    successRate,
    errorRate,
    timeoutRate,
    state: requests === 0
      ? endpointKey ? 'SIN MUESTRAS' : 'NO EJECUTADA'
      : hardFailure
        ? 'FALLIDA'
        : softFailure
          ? 'ADVERTENCIA'
          : 'APROBADA',
  };
}

function worstState(states) {
  if (states.includes('FALLIDA')) return 'FALLIDA';
  if (states.includes('ADVERTENCIA')) return 'ADVERTENCIA';
  if (states.includes('NO EJECUTADA')) return 'NO EJECUTADA';
  return 'APROBADA';
}

export function evaluateSummary(data, profile, context) {
  const profiles = profileIdsFor(profile).map((profileId) => {
    const overall = evaluateMetricSet(data, profileId);
    const endpointResults = endpoints.map((endpoint) => ({
      key: endpoint.key,
      label: endpoint.label,
      role: endpoint.role,
      ...evaluateMetricSet(data, profileId, endpoint.key),
    }));

    return {
      id: profileId,
      label: profileLabels[profileId],
      ...overall,
      endpoints: endpointResults,
    };
  });

  const stableStressLevels = profiles
    .filter((item) => item.id.startsWith('stress_') && item.state === 'APROBADA')
    .map((item) => Number(item.id.split('_')[1]));
  const degradedStressLevel = profiles.find(
    (item) => item.id.startsWith('stress_') && item.requests > 0 && item.state !== 'APROBADA',
  );

  return {
    runId: context.runId,
    generatedAt: new Date().toISOString(),
    baseUrl: context.baseUrl,
    requestedProfile: profile,
    state: worstState(profiles.map((item) => item.state)),
    profiles,
    stressCapacity: profile === 'stress'
      ? {
          maximumStableObservedVUs: stableStressLevels.length ? Math.max(...stableStressLevels) : null,
          firstDegradationObservedVUs: degradedStressLevel
            ? Number(degradedStressLevel.id.split('_')[1])
            : null,
        }
      : null,
  };
}

function pct(value) {
  return `${(value * 100).toFixed(2)}%`;
}

function ms(value) {
  return `${value.toFixed(0)} ms`;
}

function mdState(state) {
  if (state === 'SIN MUESTRAS' || state === 'NO EJECUTADA') return `➖ ${state}`;
  return state === 'APROBADA' ? `✅ ${state}` : state === 'ADVERTENCIA' ? `⚠️ ${state}` : `❌ ${state}`;
}

export function renderMarkdown(evaluation) {
  const lines = [
    '# Informe de rendimiento de Fletway',
    '',
    `- **Estado general:** ${mdState(evaluation.state)}`,
    `- **Entorno:** ${evaluation.baseUrl}`,
    `- **Fecha UTC:** ${evaluation.generatedAt}`,
    `- **Perfil solicitado:** ${evaluation.requestedProfile}`,
    '',
    '## Resumen',
    '',
    '| Prueba | Requests | p95 | Éxito | Errores | Timeouts | Estado |',
    '|---|---:|---:|---:|---:|---:|---|',
  ];

  for (const profile of evaluation.profiles) {
    lines.push(`| ${profile.label} | ${profile.requests} | ${ms(profile.p95Ms)} | ${pct(profile.successRate)} | ${pct(profile.errorRate)} | ${pct(profile.timeoutRate)} | ${mdState(profile.state)} |`);
  }

  if (evaluation.stressCapacity) {
    lines.push('', '## Capacidad observada', '');
    lines.push(`- **Máxima carga estable observada:** ${evaluation.stressCapacity.maximumStableObservedVUs ?? 'No observada'} VU`);
    lines.push(`- **Primer nivel con degradación:** ${evaluation.stressCapacity.firstDegradationObservedVUs ?? 'No observado'} VU`);
    lines.push('', '> Estos valores describen únicamente los escalones 10/20/30 VU probados; no constituyen un breakpoint definitivo.');
  }

  for (const profile of evaluation.profiles) {
    lines.push('', `## Endpoints — ${profile.label}`, '');
    lines.push('| Endpoint | Rol | Requests | p95 | Éxito | Errores | Timeouts | Estado |');
    lines.push('|---|---|---:|---:|---:|---:|---:|---|');
    for (const endpoint of profile.endpoints) {
      lines.push(`| ${endpoint.label} | ${endpoint.role} | ${endpoint.requests} | ${ms(endpoint.p95Ms)} | ${pct(endpoint.successRate)} | ${pct(endpoint.errorRate)} | ${pct(endpoint.timeoutRate)} | ${mdState(endpoint.state)} |`);
    }
  }

  lines.push(
    '',
    '## Interpretación',
    '',
    '- **Hecho:** las cifras anteriores provienen del resumen generado por k6.',
    '- **No ejecutada:** la preparación (disponibilidad, login o roles) no terminó; no se evalúa el rendimiento sin muestras.',
    '- **Interpretación:** `ADVERTENCIA` indica un incumplimiento del objetivo recomendado sin alcanzar el límite de fallo severo.',
    '- **Hipótesis:** una causa técnica requiere métricas adicionales de servidor, base de datos, CPU, memoria o logs.',
    '',
  );
  return lines.join('\n');
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function stateBadge(state) {
  return `<span class="state ${state.toLowerCase().replaceAll(' ', '-')}">${escapeHtml(state)}</span>`;
}

function profileTable(profile) {
  const rows = profile.endpoints.map((endpoint) => `
    <tr>
      <td>${escapeHtml(endpoint.label)}</td><td>${escapeHtml(endpoint.role)}</td>
      <td>${endpoint.requests}</td><td>${ms(endpoint.p95Ms)}</td>
      <td>${pct(endpoint.successRate)}</td><td>${pct(endpoint.errorRate)}</td>
      <td>${pct(endpoint.timeoutRate)}</td><td>${stateBadge(endpoint.state)}</td>
    </tr>`).join('');
  return `<section><h2>${escapeHtml(profile.label)}</h2><table><thead><tr><th>Endpoint</th><th>Rol</th><th>Requests</th><th>p95</th><th>Éxito</th><th>Errores</th><th>Timeouts</th><th>Estado</th></tr></thead><tbody>${rows}</tbody></table></section>`;
}

export function renderHtml(evaluation) {
  const summaryRows = evaluation.profiles.map((profile) => `
    <tr><td>${escapeHtml(profile.label)}</td><td>${profile.requests}</td><td>${ms(profile.p95Ms)}</td><td>${pct(profile.successRate)}</td><td>${pct(profile.errorRate)}</td><td>${pct(profile.timeoutRate)}</td><td>${stateBadge(profile.state)}</td></tr>`).join('');
  const capacity = evaluation.stressCapacity
    ? `<section><h2>Capacidad observada</h2><div class="cards"><article><strong>${evaluation.stressCapacity.maximumStableObservedVUs ?? 'N/D'}</strong><span>VU estables observados</span></article><article><strong>${evaluation.stressCapacity.firstDegradationObservedVUs ?? 'N/D'}</strong><span>VU al comenzar la degradación</span></article></div><p class="note">Estimación limitada a los escalones 10/20/30 VU.</p></section>`
    : '';

  return `<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Rendimiento Fletway</title><style>
  :root{font-family:Inter,Segoe UI,sans-serif;color:#172033;background:#f3f6fb}body{margin:0;padding:32px}main{max-width:1180px;margin:auto}header,section{background:#fff;border:1px solid #dfe6f0;border-radius:14px;padding:24px;margin-bottom:18px;box-shadow:0 6px 20px #1720330d}h1,h2{margin-top:0}header p{color:#536079}.hero{display:flex;justify-content:space-between;gap:24px;align-items:start}.state{display:inline-block;padding:5px 9px;border-radius:999px;font-size:12px;font-weight:800}.aprobada{background:#d9f7e8;color:#08653b}.advertencia{background:#fff2c7;color:#7a5200}.fallida{background:#ffe0df;color:#9b1c1c}.sin-muestras,.no-ejecutada{background:#e8edf5;color:#536079}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:10px;border-bottom:1px solid #e7ecf3}th{color:#536079}.cards{display:flex;gap:14px}.cards article{background:#f3f6fb;border-radius:12px;padding:18px;min-width:190px}.cards strong{font-size:30px;display:block}.cards span,.note{color:#667085;font-size:13px}@media(max-width:760px){body{padding:12px}.hero,.cards{display:block}section{overflow:auto}}
  </style></head><body><main><header><div class="hero"><div><h1>Informe de rendimiento de Fletway</h1><p>${escapeHtml(evaluation.baseUrl)} · ${escapeHtml(evaluation.generatedAt)} · Perfil ${escapeHtml(evaluation.requestedProfile)}</p></div>${stateBadge(evaluation.state)}</div></header>
  <section><h2>Resumen</h2><table><thead><tr><th>Prueba</th><th>Requests</th><th>p95</th><th>Éxito</th><th>Errores</th><th>Timeouts</th><th>Estado</th></tr></thead><tbody>${summaryRows}</tbody></table></section>
  ${capacity}${evaluation.profiles.map(profileTable).join('')}<section><h2>Lectura del resultado</h2><p><strong>Hecho:</strong> las métricas provienen de k6. <strong>No ejecutada:</strong> la preparación no terminó y no existen muestras para evaluar. <strong>Advertencia:</strong> se superó un objetivo recomendado sin alcanzar el límite severo. Las causas técnicas son hipótesis hasta contar con métricas del servidor.</p></section></main></body></html>`;
}

export function renderConsole(evaluation, paths) {
  const lines = [
    '',
    `Fletway ${evaluation.requestedProfile}: ${evaluation.state}`,
    ...evaluation.profiles.map((item) => `${item.label}: p95=${item.p95Ms.toFixed(0)}ms éxito=${pct(item.successRate)} errores=${pct(item.errorRate)} timeouts=${pct(item.timeoutRate)} => ${item.state}`),
    `Markdown: ${paths.markdown}`,
    `HTML: ${paths.html}`,
    `JSON: ${paths.json}`,
    '',
  ];
  return lines.join('\n');
}

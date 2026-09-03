const PLACEHOLDER_ENV = { id: 'REQUEST_ID', solicitud_id: 'SOLICITUD_ID', presupuesto_id: 'PRESUPUESTO_ID', transportista_id: 'TRANSPORTISTA_ID', filename: 'FILENAME' };

function envJson(name, fallback) {
  const raw = __ENV[name];
  if (!raw) return fallback;
  try { return JSON.parse(raw); } catch (error) { throw new Error(`${name} must contain valid JSON: ${error.message}`); }
}

export function resolvePath(path) {
  return String(path).replace(/<([^>]+)>/g, (_, placeholder) => {
    const envName = PLACEHOLDER_ENV[placeholder] || placeholder.toUpperCase();
    const value = __ENV[envName];
    if (!value) throw new Error(`Missing ${envName} for endpoint path placeholder <${placeholder}>.`);
    return encodeURIComponent(value);
  });
}

export function adapterFor(endpoint) {
  if (!endpoint || !endpoint.id) throw new Error('Endpoint manifest entry is required.');
  return {
    method: endpoint.method,
    path: endpoint.path,
    body: endpoint.method === 'GET' || endpoint.method === 'DELETE' ? undefined : () => envJson('ENDPOINT_BODY_JSON', {}),
  };
}

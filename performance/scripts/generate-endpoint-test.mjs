import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const defaultOutputDirectory = path.resolve(scriptDirectory, '..', 'k6', 'generated');
const relativeImport = (from, to) => { const value = path.relative(path.dirname(from), to).replaceAll('\\', '/'); return value.startsWith('.') ? value : `./${value}`; };

export function renderEndpointTest(endpoint, outputPath) {
  const template = relativeImport(outputPath, path.resolve(scriptDirectory, '..', 'templates', 'endpoint.template.js'));
  const adapters = relativeImport(outputPath, path.resolve(scriptDirectory, '..', 'k6', 'adapters', 'endpoint-adapters.js'));
  const config = relativeImport(outputPath, path.resolve(scriptDirectory, '..', 'k6', 'config', 'performance.config.js'));
  const placeholderEnv = { id: 'REQUEST_ID', solicitud_id: 'SOLICITUD_ID', presupuesto_id: 'PRESUPUESTO_ID', transportista_id: 'TRANSPORTISTA_ID', filename: 'FILENAME' };
  const placeholders = [...String(endpoint.path).matchAll(/<([^>]+)>/g)].map(([, name]) => placeholderEnv[name] || name.toUpperCase());
  const pathIdComment = placeholders.length ? `// Path IDs come from environment variables: ${placeholders.join(', ')}.\n` : '';
  return `import http from 'k6/http';
import { check } from 'k6';
import { captureResponseIds, requestOptions, requestTags, setupAuth, tokenForRole } from '${template}';
import { adapterFor, resolvePath } from '${adapters}';
import { buildScenarios, buildThresholds, profileIdsFor } from '${config}';

const endpoint = ${JSON.stringify(endpoint, null, 2)};
${pathIdComment}const adapter = { ...adapterFor(endpoint), method: '${endpoint.method}', path: '${endpoint.path}' };
const BASE_URL = String(__ENV.BASE_URL || '').replace(/[\\/,]+$/, '');
const PROFILE = __ENV.PROFILE || 'smoke';

export const options = { scenarios: buildScenarios(PROFILE), thresholds: buildThresholds(profileIdsFor(PROFILE), [{ key: endpoint.id }]) };
export function setup() { return setupAuth(); }
export default function runEndpoint(auth) {
  const body = adapter.body ? adapter.body() : undefined;
  const tags = requestTags({ endpointId: endpoint.id, profile: __ENV.PROFILE || 'smoke', stage: __ENV.STAGE || 'measure', role: endpoint.role });
  const token = tokenForRole(endpoint.role, auth);
  const response = http.request(adapter.method, BASE_URL + resolvePath(adapter.path), body === undefined ? null : JSON.stringify(body), requestOptions(token, tags));
  const timedOut = String(response.error || '').toLowerCase().includes('timeout');
  check(response, { [endpoint.id + ' status is successful']: () => response.status >= 200 && response.status < 400, [endpoint.id + ' does not time out']: () => !timedOut }, tags);
  const responseIds = endpoint.mutation ? captureResponseIds(response) : {};
  if (Object.keys(responseIds).length) console.log(JSON.stringify({ endpoint_id: endpoint.id, response_ids: responseIds }));
}
`;
}

export function generateEndpointTest(manifestPath, endpointId, outputPath) {
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const endpoint = manifest.endpoints?.find(({ id }) => id === endpointId);
  if (!endpoint) throw new Error(`Unknown endpoint: ${endpointId}`);
  const target = path.resolve(outputPath || path.join(defaultOutputDirectory, `${endpointId}.js`));
  const source = renderEndpointTest(endpoint, target);
  if (!outputPath) return source;
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, source, 'utf8');
  return { endpointId, outputPath: target };
}

function main() {
  const args = process.argv.slice(2); const value = (name) => { const index = args.indexOf(name); return index < 0 ? undefined : args[index + 1]; };
  const manifest = path.resolve(value('--manifest') || path.resolve(scriptDirectory, '..', 'config', 'endpoints.manifest.json'));
  const endpoint = value('--endpoint');
  if (!endpoint) throw new Error('Usage: node generate-endpoint-test.mjs --endpoint <manifest-id> [--manifest path] [--output path]');
  console.log(JSON.stringify(generateEndpointTest(manifest, endpoint, value('--output'))));
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();

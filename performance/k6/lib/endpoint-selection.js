export function selectEndpoint(endpoints, endpointId) {
  if (!endpointId) return null;
  const endpoint = endpoints.find(({ manifestId }) => manifestId === endpointId);
  if (!endpoint) throw new Error(`Unknown endpoint ID: ${endpointId}.`);
  return endpoint;
}

export function endpointForIteration(endpoints, endpointId, iteration = 0) {
  const selected = selectEndpoint(endpoints, endpointId);
  if (selected) return selected;
  const bucket = (iteration * 37) % 100;
  let upperBound = 0;
  for (const endpoint of endpoints) {
    upperBound += endpoint.weight;
    if (bucket < upperBound) return endpoint;
  }
  return endpoints[endpoints.length - 1];
}

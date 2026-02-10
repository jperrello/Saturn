/**
 * Saturn Service Discovery Inspector
 *
 * Shows how to use createSaturn() with custom options and inspect
 * the discovered services without making any chat requests.
 *
 * This is useful for:
 *   - Debugging network discovery issues
 *   - Verifying which services and models are available
 *   - Understanding the priority-based routing order
 *
 * Key concepts:
 *   - createSaturn() accepts a settings object for fine-grained control
 *     (the default `saturn` export uses all defaults)
 *   - getDiscovery().getAllServices() returns every discovered service
 *   - Each service has metadata from its mDNS TXT records: priority,
 *     deployment type, api type, capabilities, etc.
 *   - getEndpointsForModel() fetches /v1/models from each service
 *     and returns only those that advertise the requested model
 *
 * Prerequisites:
 *   1. A Saturn-compatible server running on your network
 *   2. Run: tsx examples/discovery.ts
 */

import { createSaturn } from '../src/index.js';

async function main() {
  // createSaturn() lets you override defaults.
  // Here we enable debug logging and set a shorter discovery timeout.
  const provider = createSaturn({
    discoveryTimeout: 3000,
    logLevel: 'debug',
  });

  const discovery = provider.getDiscovery();

  console.log('Searching for Saturn services on the local network...\n');
  await new Promise(resolve => setTimeout(resolve, 3000));

  const services = discovery.getAllServices();

  if (services.length === 0) {
    console.log('No Saturn services found.');
    provider.destroy();
    return;
  }

  console.log(`Found ${services.length} service(s):\n`);

  for (const service of services) {
    // Each service carries metadata from its mDNS TXT records.
    // These are set by the Saturn server at registration time.
    console.log(`  ${service.name}`);
    console.log(`    Endpoint:     ${service.endpoint}`);
    console.log(`    Deployment:   ${service.deployment}`);
    console.log(`    API Type:     ${service.apiType}`);
    console.log(`    API Base:     ${service.apiBase}`);
    console.log(`    Provider:     ${service.provider}`);
    console.log(`    Priority:     ${service.priority} (lower = preferred)`);
    console.log(`    Auth Type:    ${service.authType}`);
    console.log(`    Cost Tier:    ${service.cost}`);
    console.log(`    Features:     ${service.features || 'none'}`);
    console.log(`    Capabilities: ${service.capabilities.join(', ') || 'none'}`);

    // Models are fetched lazily from /v1/models on first access.
    // Force a fetch so we can display them.
    if (service.models.length === 0) {
      await discovery.getEndpointsForModel('__dummy__');
    }

    console.log(`    Models:       ${service.models.slice(0, 5).join(', ') || '(none)'}${service.models.length > 5 ? ` (+${service.models.length - 5} more)` : ''}`);
    console.log('');
  }

  // Show how the provider would route requests.
  // Services are sorted by priority — lowest number wins.
  console.log('Routing order:');
  for (const service of services) {
    const url = service.deployment === 'cloud' ? service.apiBase : service.endpoint;
    console.log(`  ${service.name} → ${url}/chat/completions`);
  }
  console.log('');

  provider.destroy();
}

main().catch(error => {
  console.error('Error:', error);
  process.exit(1);
});

/**
 * Example: Saturn Service Discovery Info
 * 
 * Shows detailed information about discovered Saturn services
 * without making any chat requests.
 * 
 * Prerequisites:
 * 1. Start the mock server: npm run mock
 * 2. Run this example: tsx examples/discovery-info.ts
 */

import { createSaturn } from '../src/index.js';

async function main() {
  console.log('🔍 Saturn Service Discovery');
  console.log('===========================\n');

  const provider = createSaturn({ discoveryTimeout: 3000, logLevel: 'debug' });
  const discovery = provider.getDiscovery();

  console.log('Searching for Saturn services on the local network...');
  await new Promise(resolve => setTimeout(resolve, 3000));

  const services = discovery.getAllServices();

  if (services.length === 0) {
    console.log('\n❌ No Saturn services found.');
    console.log('   Start a server with: python -m saturn.openrouter_server\n');
    provider.destroy();
    return;
  }

  console.log(`\n✅ Found ${services.length} service(s):\n`);

  for (const service of services) {
    console.log('┌─────────────────────────────────────────');
    console.log(`│ Service: ${service.name}`);
    console.log('├─────────────────────────────────────────');
    console.log(`│ Deployment:   ${service.deployment}`);
    console.log(`│ API Type:     ${service.apiType}`);
    console.log(`│ API Base:     ${service.apiBase}`);
    console.log(`│ Provider:     ${service.provider}`);
    console.log('├─────────────────────────────────────────');
    console.log(`│ Endpoint:     ${service.endpoint}`);
    console.log(`│ Host:         ${service.host}:${service.port}`);
    console.log(`│ Priority:     ${service.priority} (lower = preferred)`);
    console.log(`│ Auth Type:    ${service.authType}`);
    console.log(`│ Cost Tier:    ${service.cost}`);
    console.log(`│ Features:     ${service.features || 'none'}`);
    console.log(`│ Capabilities: ${service.capabilities.join(', ') || 'none'}`);
    console.log(`│ Ephemeral Key: ${service.ephemeralKey ? service.ephemeralKey.slice(0, 20) + '...' : 'none'}`);
    console.log('│');

    if (service.models.length === 0) {
      console.log('│ Fetching models...');
      await discovery.getEndpointsForModel('__dummy__');
    }

    console.log(`│ Models:       ${service.models.slice(0, 5).join(', ') || '(none)'}${service.models.length > 5 ? ` (+${service.models.length - 5} more)` : ''}`);
    console.log('└─────────────────────────────────────────\n');
  }

  console.log('Routing Logic Preview:');
  console.log('─'.repeat(50));
  for (const service of services) {
    const effectiveUrl = service.deployment === 'cloud' ? service.apiBase : service.endpoint;
    console.log(`  ${service.name}: ${service.deployment} → ${effectiveUrl}/chat/completions`);
  }
  console.log('');

  provider.destroy();
}

main().catch(error => {
  console.error('Error:', error);
  process.exit(1);
});

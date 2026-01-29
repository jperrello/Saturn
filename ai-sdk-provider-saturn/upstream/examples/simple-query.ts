/**
 * Example: Simple Query to Eliza
 * 
 * This is the simplest possible example of using the Saturn provider.
 * 
 * Prerequisites:
 * 1. Start the mock server: npm run mock
 * 2. Run this example: tsx examples/simple-query.ts
 */

import { saturn } from '../src/index.js';
import { generateText } from 'ai';

async function main() {
  console.log('🔍 Discovering Saturn services...\n');

  // Wait a moment for discovery (mDNS takes ~2-3 seconds)
  await new Promise(resolve => setTimeout(resolve, 3000));

  // List discovered services
  const services = saturn.getDiscovery().getAllServices();
  console.log(`Found ${services.length} service(s): ${services.map(s => s.name).join(', ')}\n`);

  // Trigger model fetching by querying for the model
  // This is done automatically on first use, but we do it explicitly here
  const endpoints = await saturn.getDiscovery().getEndpointsForModel('eliza');
  if (endpoints.length === 0) {
    console.error('Model eliza not found');
    saturn.destroy();
    process.exit(1);
  }

  // Simple query
  console.log('Asking Eliza a question...\n');

  const result = await generateText({
    model: saturn('eliza'),
    prompt: 'I am feeling anxious about my work.',
  });

  console.log('Eliza:', result.text);
  console.log('\nUsage:', result.usage?.totalTokens, 'tokens\n');

  // Cleanup
  saturn.destroy();
}

main().catch(error => {
  console.error('Error:', error);
  saturn.destroy();
  process.exit(1);
});

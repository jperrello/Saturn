/**
 * Example: Streaming Chat with Eliza
 * 
 * Demonstrates streaming responses from the Saturn provider.
 * 
 * Prerequisites:
 * 1. Start the mock server: npm run mock
 * 2. Run this example: tsx examples/streaming-chat.ts
 */

import { saturn } from '../src/index.js';
import { streamText } from 'ai';

async function main() {
  console.log('🔍 Discovering Saturn services...\n');

  // Wait for discovery (mDNS + HTTP model fetching)
  await new Promise(resolve => setTimeout(resolve, 4000));

  const services = saturn.getDiscovery().getAllServices();
  if (services.length === 0) {
    console.error('❌ No Saturn services found. Start the mock server first.');
    process.exit(1);
  }

  console.log(`✅ Found: ${services.map(s => s.name).join(', ')}\n`);

  // Stream a response
  console.log('💬 You: I need help with my anxiety\n');
  console.log('🤖 Eliza: ');

  const { textStream } = await streamText({
    model: saturn('eliza'),
    prompt: 'I need help with my anxiety',
  });

  // Print chunks as they arrive
  for await (const chunk of textStream) {
    process.stdout.write(chunk);
  }

  console.log('\n');

  // Cleanup
  saturn.destroy();
}

main().catch(error => {
  console.error('Error:', error);
  saturn.destroy();
  process.exit(1);
});

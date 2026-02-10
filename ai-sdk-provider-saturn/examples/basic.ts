/**
 * Basic Saturn Provider Usage
 *
 * Shows the two main ways to get responses from a Saturn-discovered model:
 *   1. generateText() — waits for the full response, returns it as a string
 *   2. streamText()   — returns an async iterable of chunks as they arrive
 *
 * Both use the same saturn('model-name') call to select a model.
 * The provider handles discovery, routing, and failover behind the scenes.
 *
 * Prerequisites:
 *   1. A Saturn-compatible server running on your network
 *   2. Run: tsx examples/basic.ts
 */

import { saturn } from '../src/index.js';
import { generateText, streamText } from 'ai';

async function main() {
  // Saturn discovers services via mDNS, which takes a few seconds.
  // In a real app you'd start saturn early (e.g. at boot) so discovery
  // finishes before the first request. Here we just wait.
  console.log('Discovering Saturn services...\n');
  await new Promise(resolve => setTimeout(resolve, 3000));

  const services = saturn.getDiscovery().getAllServices();
  if (services.length === 0) {
    console.error('No Saturn services found on the network.');
    saturn.destroy();
    process.exit(1);
  }

  console.log(`Found ${services.length} service(s): ${services.map(s => s.name).join(', ')}\n`);

  // --- generateText: full response at once ---
  //
  // saturn('eliza') returns a LanguageModelV3 instance routed to the
  // best available service advertising the "eliza" model.
  // If that service goes down mid-request, the provider retries on the
  // next-best service automatically.

  console.log('--- generateText ---\n');

  const result = await generateText({
    model: saturn('eliza'),
    prompt: 'I am feeling anxious about my work.',
  });

  console.log('Response:', result.text);
  console.log('Tokens:', result.usage?.totalTokens, '\n');

  // --- streamText: chunks as they arrive ---
  //
  // Same model reference, but streamText() gives you an async iterable.
  // Each chunk is a piece of the response as the server generates it.

  console.log('--- streamText ---\n');

  const { textStream } = streamText({
    model: saturn('eliza'),
    prompt: 'What should I do when I feel overwhelmed?',
  });

  for await (const chunk of textStream) {
    process.stdout.write(chunk);
  }

  console.log('\n');

  // Always call destroy() when you're done to stop the mDNS listener.
  saturn.destroy();
}

main().catch(error => {
  console.error('Error:', error);
  saturn.destroy();
  process.exit(1);
});

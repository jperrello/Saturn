/**
 * Example: Chat with Eliza using Saturn provider
 * 
 * This example demonstrates:
 * - Automatic service discovery via mDNS
 * - Using the Saturn provider with AI SDK
 * - Interactive chat loop
 * - Graceful error handling
 * 
 * Prerequisites:
 * 1. Start the mock server: npm run mock
 * 2. Run this example: tsx examples/chat-with-eliza.ts
 */

import { saturn } from '../src/index.js';
import { generateText } from 'ai';
import * as readline from 'node:readline';

async function main() {
  console.log('🔍 Saturn Chat Example');
  console.log('======================\n');

  // Give discovery a moment to find services
  console.log('Discovering Saturn services on the network...');
  await new Promise(resolve => setTimeout(resolve, 4000));

  // Check if any services were discovered
  const discovery = saturn.getDiscovery();
  const services = discovery.getAllServices();

  if (services.length === 0) {
    console.error('❌ No Saturn services found on the network.');
    console.error('   Make sure to start the mock server first: npm run mock');
    process.exit(1);
  }

  console.log(`✅ Found ${services.length} Saturn service(s):\n`);
  for (const service of services) {
    console.log(`   • ${service.name}`);
    console.log(`     Endpoint: ${service.endpoint}`);
    console.log(`     Priority: ${service.priority}`);
    console.log(`     Models: ${service.models.join(', ') || '(fetching...)'}`);
    console.log('');
  }

  // Try to get endpoints for the 'eliza' model
  console.log('Looking for "eliza" model...');
  const elizaEndpoints = await discovery.getEndpointsForModel('eliza');

  if (elizaEndpoints.length === 0) {
    console.error('❌ No services found with the "eliza" model.');
    process.exit(1);
  }

  console.log(`✅ Found "eliza" on ${elizaEndpoints.length} service(s)\n`);

  // Start interactive chat
  console.log('Starting chat with Eliza...');
  console.log('Type your messages (or "quit" to exit)\n');
  console.log('─'.repeat(50));

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  const conversationHistory: Array<{ role: 'user' | 'assistant'; content: string }> = [];

  const chat = async (userMessage: string) => {
    // Add user message to history
    conversationHistory.push({ role: 'user', content: userMessage });

    try {
      // Generate response using Saturn provider
      const result = await generateText({
        model: saturn('eliza'),
        messages: conversationHistory,
      });

      // Add assistant response to history
      conversationHistory.push({ role: 'assistant', content: result.text });

      console.log(`\n🤖 Eliza: ${result.text}\n`);

      // Show usage info
      if (result.usage) {
        console.log(`   [Tokens: ${result.usage.totalTokens}]`);
      }
    } catch (error) {
      if (error instanceof Error) {
        console.error(`\n❌ Error: ${error.message}\n`);
      } else {
        console.error(`\n❌ Unknown error occurred\n`);
      }
    }
  };

  // Initial greeting
  await chat('Hello');

  // Interactive loop
  const askQuestion = () => {
    rl.question('\n💬 You: ', async (input) => {
      const message = input.trim();

      if (message.toLowerCase() === 'quit' || message.toLowerCase() === 'exit') {
        console.log('\n👋 Goodbye!\n');
        rl.close();
        saturn.destroy(); // Clean up discovery
        process.exit(0);
      }

      if (!message) {
        askQuestion();
        return;
      }

      await chat(message);
      askQuestion();
    });
  };

  askQuestion();
}

// Handle Ctrl+C gracefully
process.on('SIGINT', () => {
  console.log('\n\n👋 Goodbye!\n');
  saturn.destroy();
  process.exit(0);
});

main().catch((error) => {
  console.error('Fatal error:', error);
  saturn.destroy();
  process.exit(1);
});

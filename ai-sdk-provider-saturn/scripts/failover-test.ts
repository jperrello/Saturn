import { createSaturn } from '../src/index.js';
import { generateText } from 'ai';

interface TestResult {
  timestamp: Date;
  serviceName: string;
  success: boolean;
  latencyMs: number;
  error?: string;
}

async function runFailoverTest() {
  const results: TestResult[] = [];

  console.log('='.repeat(60));
  console.log('SATURN FAILOVER TEST');
  console.log('='.repeat(60));

  const saturn = createSaturn({
    discoveryTimeout: 5000,
    logLevel: 'info',
    circuitBreakerThreshold: 2,
    circuitBreakerResetTimeout: 15000
  });

  console.log('\n[1/4] Waiting for service discovery...');
  await new Promise(r => setTimeout(r, 5000));

  const discovery = saturn.getDiscovery();
  const services = discovery.getAllServices();

  if (services.length < 2) {
    console.error('\nERROR: Need at least 2 Saturn services for failover test.');
    console.log('Currently discovered:');
    services.forEach(s => console.log(`  - ${s.name} (priority: ${s.priority})`));
    console.log('\nStart additional services:');
    console.log('  python -m saturn.openrouter_server --priority 10');
    console.log('  python -m saturn.openrouter_server --priority 20 --port 8081');
    saturn.destroy();
    process.exit(1);
  }

  console.log('\nDiscovered services (sorted by priority):');
  services
    .sort((a, b) => a.priority - b.priority)
    .forEach(s => {
      console.log(`  [${s.priority}] ${s.name} - ${s.deployment}/${s.apiType}`);
      console.log(`       Endpoint: ${s.deployment === 'cloud' ? s.apiBase : s.endpoint}`);
    });

  console.log('\n[2/4] Fetching available models...');
  await discovery.fetchAllModels();

  const allModels = new Set<string>();
  services.forEach(s => s.models.forEach(m => allModels.add(m)));
  console.log(`Found ${allModels.size} unique models across all services`);

  const testModel = 'eliza';
  console.log(`\nTest model: ${testModel}`);

  console.log('\n[3/4] Running test requests...');
  console.log('─'.repeat(60));

  const makeRequest = async (requestNum: number): Promise<TestResult> => {
    const start = Date.now();
    try {
      const result = await generateText({
        model: saturn(testModel),
        prompt: `Say "Request ${requestNum} received" and nothing else.`,
        maxTokens: 20,
      });

      const latency = Date.now() - start;

      return {
        timestamp: new Date(),
        serviceName: 'see-logs',
        success: true,
        latencyMs: latency,
      };
    } catch (error) {
      return {
        timestamp: new Date(),
        serviceName: 'unknown',
        success: false,
        latencyMs: Date.now() - start,
        error: (error as Error).message,
      };
    }
  };

  console.log('\n--- PHASE A: Normal Operation (all services up) ---\n');
  for (let i = 1; i <= 3; i++) {
    console.log(`Request ${i}...`);
    const result = await makeRequest(i);
    results.push(result);
    console.log(`  ${result.success ? '✓' : '✗'} ${result.latencyMs}ms`);
    await new Promise(r => setTimeout(r, 1000));
  }

  console.log('\n' + '='.repeat(60));
  console.log('MANUAL STEP REQUIRED');
  console.log('='.repeat(60));
  console.log('\nNow STOP the primary (lowest priority) service.');
  console.log('Options:');
  console.log('  - If using saturn-router: unplug/power off the router');
  console.log('  - If using Python server: Ctrl+C in that terminal');
  console.log('\nPress ENTER when you have stopped the primary service...');

  await new Promise<void>(resolve => {
    process.stdin.once('data', () => resolve());
  });

  console.log('\n--- PHASE B: After Primary Service Failure ---\n');
  for (let i = 4; i <= 6; i++) {
    console.log(`Request ${i}...`);
    const result = await makeRequest(i);
    results.push(result);
    console.log(`  ${result.success ? '✓' : '✗'} ${result.latencyMs}ms`);
    if (!result.success) {
      console.log(`  Error: ${result.error}`);
    }
    await new Promise(r => setTimeout(r, 1000));
  }

  console.log('\n[4/4] Test Summary');
  console.log('─'.repeat(60));

  const phaseA = results.slice(0, 3);
  const phaseB = results.slice(3, 6);

  console.log('\nPhase A (all services up):');
  console.log(`  Success rate: ${phaseA.filter(r => r.success).length}/3`);
  console.log(`  Avg latency: ${Math.round(phaseA.reduce((a, r) => a + r.latencyMs, 0) / 3)}ms`);

  console.log('\nPhase B (after primary failure):');
  console.log(`  Success rate: ${phaseB.filter(r => r.success).length}/3`);
  console.log(`  Avg latency: ${Math.round(phaseB.reduce((a, r) => a + r.latencyMs, 0) / 3)}ms`);

  const failoverSuccessful = phaseB.filter(r => r.success).length >= 2;
  console.log('\n' + '='.repeat(60));
  console.log(`FAILOVER TEST: ${failoverSuccessful ? 'PASSED ✓' : 'FAILED ✗'}`);
  console.log('='.repeat(60));

  saturn.destroy();
}

runFailoverTest().catch(console.error);

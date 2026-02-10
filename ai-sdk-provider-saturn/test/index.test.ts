import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  endpoint,
  SaturnDiscovery,
  SaturnChatLanguageModel,
  ServiceCircuitBreaker,
  createNoOpLogger,
  type DiscoveredService,
} from '../src/index.js';

function fixture(overrides: Partial<DiscoveredService> = {}): DiscoveredService {
  return {
    name: 'test-service',
    host: '192.168.1.100',
    port: 8080,
    endpoint: 'http://192.168.1.100:8080/v1',
    priority: 50,
    ephemeralKey: '',
    authType: 'none',
    capabilities: [],
    cost: 'unknown',
    models: [],
    modelsLastFetched: null,
    deployment: 'network',
    apiType: 'openai',
    apiBase: 'http://192.168.1.100:8080/v1',
    features: '',
    provider: 'Unknown',
    ...overrides,
  };
}



// ============================================================================
// endpoint
// ============================================================================

describe('endpoint', () => {
  it('returns apiBase for cloud deployments', () => {
    const s = fixture({
      deployment: 'cloud',
      apiBase: 'https://openrouter.ai/api/v1',
      endpoint: 'http://192.168.1.100:8080/v1',
    });
    assert.equal(endpoint(s), 'https://openrouter.ai/api/v1');
  });

  it('returns endpoint for network deployments', () => {
    const s = fixture({ deployment: 'network' });
    assert.equal(endpoint(s), 'http://192.168.1.100:8080/v1');
  });
});

// ============================================================================
// TXT record parsing
// ============================================================================

describe('TXT record parsing', () => {
  const discovery = new SaturnDiscovery(createNoOpLogger());

  function parse(records: string[]) {
    const partial: Record<string, unknown> = { name: 'test', lastSeen: Date.now() };
    (discovery as any).parseTxtRecords(partial, records.map((r) => Buffer.from(r)));
    return partial;
  }

  it('parses priority', () => {
    assert.equal(parse(['priority=10']).priority, 10);
  });

  it('defaults priority to 50 on invalid value', () => {
    assert.equal(parse(['priority=notanumber']).priority, 50);
  });

  it('parses ephemeral_key', () => {
    assert.equal(parse(['ephemeral_key=abc123']).ephemeralKey, 'abc123');
  });

  it('parses auth type', () => {
    assert.equal(parse(['auth=psk']).authType, 'psk');
  });

  it('parses capabilities as comma-separated list', () => {
    assert.deepEqual(parse(['capabilities=chat,code,vision']).capabilities, [
      'chat',
      'code',
      'vision',
    ]);
  });

  it('trims capability whitespace', () => {
    assert.deepEqual(parse(['capabilities=chat , code , vision']).capabilities, [
      'chat',
      'code',
      'vision',
    ]);
  });

  it('parses cost', () => {
    assert.equal(parse(['cost=free']).cost, 'free');
  });

  it('parses deployment=cloud', () => {
    assert.equal(parse(['deployment=cloud']).deployment, 'cloud');
  });

  it('parses deployment=network', () => {
    assert.equal(parse(['deployment=network']).deployment, 'network');
  });

  it('ignores invalid deployment', () => {
    assert.equal(parse(['deployment=invalid']).deployment, undefined);
  });

  it('parses api_type=ollama', () => {
    assert.equal(parse(['api_type=ollama']).apiType, 'ollama');
  });

  it('parses api_type=openai', () => {
    assert.equal(parse(['api_type=openai']).apiType, 'openai');
  });

  it('ignores invalid api_type', () => {
    assert.equal(parse(['api_type=invalid']).apiType, undefined);
  });

  it('parses api_base', () => {
    assert.equal(
      parse(['api_base=https://openrouter.ai/api/v1']).apiBase,
      'https://openrouter.ai/api/v1'
    );
  });

  it('parses features', () => {
    assert.equal(parse(['features=streaming,tools']).features, 'streaming,tools');
  });

  it('skips entries without =', () => {
    const p = parse(['noequals']);
    assert.equal(p.priority, undefined);
  });

  it('handles case-insensitive keys', () => {
    const p = parse(['PRIORITY=10', 'Auth=psk']);
    assert.equal(p.priority, 10);
    assert.equal(p.authType, 'psk');
  });

  it('parses all fields together', () => {
    const p = parse([
      'priority=10',
      'auth=bearer',
      'deployment=cloud',
      'api_type=openai',
      'api_base=https://openrouter.ai/api/v1',
      'capabilities=chat,vision',
      'cost=paid',
      'ephemeral_key=sk-abc',
      'features=streaming',
    ]);
    assert.equal(p.priority, 10);
    assert.equal(p.authType, 'bearer');
    assert.equal(p.deployment, 'cloud');
    assert.equal(p.apiType, 'openai');
    assert.equal(p.apiBase, 'https://openrouter.ai/api/v1');
    assert.deepEqual(p.capabilities, ['chat', 'vision']);
    assert.equal(p.cost, 'paid');
    assert.equal(p.ephemeralKey, 'sk-abc');
    assert.equal(p.features, 'streaming');
  });
});

// ============================================================================
// Prompt conversion
// ============================================================================

describe('prompt conversion', () => {
  const logger = createNoOpLogger();
  const discovery = new SaturnDiscovery(logger);
  const breaker = new ServiceCircuitBreaker();
  const model = new SaturnChatLanguageModel(
    'test',
    discovery,
    logger,
    breaker,
    {},
    async () => {}
  );

  function convert(prompt: any[]) {
    return (model as any).convertPrompt(prompt);
  }

  it('converts system message', () => {
    const result = convert([{ role: 'system', content: 'Be helpful.' }]);
    assert.deepEqual(result, [{ role: 'system', content: 'Be helpful.' }]);
  });

  it('converts user message with single text part', () => {
    const result = convert([
      { role: 'user', content: [{ type: 'text', text: 'Hello' }] },
    ]);
    assert.deepEqual(result, [{ role: 'user', content: 'Hello' }]);
  });

  it('joins multiple user text parts with newline', () => {
    const result = convert([
      {
        role: 'user',
        content: [
          { type: 'text', text: 'Line 1' },
          { type: 'text', text: 'Line 2' },
        ],
      },
    ]);
    assert.equal(result[0].content, 'Line 1\nLine 2');
  });

  it('converts assistant text message', () => {
    const result = convert([
      { role: 'assistant', content: [{ type: 'text', text: 'Hi!' }] },
    ]);
    assert.equal(result[0].role, 'assistant');
    assert.equal(result[0].content, 'Hi!');
  });

  it('converts assistant tool call with object input', () => {
    const result = convert([
      {
        role: 'assistant',
        content: [
          {
            type: 'tool-call',
            toolCallId: 'call_1',
            toolName: 'getWeather',
            input: { location: 'SF' },
          },
        ],
      },
    ]);
    assert.equal(result[0].content, null);
    assert.equal(result[0].tool_calls.length, 1);
    assert.equal(result[0].tool_calls[0].id, 'call_1');
    assert.equal(result[0].tool_calls[0].type, 'function');
    assert.equal(result[0].tool_calls[0].function.name, 'getWeather');
    assert.equal(result[0].tool_calls[0].function.arguments, '{"location":"SF"}');
  });

  it('converts assistant tool call with string input', () => {
    const result = convert([
      {
        role: 'assistant',
        content: [
          {
            type: 'tool-call',
            toolCallId: 'call_2',
            toolName: 'search',
            input: '{"q":"test"}',
          },
        ],
      },
    ]);
    assert.equal(result[0].tool_calls[0].function.arguments, '{"q":"test"}');
  });

  it('converts assistant with text and tool calls', () => {
    const result = convert([
      {
        role: 'assistant',
        content: [
          { type: 'text', text: 'Let me check.' },
          {
            type: 'tool-call',
            toolCallId: 'call_1',
            toolName: 'lookup',
            input: { id: 42 },
          },
        ],
      },
    ]);
    assert.equal(result[0].content, 'Let me check.');
    assert.equal(result[0].tool_calls.length, 1);
  });

  it('converts tool result with object output', () => {
    const result = convert([
      {
        role: 'tool',
        content: [
          { type: 'tool-result', toolCallId: 'call_1', output: { temp: 72 } },
        ],
      },
    ]);
    assert.equal(result[0].role, 'tool');
    assert.equal(result[0].tool_call_id, 'call_1');
    assert.equal(result[0].content, '{"temp":72}');
  });

  it('converts tool result with string output', () => {
    const result = convert([
      {
        role: 'tool',
        content: [
          { type: 'tool-result', toolCallId: 'call_1', output: 'sunny' },
        ],
      },
    ]);
    assert.equal(result[0].content, 'sunny');
  });

  it('converts tool result with { text } output', () => {
    const result = convert([
      {
        role: 'tool',
        content: [
          { type: 'tool-result', toolCallId: 'call_1', output: { text: 'hello' } },
        ],
      },
    ]);
    assert.equal(result[0].content, 'hello');
  });

  it('handles full multi-turn conversation', () => {
    const result = convert([
      { role: 'system', content: 'You are a weather bot.' },
      { role: 'user', content: [{ type: 'text', text: 'Weather?' }] },
      {
        role: 'assistant',
        content: [
          { type: 'tool-call', toolCallId: 'c1', toolName: 'weather', input: { city: 'SF' } },
        ],
      },
      {
        role: 'tool',
        content: [
          { type: 'tool-result', toolCallId: 'c1', output: { temp: 65 } },
        ],
      },
      {
        role: 'assistant',
        content: [{ type: 'text', text: '65F in SF.' }],
      },
    ]);
    assert.equal(result.length, 5);
    assert.equal(result[0].role, 'system');
    assert.equal(result[1].role, 'user');
    assert.equal(result[2].role, 'assistant');
    assert.equal(result[3].role, 'tool');
    assert.equal(result[4].role, 'assistant');
    assert.equal(result[4].content, '65F in SF.');
  });
});

// ============================================================================
// Finish reason mapping
// ============================================================================

describe('finish reason mapping', () => {
  const logger = createNoOpLogger();
  const discovery = new SaturnDiscovery(logger);
  const breaker = new ServiceCircuitBreaker();
  const model = new SaturnChatLanguageModel(
    'test',
    discovery,
    logger,
    breaker,
    {},
    async () => {}
  );

  function map(reason: string | null) {
    return (model as any).mapFinishReason(reason);
  }

  it('maps stop', () => {
    assert.deepEqual(map('stop'), { unified: 'stop', raw: 'stop' });
  });

  it('maps length', () => {
    assert.deepEqual(map('length'), { unified: 'length', raw: 'length' });
  });

  it('maps tool_calls', () => {
    assert.deepEqual(map('tool_calls'), { unified: 'tool-calls', raw: 'tool_calls' });
  });

  it('maps content_filter', () => {
    assert.deepEqual(map('content_filter'), { unified: 'content-filter', raw: 'content_filter' });
  });

  it('maps error', () => {
    assert.deepEqual(map('error'), { unified: 'error', raw: 'error' });
  });

  it('maps unknown to other', () => {
    assert.deepEqual(map('something_else'), { unified: 'other', raw: 'something_else' });
  });

  it('maps null to other with undefined raw', () => {
    assert.deepEqual(map(null), { unified: 'other', raw: undefined });
  });
});

// ============================================================================
// Priority sorting / service selection
// ============================================================================

describe('priority sorting', () => {
  it('returns services sorted by priority (lowest first)', async () => {
    const discovery = new SaturnDiscovery(createNoOpLogger());
    const services = (discovery as any).services as Map<string, DiscoveredService>;

    services.set('high', fixture({
      name: 'high',
      priority: 100,
      models: ['gpt-4'],
      modelsLastFetched: Date.now(),
    }));
    services.set('low', fixture({
      name: 'low',
      priority: 10,
      models: ['gpt-4'],
      modelsLastFetched: Date.now(),
    }));
    services.set('mid', fixture({
      name: 'mid',
      priority: 50,
      models: ['gpt-4'],
      modelsLastFetched: Date.now(),
    }));

    const result = await discovery.getEndpointsForModel('gpt-4');
    assert.equal(result.length, 3);
    assert.equal(result[0].name, 'low');
    assert.equal(result[1].name, 'mid');
    assert.equal(result[2].name, 'high');
  });

  it('filters to only services with the requested model', async () => {
    const discovery = new SaturnDiscovery(createNoOpLogger());
    const services = (discovery as any).services as Map<string, DiscoveredService>;

    services.set('has-it', fixture({
      name: 'has-it',
      priority: 10,
      models: ['llama3.2', 'gpt-4'],
      modelsLastFetched: Date.now(),
    }));
    services.set('nope', fixture({
      name: 'nope',
      priority: 5,
      models: ['gpt-4'],
      modelsLastFetched: Date.now(),
    }));

    const result = await discovery.getEndpointsForModel('llama3.2');
    assert.equal(result.length, 1);
    assert.equal(result[0].name, 'has-it');
  });

  it('returns empty array when no services have the model', async () => {
    const discovery = new SaturnDiscovery(createNoOpLogger());
    const services = (discovery as any).services as Map<string, DiscoveredService>;

    services.set('svc', fixture({
      name: 'svc',
      models: ['gpt-4'],
      modelsLastFetched: Date.now(),
    }));

    const result = await discovery.getEndpointsForModel('nonexistent');
    assert.equal(result.length, 0);
  });
});

// ============================================================================
// Circuit breaker
// ============================================================================

describe('circuit breaker', () => {
  it('starts available', () => {
    const cb = new ServiceCircuitBreaker();
    assert.equal(cb.isAvailable('svc'), true);
  });

  it('stays available below threshold', () => {
    const cb = new ServiceCircuitBreaker(3);
    cb.recordFailure('svc');
    cb.recordFailure('svc');
    assert.equal(cb.isAvailable('svc'), true);
  });

  it('opens after reaching threshold', () => {
    const cb = new ServiceCircuitBreaker(3);
    cb.recordFailure('svc');
    cb.recordFailure('svc');
    cb.recordFailure('svc');
    assert.equal(cb.isAvailable('svc'), false);
  });

  it('resets on success', () => {
    const cb = new ServiceCircuitBreaker(3);
    cb.recordFailure('svc');
    cb.recordFailure('svc');
    cb.recordSuccess('svc');
    cb.recordFailure('svc');
    cb.recordFailure('svc');
    // 2 failures after reset - still below threshold
    assert.equal(cb.isAvailable('svc'), true);
  });

  it('transitions to half-open after reset timeout', () => {
    const cb = new ServiceCircuitBreaker(2, 100);
    cb.recordFailure('svc');
    cb.recordFailure('svc');
    assert.equal(cb.isAvailable('svc'), false);

    // Manually backdate lastFailure to simulate timeout
    const circuit = (cb as any).circuits.get('svc');
    circuit.lastFailure = Date.now() - 200;
    assert.equal(cb.isAvailable('svc'), true);
    assert.equal(circuit.state, 'half-open');
  });

  it('isolates circuits per service', () => {
    const cb = new ServiceCircuitBreaker(2);
    cb.recordFailure('a');
    cb.recordFailure('a');
    assert.equal(cb.isAvailable('a'), false);
    assert.equal(cb.isAvailable('b'), true);
  });
});

// ============================================================================
// Stream chunk transformation
// ============================================================================

describe('stream chunk transformation', () => {
  const logger = createNoOpLogger();
  const discovery = new SaturnDiscovery(logger);
  const breaker = new ServiceCircuitBreaker();
  const model = new SaturnChatLanguageModel(
    'test',
    discovery,
    logger,
    breaker,
    {},
    async () => {}
  );

  function sse(...events: string[]): Response {
    const body =
      events.map((e) => `data: ${e}\n\n`).join('') + 'data: [DONE]\n\n';
    return new Response(body, {
      headers: { 'Content-Type': 'text/event-stream' },
    });
  }

  async function collect(response: Response): Promise<any[]> {
    const stream: ReadableStream = (model as any).createFailoverStream(response, [], {}, []);
    const reader = stream.getReader();
    const parts: any[] = [];
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      parts.push(value);
    }
    return parts;
  }

  it('emits stream-start, response-metadata, text events, and finish', async () => {
    const chunk1 = JSON.stringify({
      id: 'cmpl-1',
      model: 'gpt-4',
      created: 1700000000,
      choices: [{ index: 0, delta: { content: 'Hello' }, finish_reason: null }],
    });
    const chunk2 = JSON.stringify({
      id: 'cmpl-1',
      model: 'gpt-4',
      created: 1700000000,
      choices: [{ index: 0, delta: { content: ' world' }, finish_reason: null }],
    });

    const parts = await collect(sse(chunk1, chunk2));

    assert.equal(parts[0].type, 'stream-start');
    assert.equal(parts[1].type, 'response-metadata');
    assert.equal(parts[1].modelId, 'gpt-4');
    assert.equal(parts[1].id, 'cmpl-1');
    assert.equal(parts[2].type, 'text-start');
    assert.equal(parts[3].type, 'text-delta');
    assert.equal(parts[3].delta, 'Hello');
    assert.equal(parts[4].type, 'text-delta');
    assert.equal(parts[4].delta, ' world');
    // [DONE] triggers text-end + finish
    assert.equal(parts[5].type, 'text-end');
    assert.equal(parts[6].type, 'finish');
  });

  it('captures finish reason and usage from final chunk', async () => {
    const chunk1 = JSON.stringify({
      id: 'cmpl-1',
      model: 'gpt-4',
      created: 1700000000,
      choices: [{ index: 0, delta: { content: 'Hi' }, finish_reason: null }],
    });
    const chunk2 = JSON.stringify({
      id: 'cmpl-1',
      model: 'gpt-4',
      choices: [{ index: 0, delta: {}, finish_reason: 'stop' }],
      usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
    });

    const parts = await collect(sse(chunk1, chunk2));
    const finish = parts.find((p: any) => p.type === 'finish');
    assert.equal(finish.finishReason.unified, 'stop');
    assert.equal(finish.usage.inputTokens.total, 10);
    assert.equal(finish.usage.outputTokens.total, 5);
  });

  it('handles tool call streaming', async () => {
    const chunk1 = JSON.stringify({
      id: 'cmpl-1',
      model: 'gpt-4',
      created: 1700000000,
      choices: [{
        index: 0,
        delta: {
          tool_calls: [{
            index: 0,
            id: 'tc_1',
            type: 'function',
            function: { name: 'getWeather', arguments: '' },
          }],
        },
        finish_reason: null,
      }],
    });
    const chunk2 = JSON.stringify({
      id: 'cmpl-1',
      model: 'gpt-4',
      choices: [{
        index: 0,
        delta: {
          tool_calls: [{
            index: 0,
            function: { arguments: '{"city":"SF"}' },
          }],
        },
        finish_reason: null,
      }],
    });
    const chunk3 = JSON.stringify({
      id: 'cmpl-1',
      model: 'gpt-4',
      choices: [{ index: 0, delta: {}, finish_reason: 'tool_calls' }],
    });

    const parts = await collect(sse(chunk1, chunk2, chunk3));

    const toolStart = parts.find((p: any) => p.type === 'tool-input-start');
    assert.ok(toolStart);
    assert.equal(toolStart.id, 'tc_1');
    assert.equal(toolStart.toolName, 'getWeather');

    const toolDelta = parts.find((p: any) => p.type === 'tool-input-delta');
    assert.ok(toolDelta);
    assert.equal(toolDelta.delta, '{"city":"SF"}');

    const toolEnd = parts.find((p: any) => p.type === 'tool-input-end');
    assert.ok(toolEnd);
    assert.equal(toolEnd.id, 'tc_1');

    const finish = parts.find((p: any) => p.type === 'finish');
    assert.equal(finish.finishReason.unified, 'tool-calls');
  });

  it('handles empty stream (just [DONE])', async () => {
    const parts = await collect(sse());

    assert.equal(parts[0].type, 'stream-start');
    assert.equal(parts[1].type, 'finish');
    assert.equal(parts[1].finishReason.unified, 'other');
  });
});

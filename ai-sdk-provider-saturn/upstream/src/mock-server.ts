#!/usr/bin/env node
/**
 * Saturn Mock Server - Eliza Chatbot
 *
 * A test server that announces itself via mDNS and serves an ELIZA-style chatbot.
 * Features ephemeral API key rotation for testing Saturn's key discovery.
 */

import { createServer, IncomingMessage, ServerResponse } from 'node:http';
import { randomUUID } from 'node:crypto';
import { hostname, networkInterfaces } from 'node:os';
import multicastDns from 'multicast-dns';

// ============================================================================
// Configuration
// ============================================================================

interface ServerConfig {
  port: number;
  priority: number;
  serviceName: string;
  rotationSeconds: number;
}

function parseArgs(): ServerConfig {
  const args = process.argv.slice(2);
  const config: ServerConfig = {
    port: 0, // 0 = random available port
    priority: 50,
    serviceName: 'Eliza',
    rotationSeconds: 60,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    const next = args[i + 1];

    if ((arg === '--port' || arg === '-p') && next) {
      config.port = parseInt(next, 10);
      i++;
    } else if (arg === '--priority' && next) {
      config.priority = parseInt(next, 10);
      i++;
    } else if ((arg === '--name' || arg === '-n') && next) {
      config.serviceName = next;
      i++;
    } else if ((arg === '--rotation' || arg === '-r') && next) {
      config.rotationSeconds = parseInt(next, 10);
      i++;
    } else if (arg === '--help' || arg === '-h') {
      console.log(`
Saturn Mock Server (Eliza)

Usage: saturn-mock-server [options]

Options:
  --port, -p       Port to listen on (default: random available)
  --priority       Service priority (default: 50)
  --name, -n       Service name (default: "Eliza")
  --rotation, -r   Key rotation interval in seconds (default: 60)
  --help, -h       Show this help message
`);
      process.exit(0);
    }
  }

  return config;
}

// ============================================================================
// ELIZA Chatbot
// ============================================================================

interface ElizaPattern {
  pattern: RegExp;
  responses: string[];
}

const elizaPatterns: ElizaPattern[] = [
  {
    pattern: /I need (.*)/i,
    responses: [
      'Why do you need $1?',
      'Would it really help you to get $1?',
      'Are you sure you need $1?',
    ],
  },
  {
    pattern: /Why don'?t you (.*)/i,
    responses: [
      "Do you really think I don't $1?",
      'Perhaps eventually I will $1.',
      'Do you really want me to $1?',
    ],
  },
  {
    pattern: /Why can'?t I (.*)/i,
    responses: [
      'Do you think you should be able to $1?',
      'If you could $1, what would you do?',
      "I don't know -- why can't you $1?",
      "Have you really tried to $1?",
    ],
  },
  {
    pattern: /I can'?t (.*)/i,
    responses: [
      "How do you know you can't $1?",
      'Perhaps you could $1 if you tried.',
      'What would it take for you to $1?',
    ],
  },
  {
    pattern: /I am (.*)/i,
    responses: [
      'Did you come to me because you are $1?',
      'How long have you been $1?',
      'How do you feel about being $1?',
      'How does being $1 make you feel?',
    ],
  },
  {
    pattern: /I'?m (.*)/i,
    responses: [
      'How does being $1 make you feel?',
      'Do you enjoy being $1?',
      'Why do you tell me you are $1?',
      'Why do you think you are $1?',
    ],
  },
  {
    pattern: /Are you (.*)/i,
    responses: [
      'Why does it matter whether I am $1?',
      'Would you prefer it if I were not $1?',
      'Perhaps you believe I am $1.',
      'I may be $1 -- what do you think?',
    ],
  },
  {
    pattern: /What (.*)/i,
    responses: [
      'Why do you ask?',
      'How would an answer to that help you?',
      'What do you think?',
    ],
  },
  {
    pattern: /How (.*)/i,
    responses: [
      'How do you suppose?',
      'Perhaps you can answer your own question.',
      'What is it you are really asking?',
    ],
  },
  {
    pattern: /Because (.*)/i,
    responses: [
      'Is that the real reason?',
      'What other reasons come to mind?',
      'Does that reason apply to anything else?',
      'If $1, what else must be true?',
    ],
  },
  {
    pattern: /(.*) sorry (.*)/i,
    responses: [
      'There are many times when no apology is needed.',
      'What feelings do you have when you apologize?',
    ],
  },
  {
    pattern: /Hello(.*)/i,
    responses: [
      'Hello... I am glad you could drop by today.',
      'Hi there... how are you today?',
      'Hello, how are you feeling today?',
    ],
  },
  {
    pattern: /I think (.*)/i,
    responses: [
      'Do you doubt $1?',
      'Do you really think so?',
      'But you are not sure $1?',
    ],
  },
  {
    pattern: /(.*) friend (.*)/i,
    responses: [
      'Tell me more about your friends.',
      'When you think of a friend, what comes to mind?',
      'Why don\'t you tell me about a childhood friend?',
    ],
  },
  {
    pattern: /Yes/i,
    responses: [
      'You seem quite sure.',
      'OK, but can you elaborate a bit?',
    ],
  },
  {
    pattern: /(.*) computer(.*)/i,
    responses: [
      'Are you really talking about me?',
      'Does it seem strange to talk to a computer?',
      'How do computers make you feel?',
      'Do you feel threatened by computers?',
    ],
  },
  {
    pattern: /Is it (.*)/i,
    responses: [
      'Do you think it is $1?',
      'Perhaps it is $1 -- what do you think?',
      'If it were $1, what would you do?',
      'It could well be that it is $1.',
    ],
  },
  {
    pattern: /It is (.*)/i,
    responses: [
      'You seem very certain.',
      'If I told you that it probably is not $1, what would you feel?',
    ],
  },
  {
    pattern: /Can you (.*)/i,
    responses: [
      "What makes you think I can't $1?",
      'If I could $1, then what?',
      'Why do you ask if I can $1?',
    ],
  },
  {
    pattern: /Can I (.*)/i,
    responses: [
      'Perhaps you don\'t want to $1.',
      'Do you want to be able to $1?',
      'If you could $1, would you?',
    ],
  },
  {
    pattern: /You are (.*)/i,
    responses: [
      'Why do you think I am $1?',
      'Does it please you to think that I am $1?',
      'Perhaps you would like me to be $1.',
      'Perhaps you are really talking about yourself?',
    ],
  },
  {
    pattern: /You'?re (.*)/i,
    responses: [
      'Why do you say I am $1?',
      'Why do you think I am $1?',
      'Are we talking about you, or me?',
    ],
  },
  {
    pattern: /I don'?t (.*)/i,
    responses: [
      "Don't you really $1?",
      'Why don\'t you $1?',
      'Do you want to $1?',
    ],
  },
  {
    pattern: /I feel (.*)/i,
    responses: [
      'Good, tell me more about these feelings.',
      'Do you often feel $1?',
      'When do you usually feel $1?',
      'When you feel $1, what do you do?',
    ],
  },
  {
    pattern: /I have (.*)/i,
    responses: [
      'Why do you tell me that you have $1?',
      'Have you really got $1?',
      'Now that you have $1, what will you do next?',
    ],
  },
  {
    pattern: /I would (.*)/i,
    responses: [
      'Could you explain why you would $1?',
      'Why would you $1?',
      'Who else knows that you would $1?',
    ],
  },
  {
    pattern: /Is there (.*)/i,
    responses: [
      'Do you think there is $1?',
      'It is likely that there is $1.',
      'Would you like there to be $1?',
    ],
  },
  {
    pattern: /My (.*)/i,
    responses: [
      'I see, your $1.',
      'Why do you say that your $1?',
      'When your $1, how do you feel?',
    ],
  },
  {
    pattern: /You (.*)/i,
    responses: [
      'We should be discussing you, not me.',
      'Why do you say that about me?',
      'Why do you care whether I $1?',
    ],
  },
  {
    pattern: /Why (.*)/i,
    responses: [
      'Why don\'t you tell me the reason why $1?',
      'Why do you think $1?',
    ],
  },
  {
    pattern: /I want (.*)/i,
    responses: [
      'What would it mean to you if you got $1?',
      'Why do you want $1?',
      'What would you do if you got $1?',
      'If you got $1, then what would you do?',
    ],
  },
  {
    pattern: /(.*) mother(.*)/i,
    responses: [
      'Tell me more about your mother.',
      'What was your relationship with your mother like?',
      'How do you feel about your mother?',
      'How does this relate to your feelings today?',
    ],
  },
  {
    pattern: /(.*) father(.*)/i,
    responses: [
      'Tell me more about your father.',
      'How did your father make you feel?',
      'How do you feel about your father?',
      'Does your relationship with your father relate to your feelings today?',
    ],
  },
  {
    pattern: /(.*) child(.*)/i,
    responses: [
      'Did you have close friends as a child?',
      'What is your favorite childhood memory?',
      'Do you remember any dreams or nightmares from childhood?',
    ],
  },
  {
    pattern: /(.*)\?/,
    responses: [
      'Why do you ask that?',
      'Please consider whether you can answer your own question.',
      'Perhaps the answer lies within yourself.',
      'Why don\'t you tell me?',
    ],
  },
];

const defaultResponses = [
  'Please tell me more.',
  'Let\'s change focus a bit... Tell me about your family.',
  'Can you elaborate on that?',
  'Why do you say that?',
  'I see.',
  'Very interesting.',
  'I see. And what does that tell you?',
  'How does that make you feel?',
  'How do you feel when you say that?',
];

function generateElizaResponse(input: string): string {
  const trimmed = input.trim();

  for (const { pattern, responses } of elizaPatterns) {
    const match = trimmed.match(pattern);
    if (match) {
      const response = responses[Math.floor(Math.random() * responses.length)];
      // Replace $1, $2, etc. with captured groups
      let result = response;
      for (let i = 1; i < match.length; i++) {
        result = result.replace(new RegExp(`\\$${i}`, 'g'), match[i] || '');
      }
      // Clean up the response
      result = result
        .replace(/\bi am\b/gi, 'you are')
        .replace(/\bi'm\b/gi, "you're")
        .replace(/\bmy\b/gi, 'your')
        .replace(/\bme\b/gi, 'you')
        .replace(/\bmyself\b/gi, 'yourself');
      return result;
    }
  }

  return defaultResponses[Math.floor(Math.random() * defaultResponses.length)];
}

// ============================================================================
// Ephemeral Key Manager
// ============================================================================

class KeyManager {
  private currentKey: string = '';
  private rotationInterval: NodeJS.Timeout | null = null;
  private onRotate: (key: string) => void;

  constructor(rotationSeconds: number, onRotate: (key: string) => void) {
    this.onRotate = onRotate;
    this.rotate();

    this.rotationInterval = setInterval(() => {
      this.rotate();
    }, rotationSeconds * 1000);
  }

  rotate(): void {
    // Base64-encoded UUID (~48 chars)
    this.currentKey = Buffer.from(randomUUID()).toString('base64');
    console.log(`\n🔑 API Key rotated: ${this.currentKey.slice(0, 20)}...`);
    this.onRotate(this.currentKey);
  }

  validate(key: string): boolean {
    return key === this.currentKey;
  }

  getCurrentKey(): string {
    return this.currentKey;
  }

  stop(): void {
    if (this.rotationInterval) {
      clearInterval(this.rotationInterval);
      this.rotationInterval = null;
    }
  }
}

// ============================================================================
// mDNS Announcer
// ============================================================================

class MdnsAnnouncer {
  private mdns: ReturnType<typeof multicastDns>;
  private config: ServerConfig;
  private actualPort: number;
  private currentKey: string = '';
  private announceInterval: NodeJS.Timeout | null = null;

  constructor(config: ServerConfig, actualPort: number) {
    this.config = config;
    this.actualPort = actualPort;
    this.mdns = multicastDns();

    // Respond to queries for our service
    this.mdns.on('query', (query) => {
      for (const question of query.questions) {
        if (
          question.name === '_saturn._tcp.local' ||
          question.name === `${this.config.serviceName}._saturn._tcp.local`
        ) {
          this.announce();
        }
      }
    });
  }

  updateKey(key: string): void {
    this.currentKey = key;
    this.announce();
  }

  announce(): void {
    const hostname = getLocalHostname();
    const ip = getLocalIp();
    const serviceName = this.config.serviceName;
    const instanceName = `${serviceName}._saturn._tcp.local`;

    this.mdns.respond({
      answers: [
        // PTR record: service type → instance name
        {
          name: '_saturn._tcp.local',
          type: 'PTR',
          ttl: 120,
          data: instanceName,
        },
        // SRV record: instance → host:port
        {
          name: instanceName,
          type: 'SRV',
          ttl: 120,
          data: {
            priority: 0,
            weight: 0,
            port: this.actualPort,
            target: `${hostname}.local`,
          },
        },
        // TXT record: metadata
        {
          name: instanceName,
          type: 'TXT',
          ttl: 120,
          data: [
            'txtvers=1',
            'saturn=2.0',
            `priority=${this.config.priority}`,
            'transport=http',
            'auth=psk',
            'cost=free',
            'capabilities=chat',
            `ephemeral_key=${this.currentKey}`,
          ],
        },
        // A record: hostname → IP
        {
          name: `${hostname}.local`,
          type: 'A',
          ttl: 120,
          data: ip,
        },
      ],
    });
  }

  startPeriodicAnnounce(): void {
    // Announce immediately
    this.announce();

    // Re-announce periodically (mDNS TTL refresh)
    this.announceInterval = setInterval(() => {
      this.announce();
    }, 30000); // Every 30 seconds
  }

  stop(): void {
    if (this.announceInterval) {
      clearInterval(this.announceInterval);
      this.announceInterval = null;
    }
    this.mdns.destroy();
  }
}

// ============================================================================
// HTTP Server
// ============================================================================

function createHttpServer(config: ServerConfig, keyManager: KeyManager) {
  const server = createServer(async (req: IncomingMessage, res: ServerResponse) => {
    // CORS headers
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

    if (req.method === 'OPTIONS') {
      res.writeHead(204);
      res.end();
      return;
    }

    const url = new URL(req.url || '/', `http://${req.headers.host}`);

    // Health check (no auth required)
    if (url.pathname === '/v1/health' && req.method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ok' }));
      return;
    }

    // Models list (no auth required)
    if (url.pathname === '/v1/models' && req.method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(
        JSON.stringify({
          object: 'list',
          data: [
            {
              id: 'eliza',
              object: 'model',
              created: Math.floor(Date.now() / 1000),
              owned_by: 'saturn-mock',
            },
          ],
        })
      );
      return;
    }

    // Chat completions (auth required)
    if (url.pathname === '/v1/chat/completions' && req.method === 'POST') {
      // Validate authorization
      const authHeader = req.headers.authorization;
      if (!authHeader || !authHeader.startsWith('Bearer ')) {
        res.writeHead(401, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            error: {
              message: 'Missing Authorization header',
              type: 'authentication_error',
              code: 'missing_api_key',
            },
          })
        );
        return;
      }

      const token = authHeader.slice(7);
      if (!keyManager.validate(token)) {
        res.writeHead(401, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            error: {
              message: 'Invalid or expired API key',
              type: 'authentication_error',
              code: 'invalid_api_key',
            },
          })
        );
        return;
      }

      // Parse request body
      let body = '';
      for await (const chunk of req) {
        body += chunk;
      }

      let requestData: {
        model?: string;
        messages?: Array<{ role: string; content: string }>;
        stream?: boolean;
      };

      try {
        requestData = JSON.parse(body);
      } catch {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            error: {
              message: 'Invalid JSON in request body',
              type: 'invalid_request_error',
            },
          })
        );
        return;
      }

      // Validate model
      if (requestData.model !== 'eliza') {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            error: {
              message: `Model '${requestData.model}' not found`,
              type: 'invalid_request_error',
              code: 'model_not_found',
            },
          })
        );
        return;
      }

      // Extract the last user message
      const messages = requestData.messages || [];
      const lastUserMessage = [...messages].reverse().find((m) => m.role === 'user');
      const userInput = lastUserMessage?.content || '';

      // Generate Eliza response
      const elizaResponse = generateElizaResponse(userInput);

      // Calculate fake token counts
      const promptTokens = Math.ceil(userInput.length / 4);
      const completionTokens = Math.ceil(elizaResponse.length / 4);

      const responseId = `chatcmpl-eliza-${randomUUID().slice(0, 8)}`;
      const timestamp = Math.floor(Date.now() / 1000);

      // Handle streaming
      if (requestData.stream) {
        res.writeHead(200, {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        });

        // Send response metadata
        res.write(
          `data: ${JSON.stringify({
            id: responseId,
            object: 'chat.completion.chunk',
            created: timestamp,
            model: 'eliza',
            choices: [{ index: 0, delta: { role: 'assistant' }, finish_reason: null }],
          })}\n\n`
        );

        // Send content in one chunk (no artificial delay)
        res.write(
          `data: ${JSON.stringify({
            id: responseId,
            object: 'chat.completion.chunk',
            created: timestamp,
            model: 'eliza',
            choices: [{ index: 0, delta: { content: elizaResponse }, finish_reason: null }],
          })}\n\n`
        );

        // Send finish event with usage
        res.write(
          `data: ${JSON.stringify({
            id: responseId,
            object: 'chat.completion.chunk',
            created: timestamp,
            model: 'eliza',
            choices: [{ index: 0, delta: {}, finish_reason: 'stop' }],
            usage: {
              prompt_tokens: promptTokens,
              completion_tokens: completionTokens,
              total_tokens: promptTokens + completionTokens,
            },
          })}\n\n`
        );

        res.write('data: [DONE]\n\n');
        res.end();
        return;
      }

      // Non-streaming response
      const responseData = {
        id: responseId,
        object: 'chat.completion',
        created: timestamp,
        model: 'eliza',
        choices: [
          {
            index: 0,
            message: {
              role: 'assistant',
              content: elizaResponse,
            },
            finish_reason: 'stop',
          },
        ],
        usage: {
          prompt_tokens: promptTokens,
          completion_tokens: completionTokens,
          total_tokens: promptTokens + completionTokens,
        },
      };

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(responseData));
      return;
    }

    // 404 for unknown endpoints
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(
      JSON.stringify({
        error: {
          message: `Unknown endpoint: ${req.method} ${url.pathname}`,
          type: 'invalid_request_error',
        },
      })
    );
  });

  return server;
}

// ============================================================================
// Utilities
// ============================================================================

function getLocalIp(): string {
  const interfaces = networkInterfaces();
  for (const name of Object.keys(interfaces)) {
    for (const iface of interfaces[name] || []) {
      // Skip loopback and non-IPv4
      if (iface.family === 'IPv4' && !iface.internal) {
        return iface.address;
      }
    }
  }
  return '127.0.0.1';
}

function getLocalHostname(): string {
  return process.env.HOSTNAME || hostname().split('.')[0];
}

// ============================================================================
// Main
// ============================================================================

async function main() {
  const config = parseArgs();

  console.log(`
🤖 Saturn Mock Server (Eliza)
`);

  // Create key manager (will rotate on start)
  let announcer: MdnsAnnouncer | null = null;
  const keyManager = new KeyManager(config.rotationSeconds, (key) => {
    if (announcer) {
      announcer.updateKey(key);
    }
  });

  // Create HTTP server
  const server = createHttpServer(config, keyManager);

  // Start server
  await new Promise<void>((resolve) => {
    server.listen(config.port, () => resolve());
  });

  const address = server.address();
  const actualPort = typeof address === 'object' && address ? address.port : config.port;
  const localIp = getLocalIp();

  console.log(`   Endpoint: http://${localIp}:${actualPort}/v1`);
  console.log(`   Model: eliza`);
  console.log(`   Priority: ${config.priority}`);
  console.log(`   Key rotation: every ${config.rotationSeconds}s`);

  // Start mDNS announcer
  announcer = new MdnsAnnouncer(config, actualPort);
  announcer.updateKey(keyManager.getCurrentKey());
  announcer.startPeriodicAnnounce();

  console.log(`\n📡 Announcing via mDNS: ${config.serviceName}._saturn._tcp.local`);
  console.log(`\nPress Ctrl+C to stop\n`);

  // Graceful shutdown
  const shutdown = () => {
    console.log('\n\nShutting down...');
    keyManager.stop();
    announcer?.stop();
    server.close(() => {
      console.log('Server stopped');
      process.exit(0);
    });
  };

  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});

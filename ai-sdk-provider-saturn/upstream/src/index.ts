/**
 * AI SDK Provider for Saturn - Zero-Configuration AI Service Discovery
 *
 * This provider discovers Saturn services on the local network via mDNS/DNS-SD
 * and routes AI SDK requests to discovered endpoints with automatic failover.
 */

import {
  JSONValue,
  LanguageModelV2,
  LanguageModelV2CallOptions,
  LanguageModelV2CallWarning,
  LanguageModelV2Content,
  LanguageModelV2FinishReason,
  LanguageModelV2Prompt,
  LanguageModelV2StreamPart,
  LanguageModelV2Usage,
  NoSuchModelError,
  ProviderV2,
  SharedV2ProviderMetadata,
} from '@ai-sdk/provider';
import { generateId } from '@ai-sdk/provider-utils';
import multicastDns from 'multicast-dns';

// ============================================================================
// Logging
// ============================================================================

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface SaturnLogger {
  log(level: LogLevel, message: string, data?: Record<string, unknown>): void;
}

const LOG_LEVEL_PRIORITY: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

function createDefaultLogger(minLevel: LogLevel = 'info'): SaturnLogger {
  const minPriority = LOG_LEVEL_PRIORITY[minLevel];
  return {
    log(level, message, data) {
      if (LOG_LEVEL_PRIORITY[level] < minPriority) return;
      const prefix = `[Saturn/${level.toUpperCase()}]`;
      const logFn = level === 'debug' ? console.log : console[level];
      if (data) {
        logFn(`${prefix} ${message}`, data);
      } else {
        logFn(`${prefix} ${message}`);
      }
    },
  };
}

export function createNoOpLogger(): SaturnLogger {
  return {
    log(_level, _message, _data) {
      // Silent - no output to avoid corrupting TUI applications
    },
  };
}

// ============================================================================
// Types
// ============================================================================

export type DeploymentType = 'cloud' | 'network';
export type ApiType = 'openai' | 'ollama';

export interface DiscoveredService {
  name: string;
  host: string;
  port: number;
  endpoint: string;
  priority: number;
  ephemeralKey: string;
  authType: 'none' | 'psk' | 'bearer';
  capabilities: string[];
  cost: 'free' | 'paid' | 'unknown';
  models: string[];
  modelsLastFetched: number | null;
  deployment: DeploymentType;
  apiType: ApiType;
  apiBase: string;
  features: string;
  provider: string;
}

interface PartialService {
  name: string;
  host?: string;
  port?: number;
  priority?: number;
  ephemeralKey?: string;
  authType?: 'none' | 'psk' | 'bearer';
  capabilities?: string[];
  cost?: 'free' | 'paid' | 'unknown';
  lastSeen: number;
  deployment?: DeploymentType;
  apiType?: ApiType;
  apiBase?: string;
  features?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

export function isCloudDeployment(service: DiscoveredService): boolean {
  return service.deployment === 'cloud';
}

export function getEffectiveEndpoint(service: DiscoveredService): string {
  if (service.deployment === 'cloud') {
    return service.apiBase;
  }
  return service.endpoint;
}

export function extractProvider(apiBase: string): string {
  try {
    const url = new URL(apiBase);
    const host = url.hostname.toLowerCase();
    if (host.includes('openrouter')) return 'OpenRouter';
    if (host.includes('openai')) return 'OpenAI';
    if (host.includes('deepinfra')) return 'DeepInfra';
    if (host.includes('anthropic')) return 'Anthropic';
    if (host.includes('together')) return 'Together';
    if (host.includes('groq')) return 'Groq';
    return host;
  } catch {
    return 'Unknown';
  }
}

function isIPAddress(host: string): boolean {
  const ipv4Regex = /^(\d{1,3}\.){3}\d{1,3}$/;
  const ipv6Regex = /^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|^::1$/;
  return ipv4Regex.test(host) || ipv6Regex.test(host);
}

// ============================================================================
// Error Recovery
// ============================================================================

interface RetryOptions {
  maxAttempts: number;
  baseDelay: number;
  maxDelay: number;
}

async function withRetry<T>(
  fn: () => Promise<T>,
  options: RetryOptions,
  logger?: SaturnLogger
): Promise<T> {
  let lastError: Error | undefined;

  for (let attempt = 0; attempt < options.maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      if (attempt < options.maxAttempts - 1) {
        const delay = Math.min(
          options.baseDelay * Math.pow(2, attempt),
          options.maxDelay
        );
        logger?.log('debug', `Retry attempt ${attempt + 1}/${options.maxAttempts} after ${delay}ms`, {
          error: lastError.message,
        });
        await new Promise((r) => setTimeout(r, delay));
      }
    }
  }

  throw lastError;
}

interface CircuitState {
  failures: number;
  lastFailure: number;
  state: 'closed' | 'open' | 'half-open';
}

class ServiceCircuitBreaker {
  private circuits = new Map<string, CircuitState>();
  private readonly threshold: number;
  private readonly resetTimeout: number;

  constructor(threshold = 3, resetTimeout = 30000) {
    this.threshold = threshold;
    this.resetTimeout = resetTimeout;
  }

  recordFailure(serviceName: string): void {
    const circuit = this.circuits.get(serviceName) || {
      failures: 0,
      lastFailure: 0,
      state: 'closed' as const,
    };

    circuit.failures++;
    circuit.lastFailure = Date.now();

    if (circuit.failures >= this.threshold) {
      circuit.state = 'open';
    }

    this.circuits.set(serviceName, circuit);
  }

  recordSuccess(serviceName: string): void {
    const circuit = this.circuits.get(serviceName);
    if (circuit) {
      circuit.failures = 0;
      circuit.state = 'closed';
    }
  }

  isAvailable(serviceName: string): boolean {
    const circuit = this.circuits.get(serviceName);
    if (!circuit) return true;

    if (circuit.state === 'closed') return true;

    if (circuit.state === 'open') {
      if (Date.now() - circuit.lastFailure > this.resetTimeout) {
        circuit.state = 'half-open';
        return true;
      }
      return false;
    }

    return true;
  }
}

// ============================================================================
// OpenAI Types
// ============================================================================

interface OpenAIMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string | null;
  tool_calls?: Array<{
    id: string;
    type: 'function';
    function: { name: string; arguments: string };
  }>;
  tool_call_id?: string;
}

interface OpenAIChatResponse {
  id: string;
  object: 'chat.completion';
  created: number;
  model: string;
  choices: Array<{
    index: number;
    message: {
      role: 'assistant';
      content: string | null;
      tool_calls?: Array<{
        id: string;
        type: 'function';
        function: { name: string; arguments: string };
      }>;
    };
    finish_reason: string;
  }>;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

interface OpenAIModelsResponse {
  object: 'list';
  data: Array<{
    id: string;
    object: 'model';
    owned_by: string;
  }>;
}

// ============================================================================
// Saturn Discovery
// ============================================================================

const SATURN_SERVICE_TYPE = '_saturn._tcp.local';
const SERVICE_TIMEOUT_MS = 20000; // Reduced from 60s - goodbye packets handle normal shutdowns, this is only for crashed/unreachable services

export class SaturnDiscovery {
  private mdns: ReturnType<typeof multicastDns> | null = null;
  private services: Map<string, DiscoveredService> = new Map();
  private partialServices: Map<string, PartialService> = new Map();
  private cleanupInterval: NodeJS.Timeout | null = null;
  private queryInterval: NodeJS.Timeout | null = null;
  private started = false;
  private logger: SaturnLogger;
  private onServiceDiscovered?: (service: DiscoveredService) => void;
  private onServiceRemoved?: (serviceName: string) => void;

  constructor(
    logger?: SaturnLogger,
    onServiceDiscovered?: (service: DiscoveredService) => void,
    onServiceRemoved?: (serviceName: string) => void
  ) {
    this.logger = logger || createDefaultLogger();
    this.onServiceDiscovered = onServiceDiscovered;
    this.onServiceRemoved = onServiceRemoved;
  }

  private log(level: LogLevel, message: string, data?: Record<string, unknown>): void {
    this.logger.log(level, message, data);
  }

  start(): void {
    if (this.started) return;
    this.started = true;

    this.log('info', 'Starting mDNS discovery');

    this.mdns = multicastDns();

    this.mdns.on('response', (response) => {
      this.handleResponse(response);
    });

    this.mdns.on('error', (err: Error) => {
      this.log('error', 'mDNS socket error', { error: err.message });
    });

    this.mdns.on('warning', (err: Error) => {
      this.log('warn', 'mDNS warning', { error: err.message });
    });

    this.sendQuery();

    this.queryInterval = setInterval(() => {
      this.sendQuery();
    }, 5000); // Reduced from 10s - services announce on startup so this is just backup

    this.cleanupInterval = setInterval(() => {
      this.cleanupStaleServices();
    }, 15000);
  }

  stop(): void {
    if (!this.started) return;
    this.started = false;

    this.log('info', 'Stopping mDNS discovery', { serviceCount: this.services.size });

    if (this.queryInterval) {
      clearInterval(this.queryInterval);
      this.queryInterval = null;
    }
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
    if (this.mdns) {
      this.mdns.destroy();
      this.mdns = null;
    }
    this.services.clear();
    this.partialServices.clear();
  }

  private sendQuery(): void {
    if (!this.mdns) return;

    this.mdns.query({
      questions: [{ name: SATURN_SERVICE_TYPE, type: 'PTR' }],
    });
  }

  private handleResponse(response: multicastDns.ResponsePacket): void {
    const now = Date.now();

    for (const answer of [...response.answers, ...response.additionals]) {
      // Handle mDNS goodbye (TTL=0 means service is leaving)
      // TTL exists on mDNS packets but types don't include it
      const ttl = (answer as unknown as { ttl?: number }).ttl;
      if (ttl === 0) {
        let serviceName: string | null = null;

        if (answer.type === 'PTR' && answer.name === SATURN_SERVICE_TYPE) {
          const instanceName = answer.data as string;
          serviceName = instanceName.replace(`.${SATURN_SERVICE_TYPE}`, '');
        } else if (answer.type === 'SRV' || answer.type === 'TXT') {
          const instanceName = answer.name;
          serviceName = instanceName.replace(`.${SATURN_SERVICE_TYPE}`, '');
        }

        if (serviceName && this.services.has(serviceName)) {
          this.log('info', 'Service goodbye received', { name: serviceName });
          this.partialServices.delete(serviceName);
          this.services.delete(serviceName);
          this.onServiceRemoved?.(serviceName);
        }
        continue;
      }

      if (answer.type === 'PTR' && answer.name === SATURN_SERVICE_TYPE) {
        const instanceName = answer.data as string;
        const serviceName = instanceName.replace(`.${SATURN_SERVICE_TYPE}`, '');

        if (!this.partialServices.has(serviceName)) {
          this.partialServices.set(serviceName, {
            name: serviceName,
            lastSeen: now,
          });
        }

        this.mdns?.query({
          questions: [
            { name: instanceName, type: 'SRV' },
            { name: instanceName, type: 'TXT' },
          ],
        });
      }

      if (answer.type === 'SRV') {
        const instanceName = answer.name;
        const serviceName = instanceName.replace(`.${SATURN_SERVICE_TYPE}`, '');
        const srvData = answer.data as { target: string; port: number };

        const partial = this.partialServices.get(serviceName);
        if (partial) {
          const newHost = srvData.target.replace(/\.$/, '');
          if (!partial.host || !isIPAddress(partial.host)) {
            partial.host = newHost;
          }
          partial.port = srvData.port;
          partial.lastSeen = now;
          this.tryPromoteService(serviceName);
        }
      }

      if (answer.type === 'TXT') {
        const instanceName = answer.name;
        const serviceName = instanceName.replace(`.${SATURN_SERVICE_TYPE}`, '');
        const txtData = answer.data as Buffer[];

        const partial = this.partialServices.get(serviceName);
        if (partial) {
          partial.lastSeen = now;
          this.parseTxtRecords(partial, txtData);
          this.tryPromoteService(serviceName);
        }

        const existing = this.services.get(serviceName);
        if (existing) {
          const tempPartial: PartialService = { name: serviceName, lastSeen: now };
          this.parseTxtRecords(tempPartial, txtData);
          if (tempPartial.ephemeralKey && tempPartial.ephemeralKey !== existing.ephemeralKey) {
            this.log('info', 'Ephemeral key rotated', { service: serviceName });
            existing.ephemeralKey = tempPartial.ephemeralKey;
          }
        }
      }

      if (answer.type === 'A' || answer.type === 'AAAA') {
        const hostname = answer.name.replace(/\.$/, '');
        const ip = answer.data as string;

        for (const [name, partial] of this.partialServices) {
          if (partial.host?.toLowerCase() === hostname.toLowerCase() && !isIPAddress(partial.host)) {
            partial.host = ip;
            this.tryPromoteService(name);
          }
        }

        for (const [name, service] of this.services) {
          if (service.host.toLowerCase() === hostname.toLowerCase() && !isIPAddress(service.host)) {
            const hadNoModels = service.models.length === 0;
            service.host = ip;
            service.endpoint = `http://${ip}:${service.port}/v1`;
            if (hadNoModels) {
              this.log('info', 'Host resolved to IP, re-firing discovery callback', {
                name,
                hostname,
                ip,
              });
              this.onServiceDiscovered?.(service);
            }
          }
        }
      }
    }
  }

  private parseTxtRecords(partial: PartialService, txtData: Buffer[]): void {
    for (const buf of txtData) {
      const str = buf.toString('utf-8');
      const eqIdx = str.indexOf('=');
      if (eqIdx === -1) continue;

      const key = str.slice(0, eqIdx).toLowerCase();
      const value = str.slice(eqIdx + 1);

      switch (key) {
        case 'priority':
          partial.priority = parseInt(value, 10) || 50;
          break;
        case 'ephemeral_key':
          partial.ephemeralKey = value;
          break;
        case 'auth':
          partial.authType = value as 'none' | 'psk' | 'bearer';
          break;
        case 'capabilities':
          partial.capabilities = value.split(',').map((s) => s.trim());
          break;
        case 'cost':
          partial.cost = value as 'free' | 'paid' | 'unknown';
          break;
        case 'deployment':
          if (value === 'cloud' || value === 'network') {
            partial.deployment = value;
          }
          break;
        case 'api_type':
          if (value === 'openai' || value === 'ollama') {
            partial.apiType = value;
          }
          break;
        case 'api_base':
          partial.apiBase = value;
          break;
        case 'features':
          partial.features = value;
          break;
      }
    }
  }

  private tryPromoteService(serviceName: string): void {
    const partial = this.partialServices.get(serviceName);
    if (!partial || !partial.host || !partial.port) return;

    const existing = this.services.get(serviceName);
    if (existing) {
      const oldHostWasHostname = !isIPAddress(existing.host);
      const newHostIsIP = isIPAddress(partial.host);
      const hadNoModels = existing.models.length === 0;

      existing.host = partial.host;
      existing.port = partial.port;
      existing.endpoint = `http://${partial.host}:${partial.port}/v1`;
      existing.priority = partial.priority ?? existing.priority;
      existing.ephemeralKey = partial.ephemeralKey ?? existing.ephemeralKey;
      existing.authType = partial.authType ?? existing.authType;
      existing.capabilities = partial.capabilities ?? existing.capabilities;
      existing.cost = partial.cost ?? existing.cost;
      existing.deployment = partial.deployment ?? existing.deployment;
      existing.apiType = partial.apiType ?? existing.apiType;
      existing.apiBase = partial.apiBase ?? existing.apiBase;
      existing.features = partial.features ?? existing.features;
      existing.provider = extractProvider(existing.apiBase);

      if (oldHostWasHostname && newHostIsIP && hadNoModels) {
        this.log('info', 'Host upgraded from hostname to IP, re-firing discovery', {
          name: serviceName,
          host: partial.host,
        });
        this.onServiceDiscovered?.(existing);
      }
      return;
    }

    const defaultEndpoint = `http://${partial.host}:${partial.port}/v1`;
    const apiBase = partial.apiBase ?? defaultEndpoint;

    const service: DiscoveredService = {
      name: partial.name,
      host: partial.host,
      port: partial.port,
      endpoint: defaultEndpoint,
      priority: partial.priority ?? 50,
      ephemeralKey: partial.ephemeralKey ?? '',
      authType: partial.authType ?? 'none',
      capabilities: partial.capabilities ?? [],
      cost: partial.cost ?? 'unknown',
      models: [],
      modelsLastFetched: null,
      deployment: partial.deployment ?? 'network',
      apiType: partial.apiType ?? 'openai',
      apiBase: apiBase,
      features: partial.features ?? '',
      provider: extractProvider(apiBase),
    };

    this.services.set(serviceName, service);

    const hostIsIP = isIPAddress(partial.host);
    this.log('info', 'Service discovered', {
      name: service.name,
      host: service.host,
      hostIsIP,
      port: service.port,
      deployment: service.deployment,
      apiType: service.apiType,
      provider: service.provider,
      priority: service.priority,
    });

    if (!hostIsIP) {
      this.log('debug', 'Service host is a hostname, may need DNS resolution', {
        name: service.name,
        host: service.host,
      });
    }

    this.onServiceDiscovered?.(service);
  }

  private cleanupStaleServices(): void {
    const now = Date.now();

    for (const [name, partial] of this.partialServices) {
      if (now - partial.lastSeen > SERVICE_TIMEOUT_MS) {
        this.partialServices.delete(name);
        if (this.services.has(name)) {
          this.log('info', 'Service removed (stale)', { name });
          this.services.delete(name);
          this.onServiceRemoved?.(name);
        }
      }
    }
  }

  private async fetchModelsForService(service: DiscoveredService): Promise<void> {
    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (service.ephemeralKey) {
        headers['Authorization'] = `Bearer ${service.ephemeralKey}`;
      }

      const baseUrl = getEffectiveEndpoint(service);
      const url = `${baseUrl}/models`;

      this.log('info', `Fetching models from ${service.name}`, {
        url,
        host: service.host,
        port: service.port,
        deployment: service.deployment,
      });

      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 10000);

      try {
        const response = await fetch(url, {
          method: 'GET',
          headers,
          signal: controller.signal,
        });
        clearTimeout(timeout);

        if (!response.ok) {
          this.log('warn', `Models fetch failed for ${service.name}`, { 
            status: response.status,
            url,
          });
          return;
        }

        const data = await response.json() as { data?: Array<{ id: string } | string>; models?: Array<{ id: string } | string> };
        const modelsList = data.data ?? data.models ?? [];
        service.models = modelsList.map((m: { id: string } | string) =>
          typeof m === 'string' ? m : m.id
        );
        service.modelsLastFetched = Date.now();

        this.log('info', `Discovered ${service.models.length} models on ${service.name}`, { url });
      } catch (fetchError) {
        clearTimeout(timeout);
        const errMsg = (fetchError as Error).message;
        if (errMsg.includes('ENOTFOUND') || errMsg.includes('getaddrinfo')) {
          this.log('warn', `Hostname resolution failed for ${service.name}`, { 
            host: service.host,
            url,
            error: errMsg,
          });
        } else if ((fetchError as Error).name === 'AbortError') {
          this.log('warn', `Models fetch timed out for ${service.name}`, { url });
        } else {
          throw fetchError;
        }
      }
    } catch (error) {
      this.log('error', `Error fetching models from ${service.name}`, {
        error: (error as Error).message,
        host: service.host,
      });
    }
  }

  getAllServices(): DiscoveredService[] {
    return Array.from(this.services.values());
  }

  async getEndpointsForModel(modelId: string): Promise<DiscoveredService[]> {
    const fetchPromises: Promise<void>[] = [];
    for (const service of this.services.values()) {
      if (service.modelsLastFetched === null) {
        fetchPromises.push(this.fetchModelsForService(service));
      }
    }
    await Promise.all(fetchPromises);

    const matching = Array.from(this.services.values()).filter((s) =>
      s.models.includes(modelId)
    );

    matching.sort((a, b) => a.priority - b.priority);

    return matching;
  }

  async fetchAllModels(): Promise<void> {
    const fetchPromises: Promise<void>[] = [];
    for (const service of this.services.values()) {
      if (service.modelsLastFetched === null) {
        fetchPromises.push(this.fetchModelsForService(service));
      }
    }
    await Promise.all(fetchPromises);
  }

  hasServices(): boolean {
    return this.services.size > 0;
  }

  async checkServiceHealth(service: DiscoveredService, timeout = 3000): Promise<boolean> {
    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (service.ephemeralKey) {
        headers['Authorization'] = `Bearer ${service.ephemeralKey}`;
      }

      const baseUrl = getEffectiveEndpoint(service);
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);

      try {
        const response = await fetch(`${baseUrl}/health`, {
          method: 'GET',
          headers,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (response.ok) {
          this.log('debug', `Health check passed for ${service.name}`);
          return true;
        }

        this.log('debug', `Health check failed for ${service.name}`, { status: response.status });
        return false;
      } catch (error) {
        clearTimeout(timeoutId);
        this.log('debug', `Health check error for ${service.name}`, {
          error: (error as Error).message,
        });
        return false;
      }
    } catch (error) {
      this.log('debug', `Health check exception for ${service.name}`, {
        error: (error as Error).message,
      });
      return false;
    }
  }

  async getHealthyEndpointsForModel(
    modelId: string,
    healthCheckTimeout = 3000
  ): Promise<{ healthy: DiscoveredService[]; unhealthy: DiscoveredService[] }> {
    const endpoints = await this.getEndpointsForModel(modelId);

    if (endpoints.length === 0) {
      return { healthy: [], unhealthy: [] };
    }

    const healthChecks = await Promise.all(
      endpoints.map(async (service) => ({
        service,
        healthy: await this.checkServiceHealth(service, healthCheckTimeout),
      }))
    );

    const healthy = healthChecks.filter((h) => h.healthy).map((h) => h.service);
    const unhealthy = healthChecks.filter((h) => !h.healthy).map((h) => h.service);

    if (healthy.length > 0) {
      this.log('info', `Health check: ${healthy.length} healthy, ${unhealthy.length} unhealthy endpoints`);
    }

    return { healthy, unhealthy };
  }
}

// ============================================================================
// Language Model Implementation
// ============================================================================

interface DoGenerateResult {
  content: Array<LanguageModelV2Content>;
  finishReason: LanguageModelV2FinishReason;
  usage: LanguageModelV2Usage;
  providerMetadata?: SharedV2ProviderMetadata;
  request?: { body?: unknown };
  response?: {
    id?: string;
    timestamp?: Date;
    modelId?: string;
    headers?: Record<string, string>;
    body?: unknown;
  };
  warnings: Array<LanguageModelV2CallWarning>;
}

interface DoStreamResult {
  stream: ReadableStream<LanguageModelV2StreamPart>;
  request?: { body?: unknown };
  response?: { headers?: Record<string, string> };
}

interface SaturnModelSettings {
  maxRetries?: number;
  retryBaseDelay?: number;
  retryMaxDelay?: number;
  enableHealthChecks?: boolean;
  healthCheckTimeout?: number;
  directEndpoint?: string;
  directServiceName?: string;
  directEphemeralKey?: string;
}

export class SaturnChatLanguageModel implements LanguageModelV2 {
  readonly specificationVersion = 'v2' as const;
  readonly provider = 'saturn';
  readonly modelId: string;

  private discovery: SaturnDiscovery;
  private circuitBreaker: ServiceCircuitBreaker;
  private logger: SaturnLogger;
  private settings: SaturnModelSettings;
  private defaultObjectGenerationMode: 'json' | 'tool' | undefined = 'json';
  private waitForDiscoveryFn: () => Promise<void>;

  constructor(
    modelId: string,
    discovery: SaturnDiscovery,
    logger: SaturnLogger,
    circuitBreaker: ServiceCircuitBreaker,
    settings: SaturnModelSettings = {},
    waitForDiscoveryFn: () => Promise<void>
  ) {
    this.modelId = modelId;
    this.discovery = discovery;
    this.logger = logger;
    this.circuitBreaker = circuitBreaker;
    this.settings = settings;
    this.waitForDiscoveryFn = waitForDiscoveryFn;
  }

  private log(level: LogLevel, message: string, data?: Record<string, unknown>): void {
    this.logger.log(level, message, data);
  }

  get supportedUrls(): Record<string, RegExp[]> {
    return {};
  }

  private getDirectService(): DiscoveredService | null {
    if (!this.settings.directEndpoint) return null;
    return {
      name: this.settings.directServiceName ?? 'direct',
      host: '',
      port: 0,
      endpoint: this.settings.directEndpoint,
      priority: 0,
      ephemeralKey: this.settings.directEphemeralKey ?? '',
      authType: this.settings.directEphemeralKey ? 'bearer' : 'none',
      capabilities: [],
      cost: 'unknown',
      models: [this.modelId],
      modelsLastFetched: Date.now(),
      deployment: 'network',
      apiType: 'openai',
      apiBase: this.settings.directEndpoint,
      features: '',
      provider: 'direct',
    };
  }

  private getArgs(options: LanguageModelV2CallOptions): {
    messages: OpenAIMessage[];
    body: Record<string, unknown>;
    warnings: LanguageModelV2CallWarning[];
  } {
    const warnings: LanguageModelV2CallWarning[] = [];
    const messages = this.convertPrompt(options.prompt);

    const body: Record<string, unknown> = {
      model: this.modelId,
      messages,
    };

    if (options.maxOutputTokens) {
      body.max_tokens = options.maxOutputTokens;
    }

    if (options.temperature !== undefined) {
      body.temperature = options.temperature;
    }

    if (options.topP !== undefined) {
      body.top_p = options.topP;
    }

    if (options.stopSequences) {
      body.stop = options.stopSequences;
    }

    if (options.frequencyPenalty !== undefined) {
      body.frequency_penalty = options.frequencyPenalty;
    }

    if (options.presencePenalty !== undefined) {
      body.presence_penalty = options.presencePenalty;
    }

    if (options.topK !== undefined) {
      warnings.push({
        type: 'unsupported-setting',
        setting: 'topK',
        details: 'topK is not supported by OpenAI-compatible endpoints',
      });
    }

    if (options.responseFormat?.type === 'json' && options.responseFormat.schema) {
      body.response_format = { type: 'json_object' };
    }

    if (options.tools && options.tools.length > 0) {
      body.tools = options.tools
        .filter((tool) => tool.type === 'function')
        .map((tool) => ({
          type: 'function',
          function: {
            name: tool.name,
            description: (tool as { description?: string }).description,
            parameters: (tool as { parameters?: unknown }).parameters,
          },
        }));

      if (options.toolChoice) {
        if (options.toolChoice.type === 'auto') {
          body.tool_choice = 'auto';
        } else if (options.toolChoice.type === 'none') {
          body.tool_choice = 'none';
        } else if (options.toolChoice.type === 'required') {
          body.tool_choice = 'required';
        } else if (options.toolChoice.type === 'tool') {
          body.tool_choice = {
            type: 'function',
            function: { name: options.toolChoice.toolName },
          };
        }
      }
    }

    return { messages, body, warnings };
  }

  private convertPrompt(prompt: LanguageModelV2Prompt): OpenAIMessage[] {
    const messages: OpenAIMessage[] = [];

    for (const message of prompt) {
      switch (message.role) {
        case 'system':
          messages.push({
            role: 'system',
            content: message.content,
          });
          break;

        case 'user': {
          const userTextParts: string[] = [];
          for (const part of message.content) {
            if (part.type === 'text') {
              userTextParts.push(part.text);
            }
          }
          messages.push({
            role: 'user',
            content: userTextParts.join('\n'),
          });
          break;
        }

        case 'assistant': {
          const assistantTextParts: string[] = [];
          const toolCalls: Array<{
            id: string;
            type: 'function';
            function: { name: string; arguments: string };
          }> = [];

          for (const part of message.content) {
            if (part.type === 'text') {
              assistantTextParts.push(part.text);
            } else if (part.type === 'tool-call') {
              toolCalls.push({
                id: part.toolCallId,
                type: 'function',
                function: {
                  name: part.toolName,
                  arguments:
                    typeof part.input === 'string' ? part.input : JSON.stringify(part.input),
                },
              });
            }
          }

          messages.push({
            role: 'assistant',
            content: assistantTextParts.length > 0 ? assistantTextParts.join('\n') : null,
            ...(toolCalls.length > 0 ? { tool_calls: toolCalls } : {}),
          });
          break;
        }

        case 'tool':
          for (const part of message.content) {
            if (part.type === 'tool-result') {
              let resultContent: string;
              const output = part.output;
              if (output && typeof output === 'object' && 'text' in output) {
                resultContent = String((output as { text: unknown }).text);
              } else if (typeof output === 'string') {
                resultContent = output;
              } else {
                resultContent = JSON.stringify(output);
              }
              messages.push({
                role: 'tool',
                tool_call_id: part.toolCallId,
                content: resultContent,
              });
            }
          }
          break;
      }
    }

    return messages;
  }

  private mapFinishReason(reason: string | null): LanguageModelV2FinishReason {
    switch (reason) {
      case 'stop':
        return 'stop';
      case 'length':
        return 'length';
      case 'tool_calls':
        return 'tool-calls';
      case 'content_filter':
        return 'content-filter';
      default:
        return 'other';
    }
  }

  private async callEndpoint(
    service: DiscoveredService,
    body: Record<string, unknown>,
    abortSignal?: AbortSignal
  ): Promise<Response> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (service.ephemeralKey) {
      headers['Authorization'] = `Bearer ${service.ephemeralKey}`;
    }

    const baseUrl = getEffectiveEndpoint(service);
    const url = `${baseUrl}/chat/completions`;

    this.log('debug', `Calling ${service.name}`, {
      url,
      deployment: service.deployment,
      provider: service.provider,
    });

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal: abortSignal,
    });

    if (!response.ok) {
      const errorBody = await response.text();

      if (response.status === 401 && service.ephemeralKey) {
        this.log('warn', `Ephemeral key expired for ${service.name}, waiting for rotation`);
      }

      this.log('warn', `Request failed for ${service.name}`, {
        status: response.status,
        error: errorBody,
      });
      throw new Error(`HTTP ${response.status}: ${errorBody}`);
    }

    return response;
  }

  async doGenerate(options: LanguageModelV2CallOptions): Promise<DoGenerateResult> {
    const directService = this.getDirectService();
    let endpoints: DiscoveredService[];

    if (directService) {
      this.log('debug', 'Using direct endpoint mode', {
        endpoint: directService.endpoint,
        serviceName: directService.name,
      });
      endpoints = [directService];
    } else {
      await this.waitForDiscoveryFn();

      if (this.settings.enableHealthChecks) {
        const { healthy, unhealthy } = await this.discovery.getHealthyEndpointsForModel(
          this.modelId,
          this.settings.healthCheckTimeout ?? 3000
        );
        endpoints = healthy;

        if (endpoints.length === 0 && unhealthy.length > 0) {
          this.log('warn', 'All endpoints failed health check, trying anyway');
          endpoints = unhealthy;
        }
      } else {
        endpoints = await this.discovery.getEndpointsForModel(this.modelId);
      }

      if (endpoints.length === 0) {
        const allServices = this.discovery.getAllServices();

        if (allServices.length === 0) {
          throw new Error(
            `No Saturn services discovered on network. ` +
              `Ensure a Saturn router/beacon is running and advertising via mDNS (_saturn._tcp.local). ` +
              `If running saturn-router, check 'logread | grep saturn' on the router.`
          );
        }

        const serviceList = allServices
          .map(
            (s) =>
              `${s.name} (${s.deployment}/${s.apiType}, models: ${s.models.join(', ') || 'none fetched'})`
          )
          .join('; ');

        throw new NoSuchModelError({
          modelId: this.modelId,
          modelType: 'languageModel',
          message:
            `Model '${this.modelId}' not found on any discovered Saturn service. ` +
            `Found ${allServices.length} service(s): ${serviceList}`,
        });
      }
    }

    const { body, warnings } = this.getArgs(options);
    body.stream = false;

    const availableEndpoints = endpoints.filter((e) => this.circuitBreaker.isAvailable(e.name));
    if (availableEndpoints.length === 0) {
      this.log('warn', 'All endpoints circuit-broken, trying all anyway');
      availableEndpoints.push(...endpoints);
    }

    const errors: Error[] = [];
    for (const service of availableEndpoints) {
      try {
        const response = await withRetry(
          () => this.callEndpoint(service, body, options.abortSignal),
          {
            maxAttempts: this.settings.maxRetries ?? 2,
            baseDelay: this.settings.retryBaseDelay ?? 500,
            maxDelay: this.settings.retryMaxDelay ?? 5000,
          },
          this.logger
        );

        const data = (await response.json()) as OpenAIChatResponse;
        this.circuitBreaker.recordSuccess(service.name);

        const choice = data.choices[0];
        const content: LanguageModelV2Content[] = [];

        if (choice.message.content) {
          content.push({ type: 'text', text: choice.message.content });
        }

        if (choice.message.tool_calls) {
          for (const tc of choice.message.tool_calls) {
            content.push({
              type: 'tool-call',
              toolCallId: tc.id,
              toolName: tc.function.name,
              input: tc.function.arguments,
            });
          }
        }

        return {
          content,
          finishReason: this.mapFinishReason(choice.finish_reason),
          usage: {
            inputTokens: data.usage.prompt_tokens,
            outputTokens: data.usage.completion_tokens,
            totalTokens: data.usage.total_tokens,
          },
          request: { body },
          response: {
            id: data.id,
            timestamp: new Date(data.created * 1000),
            modelId: data.model,
            body: data as unknown as JSONValue,
          },
          warnings,
        };
      } catch (error) {
        this.circuitBreaker.recordFailure(service.name);
        errors.push(error as Error);
        this.log('info', 'Failover triggered', {
          fromService: service.name,
          reason: (error as Error).message,
        });
      }
    }

    throw new Error(
      `All Saturn endpoints failed for model '${this.modelId}':\n` +
        errors.map((e, i) => `  ${availableEndpoints[i].name}: ${e.message}`).join('\n')
    );
  }

  async doStream(options: LanguageModelV2CallOptions): Promise<DoStreamResult> {
    const directService = this.getDirectService();
    let endpoints: DiscoveredService[];

    if (directService) {
      this.log('debug', 'Using direct endpoint mode for streaming', {
        endpoint: directService.endpoint,
        serviceName: directService.name,
      });
      endpoints = [directService];
    } else {
      await this.waitForDiscoveryFn();

      if (this.settings.enableHealthChecks) {
        const { healthy, unhealthy } = await this.discovery.getHealthyEndpointsForModel(
          this.modelId,
          this.settings.healthCheckTimeout ?? 3000
        );
        endpoints = healthy;

        if (endpoints.length === 0 && unhealthy.length > 0) {
          this.log('warn', 'All endpoints failed health check, trying anyway');
          endpoints = unhealthy;
        }
      } else {
        endpoints = await this.discovery.getEndpointsForModel(this.modelId);
      }

      if (endpoints.length === 0) {
        const allServices = this.discovery.getAllServices();

        if (allServices.length === 0) {
          throw new Error(
            `No Saturn services discovered on network. ` +
              `Ensure a Saturn router/beacon is running and advertising via mDNS (_saturn._tcp.local). ` +
              `If running saturn-router, check 'logread | grep saturn' on the router.`
          );
        }

        const serviceList = allServices
          .map(
            (s) =>
              `${s.name} (${s.deployment}/${s.apiType}, models: ${s.models.join(', ') || 'none fetched'})`
          )
          .join('; ');

        throw new NoSuchModelError({
          modelId: this.modelId,
          modelType: 'languageModel',
          message:
            `Model '${this.modelId}' not found on any discovered Saturn service. ` +
            `Found ${allServices.length} service(s): ${serviceList}`,
        });
      }
    }

    const { body, warnings } = this.getArgs(options);
    body.stream = true;

    const availableEndpoints = endpoints.filter((e) => this.circuitBreaker.isAvailable(e.name));
    if (availableEndpoints.length === 0) {
      this.log('warn', 'All endpoints circuit-broken, trying all anyway');
      availableEndpoints.push(...endpoints);
    }

    const errors: Error[] = [];

    const attemptStream = async (
      service: DiscoveredService
    ): Promise<{ response: Response; headers: Record<string, string> }> => {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (service.ephemeralKey) {
        headers['Authorization'] = `Bearer ${service.ephemeralKey}`;
      }

      const baseUrl = getEffectiveEndpoint(service);
      const url = `${baseUrl}/chat/completions`;

      this.log('debug', `Streaming from ${service.name}`, {
        url,
        deployment: service.deployment,
        provider: service.provider,
      });

      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
        signal: options.abortSignal,
      });

      if (!response.ok) {
        const errorBody = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorBody}`);
      }

      return { response, headers };
    };

    for (const service of availableEndpoints) {
      try {
        const { response, headers: reqHeaders } = await withRetry(
          () => attemptStream(service),
          {
            maxAttempts: this.settings.maxRetries ?? 2,
            baseDelay: this.settings.retryBaseDelay ?? 500,
            maxDelay: this.settings.retryMaxDelay ?? 5000,
          },
          this.logger
        );

        this.circuitBreaker.recordSuccess(service.name);

        const remainingEndpoints = availableEndpoints.slice(
          availableEndpoints.indexOf(service) + 1
        );

        const stream = this.createFailoverStream(
          response,
          warnings,
          body,
          remainingEndpoints,
          options.abortSignal
        );

        return {
          stream,
          request: { body },
          response: { headers: Object.fromEntries(response.headers.entries()) },
        };
      } catch (error) {
        this.circuitBreaker.recordFailure(service.name);
        errors.push(error as Error);
        this.log('info', 'Failover triggered (streaming)', {
          fromService: service.name,
          reason: (error as Error).message,
        });
      }
    }

    throw new Error(
      `All Saturn endpoints failed for model '${this.modelId}':\n` +
        errors.map((e, i) => `  ${availableEndpoints[i].name}: ${e.message}`).join('\n')
    );
  }

  private createStreamTransformer(
    response: Response,
    initialWarnings: LanguageModelV2CallWarning[]
  ): ReadableStream<LanguageModelV2StreamPart> {
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();

    let buffer = '';
    let isFirstChunk = true;
    let finishReason: LanguageModelV2FinishReason = 'other';
    let usage: LanguageModelV2Usage = {
      inputTokens: undefined,
      outputTokens: undefined,
      totalTokens: undefined,
    };
    let currentTextId: string | null = null;
    const toolInputIds = new Map<number, string>();

    const self = this;

    return new ReadableStream({
      start(controller) {
        controller.enqueue({ type: 'stream-start', warnings: initialWarnings });
      },

      async pull(controller) {
        try {
          const { done, value } = await reader.read();

          if (done) {
            if (currentTextId) {
              controller.enqueue({ type: 'text-end', id: currentTextId });
            }
            controller.enqueue({ type: 'finish', finishReason, usage });
            controller.close();
            return;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;

            const data = line.slice(6).trim();
            if (data === '[DONE]') {
              if (currentTextId) {
                controller.enqueue({ type: 'text-end', id: currentTextId });
                currentTextId = null;
              }
              controller.enqueue({ type: 'finish', finishReason, usage });
              controller.close();
              return;
            }

            try {
              const parsed = JSON.parse(data);

              if (isFirstChunk && parsed.model) {
                controller.enqueue({
                  type: 'response-metadata',
                  id: parsed.id,
                  modelId: parsed.model,
                  timestamp: parsed.created ? new Date(parsed.created * 1000) : new Date(),
                });
                isFirstChunk = false;
              }

              const choice = parsed.choices?.[0];
              if (!choice) continue;

              const delta = choice.delta;

              if (delta?.content) {
                if (!currentTextId) {
                  currentTextId = generateId();
                  controller.enqueue({ type: 'text-start', id: currentTextId });
                }
                controller.enqueue({
                  type: 'text-delta',
                  id: currentTextId,
                  delta: delta.content,
                });
              }

              if (delta?.tool_calls) {
                for (const tc of delta.tool_calls) {
                  const index = tc.index ?? 0;
                  let toolId = toolInputIds.get(index);

                  if (tc.id) {
                    const newToolId: string = tc.id;
                    toolId = newToolId;
                    toolInputIds.set(index, newToolId);
                    controller.enqueue({
                      type: 'tool-input-start',
                      id: newToolId,
                      toolName: tc.function?.name || '',
                    });
                  }

                  if (toolId !== undefined && tc.function?.arguments) {
                    controller.enqueue({
                      type: 'tool-input-delta',
                      id: toolId,
                      delta: tc.function.arguments,
                    });
                  }
                }
              }

              if (choice.finish_reason) {
                finishReason = self.mapFinishReason(choice.finish_reason);

                for (const [, toolId] of toolInputIds) {
                  controller.enqueue({ type: 'tool-input-end', id: toolId });
                }
              }

              if (parsed.usage) {
                usage = {
                  inputTokens: parsed.usage.prompt_tokens,
                  outputTokens: parsed.usage.completion_tokens,
                  totalTokens: parsed.usage.total_tokens,
                };
              }
            } catch {
              // Ignore parse errors for malformed chunks
            }
          }
        } catch (error) {
          controller.error(error);
        }
      },

      cancel() {
        reader.cancel().catch(() => {});
      },
    });
  }

  private createFailoverStream(
    initialResponse: Response,
    initialWarnings: LanguageModelV2CallWarning[],
    requestBody: Record<string, unknown>,
    fallbackEndpoints: DiscoveredService[],
    abortSignal?: AbortSignal
  ): ReadableStream<LanguageModelV2StreamPart> {
    let currentResponse = initialResponse;
    let currentReader = currentResponse.body!.getReader();
    const decoder = new TextDecoder();

    let buffer = '';
    let isFirstChunk = true;
    let hasEmittedContent = false;
    let finishReason: LanguageModelV2FinishReason = 'other';
    let usage: LanguageModelV2Usage = {
      inputTokens: undefined,
      outputTokens: undefined,
      totalTokens: undefined,
    };
    let currentTextId: string | null = null;
    const toolInputIds = new Map<number, string>();
    let fallbackIndex = 0;

    const self = this;

    const attemptFallback = async (): Promise<boolean> => {
      if (hasEmittedContent) {
        self.log('warn', 'Cannot failover mid-stream after content was emitted');
        return false;
      }

      while (fallbackIndex < fallbackEndpoints.length) {
        const service = fallbackEndpoints[fallbackIndex];
        fallbackIndex++;

        if (!self.circuitBreaker.isAvailable(service.name)) {
          continue;
        }

        try {
          const headers: Record<string, string> = {
            'Content-Type': 'application/json',
          };

          if (service.ephemeralKey) {
            headers['Authorization'] = `Bearer ${service.ephemeralKey}`;
          }

          const baseUrl = getEffectiveEndpoint(service);
          const url = `${baseUrl}/chat/completions`;

          self.log('info', `Mid-stream failover to ${service.name}`, {
            url,
            deployment: service.deployment,
          });

          const response = await fetch(url, {
            method: 'POST',
            headers,
            body: JSON.stringify(requestBody),
            signal: abortSignal,
          });

          if (!response.ok) {
            const errorBody = await response.text();
            self.circuitBreaker.recordFailure(service.name);
            self.log('warn', `Failover attempt failed for ${service.name}`, {
              status: response.status,
              error: errorBody,
            });
            continue;
          }

          self.circuitBreaker.recordSuccess(service.name);
          currentResponse = response;
          currentReader = response.body!.getReader();
          buffer = '';
          isFirstChunk = true;
          return true;
        } catch (error) {
          self.circuitBreaker.recordFailure(service.name);
          self.log('warn', `Failover attempt error for ${service.name}`, {
            error: (error as Error).message,
          });
        }
      }

      return false;
    };

    return new ReadableStream({
      start(controller) {
        controller.enqueue({ type: 'stream-start', warnings: initialWarnings });
      },

      async pull(controller) {
        try {
          const { done, value } = await currentReader.read();

          if (done) {
            if (currentTextId) {
              controller.enqueue({ type: 'text-end', id: currentTextId });
            }
            self.log('debug', 'Stream completed (failover)', {
              finishReason,
              usage,
              hasEmittedContent,
            });
            controller.enqueue({ type: 'finish', finishReason, usage });
            controller.close();
            return;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;

            const data = line.slice(6).trim();
            if (data === '[DONE]') {
              if (currentTextId) {
                controller.enqueue({ type: 'text-end', id: currentTextId });
                currentTextId = null;
              }
              controller.enqueue({ type: 'finish', finishReason, usage });
              controller.close();
              return;
            }

            try {
              const parsed = JSON.parse(data);

              if (isFirstChunk && parsed.model) {
                controller.enqueue({
                  type: 'response-metadata',
                  id: parsed.id,
                  modelId: parsed.model,
                  timestamp: parsed.created ? new Date(parsed.created * 1000) : new Date(),
                });
                isFirstChunk = false;
              }

              const choice = parsed.choices?.[0];
              if (!choice) continue;

              const delta = choice.delta;

              if (delta?.content) {
                hasEmittedContent = true;
                if (!currentTextId) {
                  currentTextId = generateId();
                  controller.enqueue({ type: 'text-start', id: currentTextId });
                }
                controller.enqueue({
                  type: 'text-delta',
                  id: currentTextId,
                  delta: delta.content,
                });
              }

              if (delta?.tool_calls) {
                hasEmittedContent = true;
                for (const tc of delta.tool_calls) {
                  const index = tc.index ?? 0;
                  let toolId = toolInputIds.get(index);

                  if (tc.id) {
                    const newToolId: string = tc.id;
                    toolId = newToolId;
                    toolInputIds.set(index, newToolId);
                    controller.enqueue({
                      type: 'tool-input-start',
                      id: newToolId,
                      toolName: tc.function?.name || '',
                    });
                  }

                  if (toolId !== undefined && tc.function?.arguments) {
                    controller.enqueue({
                      type: 'tool-input-delta',
                      id: toolId,
                      delta: tc.function.arguments,
                    });
                  }
                }
              }

              if (choice.finish_reason) {
                self.log('debug', 'Received finish_reason', {
                  raw: choice.finish_reason,
                  mapped: self.mapFinishReason(choice.finish_reason),
                });
                finishReason = self.mapFinishReason(choice.finish_reason);

                for (const [, toolId] of toolInputIds) {
                  controller.enqueue({ type: 'tool-input-end', id: toolId });
                }
              }

              if (parsed.usage) {
                self.log('debug', 'Received usage', { usage: parsed.usage });
                usage = {
                  inputTokens: parsed.usage.prompt_tokens,
                  outputTokens: parsed.usage.completion_tokens,
                  totalTokens: parsed.usage.total_tokens,
                };
              }
            } catch {
              // Ignore parse errors for malformed chunks
            }
          }
        } catch (error) {
          self.log('warn', 'Stream error detected, attempting failover', {
            error: (error as Error).message,
            hasEmittedContent,
          });

          const failedOver = await attemptFallback();
          if (failedOver) {
            return;
          }

          controller.error(error);
        }
      },

      cancel() {
        currentReader.cancel().catch(() => {});
      },
    });
  }
}

// ============================================================================
// Provider Factory
// ============================================================================

export interface SaturnProviderSettings {
  discoveryTimeout?: number;
  logger?: SaturnLogger;
  logLevel?: LogLevel;
  maxRetries?: number;
  retryBaseDelay?: number;
  retryMaxDelay?: number;
  circuitBreakerThreshold?: number;
  circuitBreakerResetTimeout?: number;
  enableHealthChecks?: boolean;
  healthCheckTimeout?: number;
  onServiceDiscovered?: (service: DiscoveredService) => void;
  onServiceRemoved?: (serviceName: string) => void;
  serviceEndpoint?: string;
  serviceName?: string;
  serviceEphemeralKey?: string;
}

export interface SaturnProvider extends ProviderV2 {
  (modelId: string): LanguageModelV2;
  getDiscovery(): SaturnDiscovery;
  destroy(): void;
}

export function createSaturn(options: SaturnProviderSettings = {}): SaturnProvider {
  const logger = options.logger || (options.logLevel ? createDefaultLogger(options.logLevel) : createNoOpLogger());
  const discovery = new SaturnDiscovery(logger, options.onServiceDiscovered, options.onServiceRemoved);
  const circuitBreaker = new ServiceCircuitBreaker(
    options.circuitBreakerThreshold ?? 3,
    options.circuitBreakerResetTimeout ?? 30000
  );

  const isDirectMode = !!options.serviceEndpoint;

  if (!isDirectMode) {
    discovery.start();
  }

  const discoveryTimeout = options.discoveryTimeout ?? 3000;
  let initialDiscoveryPromise: Promise<void> | null = null;

  const waitForDiscovery = async (): Promise<void> => {
    if (isDirectMode) return;
    if (!initialDiscoveryPromise) {
      initialDiscoveryPromise = new Promise((resolve) => {
        const startTime = Date.now();
        const check = () => {
          if (discovery.hasServices() || Date.now() - startTime > discoveryTimeout) {
            resolve();
          } else {
            setTimeout(check, 100);
          }
        };
        check();
      });
    }
    return initialDiscoveryPromise;
  };

  const modelSettings: SaturnModelSettings = {
    maxRetries: options.maxRetries,
    retryBaseDelay: options.retryBaseDelay,
    retryMaxDelay: options.retryMaxDelay,
    enableHealthChecks: options.enableHealthChecks,
    healthCheckTimeout: options.healthCheckTimeout,
    directEndpoint: options.serviceEndpoint,
    directServiceName: options.serviceName,
    directEphemeralKey: options.serviceEphemeralKey,
  };

  const createLanguageModel = (modelId: string): LanguageModelV2 => {
    return new SaturnChatLanguageModel(modelId, discovery, logger, circuitBreaker, modelSettings, waitForDiscovery);
  };

  const provider = function (modelId: string): LanguageModelV2 {
    if (new.target) {
      throw new Error('The Saturn provider function cannot be called with the new keyword.');
    }
    return createLanguageModel(modelId);
  } as SaturnProvider;

  provider.languageModel = createLanguageModel;

  provider.textEmbeddingModel = (modelId: string) => {
    throw new NoSuchModelError({ modelId, modelType: 'textEmbeddingModel' });
  };

  provider.imageModel = (modelId: string) => {
    throw new NoSuchModelError({ modelId, modelType: 'imageModel' });
  };

  provider.getDiscovery = () => discovery;
  provider.destroy = () => {
    if (!isDirectMode) discovery.stop();
  };

  return provider;
}

export const saturn = createSaturn();

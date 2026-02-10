import multicastDns from 'multicast-dns';
import type { LogLevel, SaturnLogger } from './logger.js';
import { createDefaultLogger } from './logger.js';
import type { DiscoveredService } from './types.js';
import { endpoint, extractProvider, isIPAddress } from './helpers.js';

const SATURN_SERVICE_TYPE = '_saturn._tcp.local';
const SERVICE_TIMEOUT_MS = 20000; // Reduced from 60s - goodbye packets handle normal shutdowns, this is only for crashed/unreachable services

export class SaturnDiscovery {
  private mdns: ReturnType<typeof multicastDns> | null = null;
  private services: Map<string, DiscoveredService> = new Map();
  private cleanupInterval: NodeJS.Timeout | null = null;
  private queryInterval: NodeJS.Timeout | null = null;
  private healthCheckInterval: NodeJS.Timeout | null = null;
  private started = false;
  private logger: SaturnLogger;
  private onServiceDiscovered?: (service: DiscoveredService) => void;
  private onServiceRemoved?: (serviceName: string) => void;
  private onServiceUnhealthy?: (service: DiscoveredService) => void;
  private activeHealthCheckIntervalMs: number | null = null;

  constructor(
    logger?: SaturnLogger,
    onServiceDiscovered?: (service: DiscoveredService) => void,
    onServiceRemoved?: (serviceName: string) => void,
    onServiceUnhealthy?: (service: DiscoveredService) => void,
    activeHealthCheckIntervalMs?: number
  ) {
    this.logger = logger || createDefaultLogger();
    this.onServiceDiscovered = onServiceDiscovered;
    this.onServiceRemoved = onServiceRemoved;
    this.onServiceUnhealthy = onServiceUnhealthy;
    this.activeHealthCheckIntervalMs = activeHealthCheckIntervalMs ?? null;
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
    }, 5000);

    this.cleanupInterval = setInterval(() => {
      this.cleanupStaleServices();
    }, 15000);

    if (this.activeHealthCheckIntervalMs) {
      this.healthCheckInterval = setInterval(() => {
        this.runActiveHealthChecks();
      }, this.activeHealthCheckIntervalMs);
    }
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
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }
    if (this.mdns) {
      this.mdns.destroy();
      this.mdns = null;
    }
    this.services.clear();
  }

  private sendQuery(): void {
    if (!this.mdns) return;

    this.mdns.query({
      questions: [{ name: SATURN_SERVICE_TYPE, type: 'PTR' }],
    });
  }


  requestKeyRefresh(serviceName: string): void {
    if (!this.mdns) return;

    const instanceName = `${serviceName}.${SATURN_SERVICE_TYPE}`;
    this.log('info', 'Requesting key refresh via mDNS TXT query', { serviceName });

    this.mdns.query({
      questions: [{ name: instanceName, type: 'TXT' }],
    });
  }

  async waitForKeyRefresh(serviceName: string, timeout = 2000): Promise<string | null> {
    const service = this.services.get(serviceName);
    const oldKey = service?.ephemeralKey;
    
    this.requestKeyRefresh(serviceName);
    
    const start = Date.now();
    while (Date.now() - start < timeout) {
      await new Promise(r => setTimeout(r, 100));
      const current = this.services.get(serviceName);
      if (current?.ephemeralKey && current.ephemeralKey !== oldKey) {
        this.log('info', 'Key refresh received', { serviceName });
        return current.ephemeralKey;
      }
    }
    
    this.log('warn', 'Key refresh timed out', { serviceName, timeout });
    return this.services.get(serviceName)?.ephemeralKey || null;
  }

  removeService(serviceName: string): void {
    if (this.services.has(serviceName)) {
      this.log('info', 'Service removed manually', { name: serviceName });
      this.services.delete(serviceName);
      this.onServiceRemoved?.(serviceName);
    }
  }

  private ready(s: DiscoveredService): boolean {
    return !!s.host && !!s.port;
  }

  private ensure(name: string, now: number): DiscoveredService {
    let service = this.services.get(name);
    if (service) {
      service.lastSeen = now;
      return service;
    }
    service = {
      name,
      host: '',
      port: 0,
      endpoint: '',
      priority: 50,
      ephemeralKey: '',
      authType: 'none',
      capabilities: [],
      cost: 'unknown',
      models: [],
      modelsLastFetched: null,
      modelsLastAttempted: null,
      deployment: 'network',
      apiType: 'openai',
      apiBase: '',
      features: '',
      provider: '',
      lastSeen: now,
    };
    this.services.set(name, service);
    return service;
  }

  private handleResponse(response: multicastDns.ResponsePacket): void {
    const now = Date.now();

    for (const answer of [...response.answers, ...response.additionals]) {
      // ttl=0 is a "goodbye" packet — the service is leaving the network
      const ttl = (answer as unknown as { ttl?: number }).ttl;
      if (ttl === 0) {
        let serviceName: string | null = null;

        if (answer.type === 'PTR' && answer.name === SATURN_SERVICE_TYPE) {
          serviceName = (answer.data as string).replace(`.${SATURN_SERVICE_TYPE}`, '');
        } else if (answer.type === 'SRV' || answer.type === 'TXT') {
          serviceName = answer.name.replace(`.${SATURN_SERVICE_TYPE}`, '');
        }

        if (serviceName && this.services.has(serviceName)) {
          this.log('info', 'Service goodbye received', { name: serviceName });
          this.services.delete(serviceName);
          this.onServiceRemoved?.(serviceName);
        }
        continue;
      }

      // PTR: "what services exist?" — browse response listing instance names
      if (answer.type === 'PTR' && answer.name === SATURN_SERVICE_TYPE) {
        const instanceName = answer.data as string;
        const serviceName = instanceName.replace(`.${SATURN_SERVICE_TYPE}`, '');
        this.ensure(serviceName, now);

        // follow up to get the location (SRV) and metadata (TXT)
        this.mdns?.query({
          questions: [
            { name: instanceName, type: 'SRV' },
            { name: instanceName, type: 'TXT' },
          ],
        });
      }

      // SRV: "where is this service?" — gives us hostname + port
      if (answer.type === 'SRV') {
        const serviceName = answer.name.replace(`.${SATURN_SERVICE_TYPE}`, '');
        const srvData = answer.data as { target: string; port: number };
        const service = this.ensure(serviceName, now);
        const wasReady = this.ready(service);

        const newHost = srvData.target.replace(/\.$/, '');
        if (!service.host || !isIPAddress(service.host)) {
          service.host = newHost;
        }
        service.port = srvData.port;
        service.endpoint = `http://${service.host}:${service.port}/v1`;
        if (!service.apiBase) service.apiBase = service.endpoint;
        service.provider = extractProvider(service.apiBase);

        if (!wasReady && this.ready(service)) {
          this.log('info', 'Service discovered', {
            name: service.name,
            host: service.host,
            port: service.port,
            deployment: service.deployment,
            provider: service.provider,
          });
          this.onServiceDiscovered?.(service);
        }
      }

      // TXT: "what metadata does this service have?" — priority, keys, api base, etc.
      if (answer.type === 'TXT') {
        const serviceName = answer.name.replace(`.${SATURN_SERVICE_TYPE}`, '');
        const txtData = answer.data as Buffer[];
        const service = this.ensure(serviceName, now);
        const oldKey = service.ephemeralKey;

        this.parseTxtRecords(service, txtData);
        service.provider = extractProvider(service.apiBase);

        if (oldKey && service.ephemeralKey !== oldKey) {
          this.log('info', 'Ephemeral key rotated', { service: serviceName });
        }
      }

      // A/AAAA: "what IP is this hostname?" — resolves hostname from SRV to an address
      if (answer.type === 'A' || answer.type === 'AAAA') {
        const hostname = answer.name.replace(/\.$/, '');
        const ip = answer.data as string;

        for (const [name, service] of this.services) {
          if (service.host.toLowerCase() === hostname.toLowerCase() && !isIPAddress(service.host)) {
            const hadNoModels = service.models.length === 0;
            service.host = ip;
            service.endpoint = `http://${ip}:${service.port}/v1`;
            if (hadNoModels) {
              this.log('info', 'Host resolved to IP, re-firing discovery callback', { name, hostname, ip });
              this.onServiceDiscovered?.(service);
            }
          }
        }
      }
    }
  }

  private parseTxtRecords(service: DiscoveredService, txtData: Buffer[]): void {
    for (const buf of txtData) {
      const str = buf.toString('utf-8');
      const eqIdx = str.indexOf('=');
      if (eqIdx === -1) continue;

      const key = str.slice(0, eqIdx).toLowerCase();
      const value = str.slice(eqIdx + 1);

      switch (key) {
        case 'priority':
          service.priority = parseInt(value, 10) || 50;
          break;
        case 'ephemeral_key':
          service.ephemeralKey = value;
          break;
        case 'auth':
          service.authType = value as 'none' | 'psk' | 'bearer';
          break;
        case 'capabilities':
          service.capabilities = value.split(',').map((s) => s.trim());
          break;
        case 'cost':
          service.cost = value as 'free' | 'paid' | 'unknown';
          break;
        case 'deployment':
          if (value === 'cloud' || value === 'network') {
            service.deployment = value;
          }
          break;
        case 'api_type':
          if (value === 'openai' || value === 'ollama') {
            service.apiType = value;
          }
          break;
        case 'api_base':
          service.apiBase = value;
          break;
        case 'features':
          service.features = value;
          break;
      }
    }
  }

  private cleanupStaleServices(): void {
    const now = Date.now();

    for (const [name, service] of this.services) {
      if (now - service.lastSeen > SERVICE_TIMEOUT_MS) {
        this.log('info', 'Service removed (stale)', { name });
        this.services.delete(name);
        this.onServiceRemoved?.(name);
      }
    }
  }

  private authedFetch(service: DiscoveredService, path: string, signal?: AbortSignal): Promise<Response> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (service.ephemeralKey) headers['Authorization'] = `Bearer ${service.ephemeralKey}`;
    return fetch(`${endpoint(service)}${path}`, { method: 'GET', headers, signal });
  }

  private async fetchModelsForService(service: DiscoveredService): Promise<void> {
    service.modelsLastAttempted = Date.now();
    const url = `${endpoint(service)}/models`;

    try {
      this.log('info', `Fetching models from ${service.name}`, {
        url,
        host: service.host,
        port: service.port,
        deployment: service.deployment,
      });

      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 10000);

      const result = await (async (): Promise<Response | null> => {
        try {
          const r = await this.authedFetch(service, '/models', controller.signal);
          clearTimeout(timeout);

          if (!r.ok) {
            this.log('warn', `Models fetch failed for ${service.name}, retrying in 2s`, {
              status: r.status,
              url,
            });
            await new Promise(resolve => setTimeout(resolve, 2000));
            const r2 = await this.authedFetch(service, '/models', AbortSignal.timeout(10000));
            if (!r2.ok) {
              this.log('warn', `Models retry also failed for ${service.name}`, {
                status: r2.status,
                url,
              });
              return null;
            }
            return r2;
          }
          return r;
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
          return null;
        }
      })();

      if (!result) return;

      const data = await result.json() as { data?: Array<{ id: string } | string>; models?: Array<{ id: string } | string> };
      const modelsList = data.data ?? data.models ?? [];
      service.models = modelsList.map((m: { id: string } | string) =>
        typeof m === 'string' ? m : m.id
      );
      service.modelsLastFetched = Date.now();

      this.log('info', `Discovered ${service.models.length} models on ${service.name}`, { url });
    } catch (error) {
      this.log('error', `Error fetching models from ${service.name}`, {
        error: (error as Error).message,
        host: service.host,
      });
    }
  }

  private async fetchStaleModels(): Promise<void> {
    const COOLDOWN = 30000;
    const now = Date.now();
    const promises: Promise<void>[] = [];
    for (const service of this.services.values()) {
      if (this.ready(service) && service.modelsLastFetched === null &&
          (service.modelsLastAttempted === null || now - service.modelsLastAttempted > COOLDOWN)) {
        promises.push(this.fetchModelsForService(service));
      }
    }
    await Promise.all(promises);
  }

  getAllServices(): DiscoveredService[] {
    return Array.from(this.services.values()).filter(s => this.ready(s));
  }

  async getEndpointsForModel(modelId: string): Promise<DiscoveredService[]> {
    await this.fetchStaleModels();

    const matching = Array.from(this.services.values()).filter((s) =>
      this.ready(s) && s.models.includes(modelId)
    );

    matching.sort((a, b) => a.priority - b.priority);

    return matching;
  }

  async fetchAllModels(): Promise<void> {
    await this.fetchStaleModels();
  }

  async fetchModelsForServiceByName(name: string): Promise<boolean> {
    const service = this.services.get(name);
    if (!service) return false;
    if (service.modelsLastFetched !== null) return service.models.length > 0;
    await this.fetchModelsForService(service);
    return service.models.length > 0;
  }

  hasServices(): boolean {
    return Array.from(this.services.values()).some(s => this.ready(s));
  }

  async checkServiceHealth(service: DiscoveredService, timeout = 3000): Promise<boolean> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await this.authedFetch(service, '/health', controller.signal);
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


  private async runActiveHealthChecks(): Promise<void> {
    const services = Array.from(this.services.values());
    if (services.length === 0) return;

    this.log('debug', `Running active health checks on ${services.length} services`);

    const results = await Promise.all(
      services.map(async (service) => ({
        service,
        healthy: await this.checkServiceHealth(service, 3000),
      }))
    );

    for (const { service, healthy } of results) {
      if (!healthy) {
        this.log('warn', `Active health check failed for ${service.name}`);
        this.onServiceUnhealthy?.(service);
      }
    }
  }
}

/**
 * AI SDK Provider for Saturn - Zero-Configuration AI Service Discovery
 *
 * This provider discovers Saturn services on the local network via mDNS/DNS-SD
 * and routes AI SDK requests to discovered endpoints with automatic failover.
 */

import {
  LanguageModelV4,
  NoSuchModelError,
  ProviderV4,
} from '@ai-sdk/provider';
import type { LogLevel, SaturnLogger } from './logger.js';
import { createDefaultLogger, createNoOpLogger } from './logger.js';
import type { DiscoveredService, SaturnModelSettings } from './types.js';
import { SaturnDiscovery } from './discovery.js';
import { ServiceCircuitBreaker } from './retry.js';
import { SaturnChatLanguageModel } from './model.js';
import type { SaturnLanguageModelOptions } from './model.js';

// Re-export everything consumers might need
export type { LogLevel, SaturnLogger } from './logger.js';
export { createDefaultLogger, createNoOpLogger } from './logger.js';
export type { DeploymentType, ApiType, DiscoveredService, SaturnModelSettings } from './types.js';
export { endpoint, endpoint as getEffectiveEndpoint, extractProvider } from './helpers.js';
export { ServiceCircuitBreaker } from './retry.js';
export { SaturnDiscovery } from './discovery.js';
export { SaturnChatLanguageModel } from './model.js';
export type { SaturnLanguageModelOptions } from './model.js';

// ============================================================================
// Provider Factory
// ============================================================================

export interface SaturnProviderSettings {
  discoveryTimeout?: number;
  logger?: SaturnLogger;
  logLevel?: LogLevel;
  maxRetries?: number;
  retryDelay?: number;
  circuitBreakerThreshold?: number;
  circuitBreakerResetTimeout?: number;
  enableHealthChecks?: boolean;
  healthCheckTimeout?: number;
  activeHealthCheckInterval?: number;
  onServiceDiscovered?: (service: DiscoveredService) => void;
  onServiceRemoved?: (serviceName: string) => void;
  onServiceUnhealthy?: (service: DiscoveredService) => void;
  serviceEndpoint?: string;
  serviceName?: string;
  serviceEphemeralKey?: string;
}

export interface SaturnProvider extends ProviderV4 {
  (modelId: string): LanguageModelV4;
  getDiscovery(): SaturnDiscovery;
  destroy(): void;
}

export function createSaturn(options: SaturnProviderSettings = {}): SaturnProvider {
  const logger = options.logger || (options.logLevel ? createDefaultLogger(options.logLevel) : createNoOpLogger());
  const discovery = new SaturnDiscovery(
    logger,
    options.onServiceDiscovered,
    options.onServiceRemoved,
    options.onServiceUnhealthy,
    options.activeHealthCheckInterval
  );
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
    retryDelay: options.retryDelay,
    enableHealthChecks: options.enableHealthChecks,
    healthCheckTimeout: options.healthCheckTimeout,
    directEndpoint: options.serviceEndpoint,
    directServiceName: options.serviceName,
    directEphemeralKey: options.serviceEphemeralKey,
  };

  const createLanguageModel = (modelId: string): LanguageModelV4 => {
    return new SaturnChatLanguageModel(modelId, discovery, logger, circuitBreaker, modelSettings, waitForDiscovery);
  };

  const provider = function (modelId: string): LanguageModelV4 {
    if (new.target) {
      throw new Error('The Saturn provider function function cannot be called with the new keyword.');
    }
    return createLanguageModel(modelId);
  } as SaturnProvider;

  (provider as any).specificationVersion = 'v4';
  provider.languageModel = createLanguageModel;

  provider.embeddingModel = (modelId: string) => {
    throw new NoSuchModelError({ modelId, modelType: 'embeddingModel' });
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

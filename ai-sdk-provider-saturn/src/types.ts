/**
 * Shared types for the Saturn AI SDK provider.
 */

import type { JSONObject, JSONValue } from '@ai-sdk/provider';

// ============================================================================
// Service Types
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
  modelsLastAttempted: number | null;
  deployment: DeploymentType;
  apiType: ApiType;
  apiBase: string;
  features: string;
  provider: string;
  lastSeen: number;
}

// ============================================================================
// OpenAI-compatible types
// ============================================================================

export interface OpenAIMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string | null;
  tool_calls?: Array<{
    id: string;
    type: 'function';
    function: { name: string; arguments: string };
  }>;
  tool_call_id?: string;
}

export interface OpenAIChatResponse {
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

export interface OpenAIModelsResponse {
  object: 'list';
  data: Array<{
    id: string;
    object: 'model';
    owned_by: string;
  }>;
}

// ============================================================================
// Settings
// ============================================================================

export interface SaturnModelSettings {
  maxRetries?: number;
  retryDelay?: number;
  enableHealthChecks?: boolean;
  healthCheckTimeout?: number;
  directEndpoint?: string;
  directServiceName?: string;
  directEphemeralKey?: string;
}

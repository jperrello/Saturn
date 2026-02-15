import {
  JSONObject,
  JSONValue,
  LanguageModelV3,
  LanguageModelV3CallOptions,
  LanguageModelV3Content,
  LanguageModelV3FinishReason,
  LanguageModelV3GenerateResult,
  LanguageModelV3Prompt,
  LanguageModelV3StreamPart,
  LanguageModelV3StreamResult,
  LanguageModelV3Usage,
  NoSuchModelError,
  SharedV3Warning,
} from '@ai-sdk/provider';
import { generateId } from '@ai-sdk/provider-utils';
import type { LogLevel, SaturnLogger } from './logger.js';
import type { DiscoveredService, OpenAIChatResponse, OpenAIMessage, SaturnModelSettings } from './types.js';
import { endpoint } from './helpers.js';
import { withRetry } from './retry.js';
import type { ServiceCircuitBreaker } from './retry.js';
import type { SaturnDiscovery } from './discovery.js';

export class SaturnChatLanguageModel implements LanguageModelV3 {
  readonly specificationVersion = 'v3' as const;
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
      modelsLastAttempted: Date.now(),
      deployment: 'network',
      apiType: 'openai',
      apiBase: this.settings.directEndpoint,
      features: '',
      provider: 'direct',
      lastSeen: Date.now(),
    };
  }

  private getArgs(options: LanguageModelV3CallOptions): {
    messages: OpenAIMessage[];
    body: Record<string, unknown>;
    warnings: SharedV3Warning[];
  } {
    const warnings: SharedV3Warning[] = [];
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
        type: 'unsupported',
        feature: 'topK',
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

  private convertPrompt(prompt: LanguageModelV3Prompt): OpenAIMessage[] {
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

  private mapFinishReason(reason: string | null): LanguageModelV3FinishReason {
    let unified: 'stop' | 'length' | 'content-filter' | 'tool-calls' | 'error' | 'other';
    switch (reason) {
      case 'stop':
        unified = 'stop';
        break;
      case 'length':
        unified = 'length';
        break;
      case 'tool_calls':
        unified = 'tool-calls';
        break;
      case 'content_filter':
        unified = 'content-filter';
        break;
      case 'error':
        unified = 'error';
        break;
      default:
        unified = 'other';
    }
    return { unified, raw: reason ?? undefined };
  }

  private async callEndpoint(
    service: DiscoveredService,
    body: Record<string, unknown>,
    abortSignal?: AbortSignal,
    isRetryAfterKeyRefresh = false
  ): Promise<Response> {
    const freshService = this.discovery.getAllServices().find(s => s.name === service.name);
    const key = freshService?.ephemeralKey || service.ephemeralKey;
    
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (key) {
      headers['Authorization'] = `Bearer ${key}`;
    }

    const baseUrl = endpoint(freshService || service);
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

      if (response.status === 401 && key && !isRetryAfterKeyRefresh) {
        this.log('warn', `Ephemeral key expired for ${service.name}, requesting refresh`);
        const newKey = await this.discovery.waitForKeyRefresh(service.name, 2000);
        if (newKey && newKey !== key) {
          this.log('info', `Retrying with refreshed key for ${service.name}`);
          return this.callEndpoint(service, body, abortSignal, true);
        }
      }

      this.log('warn', `Request failed for ${service.name}`, {
        status: response.status,
        error: errorBody,
      });
      throw new Error(`HTTP ${response.status}: ${errorBody}`);
    }

    return response;
  }

  private async resolveEndpoints(options: { abortSignal?: AbortSignal }): Promise<DiscoveredService[]> {
    const directService = this.getDirectService();
    if (directService) {
      this.log('debug', 'Using direct endpoint mode', {
        endpoint: directService.endpoint,
        serviceName: directService.name,
      });
      return [directService];
    }

    await this.waitForDiscoveryFn();

    let endpoints: DiscoveredService[];

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

    return endpoints;
  }

  async doGenerate(options: LanguageModelV3CallOptions): Promise<LanguageModelV3GenerateResult> {
    const endpoints = await this.resolveEndpoints(options);

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
            delay: this.settings.retryDelay ?? 500,
          },
          this.logger
        );

        const data = (await response.json()) as OpenAIChatResponse;
        this.circuitBreaker.recordSuccess(service.name);

        const choice = data.choices[0];
        const content: LanguageModelV3Content[] = [];

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
            inputTokens: {
              total: data.usage.prompt_tokens,
              noCache: undefined,
              cacheRead: undefined,
              cacheWrite: undefined,
            },
            outputTokens: {
              total: data.usage.completion_tokens,
              text: data.usage.completion_tokens,
              reasoning: undefined,
            },
            raw: data.usage as unknown as JSONObject,
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

  async doStream(options: LanguageModelV3CallOptions): Promise<LanguageModelV3StreamResult> {
    const endpoints = await this.resolveEndpoints(options);

    const { body, warnings } = this.getArgs(options);
    body.stream = true;

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
            delay: this.settings.retryDelay ?? 500,
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

  private createFailoverStream(
    initialResponse: Response,
    initialWarnings: SharedV3Warning[],
    requestBody: Record<string, unknown>,
    fallbackEndpoints: DiscoveredService[],
    abortSignal?: AbortSignal
  ): ReadableStream<LanguageModelV3StreamPart> {
    let currentResponse = initialResponse;
    let currentReader = currentResponse.body!.getReader();
    const decoder = new TextDecoder();

    let buffer = '';
    let isFirstChunk = true;
    let hasEmittedContent = false;
    let finishReason: LanguageModelV3FinishReason = { unified: 'other', raw: undefined };
    let usage: LanguageModelV3Usage = {
      inputTokens: { total: undefined, noCache: undefined, cacheRead: undefined, cacheWrite: undefined },
      outputTokens: { total: undefined, text: undefined, reasoning: undefined },
    };
    let currentTextId: string | null = null;
    const toolInputIds = new Map<number, string>();
    const toolNames = new Map<string, string>();
    const toolInputs = new Map<string, string>();
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
          self.log('info', `Mid-stream failover to ${service.name}`);
          const response = await self.callEndpoint(service, requestBody, abortSignal);
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
                    toolNames.set(newToolId, tc.function?.name || '');
                    toolInputs.set(newToolId, '');
                    controller.enqueue({
                      type: 'tool-input-start',
                      id: newToolId,
                      toolName: tc.function?.name || '',
                    });
                  }

                  if (toolId !== undefined && tc.function?.arguments) {
                    toolInputs.set(toolId, (toolInputs.get(toolId) || '') + tc.function.arguments);
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
                  controller.enqueue({
                    type: 'tool-call',
                    toolCallId: toolId,
                    toolName: toolNames.get(toolId) || '',
                    input: toolInputs.get(toolId) || '{}',
                  });
                }
              }

              if (parsed.usage) {
                self.log('debug', 'Received usage', { usage: parsed.usage });
                usage = {
                  inputTokens: {
                    total: parsed.usage.prompt_tokens,
                    noCache: undefined,
                    cacheRead: undefined,
                    cacheWrite: undefined,
                  },
                  outputTokens: {
                    total: parsed.usage.completion_tokens,
                    text: parsed.usage.completion_tokens,
                    reasoning: undefined,
                  },
                  raw: parsed.usage,
                };
              }

              if (choice.finish_reason) {
                if (currentTextId) {
                  controller.enqueue({ type: 'text-end', id: currentTextId });
                  currentTextId = null;
                }
                if (finishReason.unified !== 'tool-calls') {
                  controller.enqueue({ type: 'finish', finishReason, usage });
                  controller.close();
                  currentReader.cancel().catch(() => {});
                  return;
                }
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

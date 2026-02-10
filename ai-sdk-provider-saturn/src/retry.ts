import type { SaturnLogger } from './logger.js';

interface RetryOptions {
  maxAttempts: number;
  delay: number;
}

export async function withRetry<T>(
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
        logger?.log('debug', `Retry attempt ${attempt + 1}/${options.maxAttempts} after ${options.delay}ms`, {
          error: lastError.message,
        });
        await new Promise((r) => setTimeout(r, options.delay));
      }
    }
  }

  throw lastError;
}

// taken from https://martinfowler.com/bliki/CircuitBreaker.html
// Per-service health tracker (Circuit Breaker pattern, credit: Martin Fowler)
// closed = healthy, open = failing (skip it), half-open = probing after cooldown
interface CircuitState {
  failures: number;
  lastFailure: number;
  state: 'closed' | 'open' | 'half-open';
}

export class ServiceCircuitBreaker {
  private circuits = new Map<string, CircuitState>();
  private readonly threshold: number;
  private readonly resetTimeout: number;

  constructor(threshold = 3, resetTimeout = 30000) {
    this.threshold = threshold;
    this.resetTimeout = resetTimeout;
  }

  // Track a failed request. After `threshold` failures, trip the circuit open.
  recordFailure(serviceName: string): void {
    const circuit = this.circuits.get(serviceName) || {
      failures: 0,
      lastFailure: 0,
      state: 'closed' as const,
    };

    circuit.failures++;
    circuit.lastFailure = Date.now();

    if (circuit.failures >= this.threshold) {
      circuit.state = 'open'; // stop sending requests to this service
    }

    this.circuits.set(serviceName, circuit);
  }

  // A request succeeded — reset the circuit back to healthy.
  recordSuccess(serviceName: string): void {
    const circuit = this.circuits.get(serviceName);
    if (circuit) {
      circuit.failures = 0;
      circuit.state = 'closed';
    }
  }

  // Should we send requests to this service?
  isAvailable(serviceName: string): boolean {
    const circuit = this.circuits.get(serviceName);
    if (!circuit) return true; // never seen = assume healthy

    if (circuit.state === 'closed') return true;

    if (circuit.state === 'open') {
      // Cooldown elapsed — let one request through to test recovery
      if (Date.now() - circuit.lastFailure > this.resetTimeout) {
        circuit.state = 'half-open';
        return true;
      }
      return false; // still in cooldown, skip this service
    }

    return true; // half-open: allow the probe request
  }
}

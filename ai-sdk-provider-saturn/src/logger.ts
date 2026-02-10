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

export function createDefaultLogger(minLevel: LogLevel = 'info'): SaturnLogger {
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

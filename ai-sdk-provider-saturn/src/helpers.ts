import type { DiscoveredService } from './types.js';

export function endpoint(service: DiscoveredService): string {
  if (service.deployment === 'cloud') return service.apiBase;
  return service.endpoint;
}

export function extractProvider(apiBase: string): string {
  try {
    return new URL(apiBase).hostname.toLowerCase();
  } catch {
    return 'unknown';
  }
}

export function isIPAddress(host: string): boolean {
  const ipv4Regex = /^(\d{1,3}\.){3}\d{1,3}$/;
  const ipv6Regex = /^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|^::1$/;
  return ipv4Regex.test(host) || ipv6Regex.test(host);
}

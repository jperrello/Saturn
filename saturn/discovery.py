import socket
import subprocess
import sys
import time
import socket
import threading
import logging
import argparse
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from zeroconf import ServiceBrowser, ServiceListener, Zeroconf, ServiceInfo

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 5.0


@dataclass
class SaturnService:
    name: str
    host: str
    port: int
    models: List[str] = field(default_factory=list)        # e.g., ["llama3.2", "mistral"]
    capabilities: List[str] = field(default_factory=list)  # e.g., ["chat", "code", "vision"]
    context: int = 4096                                    # max context window
    cost: str = "unknown"                                  # free, paid, unknown
    priority: int = 100                                    # lower = preferred (same as old)
    mcp: str = "none"                                      # MCP version or "none"
    transport: str = "http"                                # http, https, stdio
    auth: str = "none"                                     # none, psk, bearer
    saturn: str = "2.0"                                    # Saturn protocol version
    txtvers: str = "1"                                     # TXT record schema version
    # Beacon-specific fields (for pure mDNS announcers that broadcast ephemeral keys)
    ephemeral_key: str = ""                                # API key/JWT for direct provider access
    api: str = ""                                          # Provider name (e.g., "OpenRouter", "DeepInfra")
    api_base: str = ""                                     # Provider API base URL (e.g., "https://openrouter.ai/api/v1")
    beacon_features: str = ""                              # Feature flags (e.g., "ephemeral_auth")

    @property
    def is_beacon(self) -> bool:
        return bool(self.ephemeral_key)

    @property
    def endpoint(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def mcp_endpoint(self) -> str:
        return f"{self.endpoint}/mcp"

    def has_model(self, model: str) -> bool:
        return model in self.models

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities

    def has_all_capabilities(self, needs: List[str]) -> bool:
        return all(cap in self.capabilities for cap in needs)


class SaturnDiscovery(ServiceListener):
    SERVICE_TYPE = "_saturn._tcp.local."

    def __init__(self, on_service_change=None):
        self.services: Dict[str, SaturnService] = {}
        self.lock = threading.Lock()
        self.on_service_change = on_service_change
        self.zeroconf = Zeroconf()
        self.browser = ServiceBrowser(self.zeroconf, self.SERVICE_TYPE, self)

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if not info:
            return

        try:
            if info.addresses:
                ip_address = socket.inet_ntoa(info.addresses[0])
            else:
                ip_address = info.server.rstrip('.')
        except Exception:
            ip_address = info.server.rstrip('.') if info.server else "unknown"

        props = {}
        if info.properties:
            for k, v in info.properties.items():
                key = k.decode('utf-8') if isinstance(k, bytes) else k
                val = v.decode('utf-8') if isinstance(v, bytes) else str(v)
                props[key] = val

        models_str = props.get('models', '')
        models = [m for m in models_str.split(',') if m]

        capabilities_str = props.get('capabilities', '')
        capabilities = [c for c in capabilities_str.split(',') if c]

        service_name = name.replace(f'.{type_}', '')

        service = SaturnService(
            name=service_name,
            host=ip_address,
            port=info.port,
            models=models,
            capabilities=capabilities,
            context=int(props.get('context', 4096)),
            cost=props.get('cost', 'unknown'),
            priority=int(props.get('priority', 100)),
            mcp=props.get('mcp', 'none'),
            transport=props.get('transport', 'http'),
            auth=props.get('auth', 'none'),
            saturn=props.get('saturn', '2.0'),
            txtvers=props.get('txtvers', '1'),
            # Beacon-specific fields
            ephemeral_key=props.get('ephemeral_key', ''),
            api=props.get('api', ''),
            api_base=props.get('api_base', ''),
            beacon_features=props.get('features', ''),
        )

        with self.lock:
            is_new = service_name not in self.services
            self.services[service_name] = service

            if is_new:
                svc_type = "beacon" if service.is_beacon else "service"
                logger.info(f"Discovered Saturn {svc_type}: {service_name} at {ip_address}:{info.port}")
                if service.is_beacon:
                    logger.info(f"  api: {service.api} | priority: {service.priority}")
                else:
                    logger.info(f"  models: {', '.join(models) if models else 'none'}")
                    logger.info(f"  context: {service.context} | cost: {service.cost} | priority: {service.priority}")
                if self.on_service_change:
                    self.on_service_change('added', service)

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.add_service(zc, type_, name)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        service_name = name.replace(f'.{type_}', '')
        with self.lock:
            if service_name in self.services:
                removed_service = self.services.pop(service_name)
                logger.info(f"Removed Saturn service: {service_name}")
                if self.on_service_change:
                    self.on_service_change('removed', removed_service)

    def get_all_services(self) -> List[SaturnService]:
        with self.lock:
            return sorted(self.services.values(), key=lambda s: s.priority)

    def get_best_service(self) -> Optional[SaturnService]:
        with self.lock:
            if not self.services:
                return None
            return min(self.services.values(), key=lambda s: s.priority)

    def stop(self):
        self.browser.cancel()
        self.zeroconf.close()


def discover_services(timeout: float = 8.0, settle_time: float = 1.0) -> List[SaturnService]:
    # settle_time prevents returning too early - wait for network to calm down
    # mdns responses trickle in, so we wait until no new services for settle_time seconds
    service_event = threading.Event()
    last_discovery_time = [0.0]

    def on_change(action: str, service: SaturnService):
        if action == 'added':
            last_discovery_time[0] = time.time()
            service_event.set()

    discovery = SaturnDiscovery(on_service_change=on_change)
    deadline = time.time() + timeout

    while time.time() < deadline:
        service_event.wait(timeout=0.25)
        service_event.clear()

        services = discovery.get_all_services()
        if services:
            time_since_last = time.time() - last_discovery_time[0]
            if time_since_last >= settle_time:
                break

    services = discovery.get_all_services()
    discovery.stop()
    return services


def select_best_service(
    services: List[SaturnService],
    needs: Optional[List[str]] = None,
    min_context: int = 0,
    prefer_free: bool = True
) -> Optional[SaturnService]:
    candidates = services

    if needs:
        candidates = [s for s in candidates if s.has_all_capabilities(needs)]

    if min_context:
        candidates = [s for s in candidates if s.context >= min_context]

    if not candidates:
        return None

    if prefer_free:
        def sort_key(s):
            return (s.priority, 0 if s.cost == "free" else 1)
        candidates = sorted(candidates, key=sort_key)

    return candidates[0]


def _supports_unicode() -> bool:
    try:
        encoding = getattr(sys.stdout, 'encoding', None) or 'ascii'
        '\u2514\u2500'.encode(encoding)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def format_service_tree(service: SaturnService, prefix: str = "   ") -> str:
    if _supports_unicode():
        branch, tee, corner = '├─', '├─', '└─'
    else:
        branch, tee, corner = '+-', '+-', '+-'

    if service.is_beacon:
        lines = [
            f"{prefix}{corner} {service.name}._saturn._tcp.local (beacon)",
            f"{prefix}   {tee} api: {service.api}",
            f"{prefix}   {tee} api_base: {service.api_base or '(not set)'}",
            f"{prefix}   {tee} priority: {service.priority}",
            f"{prefix}   {corner} ephemeral_key: {service.ephemeral_key[:20]}..." if len(service.ephemeral_key) > 20 else f"{prefix}   {corner} ephemeral_key: {service.ephemeral_key}",
        ]
    else:
        lines = [
            f"{prefix}{corner} {service.name}._saturn._tcp.local",
            f"{prefix}   {tee} models: {', '.join(service.models) if service.models else 'none'}",
            f"{prefix}   {tee} capabilities: {', '.join(service.capabilities) if service.capabilities else 'none'}",
            f"{prefix}   {tee} context: {service.context} | cost: {service.cost}",
            f"{prefix}   {tee} priority: {service.priority}",
            f"{prefix}   {corner} mcp: {service.mcp}",
        ]
    return '\n'.join(lines)


def cli_discover(args):
    services = discover_services(timeout=args.timeout)

    if args.json:
        output = [asdict(s) for s in services]
        print(json.dumps(output, indent=2))
    else:
        if services:
            print(f"Saturn: {len(services)} service(s) discovered")
            for service in services:
                print(format_service_tree(service))
        else:
            corner = '└─' if _supports_unicode() else '+-'
            print("Saturn: 0 services found")
            print(f"   {corner} No local AI services on this network")
            print(f"   {corner} Routing will use cloud fallback")


def cli_endpoint(args):
    services = discover_services(timeout=args.timeout)
    if not services:
        print("# No Saturn services found", file=sys.stderr)
        return 1

    best = select_best_service(services, prefer_free=True)

    if args.json:
        print(json.dumps({"endpoint": best.endpoint, "name": best.name}))
    else:
        print(best.endpoint)

    return 0


def main():
    parser = argparse.ArgumentParser(
        prog='saturn',
        description='Saturn: Zero-configuration AI service discovery'
    )
    parser.add_argument('--timeout', type=float, default=5.0,
                        help='Discovery timeout in seconds')
    parser.add_argument('--json', action='store_true',
                        help='Output in JSON format')

    subparsers = parser.add_subparsers(dest='command', required=True)

    discover_parser = subparsers.add_parser('discover',
                                            help='Discover all available Saturn services')
    discover_parser.set_defaults(func=cli_discover)

    endpoint_parser = subparsers.add_parser('endpoint',
                                            help='Output the best service endpoint URL (for scripts)')
    endpoint_parser.set_defaults(func=cli_endpoint)

    args = parser.parse_args()
    return args.func(args)


class SaturnAdvertiser:
    SERVICE_TYPE = "_saturn._tcp.local."

    def __init__(
        self,
        name: str,
        port: int,
        models: List[str] = None,
        capabilities: List[str] = None,
        context: int = 4096,
        cost: str = "unknown",
        priority: int = 100,
        mcp: str = "none",
        transport: str = "http",
        auth: str = "none",
        saturn: str = "2.0",
        txtvers: str = "1",
    ):
        self.name = name
        self.port = port
        self.models = models or []
        self.capabilities = capabilities or ["chat"]
        self.context = context
        self.cost = cost
        self.priority = priority
        self.mcp = mcp
        self.transport = transport
        self.auth = auth
        self.saturn = saturn
        self.txtvers = txtvers
        self._zeroconf: Optional[Zeroconf] = None
        self._info: Optional[ServiceInfo] = None

    def _find_available_priority(self) -> int:
        # auto-resolve priority collisions by scanning existing services
        # if desired priority is taken, bump up until we find a free slot
        priorities = set()

        try:
            zc = Zeroconf()
            
            class PriorityListener(ServiceListener):
                def __init__(self):
                    self.priorities = set()
                    self.lock = threading.Lock()

                def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                    info = zc.get_service_info(type_, name)
                    if info and info.properties:
                        try:
                            p = info.properties.get(b'priority') or info.properties.get('priority')
                            if p:
                                val = p.decode('utf-8') if isinstance(p, bytes) else str(p)
                                with self.lock:
                                    self.priorities.add(int(val))
                        except (ValueError, AttributeError):
                            pass

                def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                    self.add_service(zc, type_, name)

                def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                    pass

            listener = PriorityListener()
            browser = ServiceBrowser(zc, self.SERVICE_TYPE, listener)
            time.sleep(2.0)
            browser.cancel()
            zc.close()

            with listener.lock:
                priorities = listener.priorities

        except Exception as e:
            logger.warning(f"Error checking priorities: {e}")
            return self.priority

        current = self.priority
        while current in priorities:
            logger.info(f"Priority {current} in use, trying {current + 1}")
            current += 1

        if current != self.priority:
            logger.info(f"Adjusted priority from {self.priority} to {current}")

        return current

    def register(self) -> bool:
        actual_priority = self._find_available_priority()

        # dns txt records max out at 255 bytes per string, we use 250 to be safe
        # if model list is too long, truncate and clients can hit /v1/models for full list
        models_str = ''
        models_truncated = False
        if self.models:
            parts = []
            for model in self.models:
                candidate = ','.join(parts + [model]) if parts else model
                if len(candidate.encode('utf-8')) <= 250:
                    parts.append(model)
                else:
                    models_truncated = True
                    break
            models_str = ','.join(parts)

        if models_truncated:
            logger.info(f"TXT record limited to {len(parts)}/{len(self.models)} models (full list via /v1/models)")

        capabilities_str = ','.join(self.capabilities) if self.capabilities else ''

        try:
            host = socket.gethostname()
            host_ip = socket.gethostbyname(host)

            self._zeroconf = Zeroconf()
            self._info = ServiceInfo(
                type_=self.SERVICE_TYPE,
                name=f"{self.name}.{self.SERVICE_TYPE}",
                port=self.port,
                addresses=[socket.inet_aton(host_ip)],
                server=f"{host}.local.",
                properties={
                    'txtvers': self.txtvers,
                    'saturn': self.saturn,
                    'mcp': self.mcp,
                    'transport': self.transport,
                    'models': models_str,
                    'capabilities': capabilities_str,
                    'context': str(self.context),
                    'cost': self.cost,
                    'priority': str(actual_priority),
                    'auth': self.auth,
                },
            )

            self._zeroconf.register_service(self._info)
            logger.info(f"Registered {self.name} on {self.SERVICE_TYPE} at port {self.port} with priority {actual_priority}")
            return True

        except Exception as e:
            logger.error(f"Failed to register service: {e}")
            return False

    def unregister(self):
        if self._zeroconf and self._info:
            logger.info(f"Unregistering {self.name} from {self.SERVICE_TYPE}")
            self._zeroconf.unregister_service(self._info)
            self._zeroconf.close()
            self._zeroconf = None
            self._info = None

    def __enter__(self):
        self.register()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unregister()
        return False


if __name__ == '__main__':
    exit(main() or 0)

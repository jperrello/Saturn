import socket
import subprocess
import sys
import time
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
    # Production schema fields (matches saturn-router Rust implementation)
    version: str = "1.0"                                   # Schema version
    deployment: str = "network"                            # "cloud" or "network"
    api_type: str = "openai"                               # "openai" or "ollama"
    api_base: str = ""                                     # Base URL for API calls
    priority: int = 100                                    # lower = preferred
    ephemeral_key: str = ""                                # API key for cloud deployments
    rotation_interval: int = 0                             # Key rotation interval in seconds
    features: str = ""                                     # "ephemeral_auth" or "network_proxy"
    # Extended fields for Saturn proxies (backwards compatible)
    models: List[str] = field(default_factory=list)        # e.g., ["llama3.2", "mistral"]
    capabilities: List[str] = field(default_factory=list)  # e.g., ["chat", "code", "vision"]
    context: int = 4096                                    # max context window
    cost: str = "unknown"                                  # free, paid, unknown

    @property
    def is_beacon(self) -> bool:
        return self.deployment == "cloud" and bool(self.ephemeral_key)

    @property
    def is_cloud(self) -> bool:
        return self.deployment == "cloud"

    @property
    def is_network(self) -> bool:
        return self.deployment == "network"

    @property
    def effective_endpoint(self) -> str:
        if self.deployment == "cloud" and self.api_base:
            return self.api_base
        return f"http://{self.host}:{self.port}/v1"

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

        rotation_str = props.get('rotation_interval', '0')
        try:
            rotation_interval = int(rotation_str)
        except ValueError:
            rotation_interval = 0

        service = SaturnService(
            name=service_name,
            host=ip_address,
            port=info.port,
            # Production schema fields (saturn-router compatible)
            version=props.get('version', '1.0'),
            deployment=props.get('deployment', 'network'),
            api_type=props.get('api_type', props.get('api', 'openai')),  # fallback to old 'api' field
            api_base=props.get('api_base', ''),
            priority=int(props.get('priority', 100)),
            ephemeral_key=props.get('ephemeral_key', ''),
            rotation_interval=rotation_interval,
            features=props.get('features', ''),
            # Extended fields for Saturn proxies
            models=models,
            capabilities=capabilities,
            context=int(props.get('context', 4096)),
            cost=props.get('cost', 'unknown'),
        )

        with self.lock:
            is_new = service_name not in self.services
            self.services[service_name] = service

            if is_new:
                svc_type = "beacon" if service.is_beacon else "service"
                logger.info(f"Discovered Saturn {svc_type}: {service_name} at {ip_address}:{info.port}")
                logger.info(f"  deployment: {service.deployment} | api_type: {service.api_type} | priority: {service.priority}")
                if service.is_beacon:
                    logger.info(f"  api_base: {service.api_base}")
                else:
                    logger.info(f"  models: {', '.join(models) if models else 'none'}")
                    logger.info(f"  context: {service.context} | cost: {service.cost}")
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


def discover(timeout: float = 8.0, settle_time: float = 1.0) -> List[SaturnService]:
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

    deployment_label = "cloud" if service.is_cloud else "network"
    if service.is_beacon:
        key_display = f"{service.ephemeral_key[:20]}..." if len(service.ephemeral_key) > 20 else service.ephemeral_key
        lines = [
            f"{prefix}{corner} {service.name}._saturn._tcp.local ({deployment_label})",
            f"{prefix}   {tee} api_type: {service.api_type}",
            f"{prefix}   {tee} api_base: {service.api_base or '(not set)'}",
            f"{prefix}   {tee} priority: {service.priority}",
            f"{prefix}   {tee} features: {service.features}",
            f"{prefix}   {corner} ephemeral_key: {key_display}",
        ]
    else:
        lines = [
            f"{prefix}{corner} {service.name}._saturn._tcp.local ({deployment_label})",
            f"{prefix}   {tee} api_type: {service.api_type}",
            f"{prefix}   {tee} models: {', '.join(service.models) if service.models else 'none'}",
            f"{prefix}   {tee} capabilities: {', '.join(service.capabilities) if service.capabilities else 'none'}",
            f"{prefix}   {tee} context: {service.context} | cost: {service.cost}",
            f"{prefix}   {corner} priority: {service.priority}",
        ]
    return '\n'.join(lines)


def cli_discover(args):
    services = discover(timeout=args.timeout)

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
    services = discover(timeout=args.timeout)
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


def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return socket.gethostbyname(socket.gethostname())
    finally:
        s.close()


class SaturnAdvertiser:
    SERVICE_TYPE = "_saturn._tcp.local."

    def __init__(
        self,
        name: str,
        port: int,
        # Production schema fields (matches saturn-router Rust implementation)
        deployment: str = "network",
        api_type: str = "openai",
        api_base: str = None,
        priority: int = 100,
        # Extended fields for Saturn proxies
        models: List[str] = None,
        capabilities: List[str] = None,
        context: int = 4096,
        cost: str = "unknown",
        # Legacy fields (kept for backwards compatibility but not advertised)
        mcp: str = "none",
    ):
        self.name = name
        self.port = port
        # Production schema
        self.deployment = deployment
        self.api_type = api_type
        self.api_base = api_base  # Will be computed if not provided
        self.priority = priority
        # Extended fields
        self.models = models or []
        self.capabilities = capabilities or ["chat"]
        self.context = context
        self.cost = cost
        self.mcp = mcp
        self._zeroconf: Optional[Zeroconf] = None
        self._info: Optional[ServiceInfo] = None

    def _find_available_priority(self) -> int:
        # scan network for existing services to avoid priority collisions
        try:
            services = discover(timeout=2.0, settle_time=0.5)
            priorities = {s.priority for s in services}
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


    def _properties(self) -> dict:
        MODELS_KEY = 'models'
        MAX_TXT_RECORD_BYTES = 255
        MAX_VALUE_BYTES = MAX_TXT_RECORD_BYTES - len(MODELS_KEY) - 1

        models_str = ''
        models_truncated = False
        if self.models:
            parts = []
            for model in self.models:
                candidate = ','.join(parts + [model]) if parts else model
                if len(candidate.encode('utf-8')) <= MAX_VALUE_BYTES:
                    parts.append(model)
                else:
                    models_truncated = True
                    break
            models_str = ','.join(parts)

        if models_truncated:
            logger.info(f"TXT record limited to {len(parts)}/{len(self.models)} models (full list via /v1/models)")

        capabilities_str = ','.join(self.capabilities) if self.capabilities else ''
        features = "network_proxy" if self.deployment == "network" else ""

        return {
            'version': '1.0',
            'deployment': self.deployment,
            'api_type': self.api_type,
            'api_base': self.api_base,
            'priority': str(self.priority),
            'features': features,
            'models': models_str,
            'capabilities': capabilities_str,
            'context': str(self.context),
            'cost': self.cost,
        }

    def register(self) -> bool:
        actual_priority = self._find_available_priority()

        try:
            host = socket.gethostname()
            host_ip = get_lan_ip()

            if not self.api_base:
                self.api_base = f"http://{host_ip}:{self.port}/v1"

            self.priority = actual_priority
            self._zeroconf = Zeroconf()
            self._info = ServiceInfo(
                type_=self.SERVICE_TYPE,
                name=f"{self.name}.{self.SERVICE_TYPE}",
                port=self.port,
                addresses=[socket.inet_aton(host_ip)],
                server=f"{host}.local.",
                properties=self._properties(),
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

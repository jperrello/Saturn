import socket
import subprocess
import sys
import threading
import logging
import argparse
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from saturn.mdns.identity import get_node_id
from saturn.mdns.backend import ServiceRecord
from saturn.mdns import known_nodes

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 5.0

_SELECTABLE = {"pinned", "first_seen", "allowlist"}
_trust_mode = "tofu"
_allowlist: set = set()


class TrustRebindError(RuntimeError):
    def __init__(self, service_name: str, expected_node_id: str, seen_node_id: str, seen_host: str):
        self.service_name = service_name
        self.expected_node_id = expected_node_id
        self.seen_node_id = seen_node_id
        self.seen_host = seen_host
        super().__init__(
            f"refusing service '{service_name}': pinned node_id "
            f"{expected_node_id[:8]}… does not match advertised "
            f"{seen_node_id[:8]}… (seen at {seen_host})"
        )


def set_trust_policy(mode: str, allowlist=None) -> None:
    global _trust_mode, _allowlist
    _trust_mode = mode if mode in ("tofu", "allowlist", "open") else "tofu"
    _allowlist = set(allowlist or [])


def _classify_trust(s: "SaturnService") -> str:
    if _trust_mode == "open":
        return "unknown"
    if _trust_mode == "allowlist":
        return "allowlist" if s.node_id and s.node_id in _allowlist else "rebind_rejected"
    pinned = known_nodes.known_node_id(s.name)
    if pinned is None:
        return "first_seen"
    if pinned == s.node_id:
        return "pinned"
    return "rebind_rejected"


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
    node_id: str = ""                                      # stable UUID from saturn/mdns/identity.py
    trust: str = "unknown"                                 # pinned|first_seen|rebind_rejected|allowlist|unknown

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


class SaturnDiscovery:
    SERVICE_TYPE = "_saturn._tcp.local."

    def __init__(self, on_service_change=None, backend=None):
        self.services: Dict[str, SaturnService] = {}
        self.lock = threading.Lock()
        self.on_service_change = on_service_change
        if backend is None:
            from saturn.mdns.detect import backend as make_backend
            self._backend = make_backend()
            self._backend.browse(self._on_event)
        else:
            self._backend = backend
            if backend is not False:
                backend.browse(self._on_event)

    def _to_service(self, rec: ServiceRecord) -> SaturnService:
        props = rec.txt
        models_str = props.get('models', '')
        models = [m for m in models_str.split(',') if m]
        capabilities_str = props.get('capabilities', '')
        capabilities = [c for c in capabilities_str.split(',') if c]
        rotation_str = props.get('rotation_interval', '0')
        try:
            rotation_interval = int(rotation_str)
        except ValueError:
            rotation_interval = 0
        return SaturnService(
            name=rec.name,
            host=rec.host,
            port=rec.port,
            version=props.get('version', '1.0'),
            deployment=props.get('dep', props.get('deployment', 'network')),
            api_type=props.get('api_type', props.get('api', 'openai')),
            api_base=props.get('api_base', ''),
            priority=int(props.get('priority', 100)),
            ephemeral_key=props.get('ephemeral_key', ''),
            rotation_interval=rotation_interval,
            features=props.get('features', ''),
            models=models,
            capabilities=capabilities,
            context=int(props.get('context', 4096)),
            cost=props.get('cost', 'unknown'),
            node_id=rec.node_id,
        )

    def _on_event(self, event) -> None:
        action, rec = event
        if action in ('added', 'updated'):
            self._add(rec)
        elif action == 'removed':
            self._remove(rec.name)

    def _add(self, rec: ServiceRecord) -> None:
        service = self._to_service(rec)
        service.trust = _classify_trust(service)
        if service.trust in ("first_seen", "pinned") and service.node_id:
            known_nodes.pin(service.name, service.node_id, service.host)
            service.trust = "pinned"
        elif service.trust == "rebind_rejected" and service.node_id:
            known_nodes.record_rejection(service.name, service.node_id, service.host, "rebind_attempt")
        if service.node_id:
            key = f"{service.node_id}:{service.name}"
        else:
            key = service.name

        with self.lock:
            if service.node_id:
                for k, s in self.services.items():
                    if s.node_id == service.node_id and s.name != service.name:
                        logger.warning(f"Duplicate node_id {service.node_id}: {service.name} and {s.name}")
                        break
            is_new = key not in self.services
            self.services[key] = service

            if is_new:
                svc_type = "beacon" if service.is_beacon else "service"
                logger.info(f"Discovered Saturn {svc_type}: {service.name} at {service.host}:{service.port}")
                logger.info(f"  deployment: {service.deployment} | api_type: {service.api_type} | priority: {service.priority}")
                if service.is_beacon:
                    logger.info(f"  api_base: {service.api_base}")
                else:
                    logger.info(f"  models: {', '.join(service.models) if service.models else 'none'}")
                    logger.info(f"  context: {service.context} | cost: {service.cost}")
                if self.on_service_change:
                    self.on_service_change('added', service)

    def _remove(self, name: str) -> None:
        with self.lock:
            key = name
            if name not in self.services:
                for k, s in self.services.items():
                    if s.name == name:
                        key = k
                        break
            if key in self.services:
                removed = self.services.pop(key)
                logger.info(f"Removed Saturn service: {name}")
                if self.on_service_change:
                    self.on_service_change('removed', removed)

    def get_all_services(self) -> List[SaturnService]:
        with self.lock:
            return sorted(
                (s for s in self.services.values() if (_trust_mode == "open" or s.trust in _SELECTABLE)),
                key=lambda s: s.priority,
            )

    def get_best_service(self) -> Optional[SaturnService]:
        with self.lock:
            candidates = [s for s in self.services.values() if (_trust_mode == "open" or s.trust in _SELECTABLE)]
            if not candidates:
                return None
            return min(candidates, key=lambda s: s.priority)

    def reclassify_all(self) -> None:
        with self.lock:
            for s in self.services.values():
                s.trust = _classify_trust(s)

    def stop(self):
        self._backend.stop_browse()
        self._backend.close()


def discover(timeout: float = 8.0, settle_time: float = 1.0) -> List[SaturnService]:
    from saturn.mdns.settle import SettleDetector

    settle = SettleDetector()

    def on_change(action, service):
        if action == 'added':
            settle.arm()

    discovery = SaturnDiscovery(on_service_change=on_change)
    settle.wait(timeout=timeout)

    services = discovery.get_all_services()
    discovery.stop()
    settle.close()
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


def _sanitize_txt_value(v: str) -> str:
    v = v.replace("=", "").replace("\x00", "").replace("\n", "").replace("\r", "")
    encoded = v.encode("utf-8")[:63]
    return encoded.decode("utf-8", errors="ignore")


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
        role: str = "",
    ):
        self.name = name
        self.port = port
        # Production schema
        self.deployment = deployment
        self.api_type = api_type
        self.api_base = api_base
        self.priority = priority
        # Extended fields
        self.models = models or []
        self.capabilities = capabilities or ["chat"]
        self.context = context
        self.cost = cost
        self.mcp = mcp
        from saturn.mdns.subtypes import subtypes_for_role
        self._subtypes = subtypes_for_role(role)
        from saturn.mdns.detect import backend as make_backend
        self._backend = make_backend()

    def _properties(self) -> dict:
        MODELS_KEY = 'models'
        MAX_VALUE_BYTES = 200

        models_str = ''
        models_truncated = False
        if self.models:
            parts = []
            for model in self.models:
                clean = _sanitize_txt_value(model)
                candidate = ','.join(parts + [clean]) if parts else clean
                if len(candidate.encode('utf-8')) <= MAX_VALUE_BYTES:
                    parts.append(clean)
                else:
                    models_truncated = True
                    break
            models_str = ','.join(parts)

        if models_truncated:
            logger.info(f"TXT record limited to {len(parts)}/{len(self.models)} models (full list via /v1/models)")

        capabilities_str = ','.join(self.capabilities) if self.capabilities else ''
        features = "network_proxy" if self.deployment == "network" else ""

        props = {
            'id': get_node_id(),
            'v': '2',
            'version': '1.0',
            'dep': self.deployment,       # short key (v2)
            'deployment': self.deployment, # backward compat
            'api_type': self.api_type,
            'api_base': self.api_base,
            'priority': str(self.priority),
            'features': features,
            'models': models_str,
            'capabilities': capabilities_str,
            'context': str(self.context),
            'cost': self.cost,
        }
        if models_truncated:
            props['mtrunc'] = '1'
        return props

    def register(self) -> bool:
        from saturn.mdns.backend import AdvertiseSpec
        try:
            if not self.api_base:
                host_ip = get_lan_ip()
                self.api_base = f"http://{host_ip}:{self.port}/v1"

            spec = AdvertiseSpec(
                name=self.name,
                port=self.port,
                txt=self._properties(),
                subtypes=self._subtypes,
            )
            self._backend.advertise(spec)
            logger.info(f"Registered {self.name} on {self.SERVICE_TYPE} at port {self.port} with priority {self.priority}")
            return True

        except Exception as e:
            logger.error(f"Failed to register service: {e}")
            return False

    def unregister(self):
        logger.info(f"Unregistering {self.name} from {self.SERVICE_TYPE}")
        self._backend.withdraw()
        self._backend.close()

    def __enter__(self):
        self.register()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unregister()
        return False


if __name__ == '__main__':
    exit(main() or 0)

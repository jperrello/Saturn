import socket
import subprocess
import time
import re
import threading
import logging
import argparse
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class RingsService:
    name: str
    host: str
    port: int
    models: List[str] = field(default_factory=list)
    context: int = 4096
    cost: str = "unknown"
    priority: int = 100
    mcp: str = "unknown"
    transport: str = "http"
    auth: str = "none"
    saturn: str = "2.0"

    @property
    def endpoint(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def mcp_endpoint(self) -> str:
        return f"{self.endpoint}/mcp"

    def has_model(self, model: str) -> bool:
        return model in self.models


class RingsDiscovery:
    SERVICE_TYPE = "_rings._tcp"

    def __init__(self, discovery_interval: int = 10, on_service_change=None):
        self.services: Dict[str, RingsService] = {}
        self.lock = threading.Lock()
        self.running = True
        self.discovery_interval = discovery_interval
        self.on_service_change = on_service_change
        self.service_found = threading.Event()
        self.thread = threading.Thread(target=self._discovery_loop, daemon=True)
        self.thread.start()

    def _discovery_loop(self):
        while self.running:
            try:
                self._discover_services()
            except Exception as e:
                logger.error(f"Error in rings discovery: {e}")
            time.sleep(self.discovery_interval)

    def _discover_services(self):
        try:
            browse_proc = subprocess.Popen(
                ['dns-sd', '-B', self.SERVICE_TYPE, 'local'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            time.sleep(2.0)
            browse_proc.terminate()

            try:
                stdout, stderr = browse_proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                browse_proc.kill()
                stdout, stderr = browse_proc.communicate()

            service_names = []
            for line in stdout.split('\n'):
                if 'Add' in line and self.SERVICE_TYPE in line:
                    parts = line.split()
                    if len(parts) > 6:
                        service_name = parts[6]
                        service_names.append(service_name)

            discovered_services = set()

            for service_name in service_names:
                try:
                    lookup_proc = subprocess.Popen(
                        ['dns-sd', '-L', service_name, self.SERVICE_TYPE, 'local'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )

                    time.sleep(1.5)
                    lookup_proc.terminate()

                    try:
                        stdout, stderr = lookup_proc.communicate(timeout=2)
                    except subprocess.TimeoutExpired:
                        lookup_proc.kill()
                        stdout, stderr = lookup_proc.communicate()

                    hostname = None
                    port = None
                    txt_records = {}

                    for line in stdout.split('\n'):
                        if 'can be reached at' in line:
                            match = re.search(r'can be reached at (.+):(\d+)', line)
                            if match:
                                hostname = match.group(1).rstrip('.')
                                port = int(match.group(2))

                        for key in ['models', 'context', 'cost', 'priority', 'mcp', 'transport', 'auth', 'saturn']:
                            if f'{key}=' in line:
                                match = re.search(rf'{key}=([^\s]+)', line)
                                if match:
                                    txt_records[key] = match.group(1)

                    if hostname and port:
                        try:
                            ip_address = socket.gethostbyname(hostname)
                        except socket.gaierror:
                            ip_address = hostname

                        discovered_services.add(service_name)

                        models_str = txt_records.get('models', '')
                        models = models_str.split(',') if models_str else []

                        service = RingsService(
                            name=service_name,
                            host=ip_address,
                            port=port,
                            models=models,
                            context=int(txt_records.get('context', 4096)),
                            cost=txt_records.get('cost', 'unknown'),
                            priority=int(txt_records.get('priority', 100)),
                            mcp=txt_records.get('mcp', 'unknown'),
                            transport=txt_records.get('transport', 'http'),
                            auth=txt_records.get('auth', 'none'),
                            saturn=txt_records.get('saturn', '2.0'),
                        )

                        with self.lock:
                            is_new = service_name not in self.services
                            self.services[service_name] = service

                            if is_new:
                                logger.info(f"Discovered rings service: {service_name} at {ip_address}:{port}")
                                logger.info(f"  models: {', '.join(models) if models else 'none'}")
                                logger.info(f"  context: {service.context} | cost: {service.cost} | priority: {service.priority}")
                                if self.on_service_change:
                                    self.on_service_change('added', service)

                            self.service_found.set()

                except (subprocess.TimeoutExpired, ValueError, IndexError) as e:
                    logger.debug(f"Error looking up service {service_name}: {e}")
                    continue

            with self.lock:
                services_to_remove = [name for name in self.services.keys() if name not in discovered_services]
                for name in services_to_remove:
                    removed_service = self.services[name]
                    del self.services[name]
                    logger.info(f"Removed rings service: {name}")
                    if self.on_service_change:
                        self.on_service_change('removed', removed_service)

        except FileNotFoundError:
            logger.error("dns-sd not found. Install Bonjour (Windows) or avahi-utils (Linux).")
            self.running = False
        except Exception as e:
            logger.error(f"Error during rings discovery: {e}")

    def get_all_services(self) -> List[RingsService]:
        with self.lock:
            return sorted(self.services.values(), key=lambda s: s.priority)

    def get_best_service(self) -> Optional[RingsService]:
        with self.lock:
            if not self.services:
                return None
            return min(self.services.values(), key=lambda s: s.priority)

    def stop(self):
        self.running = False


def discover_rings(timeout: float = 5.0) -> List[RingsService]:
    discovery = RingsDiscovery()
    discovery.service_found.wait(timeout=timeout)
    time.sleep(0.5)
    services = discovery.get_all_services()
    discovery.stop()
    return services


def cli_discover(args):
    services = discover_rings(timeout=args.timeout)
    output = [asdict(s) for s in services]
    print(json.dumps(output, indent=2))


def cli_select(args):
    services = discover_rings(timeout=args.timeout)
    if not services:
        print(json.dumps({"error": "No services found"}))
        return 1
    best = services[0]
    print(json.dumps(asdict(best), indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog='saturn-rings',
        description='Saturn Rings: Zero-configuration AI service discovery'
    )
    parser.add_argument('--timeout', type=float, default=5.0,
                        help='Discovery timeout in seconds')

    subparsers = parser.add_subparsers(dest='command', required=True)

    discover_parser = subparsers.add_parser('discover',
                                            help='Discover all available rings services')
    discover_parser.set_defaults(func=cli_discover)

    select_parser = subparsers.add_parser('select',
                                          help='Select the best available service')
    select_parser.set_defaults(func=cli_select)

    args = parser.parse_args()
    return args.func(args)


class RingsAdvertiser:
    SERVICE_TYPE = "_rings._tcp"

    def __init__(
        self,
        name: str,
        port: int,
        models: List[str] = None,
        context: int = 4096,
        cost: str = "unknown",
        priority: int = 100,
        mcp: str = "unknown",
        transport: str = "http",
        auth: str = "none",
        saturn: str = "2.0",
    ):
        self.name = name
        self.port = port
        self.models = models or []
        self.context = context
        self.cost = cost
        self.priority = priority
        self.mcp = mcp
        self.transport = transport
        self.auth = auth
        self.saturn = saturn
        self._proc: Optional[subprocess.Popen] = None

    def _find_available_priority(self) -> int:
        priorities = set()

        try:
            browse_proc = subprocess.Popen(
                ['dns-sd', '-B', self.SERVICE_TYPE, 'local'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            time.sleep(2.0)
            browse_proc.terminate()

            try:
                stdout, _ = browse_proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                browse_proc.kill()
                stdout, _ = browse_proc.communicate()

            for line in stdout.split('\n'):
                if self.SERVICE_TYPE in line and 'Add' in line:
                    parts = line.split()
                    if len(parts) > 6:
                        service_name = parts[6]
                        try:
                            lookup_proc = subprocess.Popen(
                                ['dns-sd', '-L', service_name, self.SERVICE_TYPE, 'local'],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )

                            time.sleep(1.5)
                            lookup_proc.terminate()

                            try:
                                lookup_stdout, _ = lookup_proc.communicate(timeout=2)
                            except subprocess.TimeoutExpired:
                                lookup_proc.kill()
                                continue

                            for lookup_line in lookup_stdout.split('\n'):
                                if 'priority=' in lookup_line:
                                    match = re.search(r'priority=(\d+)', lookup_line)
                                    if match:
                                        priorities.add(int(match.group(1)))
                        except (subprocess.TimeoutExpired, ValueError):
                            continue
        except FileNotFoundError:
            logger.warning("dns-sd not found, using desired priority")
            return self.priority
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

        models_str = ','.join(self.models) if self.models else ''

        cmd = [
            'dns-sd', '-R',
            self.name, self.SERVICE_TYPE, 'local',
            str(self.port),
            f'models={models_str}',
            f'context={self.context}',
            f'cost={self.cost}',
            f'priority={actual_priority}',
            f'mcp={self.mcp}',
            f'transport={self.transport}',
            f'auth={self.auth}',
            f'saturn={self.saturn}',
        ]

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            logger.info(f"Registered {self.name} on {self.SERVICE_TYPE} at port {self.port} with priority {actual_priority}")
            return True
        except FileNotFoundError:
            logger.error("dns-sd not found. Install Bonjour (Windows) or avahi-utils (Linux).")
            return False
        except Exception as e:
            logger.error(f"Failed to register service: {e}")
            return False

    def unregister(self):
        if self._proc:
            logger.info(f"Unregistering {self.name} from {self.SERVICE_TYPE}")
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None

    def __enter__(self):
        self.register()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unregister()
        return False


if __name__ == '__main__':
    exit(main() or 0)

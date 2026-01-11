import subprocess
import socket
import time
import requests
import threading
import re
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

# Alternatively, you could run one of these commands to listen for Saturn servers:
# Windows/macOS: dns-sd -B _saturn._tcp local
# Linux: avahi-browse _saturn._tcp -t
# For details: dns-sd -L <service_name> _saturn._tcp (or avahi-browse _saturn._tcp -t -r)

@dataclass
class SaturnService:
    name: str
    url: str
    priority: int
    ip: str
    last_seen: datetime

class ServiceDiscovery:
    """Background service discovery using DNS-SD"""
    def __init__(self, discovery_interval: int = 10, on_service_change=None):
        self.services: Dict[str, SaturnService] = {}
        self.lock = threading.Lock()
        self.running = True
        self.discovery_interval = discovery_interval
        self.on_service_change = on_service_change
        self.thread = threading.Thread(target=self._discovery_loop, daemon=True)
        self.thread.start()

    def _discovery_loop(self):
        """Continuously discover services in background"""
        while self.running:
            try:
                self._discover_services()
            except Exception as e:
                print(f"Discovery error: {e}")
            time.sleep(self.discovery_interval)

    def _discover_services(self):
        """Single discovery pass using DNS-SD"""
        discovered = self._run_dns_sd_discovery()
        if discovered is None:
            return

        current_time = datetime.now()
        discovered_names = set()

        with self.lock:
            # Update or add discovered services
            for svc in discovered:
                discovered_names.add(svc['name'])

                if svc['name'] not in self.services:
                    # New service
                    self.services[svc['name']] = SaturnService(
                        name=svc['name'],
                        url=svc['url'],
                        priority=svc['priority'],
                        ip=svc['ip'],
                        last_seen=current_time
                    )
                    if self.on_service_change:
                        self.on_service_change('added', svc['name'], svc['url'], svc['priority'])
                else:
                    # Update existing
                    service = self.services[svc['name']]
                    service.url = svc['url']
                    service.priority = svc['priority']
                    service.ip = svc['ip']
                    service.last_seen = current_time

            # Remove services that disappeared
            removed = [name for name in self.services.keys() if name not in discovered_names]
            for name in removed:
                service = self.services[name]
                del self.services[name]
                if self.on_service_change:
                    self.on_service_change('removed', name, service.url, service.priority)

    def _run_dns_sd_discovery(self) -> Optional[List[dict]]:
        """Run dns-sd discovery and return list of services"""
        services = []

        try:
            # Browse for services
            browse_proc = subprocess.Popen(
                ['dns-sd', '-B', '_saturn._tcp', 'local'],
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

            # Parse service names
            service_names = []
            for line in stdout.split('\n'):
                if 'Add' in line and '_saturn._tcp' in line:
                    parts = line.split()
                    if len(parts) > 6:
                        service_names.append(parts[6])

            # Get details for each service
            for service_name in service_names:
                try:
                    lookup_proc = subprocess.Popen(
                        ['dns-sd', '-L', service_name, '_saturn._tcp', 'local'],
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
                    priority = 50

                    for line in stdout.split('\n'):
                        if 'can be reached at' in line:
                            match = re.search(r'can be reached at (.+):(\d+)', line)
                            if match:
                                hostname = match.group(1).rstrip('.')
                                port = int(match.group(2))

                        if 'priority=' in line:
                            parts = line.split('priority=')
                            if len(parts) > 1:
                                priority_str = parts[1].split()[0]
                                priority = int(priority_str)

                    if hostname and port:
                        try:
                            ip_address = socket.gethostbyname(hostname)
                        except socket.gaierror:
                            ip_address = hostname

                        service_url = f"http://{ip_address}:{port}"
                        services.append({
                            'name': service_name,
                            'url': service_url,
                            'priority': priority,
                            'ip': ip_address
                        })

                except (subprocess.TimeoutExpired, ValueError, IndexError):
                    continue

        except FileNotFoundError:
            return None
        except Exception:
            return None

        # Deduplicate by name, preferring non-loopback
        unique_services = {}
        for svc in services:
            name = svc['name']
            ip = svc['ip']
            is_loopback = ip.startswith('127.') or ip == 'localhost'

            if name not in unique_services:
                unique_services[name] = svc
            else:
                existing = unique_services[name]
                existing_is_loopback = existing['ip'].startswith('127.') or existing['ip'] == 'localhost'

                if (svc['priority'] < existing['priority']) or \
                   (svc['priority'] == existing['priority'] and existing_is_loopback and not is_loopback):
                    unique_services[name] = svc

        return list(unique_services.values())

    def get_all_services(self) -> List[SaturnService]:
        """Get all discovered services sorted by priority"""
        with self.lock:
            services = list(self.services.values())
            return sorted(services, key=lambda s: s.priority)

    def get_best_service(self) -> Optional[SaturnService]:
        """Get service with lowest priority (highest preference)"""
        with self.lock:
            if not self.services:
                return None
            return min(self.services.values(), key=lambda s: s.priority)

    def stop(self):
        """Stop background discovery"""
        self.running = False

def discover_saturn_services():
    services = []

    try:
        print("Starting DNS-SD browsing for Saturn services...")
        # DNS-SD service browsing
        browse_proc = subprocess.Popen(
            ['dns-sd', '-B', '_saturn._tcp', 'local'],
            stdout=subprocess.PIPE, # The process writes to its stdout buffer while running.
            stderr=subprocess.PIPE,
            text=True
        )

        time.sleep(2.0)

        # Terminate and wait for output
        browse_proc.terminate() # buffer still exists in memory until communicate() is called
        try:
            stdout, stderr = browse_proc.communicate(timeout=2) #reads and returns the buffer contents
        except subprocess.TimeoutExpired:
            browse_proc.kill()
            stdout, stderr = browse_proc.communicate()

        print(f"DNS-SD browse output:\n{stdout}")
        if stderr:
            print(f"DNS-SD browse errors:\n{stderr}")

        service_names = []
        for line in stdout.split('\n'):
            print(f"Parsing line: {line}")
            if 'Add' in line and '_saturn._tcp' in line:
                parts = line.split()
                print(f"  Split into {len(parts)} parts: {parts}")
                if len(parts) > 6:
                    service_name = parts[6]
                    print(f"  Found service: {service_name}")
                    service_names.append(service_name)

        print(f"Discovered {len(service_names)} services: {service_names}")

        # DNS-SD service lookup to get details (hostname, port, priority)
        for service_name in service_names:
            try:
                print(f"\nLooking up details for service: {service_name}")
                lookup_proc = subprocess.Popen(
                    ['dns-sd', '-L', service_name, '_saturn._tcp', 'local'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                # Wait for lookup to complete this number is arbitrary
                time.sleep(1.5)

                # Terminate and get output
                lookup_proc.terminate()
                try:
                    stdout, stderr = lookup_proc.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    lookup_proc.kill()
                    stdout, stderr = lookup_proc.communicate()

                if stderr:
                    print(f"DNS-SD lookup errors:\n{stderr}")

                hostname = None
                port = None
                priority = float('inf')

                for line in stdout.split('\n'):
                    if 'can be reached at' in line:
                        match = re.search(r'can be reached at (.+):(\d+)', line)
                        if match:
                            hostname = match.group(1).rstrip('.')
                            port = int(match.group(2))
                            print(f"  Extracted hostname={hostname}, port={port}")

                    if 'priority=' in line:
                        parts = line.split('priority=')
                        if len(parts) > 1:
                            priority_str = parts[1].split()[0]
                            priority = int(priority_str)
                            

                if hostname and port:
                    try:
                        ip_address = socket.gethostbyname(hostname)
                        service_url = f"http://{ip_address}:{port}"
                        print(f"  Resolved to: {service_url} (priority={priority})")
                        services.append({
                            'name': service_name,
                            'url': service_url,
                            'priority': priority,
                            'ip': ip_address
                        })
                    except socket.gaierror as e:
                        service_url = f"http://{hostname}:{port}"
                        print(f"  Could not resolve hostname, using as-is: {service_url} (priority={priority})")
                        services.append({
                            'name': service_name,
                            'url': service_url,
                            'priority': priority,
                            'ip': hostname
                        })
                else:
                    print(f"  WARNING: Could not extract hostname/port from lookup")

            except (subprocess.TimeoutExpired, ValueError, IndexError) as e:
                print(f"  ERROR during lookup: {type(e).__name__}: {e}")
                continue

    except FileNotFoundError:
        print("ERROR: dns-sd not found. Please install Bonjour services (Windows) or ensure dns-sd is available.")
        return None, None
    except Exception as e:
        print(f"Error during service discovery: {e}")
        return None, None

    if not services:
        print("\nNo Saturn services found. Make sure:")
        print("  1. A Saturn server is running (e.g., python servers/openrouter_server.py)")
        print("  2. The server successfully registered via mDNS")
        print("  3. You're on the same network as the server")
        return None, None

    # The same service appears multiple times because machines have multiple network interfaces (WiFi, Ethernet, loopback). This means we need to deduplicate.
    unique_services = {}
    for svc in services:
        name = svc['name']
        ip = svc['ip']

        # Prefer non-loopback addresses over loopback
        is_loopback = ip.startswith('127.') or ip == 'localhost'

        if name not in unique_services:
            unique_services[name] = svc
        else:
            existing = unique_services[name]
            existing_is_loopback = existing['ip'].startswith('127.') or existing['ip'] == 'localhost'

            # Replace if: better priority, OR same priority but prefer non-loopback
            if (svc['priority'] < existing['priority']) or \
               (svc['priority'] == existing['priority'] and existing_is_loopback and not is_loopback):
                unique_services[name] = svc

    services = list(unique_services.values())

    print(f"\nFound {len(services)} unique Saturn service(s):")
    for svc in sorted(services, key=lambda s: s['priority']):
        print(f"  - {svc['name']}: {svc['url']} (priority={svc['priority']})")

    best_service = min(services, key=lambda s: s['priority'])
    print(f"\nSelecting best service: {best_service['url']} (priority={best_service['priority']})")
    return best_service['url'], best_service['priority']


def main():
    # Track service change notifications
    service_notifications = []
    notification_lock = threading.Lock()

    def handle_service_change(action, name, url, priority):
        """Callback when services are added/removed"""
        with notification_lock:
            if action == 'added':
                service_notifications.append(f"\n  ⚠️  New server discovered: {name} at {url} (priority: {priority})")
            elif action == 'removed':
                service_notifications.append(f"\n  ⚠️  Server removed: {name}")

    print("Searching for Saturn services...")

    # Start background discovery
    discovery = ServiceDiscovery(discovery_interval=10, on_service_change=handle_service_change)

    # Wait for initial discovery
    time.sleep(3)

    best_service = discovery.get_best_service()
    if not best_service:
        print("No Saturn services found.")
        discovery.stop()
        return

    print(f"Connected to service: {best_service.name} at {best_service.url} (priority: {best_service.priority})")
    print("  (Discovery continues in background - new servers will be detected automatically)")

    # Fetch initial model
    current_service_url = best_service.url
    models_response = requests.get(f"{current_service_url}/v1/models")
    model = (models_response.json().get('models', []))[0]['id'] if models_response.ok else None

    chat_history = []

    print("\nChat started. Type 'quit' to exit, 'clear' to clear history, 'servers' to list available servers.")

    try:
        while True:
            # Display any service change notifications
            with notification_lock:
                if service_notifications:
                    for notification in service_notifications:
                        print(notification)
                    service_notifications.clear()
                    print()

            # Get current best service (might have changed)
            best_service = discovery.get_best_service()
            if not best_service:
                print("\n  ⚠️  All servers offline! Waiting for services...")
                time.sleep(2)
                continue

            current_service_url = best_service.url

            user_input = input("You: ").strip()

            if user_input.lower() == "quit":
                break
            elif user_input.lower() == "clear":
                chat_history = []
                print("Chat history cleared.")
                continue
            elif user_input.lower() == "servers":
                all_services = discovery.get_all_services()
                if not all_services:
                    print("No servers available")
                else:
                    print(f"\nAvailable servers:")
                    for svc in all_services:
                        marker = " <- current" if svc.url == current_service_url else ""
                        print(f"  - {svc.name}: {svc.url} (priority: {svc.priority}){marker}")
                continue

            if not user_input:
                continue

            current_message = chat_history + [{"role": "user", "content": user_input}]
            payload = {
                "model": model,
                "messages": current_message
            }

            response = requests.post(f"{current_service_url}/v1/chat/completions", json=payload)
            if response.ok:
                data = response.json()
                assistant_message = data['choices'][0]['message']['content']
                print(f"AI: {assistant_message}")
                chat_history.append({"role": "user", "content": user_input})
                chat_history.append({"role": "assistant", "content": assistant_message})
            else:
                print(f"Error: {response.status_code} - {response.text}")

    finally:
        print("\nShutting down...")
        discovery.stop()


if __name__ == "__main__":
    main()

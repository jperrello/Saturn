import socket
import subprocess
import time
import requests
import threading
import logging
import hashlib
import re
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DEEPINFRA_API_URL = "https://api.deepinfra.com/v1/chat/completions"

@dataclass
class SaturnService:
    name: str
    url: str
    priority: int
    ip: str
    last_seen: datetime
    ephemeral_key: Optional[str] = None
    api_base: Optional[str] = None

class ServiceDiscovery:
    def __init__(self, discovery_interval: int = 10, on_service_change=None, relay_url: str = None):
        self.services: Dict[str, SaturnService] = {}
        self.lock = threading.Lock()
        self.running = True
        self.discovery_interval = discovery_interval
        self.on_service_change = on_service_change
        self.relay_url = relay_url
        self.service_found = threading.Event()
        self.thread = threading.Thread(target=self._discovery_loop, daemon=True)
        self.thread.start()

    def _discovery_loop(self):
        while self.running:
            try:
                self._discover_services()
            except Exception as e:
                logger.error(f"Error in service discovery: {e}")
            time.sleep(self.discovery_interval)

    def _discover_services(self):
        try:
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

            service_names = []
            for line in stdout.split('\n'):
                if 'Add' in line and '_saturn._tcp' in line:
                    parts = line.split()
                    if len(parts) > 6:
                        service_name = parts[6]
                        service_names.append(service_name)

            discovered_services = set()

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
                    ephemeral_key = None
                    api_base = None

                    for line in stdout.split('\n'):
                        if 'can be reached at' in line:
                            match = re.search(r'can be reached at (.+):(\d+)', line)
                            if match:
                                hostname = match.group(1).rstrip('.')
                                port = int(match.group(2))

                        if 'priority=' in line:
                            match = re.search(r'priority=(\d+)', line)
                            if match:
                                priority = int(match.group(1))

                        if 'ephemeral_key=' in line:
                            match = re.search(r'ephemeral_key=([^\s]+)', line)
                            if match:
                                ephemeral_key = match.group(1)

                        if 'api_base=' in line:
                            match = re.search(r'api_base=([^\s]+)', line)
                            if match:
                                api_base = match.group(1)

                    if hostname and port:
                        ip_address = hostname

                        discovered_services.add(service_name)
                        url = f"http://{ip_address}:{port}"

                        with self.lock:
                            is_new = service_name not in self.services
                            old_key = None
                            if not is_new:
                                old_key = self.services[service_name].ephemeral_key

                            self.services[service_name] = SaturnService(
                                name=service_name,
                                url=url,
                                priority=priority,
                                ip=ip_address,
                                last_seen=datetime.now(),
                                ephemeral_key=ephemeral_key,
                                api_base=api_base
                            )

                            if ephemeral_key:
                                key_hash = hashlib.sha256(ephemeral_key.encode()).hexdigest()[:12]
                                if is_new:
                                    logger.info(f"Discovered beacon: {service_name}")
                                    logger.info(f"  JWT fingerprint: {key_hash}")
                                elif old_key and old_key != ephemeral_key:
                                    logger.info(f"Key rotated for {service_name}")
                                    logger.info(f"  New JWT fingerprint: {key_hash}")
                            elif is_new:
                                logger.info(f"Discovered service: {service_name} at {ip_address}:{port} (priority: {priority})")

                            if is_new and self.on_service_change:
                                self.on_service_change('added', service_name, url, priority)

                            self.service_found.set()

                except (subprocess.TimeoutExpired, ValueError, IndexError) as e:
                    logger.debug(f"Error looking up service {service_name}: {e}")
                    continue

            with self.lock:
                local_services = {name for name in self.services.keys() if not name.startswith("relay:")}
                services_to_remove = [name for name in local_services if name not in discovered_services]
                for name in services_to_remove:
                    service = self.services[name]
                    del self.services[name]
                    logger.info(f"Removed service: {name}")
                    if self.on_service_change:
                        self.on_service_change('removed', name, service.url, service.priority)

            if not discovered_services and self.relay_url:
                self._discover_from_relay()

        except FileNotFoundError:
            logger.error("dns-sd not found. Install Bonjour (Windows) or avahi-utils (Linux).")
            if self.relay_url:
                logger.info("Falling back to relay discovery...")
                self._discover_from_relay()
            else:
                self.running = False
        except Exception as e:
            logger.error(f"Error during service discovery: {e}")

    def get_all_services(self) -> List[SaturnService]:
        with self.lock:
            return sorted(self.services.values(), key=lambda s: s.priority)

    def get_priority_service(self) -> Optional[SaturnService]:
        with self.lock:
            if not self.services:
                return None
            return min(self.services.values(), key=lambda s: s.priority)


    def _discover_from_relay(self):
        if not self.relay_url:
            return

        try:
            resp = requests.get(f"{self.relay_url.rstrip('/')}/beacons", timeout=10)
            if not resp.ok:
                logger.warning(f"Relay query failed: {resp.status_code}")
                return

            remote_beacons = resp.json()
            for beacon in remote_beacons:
                service_name = f"relay:{beacon['beacon_id']}"
                ephemeral_key = beacon.get('ephemeral_key')

                with self.lock:
                    is_new = service_name not in self.services
                    old_key = None
                    if not is_new:
                        old_key = self.services[service_name].ephemeral_key

                    self.services[service_name] = SaturnService(
                        name=service_name,
                        url=f"relay:{beacon['beacon_id']}",
                        priority=100,
                        ip="relay",
                        last_seen=datetime.now(),
                        ephemeral_key=ephemeral_key
                    )

                    if ephemeral_key:
                        key_hash = hashlib.sha256(ephemeral_key.encode()).hexdigest()[:12]
                        if is_new:
                            logger.info(f"Discovered remote beacon via relay: {beacon['beacon_id']}")
                            logger.info(f"  JWT fingerprint: {key_hash}")
                        elif old_key and old_key != ephemeral_key:
                            logger.info(f"Key rotated for remote beacon {beacon['beacon_id']}")
                            logger.info(f"  New JWT fingerprint: {key_hash}")

                    if is_new and self.on_service_change:
                        self.on_service_change('added', service_name, "relay", 100)

                    self.service_found.set()

        except requests.RequestException as e:
            logger.warning(f"Relay discovery error: {e}")

    def stop(self):
        self.running = False


def call_chat_api(ephemeral_key: str, model: str, messages: list, api_base: str = None) -> Optional[dict]:
    if api_base:
        api_url = f"{api_base.rstrip('/')}/chat/completions"
    else:
        api_url = DEEPINFRA_API_URL

    headers = {
        "Authorization": f"Bearer {ephemeral_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages
    }

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        if response.ok:
            return response.json()
        else:
            logger.error(f"API error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"API call failed: {e}")
        return None


def main():
    import argparse
    import os

    parser = argparse.ArgumentParser(description='Saturn Chat Client')
    parser.add_argument('--relay-url', type=str, default=os.getenv('SATURN_RELAY_URL', ''),
                        help='Saturn relay URL for remote beacon discovery')
    args = parser.parse_args()

    service_notifications = []
    notification_lock = threading.Lock()

    def handle_service_change(action, name, url, priority):
        with notification_lock:
            if action == 'added':
                service_notifications.append(f"\n  New server discovered: {name} at {url} (priority: {priority})")
            elif action == 'removed':
                service_notifications.append(f"\n  Server removed: {name}")

    print("Searching for Saturn services and beacons...")
    if args.relay_url:
        print(f"Relay fallback enabled: {args.relay_url}")
    logger.info("Starting dns-sd based discovery...")

    discovery = ServiceDiscovery(on_service_change=handle_service_change, relay_url=args.relay_url)

    print("Waiting for services (8 seconds)...")
    discovery.service_found.wait(timeout=8.0)

    best_service = discovery.get_priority_service()
    if not best_service:
        print("No Saturn services or beacons found.")
        discovery.stop()
        return

    using_beacon = best_service.ephemeral_key is not None
    is_remote = best_service.name.startswith("relay:")
    model = None

    if using_beacon:
        key_hash = hashlib.sha256(best_service.ephemeral_key.encode()).hexdigest()[:12]
        if is_remote:
            print(f"Connected to REMOTE BEACON via relay: {best_service.name}")
        else:
            print(f"Connected to BEACON: {best_service.name}")
        print(f"  URL: {best_service.url}")
        print(f"  Priority: {best_service.priority}")
        print(f"  JWT fingerprint: {key_hash}")
        if best_service.api_base:
            print(f"  API: {best_service.api_base}")
        print(f"  (Calling provider API directly)")
        if best_service.api_base and "openrouter" in best_service.api_base.lower():
            model = "meta-llama/llama-3.3-70b-instruct"
        else:
            model = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    else:
        print(f"Connected to Saturn server: {best_service.name}")
        print(f"  URL: {best_service.url}")
        print(f"  Priority: {best_service.priority}")
        print("  (Proxying through Saturn server)")

        try:
            models_response = requests.get(f"{best_service.url}/v1/models")
            models = models_response.json().get('models', []) if models_response.ok else []
            model = models[0]['id'] if models else None
        except:
            model = None

    chat_history = []

    print("\nChat started. Type 'quit' to exit, 'clear' to clear history, 'servers' to list available servers.")

    try:
        while True:
            with notification_lock:
                if service_notifications:
                    for notification in service_notifications:
                        print(notification)
                    service_notifications.clear()
                    print()

            best_service = discovery.get_priority_service()
            if not best_service:
                print("\n  All servers offline! Waiting for services...")
                time.sleep(2)
                continue

            using_beacon = best_service.ephemeral_key is not None

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
                        marker = " <- current" if svc.url == best_service.url else ""
                        beacon_marker = " [BEACON]" if svc.ephemeral_key else ""
                        remote_marker = " [REMOTE]" if svc.name.startswith("relay:") else ""
                        print(f"  - {svc.name}: {svc.url} (priority: {svc.priority}){beacon_marker}{remote_marker}{marker}")
                continue

            if not user_input:
                continue

            current_message = chat_history + [{"role": "user", "content": user_input}]

            if using_beacon:
                key_hash = hashlib.sha256(best_service.ephemeral_key.encode()).hexdigest()[:12]
                logger.info(f"Using ephemeral JWT: {key_hash}")
                data = call_chat_api(
                    ephemeral_key=best_service.ephemeral_key,
                    model=model,
                    messages=current_message,
                    api_base=best_service.api_base
                )

                if data:
                    assistant_message = data['choices'][0]['message']['content']
                    print(f"AI: {assistant_message}")
                    chat_history.append({"role": "user", "content": user_input})
                    chat_history.append({"role": "assistant", "content": assistant_message})
                else:
                    print("Error: Failed to get response from API")
            else:
                payload = {
                    "model": model,
                    "messages": current_message
                }

                try:
                    response = requests.post(f"{best_service.url}/v1/chat/completions", json=payload)
                    if response.ok:
                        data = response.json()
                        assistant_message = data['choices'][0]['message']['content']
                        print(f"AI: {assistant_message}")
                        chat_history.append({"role": "user", "content": user_input})
                        chat_history.append({"role": "assistant", "content": assistant_message})
                    else:
                        print(f"Error: {response.status_code} - {response.text}")
                except Exception as e:
                    print(f"Error: {e}")

    finally:
        print("\nShutting down...")
        discovery.stop()


if __name__ == "__main__":
    main()

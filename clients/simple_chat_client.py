import socket
import time
import requests
import threading
import logging
import hashlib
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime
from zeroconf import Zeroconf, ServiceListener, ServiceInfo, ServiceBrowser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DEEPINFRA_API_URL = "https://api.deepinfra.com/v1/chat/completions"

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
    ephemeral_key: Optional[str] = None  # JWT for beacon-provided credentials

class ServiceDiscovery(ServiceListener):
    def __init__(self, on_service_change=None):
        self.services: Dict[str, SaturnService] = {}
        self.lock = threading.Lock()
        self.on_service_change = on_service_change
        self.zeroconf = Zeroconf()
        self.browser = ServiceBrowser(self.zeroconf, "_saturn._tcp.local.", self)
        self.service_found = threading.Event()

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if not info:
            logger.warning(f"Could not get service info for {name}")
            return

        clean_name = name.replace('._saturn._tcp.local.', '')
        
        with self.lock:
            address = socket.inet_ntoa(info.addresses[0]) if info.addresses else None
            if not address:
                logger.warning(f"No address found for {name}")
                return

            port = info.port
            url = f"http://{address}:{port}"
            priority = int(info.properties.get(b'priority', b'50').decode('utf-8'))
            
            # Extract ephemeral_key if present (beacon service)
            ephemeral_key = None
            ephemeral_key_bytes = info.properties.get(b'ephemeral_key')
            if ephemeral_key_bytes:
                ephemeral_key = ephemeral_key_bytes.decode('utf-8')
                key_hash = hashlib.sha256(ephemeral_key.encode()).hexdigest()[:12]
                logger.info(f"✓ Discovered beacon with ephemeral key: {clean_name}")
                logger.info(f"  Key fingerprint: {key_hash}")
            
            is_new = clean_name not in self.services
            
            self.services[clean_name] = SaturnService(
                name=clean_name,
                url=url,
                priority=priority,
                ip=address,
                last_seen=datetime.now(),
                ephemeral_key=ephemeral_key
            )
            
            if is_new and self.on_service_change:
                self.on_service_change('added', clean_name, url, priority)
            
            self.service_found.set()

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Called when a service is updated (e.g., key rotation)
        
        This callback is triggered automatically when the beacon updates its mDNS TXT records
        with a new ephemeral_key. This event-driven approach is why we use zeroconf instead
        of dns-sd subprocess.
        
        Alternative with dns-sd (polling approach):
            while True:
                # Re-run discovery every N seconds
                browse_proc = subprocess.Popen(['dns-sd', '-B', '_saturn._tcp', 'local'], ...)
                lookup_proc = subprocess.Popen(['dns-sd', '-L', service_name, ...], ...)
                # Parse output, extract TXT records
                # Manually compare old_key vs new_key
                # Detect changes yourself
                time.sleep(30)  # Polling interval - trade-off between responsiveness and overhead
        
        With zeroconf (event-driven):
            - ServiceBrowser automatically monitors mDNS traffic
            - When beacon re-registers with new TXT records, this callback fires immediately
            - No polling overhead, no manual parsing, instant rotation detection
            - Beacon rotates every 5 minutes; we detect it within seconds, not on next poll
        
        This is the key architectural reason for using zeroconf on clients that need to handle
        ephemeral credential rotation. For one-time discovery, dns-sd would suffice.
        """
        clean_name = name.replace('._saturn._tcp.local.', '')
        
        old_key = None
        with self.lock:
            if clean_name in self.services:
                old_key = self.services[clean_name].ephemeral_key
        
        self.add_service(zc, type_, name)
        
        with self.lock:
            if clean_name in self.services:
                new_key = self.services[clean_name].ephemeral_key
                if old_key and new_key and old_key != new_key:
                    new_hash = hashlib.sha256(new_key.encode()).hexdigest()[:12]
                    logger.info(f"🔄 Key rotated for {clean_name}")
                    logger.info(f"  New JWT token fingerprint: {new_hash}")

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        clean_name = name.replace('._saturn._tcp.local.', '')
        with self.lock:
            if clean_name in self.services:
                service = self.services[clean_name]
                del self.services[clean_name]
                if self.on_service_change:
                    self.on_service_change('removed', clean_name, service.url, service.priority)

    def get_all_services(self) -> list:
        with self.lock:
            services = list(self.services.values())
            return sorted(services, key=lambda s: s.priority)

    def get_priority_service(self) -> Optional[SaturnService]:
        with self.lock:
            if not self.services:
                return None
            return min(self.services.values(), key=lambda s: s.priority)

    def stop(self):
        self.zeroconf.close()

def call_deepinfra_api(ephemeral_key: str, model: str, messages: list) -> Optional[dict]:

    headers = {
        "Authorization": f"Bearer {ephemeral_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": messages
    }
    
    try:
        response = requests.post(DEEPINFRA_API_URL, headers=headers, json=payload, timeout=60)
        if response.ok:
            return response.json()
        else:
            logger.error(f"DeepInfra API error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"DeepInfra API call failed: {e}")
        return None


def main():
    service_notifications = []
    notification_lock = threading.Lock()

    def handle_service_change(action, name, url, priority):
        with notification_lock:
            if action == 'added':
                service_notifications.append(f"\n  ⚠️  New server discovered: {name} at {url} (priority: {priority})")
            elif action == 'removed':
                service_notifications.append(f"\n  ⚠️  Server removed: {name}")

    print("Searching for Saturn services and beacons...")
    logger.info("Starting zeroconf-based discovery...")

    discovery = ServiceDiscovery(on_service_change=handle_service_change)

    # Wait for initial discovery
    print("Waiting for services (5 seconds)...")
    discovery.service_found.wait(timeout=5.0)

    best_service = discovery.get_priority_service()
    if not best_service:
        print("No Saturn services or beacons found.")
        discovery.stop()
        return

    # Determine if we're using beacon or regular Saturn server
    using_beacon = best_service.ephemeral_key is not None
    
    if using_beacon:
        key_hash = hashlib.sha256(best_service.ephemeral_key.encode()).hexdigest()[:12]
        print(f"✓ Connected to BEACON: {best_service.name}")
        print(f"  URL: {best_service.url}")
        print(f"  Priority: {best_service.priority}")
        print(f"  JWT token fingerprint: {key_hash}")
        print(f"  (Calling DeepInfra API with Saturn)")
    else:
        print(f"✓ Connected to Saturn server: {best_service.name}")
        print(f"  URL: {best_service.url}")
        print(f"  Priority: {best_service.priority}")
        print("  (Proxying through Saturn server)")
        
        # Fetch model from Saturn server
        try:
            models_response = requests.get(f"{best_service.url}/v1/models")
            model = (models_response.json().get('models', []))[0]['id'] if models_response.ok else None
        except:
            model = None

    chat_history = []

    print("\nChat started. Type 'quit' to exit, 'clear' to clear history, 'servers' to list available servers.")

    try:
        while True:
            # Display service change notifications
            with notification_lock:
                if service_notifications:
                    for notification in service_notifications:
                        print(notification)
                    service_notifications.clear()
                    print()

            # Get current best service (might have changed)
            best_service = discovery.get_priority_service()
            if not best_service:
                print("\n  ⚠️  All servers offline! Waiting for services...")
                time.sleep(2)
                continue

            # Update beacon status if it changed
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
                        print(f"  - {svc.name}: {svc.url} (priority: {svc.priority}){beacon_marker}{marker}")
                continue

            if not user_input:
                continue

            current_message = chat_history + [{"role": "user", "content": user_input}]

            # Choose API call method based on whether we have ephemeral key
            if using_beacon:
                # Direct DeepInfra API call using ephemeral JWT
                key_hash = hashlib.sha256(best_service.ephemeral_key.encode()).hexdigest()[:12]
                logger.info(f"Using ephemeral JWT with fingerprint: {key_hash}")
                data = call_deepinfra_api(
                    ephemeral_key=best_service.ephemeral_key,
                    model=model,
                    messages=current_message
                )
                
                if data:
                    assistant_message = data['choices'][0]['message']['content']
                    print(f"AI: {assistant_message}")
                    chat_history.append({"role": "user", "content": user_input})
                    chat_history.append({"role": "assistant", "content": assistant_message})
                else:
                    print("Error: Failed to get response from DeepInfra API")
            else:
                # Regular Saturn server proxy call
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

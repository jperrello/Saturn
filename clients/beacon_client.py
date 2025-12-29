import sys
import socket
import time
import logging
import threading
import requests
from typing import Dict, Optional
from zeroconf import Zeroconf, ServiceListener, ServiceInfo, ServiceBrowser


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


DEEPINFRA_API_URL = "https://api.deepinfra.com/v1/chat/completions"


class BeaconListener(ServiceListener):
    # ServiceListener callbacks (add_service, update_service, remove_service) are called by zeroconf
    # when mDNS announcements are detected - these run in zeroconf's internal thread
    def __init__(self):
        self.beacons: Dict[str, dict] = {}
        self._lock = threading.Lock()  # Protect against concurrent callback access
        self.beacon_found = threading.Event()  # Signal main thread when first beacon discovered

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if not info:
            logger.warning(f"Could not get service info for {name}")
            return

        ephemeral_key_bytes = info.properties.get(b'ephemeral_key')
        if not ephemeral_key_bytes:
            logger.debug(f"Service {name} has no ephemeral_key, skipping")
            return

        ephemeral_key = ephemeral_key_bytes.decode('utf-8')

        with self._lock:
            address = socket.inet_ntoa(info.addresses[0]) if info.addresses else None
            if not address:
                logger.warning(f"No address found for {name}")
                return

            port = info.port
            url = f"http://{address}:{port}"
            priority = int(info.properties.get(b'priority', b'50').decode('utf-8'))
            rotation_interval = int(info.properties.get(b'rotation_interval', b'300').decode('utf-8'))

            clean_name = name.replace('._saturn._tcp.local.', '')
            self.beacons[clean_name] = {
                'url': url,
                'priority': priority,
                'ephemeral_key': ephemeral_key,
                'rotation_interval': rotation_interval,
                'discovered_at': time.time(),
                'address': address,
                'port': port
            }

            logger.info(f"✓ Discovered beacon: {clean_name}")
            logger.info(f"  URL: {url}")
            logger.info(f"  Priority: {priority}")
            logger.info(f"  Key: {ephemeral_key[:60]}...")
            logger.info(f"  Rotation: every {rotation_interval}s")

            self.beacon_found.set()

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        # Called when beacon re-registers with new ephemeral key after rotation
        # This is how clients detect key rotation without polling
        logger.info(f"🔄 Beacon updated: {name}")

        clean_name = name.replace('._saturn._tcp.local.', '')
        old_key = None

        with self._lock:
            if clean_name in self.beacons:
                old_key = self.beacons[clean_name].get('ephemeral_key')

        self.add_service(zc, type_, name)

        with self._lock:
            if clean_name in self.beacons:
                new_key = self.beacons[clean_name].get('ephemeral_key')
                if old_key and new_key and old_key != new_key:
                    logger.info(f"  Old key: {old_key[:40]}...")
                    logger.info(f"  New key: {new_key[:40]}...")
                    logger.info(f"  Update timestamp: {time.time()}")

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        clean_name = name.replace('._saturn._tcp.local.', '')
        with self._lock:
            if clean_name in self.beacons:
                del self.beacons[clean_name]
                logger.info(f"✗ Beacon removed: {clean_name}")

    def get_best_beacon(self) -> Optional[dict]:
        with self._lock:
            if not self.beacons:
                return None
            return min(self.beacons.values(), key=lambda b: b['priority'])

    def get_all_beacons(self) -> Dict[str, dict]:
        with self._lock:
            return self.beacons.copy()


def chat_with_deepinfra(ephemeral_key: str, model: str, user_message: str) -> str:
    # Key design: client calls DeepInfra API directly, NOT through beacon
    # Beacon is credential dispenser, not proxy - this proves network-level access model
    headers = {
        "Authorization": f"Bearer {ephemeral_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": user_message}]
    }

    logger.info(f"\n→ Calling DeepInfra API directly...")
    logger.info(f"  Model: {model}")
    logger.info(f"  Using ephemeral key: {ephemeral_key[:60]}...")

    response = requests.post(DEEPINFRA_API_URL, headers=headers, json=payload, timeout=60)

    if response.ok:
        result = response.json()
        content = result['choices'][0]['message']['content']
        logger.info(f"✓ Success! Response: {content[:100]}...")
        return content
    else:
        logger.error(f"✗ Error: {response.status_code}")
        logger.error(f"  {response.text}")
        return None


def main():
    logger.info("Starting Saturn Beacon Test Client...")
    logger.info("=" * 60)

    logger.info("\n[1] Discovering beacons on network...")
    listener = BeaconListener()
    zeroconf = Zeroconf()
    browser = ServiceBrowser(zeroconf, "_saturn._tcp.local.", listener)

    logger.info("Waiting for beacon discovery (timeout: 5 seconds)...")
    found = listener.beacon_found.wait(timeout=5.0)

    if not found:
        logger.error("✗ No beacons discovered within timeout")
        zeroconf.close()
        sys.exit(1)

    beacon = listener.get_best_beacon()
    if not beacon:
        logger.error("✗ No beacons available")
        zeroconf.close()
        sys.exit(1)

    logger.info(f"\n[2] Selected beacon:")
    logger.info(f"  URL: {beacon['url']}")
    logger.info(f"  Priority: {beacon['priority']}")
    logger.info(f"  Ephemeral Key: {beacon['ephemeral_key'][:60]}...")

    logger.info(f"\n[3] Testing direct DeepInfra API call...")
    model = "meta-llama/Meta-Llama-3.1-8B-Instruct"
    message = "Say 'Hello from Saturn Beacon!' in exactly 5 words."

    response = chat_with_deepinfra(
        ephemeral_key=beacon['ephemeral_key'],
        model=model,
        user_message=message
    )

    if response:
        logger.info(f"\n[4] Full Response:")
        logger.info(f"{response}")
        logger.info("\n✓ End-to-end test successful!")
        logger.info(f"  - Beacon discovered: ✓")
        logger.info(f"  - Ephemeral key extracted: ✓")
        logger.info(f"  - Direct API call successful: ✓")
    else:
        logger.error("\n✗ API call failed")
        zeroconf.close()
        sys.exit(1)

    logger.info("\n[5] Keeping client running to detect key rotation...")
    logger.info("    (Press Ctrl+C to exit)")
    logger.info("    ServiceBrowser will log updates when beacon rotates keys\n")

    try:
        while True:
            time.sleep(10)
            current_beacon = listener.get_best_beacon()
            if current_beacon:
                logger.debug(f"Current key: {current_beacon['ephemeral_key'][:40]}...")
    except KeyboardInterrupt:
        logger.info("\n\nShutting down client...")
        zeroconf.close()
        logger.info("✓ Client shutdown complete")


if __name__ == "__main__":
    main()

# OpenRouter Beacon - Pure mDNS Announcer for OpenRouter Ephemeral API Keys
#
# This beacon uses OpenRouter's provisioning API to create short-lived API keys
# and broadcasts them via mDNS. Clients discovering this beacon can use the
# ephemeral_key to call OpenRouter's API directly.
#
# Unlike DeepInfra's scoped JWTs (see deepinfra_beacon.py), OpenRouter's
# provisioning keys require a separate "Provisioning API key" that can ONLY be
# used for key management - not for inference calls. The keys we CREATE with the
# provisioning API are regular API keys that CAN be used for inference.
#
# To use this beacon, create a provisioning key at:
# https://openrouter.ai/settings/provisioning-keys
# Then set OPENROUTER_PROVISIONING_KEY in your environment.

import os
import time
import socket
import argparse
import logging
import threading
import signal
import sys
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from zeroconf import ServiceInfo, Zeroconf
from dotenv import load_dotenv
load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


OPENROUTER_KEYS_URL = "https://openrouter.ai/api/v1/keys"
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"


class KeyManager:
    def __init__(self, provisioning_key: Optional[str] = None,
                 key_lifetime: int = 600,
                 rotation_interval: int = 300,
                 spending_limit: Optional[float] = None):
        self.provisioning_key = provisioning_key or os.getenv('OPENROUTER_PROVISIONING_KEY')
        if not self.provisioning_key:
            raise ValueError("OPENROUTER_PROVISIONING_KEY not found in environment or constructor")

        # Key lifetime is how long before the key expires (600s = 10 min)
        # Rotation interval is how often we create a new key (300s = 5 min)
        # This overlap ensures clients always have a valid key during transitions
        self.key_lifetime = key_lifetime
        self.rotation_interval = rotation_interval
        self.spending_limit = spending_limit

        self._lock = threading.Lock()
        self._current_key: Optional[str] = None
        self._current_hash: Optional[str] = None
        self._previous_hash: Optional[str] = None
        self._last_rotation: Optional[float] = None

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.provisioning_key}",
            "Content-Type": "application/json"
        }

    def create_key(self, name: Optional[str] = None) -> Tuple[str, str]:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.key_lifetime)
        expires_at_str = expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")

        payload = {
            "name": name or f"saturn-beacon-{int(time.time())}",
            "expires_at": expires_at_str
        }

        if self.spending_limit is not None:
            payload["limit"] = self.spending_limit

        response = requests.post(OPENROUTER_KEYS_URL, headers=self._get_headers(), json=payload)
        response.raise_for_status()

        data = response.json()
        key = data["key"]
        key_hash = data["data"]["hash"]

        with self._lock:
            # Store previous hash for cleanup
            if self._current_hash:
                self._previous_hash = self._current_hash

            self._current_key = key
            self._current_hash = key_hash
            self._last_rotation = time.time()

        return key, key_hash

    def delete_key(self, key_hash: str) -> bool:
        try:
            response = requests.delete(
                f"{OPENROUTER_KEYS_URL}/{key_hash}",
                headers=self._get_headers()
            )
            if response.status_code == 200:
                logger.info(f"Deleted old key: {key_hash[:8]}...")
                return True
            elif response.status_code == 404:
                logger.debug(f"Key already deleted or expired: {key_hash[:8]}...")
                return True
            else:
                logger.warning(f"Failed to delete key {key_hash[:8]}...: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error deleting key: {e}")
            return False

    def cleanup_previous_key(self) -> None:
        with self._lock:
            previous = self._previous_hash
            self._previous_hash = None

        if previous:
            self.delete_key(previous)

    def get_current_key(self) -> Optional[str]:
        with self._lock:
            return self._current_key

    def needs_rotation(self) -> bool:
        with self._lock:
            if self._last_rotation is None:
                return True

            time_since_rotation = time.time() - self._last_rotation
            return time_since_rotation >= self.rotation_interval


class BeaconAnnouncer:
    def __init__(self, key_manager: KeyManager, port: int, priority: int = 10):
        self.key_manager = key_manager
        self.port = port
        self.priority = priority
        self.service_type = "_saturn._tcp.local."

        self._zeroconf: Optional[Zeroconf] = None
        self._service_info: Optional[ServiceInfo] = None
        self._is_registered = False

    def register(self) -> None:
        if self._is_registered:
            logger.warning("Service already registered. Use re-register for updates.")
            return

        key = self.key_manager.get_current_key()
        if not key:
            logger.warning("No current key available. Creating new key...")
            key, _ = self.key_manager.create_key()

        if len(key) > 240:
            logger.warning(
                f"ephemeral_key length ({len(key)} chars) exceeds safe limit (240 chars). "
                "mDNS TXT records have a 255-byte limit per record, and long keys may cause issues."
            )

        host = socket.gethostname()
        host_ip = socket.gethostbyname(host)
        service_name = f"OpenRouter-Beacon.{self.service_type}"

        self._zeroconf = Zeroconf()

        self._service_info = ServiceInfo(
            type_=self.service_type,
            name=service_name,
            port=self.port,
            addresses=[socket.inet_aton(host_ip)],
            server=f"{host}.local.",
            properties={
                # Production schema (matches saturn-router)
                'version': '1.0',
                'deployment': 'cloud',
                'api_type': 'openai',
                'api_base': OPENROUTER_API_BASE,
                'priority': str(self.priority),
                'ephemeral_key': key,
                'rotation_interval': str(self.key_manager.rotation_interval),
                'features': 'ephemeral_auth'
            }
        )

        self._zeroconf.register_service(self._service_info)
        self._is_registered = True

        logger.info(f"Beacon registered: {service_name} on port {self.port} with priority {self.priority}")

    def unregister(self) -> None:
        if not self._is_registered:
            logger.warning("No service registered to unregister.")
            return

        if self._zeroconf and self._service_info:
            logger.info("Unregistering beacon service...")
            self._zeroconf.unregister_service(self._service_info)
            self._zeroconf.close()

        self._zeroconf = None
        self._service_info = None
        self._is_registered = False

        logger.info("Beacon service unregistered successfully.")

    def re_register(self) -> None:
        logger.info("Re-registering beacon with updated ephemeral key...")
        self.unregister()
        self.register()
        logger.info("Beacon re-registration complete.")

    @property
    def is_registered(self) -> bool:
        return self._is_registered


def rotation_loop(key_manager: KeyManager, beacon_announcer: BeaconAnnouncer) -> None:
    logger.info("Key rotation loop started")

    while True:
        try:
            if key_manager.needs_rotation():
                logger.info("Starting key rotation...")

                try:
                    key_manager.create_key()

                    if beacon_announcer.is_registered:
                        beacon_announcer.re_register()
                    else:
                        beacon_announcer.register()

                    # Cleanup old key after new one is active and announced
                    # Small delay ensures clients have time to discover the new key
                    time.sleep(5)
                    key_manager.cleanup_previous_key()

                    logger.info("Key rotation complete")

                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 429:
                        logger.error("OpenRouter API rate limit exceeded (429). Will retry on next check (one minute).")
                    elif e.response.status_code == 401:
                        logger.error("OpenRouter API authentication failed (401). Check OPENROUTER_PROVISIONING_KEY.")
                    else:
                        logger.error(f"HTTP error during rotation: {e}", exc_info=True)

                except requests.exceptions.RequestException as e:
                    logger.error(f"Network error during rotation: {e}. Will retry on next check.")

                except Exception as e:
                    logger.error(f"Unexpected error during rotation: {e}", exc_info=True)

            time.sleep(60)

        except Exception as e:
            logger.error(f"Unexpected error in rotation loop: {e}", exc_info=True)
            time.sleep(60)


def main():
    parser = argparse.ArgumentParser(
        prog='saturn-openrouter-beacon',
        description='Saturn Beacon: mDNS announcer for OpenRouter ephemeral API keys'
    )
    parser.add_argument('--port', type=int, default=8090, help='Port for mDNS announcement')
    parser.add_argument('--priority', type=int, default=10, help='Beacon priority (lower is higher priority)')
    parser.add_argument('--limit', type=float, default=None, help='Spending limit in USD for each ephemeral key')
    args = parser.parse_args()

    if not os.getenv('OPENROUTER_PROVISIONING_KEY'):
        logger.error("OPENROUTER_PROVISIONING_KEY environment variable not set")
        logger.error("Create a provisioning key at https://openrouter.ai/settings/provisioning-keys")
        sys.exit(1)

    key_manager = KeyManager(rotation_interval=300, spending_limit=args.limit)
    beacon_announcer = BeaconAnnouncer(key_manager, args.port, args.priority)

    def shutdown_beacon(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        beacon_announcer.unregister()

        # Cleanup current key on shutdown
        with key_manager._lock:
            current_hash = key_manager._current_hash
        if current_hash:
            key_manager.delete_key(current_hash)

        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_beacon)
    signal.signal(signal.SIGTERM, shutdown_beacon)

    print("=" * 55)
    print("  Saturn OpenRouter Beacon (Pure mDNS Announcer)")
    print("=" * 55)
    print()
    print("  This beacon broadcasts ephemeral OpenRouter API keys")
    print("  via mDNS. Clients discover the key and call")
    print("  OpenRouter directly - no traffic passes through here.")
    print()
    print(f"  Priority: {args.priority}")
    print(f"  Port (for mDNS record): {args.port}")
    if args.limit:
        print(f"  Spending limit per key: ${args.limit}")
    print()
    print("  Key rotation happens automatically every 5 minutes.")
    print("  Keys expire after 10 minutes for safety overlap.")
    print("=" * 55)

    logger.info("Initializing Saturn OpenRouter Beacon...")

    logger.info("Creating initial ephemeral key...")
    key, key_hash = key_manager.create_key()
    logger.info(f"Created key: {key_hash[:8]}... (expires in {key_manager.key_lifetime}s)")

    logger.info("Registering beacon on mDNS network...")
    beacon_announcer.register()
    logger.info(f"Beacon registered on port {args.port} with priority {args.priority}")

    rotation_thread = threading.Thread(
        target=rotation_loop,
        args=(key_manager, beacon_announcer),
        daemon=True,
        name="KeyRotationThread"
    )
    rotation_thread.start()
    logger.info("Key rotation thread started (rotation every 5 minutes)")

    logger.info("Beacon is now discoverable on the network!")
    logger.info("Press Ctrl+C to stop")

    try:
        signal.pause()
    except AttributeError:
        # Windows doesn't have signal.pause(), use sleep loop instead
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        beacon_announcer.unregister()

        with key_manager._lock:
            current_hash = key_manager._current_hash
        if current_hash:
            key_manager.delete_key(current_hash)

        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()

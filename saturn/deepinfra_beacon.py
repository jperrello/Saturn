# DeepInfra Beacon - Pure mDNS Announcer for DeepInfra Ephemeral JWT Credentials
#
# This beacon uses DeepInfra's scoped JWT API because DeepInfra allows the generated
# JWTs to be used directly for inference API calls. Clients discovering this beacon
# can use the ephemeral_key to call DeepInfra's /v1/openai/chat/completions endpoint
# directly without any proxy.
#
# Note: OpenRouter also has a key provisioning API, but their provisioning keys can
# ONLY be used for key management operations - not for making inference calls. For
# OpenRouter, see openrouter_beacon.py which broadcasts ephemeral API keys instead
# of JWTs, and beacon_proxy.py which provides an HTTP proxy approach.

import os
import time
import socket
import argparse
import logging
import threading
import signal
import sys
import requests
from typing import Optional
from zeroconf import ServiceInfo, Zeroconf
from dotenv import load_dotenv
load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JWTManager:
    def __init__(self, api_key: Optional[str] = None,
                 expires_delta: int = 600,
                 rotation_interval: int = 300):
        self.api_key = api_key or os.getenv('DEEPINFRA_API_KEY')
        if not self.api_key:
            raise ValueError("DEEPINFRA_API_KEY not found in environment or constructor")

        # Token expires in 600s but we rotate every 300s to maintain a safety buffer
        # This prevents gaps where old token expired but new one isn't ready yet
        self.expires_delta = expires_delta
        self.rotation_interval = rotation_interval
        self.api_endpoint = "https://api.deepinfra.com/v1/scoped-jwt"
        self.api_base = "https://api.deepinfra.com/v1/openai"

        # Thread safety: multiple threads may check token status concurrently
        self._lock = threading.Lock()
        self._current_token: Optional[str] = None
        self._expires_at: Optional[float] = None
        self._last_rotation: Optional[float] = None

    def generate_token(self, models: Optional[list] = None, spending_limit: Optional[float] = None) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "api_key_name": "auto",
            "expires_delta": self.expires_delta
        }

        if models is not None:
            payload["models"] = models
            if spending_limit is not None:
                payload["spending_limit"] = spending_limit

        response = requests.post(self.api_endpoint, headers=headers, json=payload)
        response.raise_for_status()

        token = response.json()["token"]

        with self._lock:
            self._current_token = token
            self._expires_at = time.time() + self.expires_delta
            self._last_rotation = time.time()

        return token

    def get_current_token(self) -> Optional[str]:
        with self._lock:
            return self._current_token

    def needs_rotation(self) -> bool:
        with self._lock:
            if self._last_rotation is None:
                return True

            time_since_rotation = time.time() - self._last_rotation
            return time_since_rotation >= self.rotation_interval


class BeaconAnnouncer:
    def __init__(self, jwt_manager: JWTManager, port: int, priority: int = 10):
        self.jwt_manager = jwt_manager
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

        token = self.jwt_manager.get_current_token()
        if not token:
            logger.warning("No current token available. Generating new token...")
            token = self.jwt_manager.generate_token()

        if len(token) > 240:
            logger.warning(
                f"ephemeral_key length ({len(token)} chars) exceeds safe limit (240 chars). "
                "mDNS TXT records have a 255-byte limit per record, and long keys may cause issues."
            )

        host = socket.gethostname()
        host_ip = socket.gethostbyname(host)
        service_name = f"DeepInfra-Beacon.{self.service_type}"

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
                'api_base': self.jwt_manager.api_base,
                'priority': str(self.priority),
                'ephemeral_key': token,
                'rotation_interval': str(self.jwt_manager.rotation_interval),
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
        # mDNS TXT records are immutable - to update ephemeral_key we must unregister then re-register
        # This is the standard pattern for dynamic TXT record updates in zeroconf
        logger.info("Re-registering beacon with updated ephemeral key...")
        self.unregister()
        self.register()
        logger.info("Beacon re-registration complete.")

    @property
    def is_registered(self) -> bool:
        return self._is_registered


def rotation_loop(jwt_manager: JWTManager, beacon_announcer: BeaconAnnouncer) -> None:
    # Runs in background thread - checks every 60s, rotates every 300s (5 min)
    # Pattern: check often, rotate less often - allows quick startup while preventing excessive API calls
    logger.info("Key rotation loop started")

    while True:
        try:
            if jwt_manager.needs_rotation():
                logger.info("Starting key rotation...")

                try:
                    jwt_manager.generate_token()

                    # Update mDNS announcement with new key - clients listening for updates get notified
                    if beacon_announcer.is_registered:
                        beacon_announcer.re_register()
                    else:
                        beacon_announcer.register()

                    logger.info("Key rotation complete")

                except requests.exceptions.HTTPError as e:
                    # Rate limit handling - DeepInfra may throttle JWT generation
                    # Non-fatal: old key still valid for up to 10 minutes
                    if e.response.status_code == 429:
                        logger.error("DeepInfra API rate limit exceeded (429). Will retry on next check (one minute).")
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
        prog='saturn-beacon',
        description='Saturn Beacon: mDNS JWT announcer for DeepInfra ephemeral credentials'
    )
    parser.add_argument('--port', type=int, default=8090, help='Port for mDNS announcement')
    parser.add_argument('--priority', type=int, default=10, help='Beacon priority (lower is higher priority)')
    args = parser.parse_args()

    if not os.getenv('DEEPINFRA_API_KEY'):
        logger.error("DEEPINFRA_API_KEY environment variable not set")
        sys.exit(1)

    jwt_manager = JWTManager(rotation_interval=300)
    beacon_announcer = BeaconAnnouncer(jwt_manager, args.port, args.priority)

    def shutdown_beacon(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        beacon_announcer.unregister()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_beacon)
    signal.signal(signal.SIGTERM, shutdown_beacon)

    print("=" * 55)
    print("  Saturn Beacon (Pure mDNS Announcer)")
    print("=" * 55)
    print()
    print("  This beacon broadcasts ephemeral JWT credentials")
    print("  via mDNS. Clients discover the token and call")
    print("  DeepInfra directly - no traffic passes through here.")
    print()
    print(f"  Priority: {args.priority}")
    print(f"  Port (for mDNS record): {args.port}")
    print()
    print("  JWT rotation happens automatically every 5 minutes.")
    print("=" * 55)

    logger.info("Initializing Saturn Beacon...")

    logger.info("Generating initial JWT...")
    token = jwt_manager.generate_token()
    logger.info(f"Generated JWT (len={len(token)} chars, expires in {jwt_manager.expires_delta}s)")

    logger.info("Registering beacon on mDNS network...")
    beacon_announcer.register()
    logger.info(f"Beacon registered on port {args.port} with priority {args.priority}")

    rotation_thread = threading.Thread(
        target=rotation_loop,
        args=(jwt_manager, beacon_announcer),
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
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()

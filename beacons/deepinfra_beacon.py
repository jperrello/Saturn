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
from datetime import datetime, timedelta
from fastapi import FastAPI
import uvicorn
from zeroconf import ServiceInfo, Zeroconf


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

        self.expires_delta = expires_delta
        self.rotation_interval = rotation_interval
        self.api_endpoint = "https://api.deepinfra.com/v1/scoped-jwt"

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

    def get_token_info(self) -> dict:
        with self._lock:
            if self._current_token is None:
                return {
                    "has_token": False,
                    "expires_at": None,
                    "time_until_expiry": None,
                    "time_until_rotation": None
                }

            now = time.time()
            time_until_expiry = self._expires_at - now if self._expires_at else None
            time_until_rotation = self.rotation_interval - (now - self._last_rotation) if self._last_rotation else None

            return {
                "has_token": True,
                "expires_at": datetime.fromtimestamp(self._expires_at).isoformat() if self._expires_at else None,
                "time_until_expiry": time_until_expiry,
                "time_until_rotation": time_until_rotation
            }


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
                'version': '1.0',
                'api': 'DeepInfra',
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
        logger.info("Re-registering beacon with updated ephemeral key...")
        self.unregister()
        self.register()
        logger.info("Beacon re-registration complete.")

    @property
    def is_registered(self) -> bool:
        return self._is_registered


def rotation_loop(jwt_manager: JWTManager, beacon_announcer: BeaconAnnouncer) -> None:
    logger.info("Key rotation loop started")

    while True:
        try:
            if jwt_manager.needs_rotation():
                logger.info("Starting key rotation...")

                try:
                    jwt_manager.generate_token()

                    if beacon_announcer.is_registered:
                        beacon_announcer.re_register()
                    else:
                        beacon_announcer.register()

                    logger.info("Key rotation complete")

                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 429:
                        logger.error("DeepInfra API rate limit exceeded (429). Will retry on next check.")
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


app = FastAPI()
jwt_manager = None
beacon_announcer = None


@app.get("/v1/health")
async def health():
    token_info = jwt_manager.get_token_info() if jwt_manager else {}
    return {
        "status": "healthy",
        "provider": "DeepInfra",
        "service_type": "beacon",
        "ephemeral_credentials": True,
        "token_info": token_info
    }


@app.get("/v1/models")
async def models():
    return {
        "object": "list",
        "data": [
            {
                "id": "meta-llama/Meta-Llama-3.1-8B-Instruct",
                "object": "model",
                "created": 1686935002,
                "owned_by": "deepinfra"
            },
            {
                "id": "Qwen/QwQ-32B-Preview",
                "object": "model",
                "created": 1686935002,
                "owned_by": "deepinfra"
            }
        ]
    }


def shutdown_handler(signum, frame):
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    if beacon_announcer:
        beacon_announcer.unregister()
    sys.exit(0)


def main():
    global jwt_manager, beacon_announcer

    parser = argparse.ArgumentParser(description='DeepInfra Beacon Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8090, help='Port to bind to')
    parser.add_argument('--priority', type=int, default=10, help='Beacon priority (lower is higher priority)')
    args = parser.parse_args()

    if not os.getenv('DEEPINFRA_API_KEY'):
        logger.error("DEEPINFRA_API_KEY environment variable not set")
        sys.exit(1)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    logger.info("Initializing DeepInfra Beacon Server...")

    jwt_manager = JWTManager(rotation_interval=300)
    logger.info("Generating initial JWT...")
    token = jwt_manager.generate_token()
    logger.info(f"✓ Generated JWT (len={len(token)} chars, expires in {jwt_manager.expires_delta}s)")

    beacon_announcer = BeaconAnnouncer(jwt_manager, args.port, args.priority)
    logger.info("Registering beacon on mDNS network...")
    beacon_announcer.register()
    logger.info(f"✓ Beacon registered on port {args.port} with priority {args.priority}")

    rotation_thread = threading.Thread(
        target=rotation_loop,
        args=(jwt_manager, beacon_announcer),
        daemon=True,
        name="KeyRotationThread"
    )
    rotation_thread.start()
    logger.info("✓ Key rotation thread started (rotation every 5 minutes)")

    logger.info(f"Starting FastAPI server on {args.host}:{args.port}...")
    logger.info("Beacon is now discoverable on the network!")

    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    finally:
        logger.info("Cleaning up...")
        beacon_announcer.unregister()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()

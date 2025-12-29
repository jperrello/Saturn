import socket
import logging
from typing import Optional
from zeroconf import ServiceInfo, Zeroconf
from jwt_manager import JWTManager


logger = logging.getLogger(__name__)


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

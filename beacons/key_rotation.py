import time
import logging
import requests
from jwt_manager import JWTManager
from beacon_announcer import BeaconAnnouncer


logger = logging.getLogger(__name__)


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

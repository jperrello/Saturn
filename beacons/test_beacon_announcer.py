import time
import logging
import os
from pathlib import Path
from jwt_manager import JWTManager
from beacon_announcer import BeaconAnnouncer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_env():
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value


def main():
    load_env()
    logger.info("Starting BeaconAnnouncer test...")

    jwt_manager = JWTManager()
    logger.info("Generating initial token...")
    jwt_manager.generate_token()

    announcer = BeaconAnnouncer(jwt_manager=jwt_manager, port=8080, priority=10)

    logger.info("Registering beacon...")
    announcer.register()

    logger.info("\n" + "="*70)
    logger.info("Beacon is now registered!")
    logger.info("="*70)
    logger.info("\nTo verify registration, run these commands in another terminal:")
    logger.info("  1. Browse for services:")
    logger.info("     dns-sd -B _saturn._tcp local")
    logger.info("\n  2. Lookup service details (replace <instance> with service name from step 1):")
    logger.info("     dns-sd -L <instance> _saturn._tcp local")
    logger.info("\n  3. Check for ephemeral_key in TXT records")
    logger.info("="*70)
    logger.info("\nPress Ctrl+C to stop and unregister...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        announcer.unregister()
        logger.info("Test complete.")


if __name__ == "__main__":
    main()

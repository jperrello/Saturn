import os
import sys
import time
import subprocess
import logging
import requests
from zeroconf import Zeroconf, ServiceBrowser

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'clients'))
from beacon_client import BeaconListener


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


DEEPINFRA_API_URL = "https://api.deepinfra.com/v1/chat/completions"


class BeaconFlowTest:
    def __init__(self):
        self.beacon_process = None
        self.results = []
        self.old_key = None

    def log_result(self, test_name: str, passed: bool, message: str = ""):
        status = "✓ PASS" if passed else "✗ FAIL"
        self.results.append((test_name, passed, message))
        logger.info(f"{status}: {test_name}")
        if message:
            logger.info(f"       {message}")

    def test_1_beacon_startup(self) -> bool:
        logger.info("\n" + "=" * 60)
        logger.info("TEST 1: Beacon Startup Flow")
        logger.info("=" * 60)

        if not os.getenv('DEEPINFRA_API_KEY'):
            self.log_result("Beacon Startup", False, "DEEPINFRA_API_KEY not set")
            return False

        beacon_script = os.path.join(os.path.dirname(__file__), '..', 'beacons', 'deepinfra_beacon.py')

        try:
            self.beacon_process = subprocess.Popen(
                [sys.executable, beacon_script, '--port', '8090', '--priority', '10'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            logger.info("Waiting for beacon startup (10 seconds)...")
            time.sleep(10)

            if self.beacon_process.poll() is not None:
                self.log_result("Beacon Startup", False, "Beacon process terminated unexpectedly")
                return False

            self.log_result("Beacon Startup", True, "Beacon process started successfully")
            return True

        except Exception as e:
            self.log_result("Beacon Startup", False, f"Error: {str(e)}")
            return False

    def test_2_mdns_announcement(self) -> bool:
        logger.info("\n" + "=" * 60)
        logger.info("TEST 2: mDNS Announcement Verification")
        logger.info("=" * 60)

        try:
            result = subprocess.run(
                ['dns-sd', '-B', '_saturn._tcp', 'local', '-t', '2'],
                capture_output=True,
                text=True,
                timeout=3
            )

            if 'DeepInfra-Beacon' in result.stdout or 'saturn' in result.stdout.lower():
                self.log_result("mDNS Announcement", True, "Service visible via dns-sd browse")
                return True
            else:
                self.log_result("mDNS Announcement", False, "Service not found in dns-sd output")
                return False

        except subprocess.TimeoutExpired:
            self.log_result("mDNS Announcement", False, "dns-sd command timed out")
            return False
        except FileNotFoundError:
            logger.warning("dns-sd command not found (expected on non-macOS), using zeroconf instead")
            return True

    def test_3_client_discovery(self) -> tuple[bool, BeaconListener, Zeroconf]:
        logger.info("\n" + "=" * 60)
        logger.info("TEST 3: Client Discovery Flow")
        logger.info("=" * 60)

        listener = BeaconListener()
        zeroconf = Zeroconf()
        browser = ServiceBrowser(zeroconf, "_saturn._tcp.local.", listener)

        logger.info("Discovering beacons (timeout: 5 seconds)...")
        found = listener.beacon_found.wait(timeout=5.0)

        if not found:
            self.log_result("Client Discovery", False, "No beacon discovered within 5 seconds")
            zeroconf.close()
            return False, None, None

        beacon = listener.get_best_beacon()
        if not beacon:
            self.log_result("Client Discovery", False, "No beacons available")
            zeroconf.close()
            return False, None, None

        ephemeral_key = beacon.get('ephemeral_key')
        if not ephemeral_key:
            self.log_result("Key Extraction", False, "No ephemeral_key in TXT records")
            zeroconf.close()
            return False, None, None

        self.log_result("Client Discovery", True, f"Beacon discovered at {beacon['url']}")
        self.log_result("Key Extraction", True, f"Key: {ephemeral_key[:60]}...")

        self.old_key = ephemeral_key

        return True, listener, zeroconf

    def test_4_direct_api_call(self, ephemeral_key: str) -> bool:
        logger.info("\n" + "=" * 60)
        logger.info("TEST 4: Direct DeepInfra API Call")
        logger.info("=" * 60)

        headers = {
            "Authorization": f"Bearer {ephemeral_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
            "messages": [{"role": "user", "content": "Say 'Test successful!' in exactly two words."}]
        }

        try:
            response = requests.post(DEEPINFRA_API_URL, headers=headers, json=payload, timeout=60)

            if response.ok:
                result = response.json()
                content = result['choices'][0]['message']['content']
                self.log_result("Direct API Call", True, f"Response: {content[:100]}")
                return True
            else:
                self.log_result("Direct API Call", False, f"HTTP {response.status_code}: {response.text[:100]}")
                return False

        except Exception as e:
            self.log_result("Direct API Call", False, f"Error: {str(e)}")
            return False

    def test_5_key_rotation(self, listener: BeaconListener) -> bool:
        logger.info("\n" + "=" * 60)
        logger.info("TEST 5: Key Rotation Detection")
        logger.info("=" * 60)
        logger.info("Waiting for key rotation (this takes ~5 minutes)...")
        logger.info("Checking every 30 seconds...")

        start_time = time.time()
        timeout = 360

        while time.time() - start_time < timeout:
            time.sleep(30)

            beacon = listener.get_best_beacon()
            if beacon:
                current_key = beacon.get('ephemeral_key')
                if current_key and current_key != self.old_key:
                    elapsed = time.time() - start_time
                    self.log_result("Key Rotation", True, f"New key detected after {elapsed:.0f}s")
                    logger.info(f"       Old: {self.old_key[:40]}...")
                    logger.info(f"       New: {current_key[:40]}...")

                    if self.test_4_direct_api_call(current_key):
                        self.log_result("New Key Works", True, "API call with new key successful")
                    else:
                        self.log_result("New Key Works", False, "API call with new key failed")

                    return True

            remaining = timeout - (time.time() - start_time)
            logger.info(f"  Still waiting... ({remaining:.0f}s remaining)")

        self.log_result("Key Rotation", False, f"No rotation detected within {timeout}s")
        return False

    def cleanup(self, zeroconf: Zeroconf = None):
        logger.info("\n" + "=" * 60)
        logger.info("CLEANUP")
        logger.info("=" * 60)

        if zeroconf:
            zeroconf.close()
            logger.info("✓ Zeroconf closed")

        if self.beacon_process:
            self.beacon_process.terminate()
            try:
                self.beacon_process.wait(timeout=5)
                logger.info("✓ Beacon process terminated")
            except subprocess.TimeoutExpired:
                self.beacon_process.kill()
                logger.info("✓ Beacon process killed (timeout)")

    def print_summary(self):
        logger.info("\n" + "=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)

        total = len(self.results)
        passed = sum(1 for _, p, _ in self.results if p)
        failed = total - passed

        for test_name, passed, message in self.results:
            status = "✓ PASS" if passed else "✗ FAIL"
            logger.info(f"{status}: {test_name}")

        logger.info("-" * 60)
        logger.info(f"Total: {total} | Passed: {passed} | Failed: {failed}")

        if failed == 0:
            logger.info("\n🎉 ALL TESTS PASSED!")
            return 0
        else:
            logger.info(f"\n❌ {failed} TEST(S) FAILED")
            return 1


def main():
    test = BeaconFlowTest()
    zeroconf = None
    listener = None

    try:
        if not test.test_1_beacon_startup():
            test.cleanup()
            return test.print_summary()

        test.test_2_mdns_announcement()

        success, listener, zeroconf = test.test_3_client_discovery()
        if not success:
            test.cleanup()
            return test.print_summary()

        beacon = listener.get_best_beacon()
        ephemeral_key = beacon['ephemeral_key']

        if not test.test_4_direct_api_call(ephemeral_key):
            test.cleanup(zeroconf)
            return test.print_summary()

        logger.info("\n⚠️  NOTE: Skipping 5-minute rotation test for quick validation")
        logger.info("   To test rotation, run beacon_test_client.py and wait 5+ minutes\n")

        test.cleanup(zeroconf)
        return test.print_summary()

    except KeyboardInterrupt:
        logger.info("\n\nTest interrupted by user")
        test.cleanup(zeroconf)
        return 1

    except Exception as e:
        logger.error(f"\n\nUnexpected error: {e}", exc_info=True)
        test.cleanup(zeroconf)
        return 1


if __name__ == "__main__":
    sys.exit(main())

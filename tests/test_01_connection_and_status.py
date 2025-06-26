# tests/test_01_connection_and_status.py
import logging
import sys
sys.path.append('..') # Add parent directory to path to import modules

from mtq_driver import MTQDriver, MTQCommunicationError
from magtorquer.logging_config import setup_logging
from magtorquer.config_mtq import SERIAL_PORT, BAUD_RATE, HOST_ADDRESS, MTQ_ADDRESS, SERIAL_TIMEOUT

# Setup logging to file and console
setup_logging()
logger = logging.getLogger(__name__)

def main():
    """Test basic connection, ping, and status retrieval."""
    driver = MTQDriver(
        port=SERIAL_PORT,
        baudrate=BAUD_RATE,
        host_address=HOST_ADDRESS,
        mtq_address=MTQ_ADDRESS,
        timeout=SERIAL_TIMEOUT
    )

    try:
        driver.connect()

        # Test 1: Ping the device
        if driver.ping():
            logger.info("Ping Test: PASSED")
        else:
            logger.error("Ping Test: FAILED")

        # Test 2: Get device status
        status = driver.get_status()
        if status is not None:
            logger.info(f"Get Status Test: PASSED (Status: {status.name})")
        else:
            logger.error("Get Status Test: FAILED")

    except MTQCommunicationError as e:
        logger.error(f"A communication error occurred: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        driver.disconnect()

if __name__ == "__main__":
    main()
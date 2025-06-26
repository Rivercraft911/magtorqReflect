# tests/test_02_get_telemetry.py
import logging
import sys
sys.path.append('..') 

from mtq_driver import MTQDriver, MTQCommunicationError
from magtorquer.logging_config import setup_logging
from magtorquer.config_mtq import SERIAL_PORT, BAUD_RATE, HOST_ADDRESS, MTQ_ADDRESS, SERIAL_TIMEOUT

setup_logging()
logger = logging.getLogger(__name__)

def main():
    """Test retrieval of telemetry data like temperature and dipole moment."""
    driver = MTQDriver(SERIAL_PORT, BAUD_RATE, HOST_ADDRESS, MTQ_ADDRESS, SERIAL_TIMEOUT)

    try:
        driver.connect()

        # Test 1: Get Temperature
        temp = driver.get_temperature()
        if temp is not None:
            logger.info(f"Get Temperature Test: PASSED ({temp:.2f} °C)")
        else:
            logger.error("Get Temperature Test: FAILED")

        # Test 2: Get Measured Dipole Moment
        moment = driver.get_dipole_moment()
        if moment is not None:
            logger.info(f"Get Dipole Moment Test: PASSED ({moment} mAm²)")
        else:
            logger.error("Get Dipole Moment Test: FAILED")

    except MTQCommunicationError as e:
        logger.error(f"A communication error occurred: {e}")
    finally:
        driver.disconnect()

if __name__ == "__main__":
    main()
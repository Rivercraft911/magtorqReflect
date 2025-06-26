# tests/test_02_get_telemetry.py
import logging

from magtorquer.mtq_driver import MTQDriver, MTQCommunicationError
from magtorquer.logging_config import setup_logging
from magtorquer.config_mtq import (
    SERIAL_PORT,
    BAUD_RATE,
    HOST_ADDRESS,
    MTQ_ADDRESS,
    SERIAL_TIMEOUT,
)

setup_logging()
logger = logging.getLogger(__name__)


def main() -> None:
    try:
        with MTQDriver(
            SERIAL_PORT, BAUD_RATE, HOST_ADDRESS, MTQ_ADDRESS, SERIAL_TIMEOUT
        ) as drv:
            temp = drv.get_temperature()
            if temp is not None:
                logger.info("Temperature   : %.2f °C", temp)
            else:
                logger.error("Temperature   : FAILED")

            moment = drv.get_dipole_moment()
            if moment is not None:
                logger.info("Dipole moment : %.1f mAm²", moment)
            else:
                logger.error("Dipole moment : FAILED")
    except MTQCommunicationError as e:
        logger.error("Communication error: %s", e)


if __name__ == "__main__":
    main()

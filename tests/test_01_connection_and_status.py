#tests/test_01_connection_and_status.py
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
            if drv.ping():
                logger.info("Ping          : PASSED")
            else:
                logger.error("Ping          : FAILED")

            status = drv.get_status()
            if status:
                logger.info("Get Status    : PASSED (%s)", status.name)
            else:
                logger.error("Get Status    : FAILED")
    except MTQCommunicationError as e:
        logger.error("Communication error: %s", e)


if __name__ == "__main__":
    main()

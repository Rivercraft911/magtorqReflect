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

# You may need a logging_config.py file, or just use basicConfig
# setup_logging()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("--- Starting MTQ Connection Test ---")
    try:
        with MTQDriver(
            SERIAL_PORT, BAUD_RATE, HOST_ADDRESS, MTQ_ADDRESS, SERIAL_TIMEOUT
        ) as drv:
            
            # Use WHO_AM_I for the initial handshake, as it's guaranteed to be implemented.
            ident_payload = drv.who_am_i()
            if ident_payload:
                logger.info("WHO_AM_I      : PASSED (Response: %s)", ident_payload.hex().upper())
            else:
                logger.error("WHO_AM_I      : FAILED - No response.")
                return # Exit if the first command fails

            # Now that we know communication works, test another command.
            status = drv.get_status()
            if status:
                logger.info("Get Status    : PASSED (Status: %s)", status.name)
            else:
                logger.error("Get Status    : FAILED")

    except MTQCommunicationError as e:
        logger.error("A critical communication error occurred: %s", e)
    except Exception as e:
        logger.error("An unexpected error occurred: %s", e)

if __name__ == "__main__":
    main()
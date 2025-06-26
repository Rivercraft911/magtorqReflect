# tests/test_03_set_and_verify_dipole.py
import logging

from magtorquer.mtq_driver import MTQDriver, MTQCommunicationError
from magtorquer.logging_config import setup_logging
from magtorquer.config_mtq import SERIAL_PORT, BAUD_RATE, HOST_ADDRESS, MTQ_ADDRESS, SERIAL_TIMEOUT

setup_logging()
logger = logging.getLogger(__name__)

def main():
    """Test setting the dipole moment and controlling the device mode."""
    driver = MTQDriver(SERIAL_PORT, BAUD_RATE, HOST_ADDRESS, MTQ_ADDRESS, SERIAL_TIMEOUT)
    
    # Dipole moment to test with
    test_dipole_moment = 5000.0  # mAm^2

    try:
        driver.connect()

        # Step 1: Ensure device is stopped (IDLE) before starting
        logger.info("--- Ensuring device is in IDLE mode ---")
        driver.stop()
        time.sleep(0.5)

        # Step 2: Set the dipole moment
        logger.info(f"--- Setting dipole moment to {test_dipole_moment} mAm² ---")
        driver.set_dipole_moment(test_dipole_moment)
        time.sleep(0.5)

        # Step 3: Start the device (activate the coil)
        logger.info("--- Starting device (activating coil) ---")
        driver.start()
        time.sleep(1) # Wait for the current to stabilize

        # Step 4: Read back the measured dipole moment
        logger.info("--- Reading back measured dipole moment ---")
        measured_moment = driver.get_dipole_moment()
        if measured_moment is not None:
            # Check if the measured value is close to the setpoint
            # Allow for some tolerance in the measurement
            tolerance = 100.0 
            if abs(measured_moment - test_dipole_moment) <= tolerance:
                logger.info(f"Set/Get Dipole Test: PASSED (Set: {test_dipole_moment}, Got: {measured_moment})")
            else:
                logger.error(f"Set/Get Dipole Test: FAILED - value out of tolerance (Set: {test_dipole_moment}, Got: {measured_moment})")
        else:
            logger.error("Set/Get Dipole Test: FAILED - could not read back moment")

        # Step 5: Stop the device
        logger.info("--- Stopping device ---")
        driver.stop()
        time.sleep(0.5)
        
        # Step 6: Verify it has stopped
        final_moment = driver.get_dipole_moment()
        if final_moment is not None and abs(final_moment) < 100.0:
             logger.info(f"Stop Test: PASSED (Dipole moment near zero: {final_moment} mAm²)")
        else:
             logger.error(f"Stop Test: FAILED (Dipole moment not near zero: {final_moment} mAm²)")

    except MTQCommunicationError as e:
        logger.error(f"A communication error occurred: {e}")
    finally:
        driver.disconnect()

if __name__ == "__main__":
    main()
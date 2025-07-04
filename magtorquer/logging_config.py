# logging_config.py
"""
Centralized logging configuration for the reaction wheel controller.
This setup allows us to log important data to both the console and a file.
"""
import logging
import sys

LOG_FILENAME = "mag_test_log.txt"

def setup_logging():
    """
    Configures the root logger to output to a file and the console.
    """
    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Capture all levels of logs

    file_handler = logging.FileHandler(LOG_FILENAME, mode='w')
    file_handler.setLevel(logging.DEBUG)  # Log everything to the file

    # --- Create a handler to print logs to the console (terminal) ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  # Only show INFO and higher in console

    # --- Create a formatter to define the log message format ---
    # This format includes timestamp, logger name, log level, and message.
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Apply the formatter to both handlers
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # --- Add the handlers to the root logger ---
    # This prevents adding duplicate handlers if the function is called again.
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    print(f"Logging configured. Detailed logs will be written to '{LOG_FILENAME}'")
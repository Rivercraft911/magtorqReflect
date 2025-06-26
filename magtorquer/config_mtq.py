# config_mtq.py
"""
Configuration file for the AAC Hyperion MTQ800.15 Magnetorquer test setup.
"""

# --- Serial Port Configuration ---
SERIAL_PORT = "/dev/cu.usbserial-B00320NW"
BAUD_RATE = 115200

# --- Addresses ---
HOST_ADDRESS = 0x11
MTQ_ADDRESS = 0x31

# --- Timeouts ---
SERIAL_TIMEOUT = 2.0
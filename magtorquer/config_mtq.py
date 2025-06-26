# config_mtq.py
"""
Configuration file for the AAC Hyperion MTQ800.15 Magnetorquer test setup.
"""

# --- Serial Port Configuration ---
SERIAL_PORT = "/dev/cu.usbserial-BG00Q8TP"
BAUD_RATE = 115200

# --- Addresses ---
HOST_ADDRESS = 0x20
MTQ_ADDRESS = 0x30

# --- Timeouts ---
SERIAL_TIMEOUT = 2.0
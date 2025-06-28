
from typing import List, Tuple

# --- Serial Port Configuration ---
SERIAL_PORT = "/dev/cu.usbserial-B00320NW"
BAUD_RATE = 115200
SERIAL_TIMEOUT = 2.0  

# --- Addresses ---
HOST_ADDRESS = 0x11
MTQ_ADDRESS = 0x60

# --- Test Parameters for Power Profile ---
# Dipole moments to test, in mAm².
TEST_LEVELS_MAM2 = [0, 1875, 3750, 5000, 7500, 9000, 11250, 15000, 20000, 25000, 30000]

# Time to wait at each power level for stabilization (in seconds).
STABILIZATION_DELAY_S = 2.2

# --- Constants from ICD for reporting ---
RECOMMENDED_MAX_MAM2 = 20000.0
BOOST_START_MAM2 = 20001.0

POWER_LOOKUP_TABLE: List[Tuple[float, float]] = [
    (0,      0.070),   
    (5000,   0.760),
    (10000,  1.600),
    (15000,  3.000),
    (20000,  4.900),
    (25000,  7.200),
    (30000, 10.800),
]
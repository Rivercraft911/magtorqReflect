# magtorquer/mtq_driver.py
"""
Python Driver for the AAC Hyperion MTQ800.15 Magnetorquer
(Protocol: Hyperion Protocol)

This driver provides a high-level API for controlling the MTQ800.15,
including both general Hyperion protocol commands and device-specific
functionality.

Author : River Dowdy
Date: June 2025
"""

from __future__ import annotations

import logging
import struct
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import serial
from crc import Calculator, Configuration

logger = logging.getLogger(__name__)

# ----------------------- Protocol Constants -----------------------

# CRC configuration (poly 0xEB, init 0x00, non‑reflected) – see Protocol §3
_crc_cfg = Configuration(
    width=8, polynomial=0xEB, init_value=0x00, final_xor_value=0x00,
    reverse_input=False, reverse_output=False,
)
CRC_CALCULATOR = Calculator(_crc_cfg)

# ----------------------- Data Types & Enums -----------------------

@dataclass(frozen=True, slots=True)
class IdentifyInfo:
    """A structured container for the response from an IDENTIFY command."""
    hw_version: str
    sw_version: str

class MTQMode(Enum):
    """Device operating modes (ICD §3.2.5 - §3.2.8)."""
    IDLE       = 0x01
    RUNNING    = 0x02
    BRAKING    = 0x03
    DEGAUSSING = 0x04

class MTQStatus(Enum):
    """Device status flags (ICD §3.2.9)."""
    OK          = 0x00
    OVERCURRENT = 0x0F

class Command(Enum):
    """All available command IDs, combining General and MTQ-specific commands."""
    # -- Hyperion General Commands (Protocol Manual §5) --
    RESET             = 0x01
    ACK               = 0x02  
    PING              = 0x04
    WHO_AM_I          = 0x10
    IDENTIFY          = 0x11
    GET_SERIAL_NO     = 0x12
    GET_MODE          = 0x16  
    SET_MODE          = 0x17
    # -- MTQ-800.15 Specific Commands (ICD Table 4) --
    GET_TEMPERATURE              = 0x20
    GET_DIPOLE_MOMENT            = 0x21
    SET_DIPOLE_MOMENT_SETPOINT   = 0x22
    GET_DIPOLE_MOMENT_SETPOINT   = 0x23
    START                        = 0x25
    STOP                         = 0x26
    BRAKE                        = 0x27
    DEGAUSS                      = 0x28
    GET_STATUS                   = 0x34

class MTQCommunicationError(Exception):
    """Raised on framing, CRC or transpor issues."""

# ----------------------- Main Driver Class -----------------------

@dataclass(slots=True)
class MTQDriver:
    """ Lightweight test‑driver for the AAC Hyperion MTQ800.15. """
    port: str
    baudrate: int
    host_address: int
    mtq_address: int
    timeout: float = 2.0
    serial_conn: Optional[serial.Serial] = None

    # --- Magic Methods & Connection Handling ---
    def __post_init__(self) -> None:
        for name, val in (("host_address", self.host_address), ("mtq_address", self.mtq_address)):
            if not (0 <= val <= 0xFF): raise ValueError(f"{name} {val:#x} out of 0x00‑0xFF range")
        if self.timeout <= 0: raise ValueError("timeout must be positive")

    def __enter__(self) -> "MTQDriver":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.disconnect()

    def connect(self) -> None:
        if self.serial_conn and self.serial_conn.is_open: return
        logger.info(f"Connecting to MTQ on {self.port} @ {self.baudrate} bps…")
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            logger.info("Connection established.")
        except serial.SerialException as e:
            raise MTQCommunicationError(f"Could not open {self.port}") from e

    def disconnect(self) -> None:
        if self.serial_conn and self.serial_conn.is_open:
            logger.info("Ensuring MTQ is in a safe, idle state before disconnecting.")
            try:
                self.set_dipole_moment(0.0)
                self.stop()
            except MTQCommunicationError as e:
                logger.warning(f"Could not send final stop command: {e}")
            self.serial_conn.close()
            logger.info("Serial connection closed.")
        self.serial_conn = None

    # --- Core Protocol Layer (Internal Use) ---
    def _encode_packet(self, command_id: int, payload: bytes = b"") -> bytes:
        len_field = len(payload).to_bytes(2, "big")
        ascii_parts = (f"{self.host_address:02X}".encode("ascii"), f"{self.mtq_address:02X}".encode("ascii"), f"{command_id:02X}".encode("ascii"), len_field.hex().upper().encode("ascii"), payload.hex().upper().encode("ascii"))
        body = b"".join(ascii_parts)
        data_for_crc = body + b":"
        crc = CRC_CALCULATOR.checksum(data_for_crc)
        return b"$" + data_for_crc + f"{crc:02X}".encode("ascii") + b"\n"

    def _decode_response(self, frame: bytes) -> tuple[int, int, int, bytes]:
        if not frame.startswith(b"$") or not frame.endswith(b"\n") or b":" not in frame:
            raise MTQCommunicationError(f"Malformed packet received: {frame!r}")
        body_with_crc = frame[1:-1]
        body, crc_ascii = body_with_crc.rsplit(b":", 1)
        calculated_crc = CRC_CALCULATOR.checksum(body + b":")
        received_crc = int(crc_ascii, 16)
        if calculated_crc != received_crc:
            raise MTQCommunicationError(f"CRC mismatch! (Got {received_crc:#04x}, want {calculated_crc:#04x})")
        src, dst, cmd, length = int(body[0:2], 16), int(body[2:4], 16), int(body[4:6], 16), int(body[6:10], 16)
        payload_ascii = body[10:]
        if len(payload_ascii) != length * 2: raise MTQCommunicationError("Payload length mismatch.")
        return src, dst, cmd, bytes.fromhex(payload_ascii.decode("ascii")) if length else b""

    def _transport(self, command: Command, payload: bytes = b"", *, expect_response: bool = True) -> Optional[bytes]:
        if not (self.serial_conn and self.serial_conn.is_open):
            raise MTQCommunicationError("Port not open.")
        pkt = self._encode_packet(command.value, payload)
        logger.debug("TX -> %r", pkt)
        self.serial_conn.write(pkt)
        self.serial_conn.flush()
        time.sleep(0.05) # Allow time for the device to process the command
        if not expect_response: return None
        resp = self.serial_conn.readline()
        logger.debug("RX <- %r", resp)
        if not resp: raise MTQCommunicationError(f"Timeout from MTQ (Addr: {self.mtq_address:#04x})")
        src, _, _, resp_payload = self._decode_response(resp)
        if src != self.mtq_address: logger.warning(f"Response from unexpected address {src:#04x}")
        return resp_payload

    # ----------------------- High-Level API: General Hyperion Commands -----------------------
    def ping(self) -> None:
        """Sends a PING command to reset the device's watchdog timer."""
        self._transport(Command.PING, expect_response=False)

    def reset_device(self) -> None:
        """Sends a RESET command. The device will reboot."""
        self._transport(Command.RESET, expect_response=False)

    def who_am_i(self) -> Optional[bytes]:
        """Gets the 4-byte product line specification (e.g., 'P', 'M', 200, 1)."""
        return self._transport(Command.WHO_AM_I)

    def identify(self) -> Optional[IdentifyInfo]:
        """Gets the hardware and software version of the device."""
        pl = self._transport(Command.IDENTIFY)
        if not pl: return None
        ww, xx, yy, zz = struct.unpack(">BBBB", pl)
        return IdentifyInfo(hw_version=f"{ww}.{xx}", sw_version=f"{yy}.{zz}")

    def get_serial_no(self) -> Optional[int]:
        """Gets the unique 32-bit serial number of the device."""
        pl = self._transport(Command.GET_SERIAL_NO)
        return struct.unpack(">I", pl)[0] if pl else None

    # ----------------------- High-Level API: MTQ800.15 Specific Commands -----------------------

    def get_status(self) -> Optional[MTQStatus]:
        """Gets the device status (OK or OVERCURRENT)."""
        pl = self._transport(Command.GET_STATUS)
        return MTQStatus(int.from_bytes(pl, "big")) if pl else None

    def get_temperature(self) -> Optional[float]:
        """Returns the on-chip temperature in Celsius."""
        pl = self._transport(Command.GET_TEMPERATURE)
        if not pl: return None
        return (struct.unpack(">H", pl)[0] / 10.0) - 273.15

    def set_dipole_moment(self, mAm2: float | int) -> None:
            """ Set the desired magnetic dipole moment. """

            mAm2_int = int(round(mAm2))
            if not (-30_000 <= mAm2_int <= 30_000):
                raise ValueError("dipole set‑point must be within ±30 000 mAm²")

            payload = mAm2_int.to_bytes(2, "big", signed=True)   # 2‑byte payload
            self._transport(Command.SET_DIPOLE_MOMENT_SETPOINT,
                            payload,
                            expect_response=False)


    def get_dipole_moment(self) -> Optional[int]:
        """Returns the currently measured dipole moment in mAm² as a signed 16-bit int."""
        pl = self._transport(Command.GET_DIPOLE_MOMENT)
        return struct.unpack(">h", pl)[0] if pl else None

    def get_dipole_moment_setpoint(self) -> Optional[float]:
        """Returns the currently configured dipole moment setpoint as a float."""
        pl = self._transport(Command.GET_DIPOLE_MOMENT_SETPOINT)
        return struct.unpack(">f", pl)[0] if pl else None

    # --- High-Level API: Mode Control Shorthands ---
    def start(self) -> None:
        """Shorthand to enter RUNNING mode."""
        self._transport(Command.START, expect_response=False)

    def stop(self) -> None:
        """Shorthand to enter IDLE mode."""
        self._transport(Command.STOP, expect_response=False)

    def brake(self) -> None:
        """Shorthand to enter BRAKING mode."""
        self._transport(Command.BRAKE, expect_response=False)

    def degauss(self) -> None:
        """Shorthand to enter DEGAUSSING mode. Takes ~10 seconds."""
        self._transport(Command.DEGAUSS, expect_response=False)
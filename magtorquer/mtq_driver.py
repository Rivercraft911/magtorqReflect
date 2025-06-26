"""
Python Driver for the AAC Hyperion MTQ800.15 Magnetorquer
(Protocol: Hyperion Protocol)

Author : River Dowdy
Date: June 2025
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import serial
from crc import Calculator, Configuration

logger = logging.getLogger(__name__)

#  CRC configuration (poly 0xEB, init 0x00, non‑reflected) – see Protocol 3  

_crc_cfg = Configuration(
    width=8,
    polynomial=0xEB,
    init_value=0x00,
    final_xor_value=0x00,
    reverse_input=False,
    reverse_output=False,
)
CRC_CALCULATOR = Calculator(_crc_cfg)


#  Enums                                                           
class MTQMode(Enum):
    IDLE       = 0x01
    RUNNING    = 0x02
    BRAKING    = 0x03
    DEGAUSSING = 0x04


class MTQStatus(Enum):
    OK          = 0x00
    OVERCURRENT = 0x0F


class Command(Enum):
    # — General —
    RESET             = 0x01
    ACK               = 0x02
    PING              = 0x04
    WHO_AM_I          = 0x10
    IDENTIFY          = 0x11
    GET_SERIAL_NO     = 0x12
    GET_MODE          = 0x16
    SET_MODE          = 0x17
    # — MTQ‑specific —
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
    """Raised on framing, CRC or transport issues."""



#  Main Driver                                      
@dataclass(slots=True)
class MTQDriver:
    """ Lightweight test‑driver for the AAC Hyperion MTQ800.15. """

    port: str
    baudrate: int
    host_address: int
    mtq_address: int
    timeout: float = 2.0

    # Instance variable created post‑init
    serial_conn: Optional[serial.Serial] = None

    #  Magic methods  #
    def __post_init__(self) -> None:
        # Fast sanity checks – fail early on typos
        for name, val in (("host_address", self.host_address),
                          ("mtq_address",  self.mtq_address)):
            if not (0 <= val <= 0xFF):
                raise ValueError(f"{name} {val:#x} out of 0x00‑0xFF range")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")

    # Context‑manager sugar
    def __enter__(self) -> "MTQDriver":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:        # noqa: D401 (imperative)
        self.disconnect()

    #  Transport layer  #
    def connect(self) -> None:
        if self.serial_conn and self.serial_conn.is_open:
            logger.info("Serial connection already open – skipping.")
            return
        logger.info("Connecting to MTQ on %s @ %d bps …", self.port, self.baudrate)
        try:
            self.serial_conn = serial.Serial(
                self.port, self.baudrate, timeout=self.timeout
            )
            logger.info("Connection established.")
        except serial.SerialException as e:
            logger.error("Could not open serial port %s: %s", self.port, e)
            raise MTQCommunicationError(f"Could not open {self.port}") from e

    def disconnect(self) -> None:
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logger.info("Serial connection closed.")
        self.serial_conn = None

    #  Framing helpers  #
    def _encode_packet(self, command_id: int, payload: bytes = b"") -> bytes:
        if len(payload) > 0xFFFF:
            raise ValueError("payload too large (max 65 535 bytes)")

        len_field = len(payload).to_bytes(2, "big")

        ascii_parts = (
            f"{self.host_address:02X}".encode("ascii"),
            f"{self.mtq_address:02X}".encode("ascii"),
            f"{command_id:02X}".encode("ascii"),
            len_field.hex().upper().encode("ascii"),
            payload.hex().upper().encode("ascii"),
        )
        body = b"".join(ascii_parts)
        data_for_crc = body + b":"
        crc = CRC_CALCULATOR.checksum(data_for_crc)
        packet = b"$" + data_for_crc + f"{crc:02X}".encode("ascii") + b"\n"
        return packet

    def _decode_response(self, frame: bytes) -> tuple[int, int, int, bytes]:
        # 1) Validate framing first (newline intact)
        if not frame.startswith(b"$") or not frame.endswith(b"\n") or b":" not in frame:
            raise MTQCommunicationError(f"Malformed packet: {frame!r}")

        # 2) Strip start/stop markers AFTER validation
        body_with_crc = frame[1:-1]  # drop $ and \n
        body, crc_ascii = body_with_crc.rsplit(b":", 1)
        calculated = CRC_CALCULATOR.checksum(body + b":")
        received = int(crc_ascii, 16)
        if calculated != received:
            raise MTQCommunicationError(
                f"CRC mismatch (got {received:#04x}, want {calculated:#04x})"
            )

        src   = int(body[0:2], 16)
        dst   = int(body[2:4], 16)
        cmd   = int(body[4:6], 16)
        length = int(body[6:10], 16)
        pl_ascii = body[10:]

        if len(pl_ascii) != length * 2:
            raise MTQCommunicationError("Payload length mismatch after decode.")
        payload = bytes.fromhex(pl_ascii.decode("ascii")) if length else b""
        return src, dst, cmd, payload

    #  Core send/recv  #
    def _transport(self, cmd: int, payload: bytes = b"", *, expect_response=True
                   ) -> Optional[bytes]:
        if not (self.serial_conn and self.serial_conn.is_open):
            raise MTQCommunicationError("Port not open – call connect()/use 'with'.")

        pkt = self._encode_packet(cmd, payload)
        logger.debug("TX: %s", pkt)
        self.serial_conn.write(pkt)
        self.serial_conn.flush()

        if not expect_response:
            return None

        resp = self.serial_conn.readline()
        logger.debug("RX: %s", resp)
        if not resp:
            raise MTQCommunicationError("Timeout waiting for response.")
        _, _, _, resp_payload = self._decode_response(resp)
        return resp_payload

    #  Public high‑level API #
    def ping(self) -> bool:
        try:
            self._transport(Command.PING.value, expect_response=False)
            return True
        except MTQCommunicationError as e:
            logger.error("Ping failed: %s", e)
            return False

    def get_status(self) -> Optional[MTQStatus]:
        pl = self._transport(Command.GET_STATUS.value)
        return MTQStatus(int.from_bytes(pl, "big")) if pl else None

    def get_temperature(self) -> Optional[float]:
        """Returns °C or None on comms error."""
        pl = self._transport(Command.GET_TEMPERATURE.value)
        if not pl:
            return None
        deci_kelvin = struct.unpack(">H", pl)[0]
        return (deci_kelvin / 10.0) - 273.15

    def set_dipole_moment(self, mAm2: float) -> None:
        pl = struct.pack(">f", mAm2)          # ICD §3.2.4 – 4‑byte float
        self._transport(Command.SET_DIPOLE_MOMENT_SETPOINT.value, pl)

    def get_dipole_moment(self) -> Optional[float]:
        pl = self._transport(Command.GET_DIPOLE_MOMENT.value)
        return float(struct.unpack(">h", pl)[0]) if pl else None

    # --- Convenience wrappers ---
    def set_mode(self, mode: MTQMode) -> None:
        self._transport(Command.SET_MODE.value, mode.value.to_bytes(1, "big"))

    def start(self) -> None:
        self._transport(Command.START.value)

    def stop(self) -> None:
        self._transport(Command.STOP.value)

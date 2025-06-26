# mtq_driver.py
"""
Python Driver for the AAC Hyperion MTQ800.15 Magnetorquer.

Author: River Dowdy
Date: June 2025
"""
import logging
import struct
import time
from enum import Enum

import serial
from crc import CrcCalculator, Crc8

logger = logging.getLogger(__name__)

# As per Hyperion Protocol Manual, §3: CRC-8 with polynomial 0xEB, init 0x00.
# The CRC is calculated over the ASCII-encoded bytes from source address to the ':' separator.
CRC_CALCULATOR = CrcCalculator(Crc8.ROHC,-1) # This is equivalent to poly=0xEB, init=0x00


class MTQMode(Enum):
    """Operational modes for the MTQ800.15 device."""
    IDLE = 0x01
    RUNNING = 0x02
    BRAKING = 0x03
    DEGAUSSING = 0x04

class MTQStatus(Enum):
    """Device status codes for the MTQ800.15 device."""
    OK = 0x00
    OVERCURRENT = 0x0F

class Command(Enum):
    """Hyperion Protocol General and MTQ-specific Command IDs."""
    # General Commands
    RESET = 0x01
    ACK = 0x02
    PING = 0x04
    WHO_AM_I = 0x10
    IDENTIFY = 0x11
    GET_SERIAL_NO = 0x12
    GET_MODE = 0x16
    SET_MODE = 0x17

    # Mag Specific Commands
    GET_TEMPERATURE = 0x20
    GET_DIPOLE_MOMENT = 0x21
    SET_DIPOLE_MOMENT_SETPOINT = 0x22
    GET_DIPOLE_MOMENT_SETPOINT = 0x23
    START = 0x25
    STOP = 0x26
    BRAKE = 0x27
    DEGAUSS = 0x28
    GET_STATUS = 0x34


class MTQCommunicationError(Exception):
    """Exception for driver-related errors."""
    pass


class MTQDriver:
    """
    Manages communication with the MTQ800.15 magnetorquer.
    """

    def __init__(self, port: str, baudrate: int, host_address: int, mtq_address: int, timeout: float):
        """
        Initializes the MTQDriver.
        """
        self.port = port
        self.baudrate = baudrate
        self.host_address = host_address
        self.mtq_address = mtq_address
        self.timeout = timeout
        self.serial_conn = None

    def connect(self):
        """Establishes the serial connection to the device."""
        if self.serial_conn and self.serial_conn.is_open:
            logger.info("Serial connection is already open.")
            return
        try:
            logger.info(f"Connecting to MTQ on {self.port} at {self.baudrate} bps...")
            self.serial_conn = serial.Serial(
                self.port, self.baudrate, timeout=self.timeout
            )
            logger.info("Connection successful.")
        except serial.SerialException as e:
            logger.error(f"Failed to connect to {self.port}: {e}")
            raise MTQCommunicationError(f"Could not open serial port {self.port}") from e

    def disconnect(self):
        """Closes the serial connection."""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logger.info("Serial connection closed.")
        self.serial_conn = None

    def _encode_packet(self, command_id: int, payload: bytes = b'') -> bytes:
        
        """ Encodes a command and payload into a full Hyperion Protocol packet. """

        # Data length is the number of un-encoded payload bytes, as a 2-byte big-endian value
        data_length_bytes = len(payload).to_bytes(2, 'big')

        # Create the core ASCII-encoded data string for CRC calculation
        # Each byte is converted to a two-character hex string
        src_ascii = f'{self.host_address:02X}'.encode('ascii')
        dst_ascii = f'{self.mtq_address:02X}'.encode('ascii')
        cmd_ascii = f'{command_id:02X}'.encode('ascii')
        len_ascii = data_length_bytes.hex().upper().encode('ascii')
        payload_ascii = payload.hex().upper().encode('ascii')

        # The data over which the CRC is calculated
        data_for_crc = src_ascii + dst_ascii + cmd_ascii + len_ascii + payload_ascii + b':'
        
        # Calculate CRC
        crc_val = CRC_CALCULATOR.calculate(data_for_crc)
        crc_ascii = f'{crc_val:02X}'.encode('ascii')

        # Assemble the final packet
        packet = b'$' + data_for_crc + crc_ascii + b'\n'
        return packet

    def _decode_response(self, response: bytes) -> tuple[int, int, int, bytes]:
        """
        Decodes and validates a raw response packet from the device."""


        response = response.strip()
        if not response.startswith(b'$') or not response.endswith(b'\n') or b':' not in response:
            raise MTQCommunicationError(f"Malformed packet received: {response}")

        # Remove start/stop markers
        clean_packet = response[1:-1]
        
        parts = clean_packet.split(b':')
        if len(parts) != 2:
            raise MTQCommunicationError(f"Invalid packet structure (missing or extra ':'): {response}")
            
        body, received_crc_ascii = parts
        data_for_crc = body + b':'
        
        # Verify CRC
        calculated_crc = CRC_CALCULATOR.calculate(data_for_crc)
        received_crc = int(received_crc_ascii, 16)

        if calculated_crc != received_crc:
            raise MTQCommunicationError(
                f"CRC mismatch! Got {received_crc:02X}, calculated {calculated_crc:02X}. Packet: {response}"
            )

        # Parse the validated packet body
        src = int(body[0:2], 16)
        dst = int(body[2:4], 16)
        cmd = int(body[4:6], 16)
        length = int(body[6:10], 16)
        payload_ascii = body[10:]
        
        # Convert ASCII payload back to binary
        if length > 0:
            payload = bytes.fromhex(payload_ascii.decode('ascii'))
            if len(payload) != length:
                raise MTQCommunicationError("Payload length mismatch after decoding.")
        else:
            payload = b''
            
        return src, dst, cmd, payload

    def send_command(self, command_id: int, payload: bytes = b'', expect_response=True) -> bytes | None:
        """
        Sends a command and handles the response.
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            raise MTQCommunicationError("Serial connection is not open. Call connect() first.")

        packet_to_send = self._encode_packet(command_id, payload)
        logger.debug(f"TX: {packet_to_send}")
        
        self.serial_conn.write(packet_to_send)
        self.serial_conn.flush()

        if not expect_response:
            return None

        response = self.serial_conn.readline()
        logger.debug(f"RX: {response}")
        
        if not response:
            raise MTQCommunicationError("Timeout: No response from device.")
            
        _, _, _, resp_payload = self._decode_response(response)
        return resp_payload

    # --- High-Level API ---

    def ping(self) -> bool:
        """Sends a PING command to the device to keep the watchdog happy."""
        logger.info("Pinging device...")
        try:
            self.send_command(Command.PING.value, expect_response=False)
            logger.info("Ping sent successfully.")
            return True
        except MTQCommunicationError as e:
            logger.error(f"Ping failed: {e}")
            return False

    def get_status(self) -> MTQStatus | None:
        """Retrieves the current status of the device."""
        logger.info("Requesting device status...")
        payload = self.send_command(Command.GET_STATUS.value)
        if payload:
            status_val = int.from_bytes(payload, 'big')
            status = MTQStatus(status_val)
            logger.info(f"Device status: {status.name}")
            return status
        return None

    def get_temperature(self) -> float | None:
        """
        Retrieves the on-chip temperature.
        """
        logger.info("Requesting temperature...")
        payload = self.send_command(Command.GET_TEMPERATURE.value)
        if payload:
            # Returns uint16_t (Big Endian) in deci-Kelvin
            deci_kelvin = struct.unpack('>H', payload)[0]
            celsius = (deci_kelvin / 10.0) - 273.15
            logger.info(f"Temperature: {celsius:.2f} °C")
            return celsius
        return None

    def set_dipole_moment(self, mAm2: float) -> None:
        """
        Sets the magnetic dipole moment setpoint.
        """
        logger.info(f"Setting dipole moment to {mAm2:.2f} mAm²...")
        # Payload is a 4-byte float (Big Endian)
        payload = struct.pack('>f', mAm2)
        # This command doesn't return a value, but expect an ACK packet.
        # The ACK packet (CMD 0x02) has an optional 2-byte payload we can ignore.
        self.send_command(Command.SET_DIPOLE_MOMENT_SETPOINT.value, payload)
        logger.info("Dipole moment set.")

    def get_dipole_moment(self) -> float | None:
        """
        Retrieves the currently measured magnetic dipole moment.
        """
        logger.info("Requesting measured dipole moment...")
        payload = self.send_command(Command.GET_DIPOLE_MOMENT.value)
        if payload:
            # Returns int16_t (Big Endian) in mAm²
            moment = struct.unpack('>h', payload)[0]
            logger.info(f"Measured dipole moment: {moment} mAm²")
            return float(moment)
        return None

    def set_mode(self, mode: MTQMode):
        """Sets the operational mode of the device."""
        logger.info(f"Setting mode to {mode.name} (0x{mode.value:02X})...")
        payload = mode.value.to_bytes(1, 'big')
        self.send_command(Command.SET_MODE.value, payload)
        logger.info("Mode set.")

    def start(self):
        """Shorthand to set the device to RUNNING mode."""
        logger.info("Sending START command...")
        self.send_command(Command.START.value)
        logger.info("Device started (RUNNING mode).")

    def stop(self):
        """Shorthand to set the device to IDLE mode."""
        logger.info("Sending STOP command...")
        self.send_command(Command.STOP.value)
        logger.info("Device stopped (IDLE mode).")
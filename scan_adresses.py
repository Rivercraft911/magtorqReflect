#!/usr/bin/env python3
import sys
import time

from crc import Calculator, Configuration
import serial


crc_config = Configuration(
    width=8,
    polynomial=0xEB,
    init_value=0x00,
    final_xor_value=0x00,
    reverse_input=False,
    reverse_output=False,
)
crc_calc = Calculator(crc_config)


def build_whoami_frame(host_addr: int, node_addr: int) -> bytes:
\
    ascii_body = f"{host_addr:02X}{node_addr:02X}10" + "0000:"
    data = ascii_body.encode('ascii')
    crc_val = crc_calc.checksum(data)
    return b'$' + data + f"{crc_val:02X}".encode('ascii') + b"\n"


def scan_addresses(port: str, baud: int, host: int, start: int, end: int) -> None:
\
    print(f"Scanning addresses 0x{start:02X} to 0x{end:02X} with host 0x{host:02X}...")
    try:
        ser = serial.Serial(port, baud, timeout=0.5)
    except Exception as e:
        print(f"Error opening {port}: {e}")
        sys.exit(1)

    with ser:
        for node in range(start, end + 1):
            frame = build_whoami_frame(host, node)
            ser.reset_input_buffer()
            ser.write(frame)
            ser.flush()
            time.sleep(0.05)
            reply = ser.readline()
            if reply:
                hex_dump = ' '.join(f"{b:02X}" for b in reply)
                try:
                    ascii_rep = reply.decode('ascii', errors='replace').strip()
                except Exception:
                    ascii_rep = '<non-ASCII reply>'
                print(f"Address 0x{node:02X} replied: {hex_dump}  ({ascii_rep})")
                break
            else:
                print(f"No reply from 0x{node:02X}")
        else:
            print("No devices responded in the specified range.")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scan_addresses.py /dev/cu.usbserial-XXXX [baud] [host] [start] [end]")
        sys.exit(1)

    port = sys.argv[1]
    baud = int(sys.argv[2]) if len(sys.argv) >= 3 else 115200
    host = int(sys.argv[3], 0) if len(sys.argv) >= 4 else 0x11
    start = int(sys.argv[4], 0) if len(sys.argv) >= 5 else 0x00
    end   = int(sys.argv[5], 0) if len(sys.argv) >= 6 else 0xFF

    scan_addresses(port, baud, host, start, end)

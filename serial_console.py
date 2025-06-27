#!/usr/bin/env python3
import sys
import threading
import time
import serial

def reader(ser):
\
    while True:
        line = ser.readline() 
        if line:
            print("RX:", ' '.join(f"{b:02X}" for b in line))


def main():
    if len(sys.argv) < 2:
        print("Usage: python serial_console.py /dev/cu.usbserial-XXXX [baud]")
        sys.exit(1)

    port = sys.argv[1]
    baud = int(sys.argv[2]) if len(sys.argv) >= 3 else 115200

    try:
        ser = serial.Serial(port, baud, timeout=1)
    except Exception as e:
        print(f"Error opening {port}: {e}")
        sys.exit(1)


    print(f"Opened {port} @ {baud} bps.")
    t = threading.Thread(target=reader, args=(ser,), daemon=True)
    t.start()
    try:
        while True:
            line = input("TX> ")
            if not line:
                continue
            if line.lower().strip() in ("exit", "quit"):
                break
            send = line.encode("ascii") + b"\n"
            ser.write(send)
            print("TX:", ' '.join(f"{b:02X}" for b in send))
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()


if __name__ == "__main__":
    main()

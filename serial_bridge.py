#!/usr/bin/env python3
"""
serial_bridge.py - USB Serial <-> TCP Bridge

Forwards data between the ground ESP32-S3 (via USB-to-UART) and
mosquitto MQTT broker (localhost:1883).

Usage:
    python serial_bridge.py [COM_PORT] [BAUDRATE]

    Default: COM3, 115200
"""

import sys
import time
import socket
import threading
import serial
import serial.tools.list_ports

SERIAL_PORT = sys.argv[1] if len(sys.argv) > 1 else "COM3"
BAUDRATE = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
TCP_HOST = "127.0.0.1"
TCP_PORT = 1883
RECONNECT_DELAY = 2.0


def list_ports():
    print("Available serial ports:")
    for port in serial.tools.list_ports.comports():
        print(f"  {port.device} - {port.description}")


def connect_tcp():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    sock.connect((TCP_HOST, TCP_PORT))
    return sock


def main():
    print("=" * 60)
    print("Serial Bridge - Ground ESP32 <-> MQTT Broker")
    print("=" * 60)

    print(f"\nOpening serial port: {SERIAL_PORT} @ {BAUDRATE} baud")
    ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0.1)
    ser.dtr = False
    ser.rts = False
    print(f"Serial port opened: {ser.name} (DTR/RTS disabled)")

    reconnect_count = 0

    while True:
        try:
            sock = None

            print(f"\nConnecting to MQTT broker: {TCP_HOST}:{TCP_PORT}")
            sock = connect_tcp()
            print(f"TCP connected to {TCP_HOST}:{TCP_PORT}")
            reconnect_count = 0

            print("Bridge active (forwarding all data). Ctrl+C to stop.")
            print("(airborne ESP32 <-> ground ESP32 <-> serial <-> mosquitto)")

            stop_event = threading.Event()
            tcp_error = []

            def serial_to_tcp():
                buf = bytearray(4096)
                while not stop_event.is_set():
                    try:
                        n = ser.readinto(buf)
                        if n > 0:
                            sock.sendall(buf[:n])
                    except serial.SerialException:
                        break
                    except (OSError, ConnectionError) as e:
                        tcp_error.append(e)
                        break

            def tcp_to_serial():
                while not stop_event.is_set():
                    try:
                        data = sock.recv(4096)
                        if not data:
                            break
                        ser.write(data)
                        ser.flush()
                    except socket.timeout:
                        continue
                    except (OSError, ConnectionError) as e:
                        tcp_error.append(e)
                        break
                    except serial.SerialException:
                        break

            t1 = threading.Thread(target=serial_to_tcp, daemon=True)
            t2 = threading.Thread(target=tcp_to_serial, daemon=True)
            t1.start()
            t2.start()

            t1.join()
            t2.join()

            if tcp_error:
                raise tcp_error[0]

        except serial.SerialException as e:
            print(f"Serial error: {e}")
            ser.close()
            break
        except (OSError, ConnectionError) as e:
            reconnect_count += 1
            print(f"TCP error: {e}")
        except KeyboardInterrupt:
            break

        if sock:
            try:
                sock.close()
            except Exception:
                pass

        delay = min(RECONNECT_DELAY * reconnect_count, 10.0)
        print(f"Reconnecting in {delay:.1f}s (attempt #{reconnect_count})...")
        time.sleep(delay)

    print("\nBridge stopped.")
    ser.close()


if __name__ == "__main__":
    main()
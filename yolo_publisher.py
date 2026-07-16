#!/usr/bin/env python3
"""
yolo_publisher.py - Publish YOLO detection results to MQTT

Reads YOLO detection output (from file/stdin/API) and publishes
to MQTT topic "drone/yolo_detect" for the airborne ESP32-S3.

Usage:
    # Method 1: File input (YOLO saves results to JSON)
    python yolo_publisher.py --input detections.json

    # Method 2: Stdin pipe (YOLO outputs JSON lines)
    python yolo.py detect video.mp4 | python yolo_publisher.py --stdin

    # Method 3: API mode (listen for HTTP POST with detection data)
    python yolo_publisher.py --api --port 9090

Output format (JSON per line):
    {"objects": [{"class": "plastic_bottle", "conf": 0.85}, ...]}
"""

import json
import sys
import time
import threading
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("ERROR: pip install paho-mqtt")
    sys.exit(1)

# ---- Config ----
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "drone/debris_event"
QOS = 1

# ---- Global state ----
client = None
publish_count = 0
last_publish_time = 0


def on_connect(c, userdata, flags, rc):
    if rc == 0:
        print(f"[YOLO] Connected to {MQTT_BROKER}:{MQTT_PORT}")
        print(f"[YOLO] Publishing to topic: {MQTT_TOPIC}")
    else:
        print(f"[YOLO] Connect failed, rc={rc}")


def publish_detection(data: dict):
    global publish_count, last_publish_time

    if client is None or not client.is_connected():
        print("[WARNING] MQTT not connected, skipping")
        return

    payload = json.dumps(data, ensure_ascii=False)
    result = client.publish(MQTT_TOPIC, payload, qos=QOS)

    publish_count += 1
    last_publish_time = time.time()

    objs = data.get("objects", [])
    cls_list = [o.get("class", "?") for o in objs]
    print(f"[YOLO #{publish_count}] Published: {len(objs)} objects - {cls_list}")


# ---- Method 1: File input ----

def read_file_loop(filepath: str, interval_sec: float = 0.5):
    """Read detection file and publish each line as a detection."""
    print(f"[YOLO] Reading from file: {filepath}")
    print(f"[YOLO] Press Ctrl+C to stop")

    last_line_count = 0

    while True:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            new_lines = lines[last_line_count:]
            last_line_count = len(lines)

            for line in new_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    publish_detection(data)
                except json.JSONDecodeError:
                    print(f"[WARNING] Invalid JSON: {line[:80]}")

            time.sleep(interval_sec)

        except FileNotFoundError:
            print(f"[WAITING] File not found: {filepath}, waiting...")
            time.sleep(2)
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(2)


# ---- Method 2: Stdin pipe ----

def stdin_loop():
    """Read JSON lines from stdin and publish."""
    print("[YOLO] Reading from stdin (pipe mode)")
    print("[YOLO] Send one JSON object per line:")
    print('  Example: {"objects":[{"class":"bottle","conf":0.9}]}')
    print("Press Ctrl+C to stop")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            publish_detection(data)
        except json.JSONDecodeError:
            print(f"[WARNING] Invalid JSON: {line[:80]}")


# ---- Method 3: HTTP API server ----

class YOLOHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')

        try:
            data = json.loads(body)
            publish_detection(data)

            response = {
                "status": "ok",
                "published": True,
                "topic": MQTT_TOPIC,
                "total_published": publish_count
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "invalid_json"}).encode())

    def do_GET(self):
        response = {
            "service": "yolo_publisher",
            "topic": MQTT_TOPIC,
            "connected": client.is_connected() if client else False,
            "total_published": publish_count,
            "last_publish": last_publish_time
        }
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

    def log_message(self, format, *args):
        pass


def api_server(port: int):
    """Start HTTP server for receiving YOLO detections."""
    server = HTTPServer(('0.0.0.0', port), YOLOHandler)
    print(f"[YOLO] API server listening on http://localhost:{port}")
    print(f"[YOLO] POST JSON to http://localhost:{port}/")
    print(f"       curl -X POST http://localhost:{port}/ -d '{{\"objects\":[...]}}'")
    server.serve_forever()


# ---- Main ----

def main():
    global client

    parser = argparse.ArgumentParser(description="YOLO Detection Publisher")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", "-i", help="Input JSON file path")
    group.add_argument("--stdin", "-s", action="store_true", help="Read from stdin pipe")
    group.add_argument("--api", "-a", action="store_true", help="HTTP API server mode")
    parser.add_argument("--port", "-p", type=int, default=9090, help="API port (default: 9090)")
    parser.add_argument("--interval", type=float, default=0.5, help="File poll interval sec")
    args = parser.parse_args()

    print("=" * 50)
    print("  YOLO Detection Publisher")
    print("=" * 50)

    # Connect MQTT
    client = mqtt.Client()
    client.on_connect = on_connect
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        time.sleep(1)
    except Exception as e:
        print(f"[ERROR] Cannot connect to MQTT at {MQTT_BROKER}:{MQTT_PORT}")
        print("       Make sure mosquitto is running!")
        sys.exit(1)

    # Start appropriate mode
    if args.input:
        read_file_loop(args.input, args.interval)
    elif args.stdin:
        stdin_loop()
    elif args.api:
        api_server(args.port)

# 在 yolo_publisher.py 的末尾（if __name__ 之前）添加：

def init_mqtt():
    """初始化 MQTT 连接，供外部 import 调用"""
    global client
    client = mqtt.Client()
    client.on_connect = on_connect
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        time.sleep(1)
        print(f"[YOLO] MQTT connected to {MQTT_BROKER}:{MQTT_PORT}")
        return True
    except Exception as e:
        print(f"[ERROR] MQTT connect failed: {e}")
        return False

if __name__ == '__main__':
    main()
import paho.mqtt.client as mqtt
import json
import time
import random
import socket

# ==================== 配置 ====================
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
UDP_PORT = 14550

TOPICS = {
    "telemetry": "drone/telemetry",
    "health": "drone/health",
    "yolo": "drone/yolo_detect",
    "rtl": "drone/rtl"
}
# =============================================

client = mqtt.Client()


def publish_telemetry():
    """模拟遥测数据，包含RSSI变化"""
    # 故意模拟三种信号状态：Good / Weak / Critical
    rssi = random.choice([-62, -68, -78, -85, -98, -102])

    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "lat": 28.008 + random.random() * 0.02,  # 湖南科技大学附近
        "lon": 112.945 + random.random() * 0.02,
        "alt": 50 + random.randint(-10, 20),
        "rssi": rssi,
        "battery": random.randint(25, 100),
        "mode": "AUTO" if rssi > -95 else "RTL",  # Critical时自动返航
        "link": "TCP" if rssi > -95 else "UDP_FALLBACK"
    }
    client.publish(TOPICS["telemetry"], json.dumps(payload))

    # Critical信号：RSSI<-95时，同时通过UDP 14550发送（模拟天空端fallback）
    if rssi < -95:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(json.dumps(payload).encode(), ("127.0.0.1", UDP_PORT))
            sock.close()
            print(f"  [UDP:14550] Critical fallback sent! RSSI={rssi}")
        except Exception as e:
            print(f"  [UDP] Error: {e}")

    color = "🟢" if rssi > -75 else ("🟡" if rssi > -95 else "🔴")
    print(f"{color} [Telemetry] RSSI={rssi}dBm | Mode={payload['mode']} | Link={payload['link']}")
    return rssi


def publish_health():
    """模拟健康状态"""
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "good",
        "cpu": random.randint(30, 80),
        "mem": random.randint(40, 90),
        "temp": random.randint(45, 70),
        "uptime": int(time.time()) % 3600
    }
    client.publish(TOPICS["health"], json.dumps(payload))
    print("  [Health] good")


def publish_yolo():
    """模拟YOLO检测结果，格式和detect_sd_mqtt.py完全一致"""
    objects = []
    for _ in range(random.randint(0, 3)):
        objects.append({
            "class": random.choice(["plastic", "bottle", "can", "carton", "paper"]),
            "conf": round(random.uniform(0.65, 0.92), 2),
            "x": random.randint(120, 480),
            "y": random.randint(100, 360),
            "w": random.randint(60, 140),
            "h": random.randint(60, 140)
        })
    payload = {
        "type": "debris_detection",
        "frame_id": int(time.time()) % 10000,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "count": len(objects),
        "objects": objects
    }
    client.publish(TOPICS["yolo"], json.dumps(payload))
    print(f"  [YOLO] {len(objects)} objects: {[o['class'] for o in objects]}")


def main():
    print("=" * 50)
    print("Mock ESP32 - 模拟天空端数据流")
    print("=" * 50)
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    print(f"Connected to MQTT {MQTT_BROKER}:{MQTT_PORT}")
    print("Ctrl+C to stop.\n")

    frame = 0
    try:
        while True:
            frame += 1
            rssi = publish_telemetry()

            if frame % 5 == 0:
                publish_health()

            # Weak/Critical信号时不发YOLO（模拟天空端策略）
            if frame % 3 == 0 and rssi > -95:
                publish_yolo()

            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nStopped")


if __name__ == "__main__":
    main()
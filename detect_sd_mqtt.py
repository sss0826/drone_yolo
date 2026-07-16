# detect_sd_mqtt.py
# 从视频源读取 → YOLO检测 → MQTT发布（单条/含GPS）

import cv2
import json
import time
import sys
from datetime import datetime
from pathlib import Path
from ultralytics import YOLO

# 导入 yolo_publisher
try:
    from yolo_publisher import publish_detection, init_mqtt

    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    print("❌ 找不到 yolo_publisher.py")
    sys.exit(1)

# 新增：订阅 telemetry 获取 GPS
import paho.mqtt.client as mqtt

latest_gps = {"lat": 0.0, "lon": 0.0}


def on_telemetry_msg(client, userdata, msg):
    global latest_gps
    try:
        data = json.loads(msg.payload.decode())
        latest_gps["lat"] = data.get("lat", 0.0)
        latest_gps["lon"] = data.get("lon", 0.0)
    except Exception:
        pass


# ==================== 配置 ====================
SOURCE = 0  # 0=摄像头，比赛时改SD卡视频路径
CONF = 0.5  # 置信度阈值
PUBLISH_INTERVAL = 1.0  # 发布间隔（秒）
SAVE_VIDEO = False
OUTPUT_VIDEO_PATH = "output_detection.mp4"


# =============================================


def main():
    print("=" * 50)
    print("YOLO 检测 + MQTT 发布（debris_event 单条格式）")
    print("=" * 50)

    # 初始化 MQTT（发布）
    print("[0/3] 连接 MQTT...")
    if not init_mqtt():
        print("❌ MQTT 连接失败，请确认 mosquitto 已运行")
        return
    print("[0/3] MQTT 已连接")

    # 新增：启动 telemetry 订阅（获取GPS）
    print("[0/3] 订阅 drone/telemetry 获取GPS...")
    tele_client = mqtt.Client()
    tele_client.on_message = on_telemetry_msg
    tele_client.connect("127.0.0.1", 1883, 60)
    tele_client.subscribe("drone/telemetry")
    tele_client.loop_start()
    print("[0/3] GPS 订阅已启动")

    # 检查视频源
    if SOURCE != 0 and not Path(SOURCE).exists():
        print(f"❌ 找不到视频: {SOURCE}")
        return

    # 加载模型
    print("[1/3] 加载 best.pt...")
    model = YOLO("best.pt")
    print("[1/3] 完成")

    # 打开视频
    print(f"[2/3] 打开视频源: {SOURCE}")
    cap = cv2.VideoCapture(SOURCE)
    if not cap.isOpened():
        print("❌ 无法打开视频源")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"视频: {total}帧, {fps:.1f}fps")

    # 保存视频
    writer = None
    if SAVE_VIDEO:
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        writer = cv2.VideoWriter(OUTPUT_VIDEO_PATH,
                                 cv2.VideoWriter_fourcc(*'mp4v'),
                                 fps, (w, h))

    frame_id = 0
    last_publish = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("✅ 视频播放完毕")
                break

            frame_id += 1

            # YOLO推理（增加 iou=0.3 减少密集漏检）
            results = model.predict(frame, imgsz=640, verbose=False,
                                    device="cpu", iou=0.3)[0]

            # 解析结果
            objs = []
            if results.boxes is not None:
                boxes = results.boxes.xywh.cpu().numpy()
                confs = results.boxes.conf.cpu().numpy()
                clss = results.boxes.cls.cpu().numpy().astype(int)
                names = results.names

                for i in range(len(boxes)):
                    if confs[i] < CONF:
                        continue
                    objs.append({
                        "class": names[clss[i]],
                        "conf": round(float(confs[i]), 2)
                    })

            # 定时发布：每个物体单独发一条消息
            now = time.time()
            if now - last_publish >= PUBLISH_INTERVAL and objs:
                ts = datetime.now().isoformat()
                for obj in objs:
                    payload = {
                        "type": "debris_detection",
                        "class": obj["class"],
                        "conf": obj["conf"],
                        "lat": latest_gps["lat"],
                        "lon": latest_gps["lon"],
                        "timestamp": ts
                    }
                    publish_detection(payload)

                print(f"[YOLO] Published {len(objs)} debris_event(s): "
                      f"{[o['class'] for o in objs]} | "
                      f"GPS=({latest_gps['lat']:.4f}, {latest_gps['lon']:.4f})")

                last_publish = now

            # 保存画框视频
            if SAVE_VIDEO and writer:
                writer.write(results.plot())

            # 控制播放速度
            time.sleep(1 / fps if fps > 0 else 0.033)

    except KeyboardInterrupt:
        print("\n⏹️ 用户停止")

    cap.release()
    if writer: writer.release()
    tele_client.loop_stop()
    tele_client.disconnect()
    print("系统已关闭")


if __name__ == "__main__":
    main()
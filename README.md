# 无人机水面垃圾检测 - YOLO 模块

## 文件说明
| 文件 | 功能 |
|------|------|
| detect_sd_mqtt.py | YOLO检测 + MQTT发布（debris_event） |
| yolo_publisher.py | MQTT发布器，主题：drone/debris_event |
| serial_bridge.py | 地面端串口桥接（ESP32 <-> Mosquitto） |
| mock_esp32.py | Mock天空端（模拟遥测+GPS） |
| 	est_yolo.py | 批量测试脚本 |
| est.pt | YOLOv8n 自定义模型（5类垃圾） |

## 快速启动
`powershell
# 1. 启动 MQTT Broker
mosquitto -v

# 2. 启动 Mock GPS（如无真实ESP32）
python mock_esp32.py

# 3. 启动 YOLO 检测
python detect_sd_mqtt.py
``n
## 后端对接
- 订阅主题：drone/debris_event`n- 消息格式：单条 JSON，含 class, conf, lat, lon, 	imestamp`n- 详见 YOLO_API.md`n
## 模型性能
- mAP@50: 0.860
- mAP@50-95: 0.504
- 类别：bottle, can, carton, paper, plastic

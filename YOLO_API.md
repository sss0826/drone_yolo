# YOLO 检测模块接口文档

> **版本**：v1.0  
> **日期**：2026-07-16  
> **负责**：YOLO 模块（目标检测 + MQTT 发布）  
> **对接**：后端 main.py（订阅 + 前端展示）

---

## 1. 模块概述

本模块负责从视频源（摄像头 / SD 卡视频 / 实时视频流）读取画面，使用 YOLOv8n 自定义模型（`best.pt`，5 类水面垃圾）进行目标检测，并将检测结果通过 MQTT 发布到后端。

---

## 2. 输入

### 2.1 模型文件
- **文件**：`best.pt`
- **位置**：项目根目录（与 `detect_sd_mqtt.py` 同级）
- **架构**：YOLOv8n（3.0M 参数）
- **类别**：`bottle`, `can`, `carton`, `paper`, `plastic`

### 2.2 视频源
- **开发/测试**：本地摄像头（`SOURCE = 0`）
- **比赛/生产**：SD 卡视频文件路径，或 ESP32 推流地址（待联调确认）
- **分辨率**：自动缩放至 640×640（YOLO 输入尺寸）

### 2.3 GPS 数据来源
- 本模块**不直接获取 GPS**，而是通过**订阅 MQTT 主题 `drone/telemetry`** 获取实时经纬度。
- 要求天空端 ESP32 或 Mock 数据持续发布 `drone/telemetry` 消息。

---

## 3. 输出（MQTT 发布）

### 3.1 主题

```
drone/debris_event
```

> ⚠️ **注意**：旧版本使用 `drone/yolo_detect`，已废弃。后端请订阅 `drone/debris_event`。

### 3.2 消息格式（单条）

**每个漂浮物单独发送一条消息**，不批量发送。

```json
{
  "type": "debris_detection",
  "class": "plastic",
  "conf": 0.87,
  "lat": 28.015623,
  "lon": 112.948312,
  "timestamp": "2026-07-16T20:38:15.123456"
}
```

### 3.3 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | 固定为 `"debris_detection"` |
| `class` | string | ✅ | 垃圾类别：`bottle` / `can` / `carton` / `paper` / `plastic` |
| `conf` | float | ✅ | 置信度，范围 0.0 ~ 1.0 |
| `lat` | float | ✅ | 纬度（来自 `drone/telemetry` 的 GPS） |
| `lon` | float | ✅ | 经度（来自 `drone/telemetry` 的 GPS） |
| `timestamp` | string | ✅ | ISO 8601 格式，UTC+8 |

### 3.4 发布频率

- **间隔**：`PUBLISH_INTERVAL = 1.0` 秒（每秒最多发布一次）
- **策略**：如果 1 秒内检测到多个物体，**每个物体各发一条**；如果 1 秒内无物体，则不发布。

---

## 4. 关键配置参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `MODEL_PATH` | `"best.pt"` | 模型文件路径 |
| `SOURCE` | `0` 或 `"video.mp4"` | 视频源（比赛时改路径） |
| `CONF` | `0.5` | 置信度阈值（低于此值过滤） |
| `iou` | `0.3` | NMS IoU 阈值（密集场景保留更多框） |
| `PUBLISH_INTERVAL` | `1.0` | 发布间隔（秒） |
| `MQTT_TOPIC` | `drone/debris_event` | 发布主题（在 `yolo_publisher.py` 中定义） |
| `MQTT_BROKER` | `127.0.0.1:1883` | 本地 Mosquitto（开发环境） |

---

## 5. 启动方式

### 5.1 前置依赖

确保以下服务已启动：

```powershell
# 1. 启动 MQTT Broker
& "D:\比赛资料\无人机\Mosquitto\mosquitto.exe" -v

# 2. 启动 serial_bridge（硬件联调时）
python serial_bridge.py COM6 115200

# 3. 启动 Mock GPS（如无真实 ESP32）
python mock_esp32.py
```

### 5.2 启动 YOLO 检测

```powershell
cd "D:\比赛资料\无人机\drone"
python detect_sd_mqtt.py
```

正常输出示例：
```
[YOLO] Published 2 debris_event(s): ['plastic', 'bottle'] | GPS=(28.0156, 112.9483)
```

---

## 6. 依赖列表

```
ultralytics>=8.0.0
opencv-python>=4.8.0
paho-mqtt>=1.6.0
numpy>=1.24.0
```

安装命令：
```powershell
pip install ultralytics opencv-python paho-mqtt numpy
```

---

## 7. 后端对接检查清单

后端 `main.py` 开发者请确认：

- [ ] 订阅主题：`drone/debris_event`
- [ ] 解析字段：`class`, `conf`, `lat`, `lon`, `timestamp`
- [ ] 不再使用旧主题 `drone/yolo_detect`
- [ ] 不再期望 `objects` 数组（已改为单条消息）
- [ ] 不再使用 `x, y, w, h`（已改为 `lat, lon`）
- [ ] 地图标点使用 `lat` + `lon`

---

## 8. 常见问题（FAQ）

**Q：为什么检测不到人？**  
A：`best.pt` 是自定义模型，只认识 5 类垃圾，不认识人、车、动物等 COCO 类别。

**Q：室内测试误报很多？**  
A：正常。模型在**水面漂浮场景**训练，室内环境差异大。请用**水面垃圾图片**或**真实飞行场景**测试。

**Q：GPS 为 0,0？**  
A：说明 `drone/telemetry` 没有数据。请确认 Mock ESP32 或真实天空端已发布遥测数据。

**Q：消息是单条还是批量？**  
A：单条。每个漂浮物一条消息，后端无需遍历 `objects` 数组。

---

*文档版本：v1.0*  
*最后更新：2026-07-16*

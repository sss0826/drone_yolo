# test_yolo.py
# 作用：测试YOLO环境是否正常，用官方模型检测一张网络图片

from ultralytics import YOLO
import cv2

print("正在加载模型...")
model = YOLO("yolov8n.pt")  # 第一次会自动下载（约6MB）

print("正在检测...")
results = model.predict("https://ultralytics.com/images/bus.jpg", save=False)

# 显示结果
img = results[0].plot()
cv2.imshow("YOLO检测结果 - 按任意键关闭", img)
cv2.waitKey(0)
cv2.destroyAllWindows()
print("成功！环境没问题。")
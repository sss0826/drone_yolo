from ultralytics import YOLO
import cv2
import glob
import os

model = YOLO("best.pt")

test_dir = "test_images"
os.makedirs("test_results", exist_ok=True)

print("=" * 50)
print("YOLO 真实场景测试")
print("=" * 50)

results_log = []

for img_path in glob.glob(f"{test_dir}/*.jpg") + glob.glob(f"{test_dir}/*.png"):
    print(f"\n测试: {img_path}")

    results = model(img_path, conf=0.5, verbose=False)[0]

    objs = []
    for box in results.boxes:
        cls = results.names[int(box.cls)]
        conf = float(box.conf)
        objs.append(f"{cls}({conf:.2f})")

    print(f"  检测到 {len(objs)} 个: {objs}")
    results_log.append(f"{os.path.basename(img_path)}: {len(objs)} objects - {objs}")

    # 保存带框的结果图
    out = img_path.replace("test_images", "test_results")
    cv2.imwrite(out, results.plot())

print(f"\n{'=' * 50}")
print("测试完成，结果保存在 test_results/ 文件夹")
print("总结:")
for line in results_log:
    print(f"  {line}")
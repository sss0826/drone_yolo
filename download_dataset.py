from roboflow import Roboflow

rf = Roboflow(api_key="public")
project = rf.workspace("roboflow-jvuqo").project("floating-waste")
dataset = project.version(4).download("yolov8")

print(f"数据集下载完成！位置: {dataset.location}")
print("文件夹结构：")
print("  Floating-Waste-4/")
print("    ├── train/images/  train/labels/")
print("    ├── valid/images/  valid/labels/")
print("    ├── test/images/   test/labels/")
print("    └── data.yaml")
import os, sys, glob
BASE = os.path.dirname(os.path.abspath(__file__))
from ultralytics import YOLO

p = os.path.join(BASE, "liverV1.pt")
m = YOLO(p)
print("names:", m.names)
try:
    print("task:", m.task)
except Exception as e:
    print("task err:", e)

# quick real prediction on the first image found in the project
imgs = []
for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp"):
    imgs += glob.glob(os.path.join(BASE, ext))
    imgs += glob.glob(os.path.join(BASE, "assets", ext))
if imgs:
    print("test image:", imgs[0])
    r = m.predict(imgs[0], imgsz=640, conf=0.25, verbose=False)[0]
    if r.boxes is not None and len(r.boxes):
        for b in r.boxes:
            print("det:", r.names[int(b.cls[0].item())], round(float(b.conf[0].item()), 4))
    else:
        print("no detections")
else:
    print("no test image in project")

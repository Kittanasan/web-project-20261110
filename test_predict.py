import os, sys, io, json
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

# สร้างภาพทดสอบสังเคราะห์ (ไม่มีภาพตับในเครื่อง) เพื่อพิสูจน์ว่า API คืน verdict ได้จริง
from PIL import Image
import numpy as np

# 1) ตรวจว่า app.py import และให้ผลระดับได้
import app as A

spec = A.MODEL_SPEC if hasattr(A, "MODEL_SPEC") else None
print("spec:", spec)

rng = np.random.default_rng(0)
arr = (rng.random((480, 640, 3)) * 255).astype("uint8")
buf = io.BytesIO()
Image.fromarray(arr).save(buf, format="JPEG")
res = A.predict_image(buf.getvalue())
out = {k: v for k, v in res.items() if k != "image"}
print(json.dumps(out, ensure_ascii=False, indent=2))
print("has image:", "image" in res and len(res["image"]) > 100)

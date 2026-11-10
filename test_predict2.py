# ทดสอบ /predict ด้วยภาพที่มีลวดลาย (ต้องได้ผล Hight/Medium/Low จริง)
import json, io, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from PIL import Image, ImageDraw

img = Image.new("RGB", (640, 480), (95, 105, 85))
d = ImageDraw.Draw(img)
# ลายจุดคล้ายเม็ดไขมัน
for i in range(140):
    x = (i * 61) % 600 + 20
    y = (i * 97) % 430 + 25
    d.ellipse([x, y, x + 14 + (i % 5) * 3, y + 12 + (i % 4) * 3], fill=(205, 190, 150))

buf = io.BytesIO()
img.save(buf, format="JPEG", quality=92)

req = urllib.request.Request("http://127.0.0.1:8000/predict", data=buf.getvalue(),
                             headers={"Content-Type": "image/jpeg"})
with urllib.request.urlopen(req, timeout=180) as r:
    out = json.loads(r.read().decode("utf-8"))

print("ok:", out.get("ok"))
print("verdict:", out.get("verdict"), "|", out.get("verdict_th"), "|", out.get("verdict_level_th"))
print("confidence_pct:", out.get("confidence_pct"))
print("level_pct:", out.get("level_pct"))
print("detections:", len(out.get("detections") or []))
print("image bytes:", len(out.get("image") or ""))

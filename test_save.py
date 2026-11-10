# ทดสอบ /predict + /save + /exports ของเซิร์ฟเวอร์ที่กำลังรันอยู่ (127.0.0.1:8000)
import json, urllib.request, urllib.error, io, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8000"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=20) as r:
        return r.status, r.read()


def post(path, body, ctype):
    data = body if isinstance(body, (bytes, bytearray)) else body.encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


# 1) health
st, body = get("/health")
print("[health]", st, body.decode("utf-8")[:200])

# 2) assets
st, body = get("/assets/logo-dof.svg")
print("[logo]", st, len(body), "bytes", body[:60])

# 3) index
st, body = get("/")
html = body.decode("utf-8")
print("[index]", st, len(html), "chars | has logo:", "assets/logo-dof.svg" in html,
      "| has save:", "saveBtn" in html, "| has override:", "finalLevel" in html,
      "| has rubric:", "ตรวจพบเม็ดไขมันมาก" in html)

# 4) predict with a generated image
from PIL import Image, ImageDraw
img = Image.new("RGB", (640, 480), (120, 40, 35))
d = ImageDraw.Draw(img)
d.ellipse([80, 60, 560, 420], fill=(150, 52, 44))
for i in range(70):
    d.ellipse([20 + (i * 47) % 600, 20 + (i * 61) % 440, 45 + (i * 47) % 600, 45 + (i * 61) % 440], fill=(220, 180, 90))
buf = io.BytesIO()
img.save(buf, format="JPEG")
st, body = post("/predict", buf.getvalue(), "image/jpeg")
data = json.loads(body.decode("utf-8"))
print("[predict]", st, "verdict=", data.get("verdict"), "verdict_th=", data.get("verdict_th"),
      "conf=", data.get("confidence_pct"), "dets=", len(data.get("detections") or []))

# 5) save
payload = {
    "image": data.get("image"),
    "title": "ทดสอบระบบ_บันทึกรายงาน",
    "sampleId": "CC-AQ-2569-TEST",
    "inspector": "ทดสอบอัตโนมัติ",
    "note": "ภาพทดสอบจากสคริปต์",
    "modelResult": data.get("verdict"),
    "modelConfidence": data.get("confidence_pct"),
    "finalResult": "Medium",
    "finalConfidence": None,
    "edited": data.get("verdict") != "Medium",
    "detections": data.get("detections"),
}
st, body = post("/save", json.dumps(payload), "application/json")
print("[save]", st, body.decode("utf-8")[:400])
saved = json.loads(body.decode("utf-8"))

# 6) list exports
st, body = get("/exports")
lst = json.loads(body.decode("utf-8"))
print("[exports]", st, "count=", len(lst.get("exports") or []))
print("  first:", (lst.get("exports") or [{}])[0])

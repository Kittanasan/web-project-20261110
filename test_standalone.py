# ทดสอบหน้า HTML เดี่ยว + endpoint ใหม่ของ app.py (ไฟล์ชั่วคราวสำหรับตรวจสอบ)
import io, json, sys, base64, urllib.request, urllib.error

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8000"


def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=30) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers.get("Content-Type", "")


def post_json(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


# 1) หน้า HTML เดี่ยวต้องเปิดได้ผ่านเซิร์ฟเวอร์
st, body, ctype = get("/standalone")
html = body.decode("utf-8", "replace")
print("[standalone] status=%s ctype=%s chars=%d" % (st, ctype, len(html)))
checks = {
    "has agency": "ศูนย์วิจัยและพัฒนาการเพาะเลี้ยงสัตว์น้ำชายฝั่งฉะเชิงเทรา" in html,
    "has logo svg": 'aria-label="ตรากรมประมง"' in html,
    "has verdict div": 'id="verdictLine"' in html,
    "has override": 'id="finalLevel"' in html,
    "has save button": 'id="saveBtn"' in html,
    "has detect mode": "API_BASES" in html,
    "no external src": 'src="assets/' not in html,
}
print("[standalone] checks:", checks)
print("[standalone] all ok:", all(checks.values()))

# 2) /exports (รายการเดิมต้องยังใช้ได้)
st, body, _ = get("/exports")
lst = json.loads(body.decode("utf-8"))
print("[exports] status=%s count=%d" % (st, len(lst.get("exports") or [])))

# 3) เสิร์ฟภาพจาก exports/ ได้ (ใช้รายการแรก)
first = (lst.get("exports") or [{}])[0]
if first.get("image"):
    st, body, ctype = get("/exports/" + urllib.request.quote(first["image"]))
    print("[exports/image] status=%s ctype=%s bytes=%d" % (st, ctype, len(body)))

# 4) กัน path traversal
st, body, _ = get("/exports/..%2Fapp.py")
print("[traversal blocked] status=%s" % st)

# 5) /save จากหน้า HTML เดี่ยว (payload แบบที่หน้าเว็บส่ง)
from PIL import Image
buf = io.BytesIO()
Image.new("RGB", (240, 180), (30, 90, 140)).save(buf, format="JPEG")
b64 = base64.b64encode(buf.getvalue()).decode("ascii")
st, out = post_json("/save", {
    "image": "data:image/jpeg;base64," + b64,
    "title": "ทดสอบหน้า HTML เดี่ยว",
    "sampleId": "CC-AQ-TEST",
    "inspector": "ผู้ทดสอบระบบ",
    "note": "ทดสอบ endpoint",
    "modelResult": "Hight",
    "modelConfidence": 88.5,
    "finalResult": "Medium",
    "finalConfidence": None,
    "overrideNote": "ตรวจซ้ำด้วยกล้องจุลทรรศน์",
    "edited": True,
    "detections": [{"level": "Hight", "conf": 0.885, "box": [0, 0, 1, 1]}],
})
print("[save] status=%s ok=%s image=%s" % (st, out.get("ok"), out.get("image_file")))

# 6) ภาพที่บันทึกใหม่ต้องดาวน์โหลดผ่าน /exports/ ได้
if out.get("image_file"):
    st, body, ctype = get("/exports/" + urllib.request.quote(out["image_file"]))
    print("[saved image] status=%s ctype=%s bytes=%d" % (st, ctype, len(body)))

# 7) /health ยังปกติ
st, body, _ = get("/health")
h = json.loads(body.decode("utf-8"))
print("[health] status=%s model=%s classes=%s" % (st, h.get("model"), h.get("classes")))

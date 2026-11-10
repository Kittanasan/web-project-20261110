# -*- coding: utf-8 -*-
"""verify_engine_bridge.py - ทดสอบท่อส่งภาพ cloud_app.py --engine แบบไม่ต้องมี torch

ยิง HTTP จริงไปที่พอร์ตของท่อ:
  GET  /health   ต้องตอบ ok + บอกว่าพร้อมประเมินหรือไม่
  GET  /         ต้องไม่ 403 (เป็นหน้าคำอธิบาย)
  GET  /liverV1.pt  ต้องถูกปฏิเสธ 403 (ห้ามเปิดไฟล์โปรเจกต์ออกอินเทอร์เน็ต)
  POST /predict  ต้องตอบ JSON (ok=false พร้อมเหตุผล ถ้าไม่มี ultralytics)
ใช้: python verify_engine_bridge.py [พอร์ต]
"""
import json
import sys
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9000
BASE = "http://127.0.0.1:%d" % PORT
ok_all = True


def check(label, cond, extra=""):
    global ok_all
    if not cond:
        ok_all = False
    print(("  OK   " if cond else "  FAIL ") + label + (("  " + str(extra)) if extra else ""))


def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=15) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def post(path, body, ctype="application/octet-stream"):
    req = urllib.request.Request(BASE + path, data=body, headers={"Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


st, body = get("/health")
h = json.loads(body.decode("utf-8"))
check("GET /health = 200", st == 200, st)
check("health.mode = engine", h.get("mode") == "engine", h.get("mode"))
check("health.model_file = True", bool(h.get("model_file")), h.get("model_file"))
print("     engine_ready=%s lib_ok=%s" % (h.get("engine_ready"), h.get("lib_ok")))

st, body = get("/")
check("GET / = 200 (หน้าคำอธิบาย)", st == 200, st)

st, body = get("/liverV1.pt")
check("GET /liverV1.pt ถูกปฏิเสธ", st == 403, st)

st, body = get("/%2e%2e/app.py")
check("GET path traversal ถูกปฏิเสธ", st in (403, 404), st)

st, body = post("/predict", b"\xff\xd8\xff\xe0fakejpeg")
d = json.loads(body.decode("utf-8"))
check("POST /predict ตอบ JSON", isinstance(d, dict), str(d)[:120])
print("     predict ok=%s error=%s" % (d.get("ok"), (d.get("error") or "")[:90]))

st, body = post("/save", json.dumps({"name": "x"}).encode("utf-8"), "application/json")
check("POST /save เข้าถึงได้", st in (200, 500), st)

print("\nผลรวม:", "ผ่านทั้งหมด" if ok_all else "มีข้อที่ไม่ผ่าน")
sys.exit(0 if ok_all else 1)

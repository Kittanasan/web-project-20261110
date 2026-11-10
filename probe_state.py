# -*- coding: utf-8 -*-
"""ตรวจสถานะจริงของระบบ ณ ตอนนี้ (ใช้ก่อนเริ่มงาน deploy/ฐานข้อมูล)

- มีเซิร์ฟเวอร์ตอบพอร์ต 8000-8020 หรือไม่ และ /health ตอบอะไร
- ไฟล์สำคัญในโฟลเดอร์มีครบไหม (Index.html, app.py, liverV1.pt, data/, assets/)
- มีป้ายบอกเวอร์ชัน BUILD_TAG ใน app.py หรือยัง
"""
import json
import os
import socket
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = os.path.dirname(os.path.abspath(__file__))


def get(port, path, timeout=4):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path), timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return None, str(e).encode("utf-8", "replace")


def busy(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


print("=== 1) เซิร์ฟเวอร์ที่ตอบอยู่ ===")
found = []
for p in range(8000, 8021):
    if not busy(p):
        continue
    st, body = get(p, "/health")
    info = {}
    try:
        info = json.loads(body.decode("utf-8"))
    except Exception:
        info = {}
    keys = ("ok", "build", "model", "model_file", "model_loaded", "lib_ok", "port", "store", "store_note")
    summary = {k: info.get(k) for k in keys if k in info}
    print("port %d status=%s keys=%s" % (p, st, summary or "ไม่มี /health"))
    found.append(p)
if not found:
    print("ไม่มีเซิร์ฟเวอร์ตอบที่พอร์ต 8000-8020")

print("\n=== 2) ไฟล์สำคัญ ===")
for rel in ("app.py", "Index.html", "live.js", "liverV1.pt", "assets/logo-dof.svg",
            "data", "data/db.json", "templates/index.html", "liver-eval-standalone.html"):
    full = os.path.join(BASE, *rel.split("/"))
    if os.path.isdir(full):
        n = len([x for x in os.listdir(full)])
        print("[dir ] %-32s มี %d รายการ" % (rel, n))
    elif os.path.isfile(full):
        print("[file] %-32s %.1f KB" % (rel, os.path.getsize(full) / 1024.0))
    else:
        print("[----] %-32s ไม่มี" % rel)

print("\n=== 3) ชุดข้อมูลที่บันทึกไว้ (exports) ===")
exp = os.path.join(BASE, "exports")
if os.path.isdir(exp):
    js = [x for x in os.listdir(exp) if x.lower().endswith(".json")]
    im = [x for x in os.listdir(exp) if x.lower().endswith((".jpg", ".png"))]
    print("รายงาน .json = %d ไฟล์ | ภาพ = %d ไฟล์" % (len(js), len(im)))
else:
    print("ไม่มีโฟลเดอร์ exports")

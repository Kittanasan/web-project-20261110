# -*- coding: utf-8 -*-
"""verify_cloud_final.py - ตรวจครั้งสุดท้ายว่าโฟลเดอร์พร้อมขึ้นเว็บจริง

ตรวจกับเซิร์ฟเวอร์ที่กำลังรันอยู่ (ค่าเริ่มต้น 8080 = cloud_app.py, 8000 = app.py)
  1) ฐานข้อมูลจริง data/db.sqlite + ข้อมูลตั้งต้นที่พร้อมใช้
  2) หน้าเว็บฝั่งคลาวด์มีตัวอ่าน LIVER_ENGINE (ให้เว็บชี้ไปเครื่องประมวลผลอื่นได้)
  3) ฝั่งเว็บบันทึก/อ่าน/ลบผลตรวจได้ (ฐานข้อมูลกลาง)
  4) เครื่องประมวลผลยังวิเคราะห์ภาพได้
ใช้:  python verify_cloud_final.py [พอร์ตเว็บ] [พอร์ตเครื่องประมวลผล]
"""
import io
import json
import os
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = os.path.dirname(os.path.abspath(__file__))
CLOUD = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
ENGINE = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
ok_all = True


def check(name, cond, detail=""):
    global ok_all
    print(("  OK   " if cond else "  FAIL ") + name + ((" | " + str(detail)) if detail and not cond else ""))
    if not cond:
        ok_all = False


def req(url, body=None, ctype="application/json"):
    data = None
    if body is not None:
        data = body if isinstance(body, (bytes, bytearray)) else json.dumps(body).encode("utf-8")
    r = urllib.request.Request(url, data=data, method="GET" if data is None else "POST")
    if data is not None:
        r.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(r, timeout=180) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


print("=== 1) ฐานข้อมูลในโฟลเดอร์ ===")
dbp = os.path.join(BASE, "data", "db.sqlite")
check("มีไฟล์ data/db.sqlite", os.path.isfile(dbp),
      "%.1f KB" % (os.path.getsize(dbp) / 1024.0 if os.path.isfile(dbp) else 0))
seed = os.path.join(BASE, "data", "seed_report.json")
check("มี data/seed_report.json (ข้อมูลตั้งต้นพร้อมใช้)", os.path.isfile(seed))
if os.path.isfile(seed):
    with io.open(seed, encoding="utf-8") as f:
        d = json.load(f)
    check("seed มีผลตรวจตั้งต้น", len(d.get("samples") or []) >= 1,
          "%d แถว" % len(d.get("samples") or []))
    check("seed มีทะเบียนฟาร์ม", len(d.get("farmers") or []) >= 1)
for rel in ("cloud_app.py", "requirements.txt", "Procfile", "runtime.txt", "README-ขึ้นเว็บ.txt",
            "backup_db.py", "prepare_cloud_folder.py"):
    check("มีไฟล์ " + rel, os.path.isfile(os.path.join(BASE, rel)))

print("\n=== 2) หน้าเว็บฝั่งเว็บไซต์ (%d) ===" % CLOUD)
st, body = req("http://127.0.0.1:%d/" % CLOUD)
page = body.decode("utf-8", "replace")
check("หน้าเว็บ 200", st == 200, st)
check("หน้าเว็บอ่าน window.LIVER_ENGINE ได้", "window.LIVER_ENGINE" in page)
check("มีตารางบันทึกผล", 'id="recordBody"' in page)
check("มีปุ่มบันทึกผลการตรวจ", 'id="saveRecordBtn"' in page)
st, hb = req("http://127.0.0.1:%d/health" % CLOUD)
h = json.loads(hb.decode("utf-8"))
check("/health ระบุฐานข้อมูลใช้งานได้", h.get("db") is True, h.get("store_note"))
check("/health มีจำนวนรายการในฐานข้อมูล", (h.get("db_records") or 0) >= 1, h.get("db_records"))

print("\n=== 3) บันทึก/อ่าน/ลบ ผ่านฐานข้อมูลกลาง ===")
st, ab = req("http://127.0.0.1:%d/records" % CLOUD,
             {"label": "FINAL-CHECK", "farm": "ฟาร์มตรวจครั้งสุดท้าย", "inspector": "ผู้ตรวจทดสอบ",
              "finalResult": "Low", "finalConfidence": 71.5, "client": "verify"})
add = json.loads(ab.decode("utf-8"))
check("เพิ่มผลตรวจได้", st == 200 and add.get("ok") is True, add)
rid = (add.get("record") or {}).get("id")
st, lb = req("http://127.0.0.1:%d/records?q=FINAL-CHECK" % CLOUD)
rows = json.loads(lb.decode("utf-8")).get("records") or []
check("อ่านกลับมาเจอในตาราง", any(r.get("id") == rid for r in rows), len(rows))
st, _ = req("http://127.0.0.1:%d/records-delete" % CLOUD, {"id": rid})
check("ลบรายการทดสอบได้", st == 200, st)

print("\n=== 4) เครื่องประมวลผล (%d) ===" % ENGINE)
try:
    st, eb = req("http://127.0.0.1:%d/health" % ENGINE)
    eh = json.loads(eb.decode("utf-8"))
    check("เครื่องประมวลผลตอบ /health", st == 200, st)
    check("มี torch/ultralytics", eh.get("lib_ok") is True, eh.get("lib_note"))
    check("มีไฟล์ liverV1.pt", eh.get("model_file") is True)
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (320, 240), (155, 100, 65)).save(b, "JPEG")
    st, pb = req("http://127.0.0.1:%d/predict" % ENGINE, b.getvalue(), "image/jpeg")
    pj = json.loads(pb.decode("utf-8"))
    check("วิเคราะห์ภาพได้", st == 200 and "detections" in pj, str(pj.get("error"))[:120])
except Exception as e:
    check("เชื่อมเครื่องประมวลผลได้", False, e)

print("\n[result]", "PASS" if ok_all else "FAIL")
sys.exit(0 if ok_all else 1)

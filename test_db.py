# -*- coding: utf-8 -*-
"""ทดสอบฐานข้อมูลกลางผ่าน API จริง (health / records / save / update / farmers / delete)"""
import io
import json
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE_URL = "http://127.0.0.1:8000"
ok_all = True


def req(path, body=None, ctype="application/json"):
    data = None
    if body is not None:
        data = body if isinstance(body, (bytes, bytearray)) else json.dumps(body).encode("utf-8")
    r = urllib.request.Request(BASE_URL + path, data=data,
                               headers={"Content-Type": ctype} if data else {})
    try:
        with urllib.request.urlopen(r, timeout=180) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {"ok": False}


def check(name, cond, extra=""):
    global ok_all
    print(("  OK   " if cond else "  FAIL ") + name + (" | " + str(extra) if extra else ""))
    if not cond:
        ok_all = False


print("=== 1) /health (ต้องมี db:true และ build) ===")
st, h = req("/health")
check("health 200 + db=true", st == 200 and h.get("db") is True, "build=%s records=%s" %
      (h.get("build"), h.get("db_records")))
check("ฐานข้อมูลมีรายการนำเข้าจาก exports", (h.get("db_records") or 0) >= 1, h.get("db_path"))

print("\n=== 2) /records (อ่านตารางจากฐานข้อมูล) ===")
st, r = req("/records?limit=500")
check("records 200 + มีข้อมูล", st == 200 and r.get("ok") and r.get("count", 0) >= 1,
      "count=%s" % r.get("count"))

print("\n=== 3) บันทึกผลใหม่ผ่าน /save (ต้องลงฐานข้อมูลด้วย) ===")
b = io.BytesIO()
from PIL import Image
Image.new("RGB", (320, 240), (150, 90, 60)).save(b, format="JPEG")
st, p = req("/save", {
    "image": "data:image/jpeg;base64," + __import__("base64").b64encode(b.getvalue()).decode(),
    "title": "ทดสอบฐานข้อมูล", "sampleId": "TEST-DB-001", "sampleName": "TEST-DB-001",
    "farm": "ฟาร์มตัวอย่างทดสอบ (ศูนย์วิจัยฯ)", "inspector": "ผู้ทดสอบระบบ",
    "modelResult": "Medium", "modelConfidence": 88.5, "finalResult": "Medium",
    "finalConfidence": 88.5, "edited": False, "overrideNote": "", "detections": 1,
})
check("/save 200 + ได้ db_id", st == 200 and p.get("ok") and p.get("db_id"), p.get("db_warning") or p.get("label"))
new_id = p.get("db_id")

print("\n=== 4) แก้ผลการประเมิน (เจ้าหน้าที่แก้ผล) ===")
if new_id:
    st, u = req("/records-update", {"id": new_id, "patch": {
        "final_result": "Hight", "override_note": "ตรวจซ้ำแล้วพบมาก", "edited": True}})
    check("แก้ผลได้", st == 200 and u.get("record", {}).get("final_result") == "Hight",
          u.get("record", {}).get("override_note"))

print("\n=== 5) ทะเบียนฟาร์ม ===")
st, f = req("/farmers")
check("farmers 200 + มีฟาร์มตั้งต้น", st == 200 and f.get("count", 0) >= 1, f.get("count"))
st, f2 = req("/farmers", {"name": "ฟาร์มทดสอบ " + str(p.get("no")), "owner_name": "ทดสอบ",
                          "district": "บางปะกง", "province": "ฉะเชิงเทรา", "species": "ปลากะพงขาว"})
check("เพิ่มฟาร์มได้", st == 200 and f2.get("farmer", {}).get("id"), f2.get("error"))
fid = f2.get("farmer", {}).get("id")
if fid:
    st, f3 = req("/farmers-delete", {"id": fid})
    check("ลบฟาร์มได้", st == 200 and f3.get("removed") == 1)

print("\n=== 6) ลบรายการทดสอบ ===")
if new_id:
    st, d = req("/records-delete", {"id": new_id, "report_file": p.get("report_file")})
    check("ลบรายการได้", st == 200 and d.get("removed") == 1, d.get("error"))

print("\n=== 7) ไฟล์ฐานข้อมูลบนดิสก์ ===")
import os
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "db.sqlite")
print("  path:", db_path, "exists:", os.path.isfile(db_path),
      "size: %.1f KB" % (os.path.getsize(db_path) / 1024.0 if os.path.isfile(db_path) else 0))

print("\n[result]", "PASS" if ok_all else "FAIL")
sys.exit(0 if ok_all else 1)

# -*- coding: utf-8 -*-
"""test_cloud_api.py - ทดสอบ 'ฝั่งเว็บไซต์' (cloud_app.py) กับเซิร์ฟเวอร์จริง

ตรวจว่าโฟลเดอร์นี้พร้อมขึ้นเว็บจริงหรือยัง:
  1) ไฟล์ที่เว็บโฮสต์ต้องใช้มีครบ (cloud_app.py, requirements.txt, Procfile, data/db.sqlite)
  2) ฐานข้อมูลกลางใช้งานได้: /records /stats /farmers
  3) บันทึกผลใหม่ผ่าน /records (ไม่ต้องมีแบบจำลอง) + แก้ไข + ลบ
  4) /save บันทึกภาพ+รายงานลง exports/ และลงฐานข้อมูล
  5) /predict: ถ้าตั้ง LIVER_ENGINE ไว้ ต้องได้ผลจากเครื่องประมวลผลจริง

ใช้:  python test_cloud_api.py [พอร์ตคลาวด์] [พอร์ตเครื่องประมวลผล]
"""
import io
import json
import os
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CLOUD = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
ENGINE = int(sys.argv[2]) if len(sys.argv) > 2 else 0
CB = "http://127.0.0.1:%d" % CLOUD
EB = "http://127.0.0.1:%d" % ENGINE if ENGINE else ""
BASE = os.path.dirname(os.path.abspath(__file__))
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
        with urllib.request.urlopen(r, timeout=120) as resp:
            return resp.status, resp.read(), resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), ""


def get_json(path):
    st, body, _ = req(CB + path)
    try:
        return st, json.loads(body.decode("utf-8"))
    except Exception:
        return st, {}


print("=" * 68)
print(" ทดสอบฝั่งเว็บไซต์ (cloud_app.py) ที่ %s" % CB)
print("=" * 68)

# 1) ไฟล์ที่ต้องมีเมื่ออัปขึ้นเว็บ
print("\n=== 1) ไฟล์สำหรับขึ้นเว็บ ===")
for rel, label in [("cloud_app.py", "ตัวรันฝั่งเว็บ"), ("requirements.txt", "รายการไลบรารี"),
                   ("Procfile", "คำสั่งเริ่มระบบ"), ("Index.html", "หน้าเว็บ"),
                   ("live.js", "ตัวเชื่อมต่อเครื่องประมวลผล"), ("db.py", "โค้ดฐานข้อมูล"),
                   ("app.py", "ตัวประเมินภาพ (ใช้ร่วม)"),
                   ("data/db.sqlite", "ไฟล์ฐานข้อมูลจริง")]:
    p = os.path.join(BASE, *rel.split("/"))
    size = os.path.getsize(p) if os.path.isfile(p) else 0
    check("%s (%s)" % (rel, label), size > 0, "%d ไบต์" % size)

# 2) หน้าเว็บ + health
print("\n=== 2) หน้าเว็บและสถานะ ===")
st, body, ctype = req(CB + "/")
page = body.decode("utf-8", "replace")
check("/ 200 html", st == 200 and "text/html" in ctype, "%s %s" % (st, ctype))
check("หน้าเว็บเป็นตัวจริง", "ศูนย์วิจัยและพัฒนาการเพาะเลี้ยงสัตว์น้ำชายฝั่งฉะเชิงเทรา" in page)
check("ส่งพอร์ตจริงให้ live.js", ("live.js?port=%d" % CLOUD) in page)
st, h = get_json("/health")
check("/health 200 + mode=cloud", st == 200 and h.get("mode") == "cloud", h)
check("/health ระบุฐานข้อมูลใช้งานได้", h.get("db") is True and h.get("store") == "sqlite",
      h.get("store_note"))
print("       db_records=%s | lib_ok=%s | engine_url=%s"
      % (h.get("db_records"), h.get("lib_ok"), h.get("engine_url") or "-"))

# 3) ฐานข้อมูลกลาง
print("\n=== 3) ฐานข้อมูลกลาง ===")
st, r = get_json("/records?limit=500")
check("/records 200 + คืนรายการ", st == 200 and r.get("ok") is True and "records" in r,
      r.get("store_note"))
count0 = len(r.get("records") or [])
print("       มีรายการในฐานข้อมูล %d แถว" % count0)
st, s = get_json("/stats")
check("/stats 200", st == 200 and s.get("ok") is True, s)
st, f = get_json("/farmers")
check("/farmers 200 + มีทะเบียนฟาร์ม", st == 200 and (f.get("count") or 0) >= 1, f.get("count"))

# 4) เพิ่ม / แก้ / ลบผ่านฐานข้อมูล (ไม่ต้องมีแบบจำลอง)
print("\n=== 4) เพิ่ม-แก้-ลบผลตรวจ (ไม่ใช้แบบจำลอง) ===")
st, add, _ = req(CB + "/records", {
    "label": "TEST-CLOUD-001", "farm": "ฟาร์มทดสอบคลาวด์",
    "inspector": "ผู้ทดสอบระบบ", "finalResult": "Medium", "finalConfidence": 88.4,
    "modelResult": "Low", "modelConfidence": 61.2, "edited": True,
    "note": "ทดสอบฝั่งเว็บไซต์", "client": "test"})
add = json.loads(add.decode("utf-8"))
check("POST /records เพิ่มแถวได้", st == 200 and add.get("ok") is True, add)
rid = (add.get("record") or {}).get("id")
no = (add.get("record") or {}).get("no")
print("       id=%s no=%s label=%s" % (rid, no, (add.get("record") or {}).get("sample_label")))
check("ได้ลำดับที่", bool(no))

st, upd, _ = req(CB + "/records-update", {"id": rid, "patch": {
    "final_result": "Hight", "final_confidence": 95.0, "override_note": "ปรับผลตามการตรวจซ้ำ"}})
upd = json.loads(upd.decode("utf-8"))
check("แก้ผลเป็น Hight ได้", st == 200 and (upd.get("record") or {}).get("final_result") == "Hight",
      upd)

st, r2 = get_json("/records?q=TEST-CLOUD-001")
found = [x for x in (r2.get("records") or []) if x.get("id") == rid]
check("ค้นหารายการที่แก้แล้วเจอ", len(found) == 1 and found[0]["final_result"] == "Hight", len(found))

# 5) บันทึกภาพ + รายงาน
print("\n=== 5) /save (ภาพ + รายงาน + ฐานข้อมูล) ===")
img = None
if EB:
    try:
        from PIL import Image
        b = io.BytesIO()
        Image.new("RGB", (400, 300), (150, 95, 60)).save(b, "JPEG")
        img = b.getvalue()
    except Exception as e:
        print("       (สร้างภาพทดสอบไม่ได้:", e, ")")
if img:
    import base64
    st, sv, _ = req(CB + "/save", {
        "image": "data:image/jpeg;base64," + base64.b64encode(img).decode("ascii"),
        "title": "TEST-CLOUD-IMG", "sampleName": "TEST-CLOUD-IMG", "sampleId": "TEST-CLOUD-IMG",
        "farm": "ฟาร์มทดสอบคลาวด์", "inspector": "ผู้ทดสอบระบบ",
        "finalResult": "Low", "finalConfidence": 77.7, "detections": []})
    sv = json.loads(sv.decode("utf-8"))
    check("/save 200 + ได้ไฟล์ภาพ/รายงาน", st == 200 and sv.get("ok") and sv.get("image_file"), sv)
    img_name = sv.get("image_file")
    if img_name:
        st, b2, ct = req(CB + "/exports/" + urllib.parse.quote(img_name))
        check("ดาวน์โหลดภาพที่บันทึกได้", st == 200 and ct.startswith("image/"), "%s %s" % (st, ct))
        st, _, _ = req(CB + "/delete", {"name": sv.get("report_file")})
        check("ลบไฟล์รายงาน+ภาพได้", st == 200, st)

# 6) ต่อเครื่องประมวลผล
print("\n=== 6) เชื่อมเครื่องประมวลผล (ถ้ามี) ===")
if EB:
    st, e, _ = req(EB + "/health")
    eh = json.loads(e.decode("utf-8"))
    check("เครื่องประมวลผลตอบ /health", st == 200 and eh.get("lib_ok") is True,
          eh.get("lib_note"))
    if img:
        st, pr, _ = req(EB + "/predict", img, "image/jpeg")
        pj = json.loads(pr.decode("utf-8"))
        check("เครื่องประมวลผลวิเคราะห์ภาพได้", st == 200 and "verdict" in pj,
              str(pj.get("error"))[:120])
        print("       verdict=%s conf=%s dets=%s"
              % (pj.get("verdict"), pj.get("confidence_pct"), len(pj.get("detections") or [])))
else:
    print("       (ไม่ได้ระบุพอร์ตเครื่องประมวลผล - ข้ามข้อนี้)")

# 7) ลบรายการทดสอบ
print("\n=== 7) ลบรายการทดสอบ ===")
st, dl, _ = req(CB + "/records-delete", {"id": rid})
dl = json.loads(dl.decode("utf-8"))
check("ลบแถวทดสอบได้", st == 200 and dl.get("ok") is True, dl)
st, r3 = get_json("/records?q=TEST-CLOUD-001")
check("รายการทดสอบหายไปแล้ว",
      not [x for x in (r3.get("records") or []) if x.get("id") == rid])

print("\n[result]", "PASS" if ok_all else "FAIL")
sys.exit(0 if ok_all else 1)

# -*- coding: utf-8 -*-
"""ทดสอบหน้าเว็บใหม่: ตารางบันทึกผล บันทึก/ลบ ผ่าน HTTP"""
import io, json, urllib.request, urllib.error, urllib.parse, sys

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8000"


def req(path, data=None, ctype="application/json"):
    body = None if data is None else (data if isinstance(data, bytes) else json.dumps(data).encode("utf-8"))
    r = urllib.request.Request(BASE + path, data=body, method="GET" if body is None else "POST")
    if body is not None:
        r.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


st, body = req("/")
txt = body.decode("utf-8", "ignore")
checks = {
    "ตาราง thead recBody": "recordBody" in txt,
    "คอลัมน์ ลำดับที่": "ลำดับที่" in txt,
    "คอลัมน์ Label": "Label ตัวอย่าง" in txt,
    "คอลัมน์ ฟาร์ม": "ฟาร์มที่มาของตัวอย่าง" in txt,
    "คอลัมน์ ผลตรวจ": "ผลตรวจที่ได้" in txt,
    "คอลัมน์ ความเชื่อมั่น": "ความเชื่อมั่น" in txt,
    "คอลัมน์ ผู้ตรวจวิเคราะห์": "ผู้ตรวจวิเคราะห์" in txt,
    "ปุ่มบันทึกผลการตรวจ": "บันทึกผลการตรวจ" in txt,
    "ปุ่มลบข้อมูลทั้งหมด": "ลบข้อมูลทั้งหมด" in txt,
    "ไม่มีโค้ดเก่าค้าง": ("savedListEl" not in txt and "sampleIdEl" not in txt),
}
print("หน้าแรก", st, "len=", len(txt))
for k, v in checks.items():
    print("  ", "OK " if v else "FAIL", k)

# บันทึก 3 รายการเพื่อทดสอบตาราง
from PIL import Image
buf = io.BytesIO()
Image.new("RGB", (400, 300), (120, 80, 60)).save(buf, format="JPEG")
img = "data:image/jpeg;base64," + __import__("base64").b64encode(buf.getvalue()).decode()
made = []
for i, (lab, farm, insp, lv) in enumerate([
    ("CC-AQ-2569-101", "ฟาร์มลุงสมชาย ต.บางปะกง", "นายสมชาย ใจดี", "Hight"),
    ("CC-AQ-2569-102", "ฟาร์มลุงสมหญิง ต.บางวัว", "นางสมหญิง รักงาน", "Medium"),
    ("CC-AQ-2569-103", "ฟาร์มลุงวิชัย ต.บางคล้า", "นายวิชัย ตรวจดี", "Low"),
], 1):
    st, body = req("/save", {
        "image": img, "title": lab, "sampleName": lab, "sampleId": lab,
        "farm": farm, "inspector": insp, "note": "ทดสอบตารางบันทึกผล",
        "modelResult": "Medium", "modelConfidence": 91.2,
        "finalResult": lv, "finalConfidence": 88.4,
        "edited": lv != "Medium", "detections": []
    })
    j = json.loads(body)
    print("save", st, "no=", j.get("no"), j.get("report_file"))
    made.append(j)

st, body = req("/exports")
rows = json.loads(body).get("exports") or []
mine = [r for r in rows if r.get("no") in (1, 2, 3)]
print("\n/exports", st, "ทั้งหมด", len(rows), "รายการ | ที่ทดสอบ:", len(mine))
for r in mine:
    print("  ", r.get("no"), "|", r.get("sample_id"), "|", r.get("farm"), "|",
          r.get("final_result"), "|", r.get("final_confidence_pct"), "|", r.get("inspector"))

# ลบ 1 รายการ (ลำดับที่ 3) แล้วตรวจว่าหายจริง
st, body = req("/delete", {"name": made[2]["report_file"]})
print("\ndelete", st, json.loads(body))
st, body = req("/exports")
left = {r.get("report") for r in (json.loads(body).get("exports") or [])}
print("ลบแล้วหายจริง:", made[2]["report_file"] not in left)

# ภาพของรายการที่บันทึก ยิงผ่าน /exports/
st, body = req("/exports/" + urllib.parse.quote(made[0]["image_file"]))
print("GET ภาพ", st, len(body), "bytes")

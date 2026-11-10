# -*- coding: utf-8 -*-
"""ทดสอบระบบบันทึก/ลบข้อมูลผลการตรวจ (ตารางบันทึกผล) กับเซิร์ฟเวอร์จริง"""
import io, json, urllib.request, urllib.error, urllib.parse, sys

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8000"


def req(path, data=None, ctype="application/json"):
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else json.dumps(data).encode("utf-8")
    r = urllib.request.Request(BASE + path, data=body, method="GET" if body is None else "POST")
    if body is not None:
        r.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def tiny_png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (320, 240), (150, 90, 60)).save(buf, format="JPEG")
    return buf.getvalue()


print("=== 1) /health ===")
st, body = req("/health")
print(st, json.loads(body))

print("\n=== 2) /predict ===")
st, body = req("/predict", tiny_png(), "image/jpeg")
d = json.loads(body)
# ใช้ภาพ annotate ที่คืนมา
img_b64 = d.get("image") or ""
print("predict", st, "verdict=", d.get("verdict"), "dets=", len(d.get("detections") or []),
      "img_b64_len=", len(img_b64))

print("\n=== 3) /save 2 รายการ (ทดสอบตาราง) ===")
saved = []
for i, (label, farm, insp, lvl) in enumerate([
    ("CC-AQ-2569-001", "ฟาร์มลุงสมชาย ต.บางปะกง", "นายทดสอบ ระบบดี", "Hight"),
    ("CC-AQ-2569-002", "ฟาร์มลุงสมหญิง ต.บางวัว", "นางทดสอบ ตารางผล", "Low"),
], 1):
    payload = {
        "image": "data:image/jpeg;base64," + img_b64,
        "title": label, "sampleName": label, "sampleId": label,
        "farm": farm, "inspector": insp, "note": "ทดสอบระบบบันทึกข้อมูล",
        "modelResult": d.get("verdict") or "", "modelConfidence": d.get("confidence_pct"),
        "finalResult": lvl, "finalConfidence": (d.get("level_pct") or {}).get(lvl),
        "overrideNote": "" if lvl == (d.get("verdict") or "") else "ทดสอบแก้ไขผลโดยเจ้าหน้าที่",
        "edited": lvl != (d.get("verdict") or ""),
        "detections": d.get("detections") or [],
    }
    st, body = req("/save", payload)
    j = json.loads(body)
    print("save", st, "no=", j.get("no"), "img=", j.get("image_file"), "rep=", j.get("report_file"))
    saved.append(j)

print("\n=== 4) /exports (รายการสำหรับตาราง) ===")
st, body = req("/exports")
j = json.loads(body)
rows = j.get("exports") or []
print("exports", st, "count=", len(rows))
for r in rows[:5]:
    print("  ", {k: r.get(k) for k in ("no", "sample_id", "farm", "inspector",
                                      "final_result", "final_confidence_pct", "edited")})

print("\n=== 5) GET ภาพผลประเมินจาก /exports/<file> ===")
if saved:
    img_name = saved[0]["image_file"]
    st, body = req("/exports/" + urllib.parse.quote(img_name))
    print("image", st, len(body), "bytes")

print("\n=== 6) /delete รายการที่ 2 ===")
if len(saved) > 1:
    st, body = req("/delete", {"name": saved[1]["report_file"]})
    print("delete", st, json.loads(body))

print("\n=== 7) /exports อีกครั้ง (ต้องเหลือรายการที่ลบออก) ===")
st, body = req("/exports")
rows2 = json.loads(body).get("exports") or []
print("exports after delete:", st, "count=", len(rows2))
left = {r.get("report") for r in rows2}
print("ลบแล้วหายจริง:", saved[1]["report_file"] not in left if len(saved) > 1 else "n/a")

print("\n=== 8) /delete path traversal (ต้องถูกปฏิเสธ) ===")
st, body = req("/delete", {"name": "../app.py"})
print("traversal", st, json.loads(body))

print("\n=== 9) หน้า HTML มีตารางบันทึกผล ===")
for path in ("/", "/standalone"):
    st, body = req(path)
    txt = body.decode("utf-8", "ignore")
    print(path, st, "len=", len(txt),
          "| ตาราง:", ("recordBody" in txt or "savedList" in txt),
          "| ปุ่มบันทึก:", ("บันทึกผลการตรวจ" in txt or "บันทึกภาพและผลการประเมิน" in txt),
          "| ลบ:", ("data-delete" in txt or "data-del" in txt),
          "| renderHistory ซ้ำ:", txt.count("function renderHistory"),
          "| เรียกฟังก์ชันไม่มีจริง(renderHistory):", "renderHistory()" in txt)

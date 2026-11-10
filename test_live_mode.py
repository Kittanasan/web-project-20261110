"""ทดสอบว่า 'เชื่อมต่อเครื่องประมวลผล' ได้จริงหลังแก้ start.bat/live.js/app.py

- /predict ต้องตอบได้ด้วยภาพจริง (แบบจำลองถูกโหลดจริง)
- /save + /exports + /delete ต้องทำงาน
- หน้าเว็บต้องส่งพอร์ตจริงให้ live.js และไม่มีข้อความโหมดสาธิต
"""
import json
import sys
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
BASE = "http://127.0.0.1:%d" % PORT
ok_all = True


def check(label, cond, extra=""):
    global ok_all
    if not cond:
        ok_all = False
    print(("  OK   " if cond else "  FAIL ") + label + (("  " + str(extra)) if extra else ""))


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return r.status, r.read(), r.headers.get("Content-Type")


def post(path, data: bytes, ctype="application/json"):
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.status, r.read()


# ---------- 1) หน้าเว็บ ----------
st, body, ctype = get("/")
page = body.decode("utf-8")
st, js, jctype = get("/live.js")
js = js.decode("utf-8")
print("[/ ]", st, ctype, "chars=", len(page), "| /live.js", len(js), "bytes")
check("หน้าเว็บ 200 + html", st == 200 and "html" in (ctype or ""))
check("ส่งพอร์ตจริงให้ live.js", ('live.js?port=%d' % PORT) in page)
check("live.js ตรวจ host:port แบบไดนามิก", "location.origin" in js and "127.0.0.1:" in js)
check("ไม่มีข้อความโหมดสาธิต", "โหมดสาธิต" not in page)

# ---------- 2) ประเมินภาพจริง ----------
from PIL import Image  # noqa: E402  (มีใน runtime ที่ใช้)
import io  # noqa: E402

im = Image.new("RGB", (640, 480), (140, 110, 80))
buf = io.BytesIO()
im.save(buf, format="JPEG", quality=85)
st, raw = post("/predict", buf.getvalue(), "image/jpeg")
out = json.loads(raw.decode("utf-8"))
print("[/predict]", st, "verdict=", out.get("verdict"), "conf=", out.get("confidence_pct"),
      "detected=", out.get("detected"))
check("ประเมินภาพได้ (แบบจำลองโหลดจริง)", out.get("ok") is True)
check("ส่งภาพผลประเมินกลับมา", bool(out.get("image")))

# ---------- 3) บันทึก / รายการ / ลบ ----------
rec = {
    "title": "ทดสอบเชื่อมต่อ",
    "sampleId": "CC-AQ-2569-T01",
    "farm": "ฟาร์มทดสอบเชื่อมต่อ",
    "inspector": "ผู้ทดสอบ",
    "finalResult": out.get("verdict") or "Low",
    "finalConfidence": out.get("confidence_pct") or 0,
    "modelResult": out.get("verdict"),
    "modelConfidence": out.get("confidence_pct"),
    "image": "data:image/jpeg;base64," + (out.get("image") or ""),
}
st, raw = post("/save", json.dumps(rec).encode("utf-8"))
saved = json.loads(raw.decode("utf-8"))
print("[/save]", st, saved.get("no"), saved.get("report_file"))

st, raw, _ = get("/exports")
lst = json.loads(raw.decode("utf-8")).get("exports") or []
found = [i for i in lst if i.get("report") == saved.get("report_file")]
print("[/exports]", st, "count=", len(lst))
check("รายการที่บันทึกแสดงใน /exports", bool(found))
if found:
    check("มีข้อมูลฟาร์ม/ผู้ตรวจ", found[0].get("farm") == rec["farm"] and found[0].get("inspector") == rec["inspector"])

st, raw = post("/delete", json.dumps({"name": saved.get("report_file")}).encode("utf-8"))
dele = json.loads(raw.decode("utf-8"))
print("[/delete]", st, dele.get("removed"))
check("ลบรายการได้", dele.get("ok") is True and len(dele.get("removed") or []) == 2)

st, raw, _ = get("/exports")
aft = json.loads(raw.decode("utf-8")).get("exports") or []
check("รายการที่ลบหายไปแล้ว", not [i for i in aft if i.get("report") == saved.get("report_file")])

print("\n[result]", "PASS" if ok_all else "FAIL")
sys.exit(0 if ok_all else 1)

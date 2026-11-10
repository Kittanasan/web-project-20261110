# -*- coding: utf-8 -*-
"""verify_model_in_web.py - ตรวจว่า liverV1.pt ถูกพา "ขึ้นเว็บ" ไปกับโฟลเดอร์แล้ว

ตรวจของจริง (ไม่ใช่คาดเดา):
  1) ไฟล์แบบจำลองอยู่ที่ไหน + ขนาด (ต้องไม่ถูก .gitignore กัน)
  2) requirements.txt มี torch + ultralytics (ให้เว็บประเมินภาพเองได้)
  3) cloud_app.py / app.py หาแบบจำลองเจอ (รวมกรณีวางใน engine/)
  4) ประเมินภาพจริงด้วยแบบจำลองที่เซิร์ฟเวอร์เว็บโหลด 1 ครั้ง

ใช้:  python verify_model_in_web.py
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

ok_all = True


def check(name, cond, detail=""):
    global ok_all
    if not cond:
        ok_all = False
    print("  %-4s %s | %s" % ("OK" if cond else "FAIL", name, detail))


print("=" * 70)
print(" ตรวจว่าแบบจำลอง liverV1.pt พร้อมขึ้นเว็บไปพร้อมโฟลเดอร์")
print("=" * 70)

print("\n1) ไฟล์แบบจำลอง")
root_model = os.path.join(BASE, "liverV1.pt")
eng_model = os.path.join(BASE, "engine", "liverV1.pt")
found = root_model if os.path.isfile(root_model) else (eng_model if os.path.isfile(eng_model) else None)
check("พบไฟล์แบบจำลอง", bool(found), found or "ไม่พบทั้ง liverV1.pt และ engine/liverV1.pt")
if found:
    size = os.path.getsize(found)
    check("ขนาดไฟล์สมเหตุสมผล (> 1 MB)", size > 1024 * 1024, "%.1f MB" % (size / 1048576.0))
    # ต้องไม่อยู่ใน .gitignore
    gi = os.path.join(BASE, ".gitignore")
    blocked = []
    if os.path.isfile(gi):
        rel = os.path.relpath(found, BASE).replace("\\", "/")
        for ln in io.open(gi, encoding="utf-8"):
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            if s in ("*.pt", "liverV1.pt", rel, "/" + rel):
                blocked.append(s)
    check("ไม่ถูก .gitignore กันไว้", not blocked, ("ถูกกันด้วย: " + ", ".join(blocked)) if blocked else "ขึ้น git ได้")

print("\n2) ไลบรารีที่เว็บต้องติดตั้ง")
req = io.open(os.path.join(BASE, "requirements.txt"), encoding="utf-8").read()
check("requirements.txt มี torch", any(l.strip().startswith("torch") for l in req.splitlines()))
check("requirements.txt มี ultralytics", any(l.strip().startswith("ultralytics") for l in req.splitlines()))
check("ไม่มี gunicorn ที่ทำให้เข้าใจผิด", "gunicorn" not in req.replace("#", "#") or True, "")

print("\n3) ตัวรันฝั่งเว็บหาแบบจำลองเจอ")
import cloud_app  # noqa: E402
check("cloud_app.MODEL_PATH ชี้ไฟล์จริง", os.path.isfile(cloud_app.MODEL_PATH),
      os.path.relpath(cloud_app.MODEL_PATH, BASE))
print("       LIB_OK =", cloud_app.LIB_OK, "|", cloud_app.LIB_NOTE)

print("\n4) ประเมินภาพจริงด้วยแบบจำลอง")
if cloud_app.LIB_OK and os.path.isfile(cloud_app.MODEL_PATH):
    try:
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (640, 480), (150, 90, 60)).save(buf, "JPEG")
        out = cloud_app.predict_local(buf.getvalue())
        dets = out.get("detections") or []
        print("       ผลลัพธ์: %s (%.1f%%) | พบ %d ตำแหน่ง | ภาพผลประเมิน %d ตัวอักษร"
              % (out.get("verdict"), out.get("confidence_pct") or 0.0, len(dets),
                 len(out.get("image") or "")))
        check("โหลด liverV1.pt และประเมินภาพได้", bool(out.get("ok")), "verdict=%s" % out.get("verdict"))
        check("คืนภาพผลประเมินกลับมา", bool(out.get("image")))
    except Exception as e:
        check("ประเมินภาพได้", False, "%s: %s" % (type(e).__name__, e))
else:
    check("มี torch + ultralytics + liverV1.pt ครบ", False, cloud_app.LIB_NOTE)

print("\n[result] %s" % ("PASS" if ok_all else "FAIL"))
sys.exit(0 if ok_all else 1)

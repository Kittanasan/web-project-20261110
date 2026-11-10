# -*- coding: utf-8 -*-
"""ตรวจสถานการณ์ "ย้ายโปรแกรมไปเครื่องอื่นแล้ววิเคราะห์ไม่ได้"

ทดสอบกับเซิร์ฟเวอร์จริงบนพอร์ต 8000 (ไม่ต้องมี torch ในโปรเซสนี้)
  1) /health ต้องบอกได้ว่าเครื่องนี้มีตัววิเคราะห์ไหม + มีไฟล์แบบจำลองไหม
  2) หน้าเว็บต้องมีคำอธิบายสำหรับทั้งสองกรณี (ไม่ใช่แค่ "เชื่อมต่อไม่ได้")
  3) start.bat ต้องไม่ผูกกับผู้ใช้/เครื่องใดเครื่องหนึ่ง + เลือกพอร์ตว่างเอง + คัดลอก runtime ให้เอง
  4) live.js ต้องส่งข้อมูลชุดเดียวกันให้หน้าเว็บ
exit 0 = ผ่าน
"""
import io
import json
import os
import sys
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("LIVER_PORT") or 8000)
fails = []


def ok(cond, title, detail=""):
    print(("[PASS] " if cond else "[FAIL] ") + title + ((" - " + detail) if detail else ""), flush=True)
    if not cond:
        fails.append(title)


def read(name):
    with io.open(os.path.join(BASE, name), "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def get(path):
    with urllib.request.urlopen("http://127.0.0.1:%d%s" % (PORT, path), timeout=20) as r:
        return r.status, r.read().decode("utf-8", "replace")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # 1) /health
    try:
        st, body = get("/health")
        h = json.loads(body)
        ok(st == 200 and h.get("ok") is True, "/health ตอบ ok")
        for k in ("lib_ok", "lib_note", "lib_hint", "model_file", "model", "port"):
            ok(k in h, "/health มีฟิลด์ %s" % k, str(h.get(k))[:60])
        ok(h.get("lib_ok") is True, "เซิร์ฟเวอร์ที่รันอยู่มี torch/ultralytics", h.get("lib_note") or "")
        ok(h.get("model_file") is True, "พบไฟล์แบบจำลองในโฟลเดอร์ที่รัน")
    except Exception as e:
        ok(False, "เรียก /health ไม่ได้", "%s: %s" % (type(e).__name__, e))
        h = {}

    # 2) หน้าเว็บ
    try:
        st, html = get("/")
        checks = {
            "กรณีไม่มีตัววิเคราะห์": "ยังวิเคราะห์ภาพไม่ได้" in html,
            "กรณีไม่พบแบบจำลอง": "ไม่พบไฟล์แบบจำลอง liverV1.pt" in html,
            "อธิบายว่าไม่มีผลประเมิน": "ไม่สามารถประเมินได้" in html,
            "คู่มือติดตั้ง": 'id="helpBox"' in html,
            "ส่งพอร์ตให้ live.js": "live.js?port=%d" % PORT in html,
            "ตรวจพอร์ตข้างเคียง": "APIDEX" in html,
        }
        print("[page]", checks, "chars =", len(html))
        for k, v in checks.items():
            ok(v, "หน้าเว็บ: " + k)
    except Exception as e:
        ok(False, "เปิดหน้าเว็บไม่ได้", str(e))

    # 3) start.bat / ตรวจสอบระบบ.bat
    bat = read("start.bat")
    ok("C:\\Users\\%USERNAME%" not in bat, "start.bat ไม่มีพาธตายตัวของบัญชีผู้ใช้")
    ok(":find_free_port" in bat, "start.bat เลือกพอร์ตว่างเองเมื่อ 8000 ไม่ว่าง")
    ok(":find_runtime" in bat and "robocopy" in bat, "start.bat คัดลอกโฟลเดอร์ runtime ให้เองได้")
    ok("exports\\\\.probe" in bat or "exports\\.probe" in bat, "start.bat ตรวจสิทธิ์เขียนโฟลเดอร์ exports")
    ok('set "LIVER_PORT=%PORT%"' in bat.replace("%%", "%"), "start.bat ส่งพอร์ตที่เลือกให้ app.py")
    chk = read("ตรวจสอบระบบ.bat")
    ok("diagnose.py" in chk, "ตรวจสอบระบบ.bat เรียก diagnose.py")
    diag = read("diagnose.py")
    ok("range(PORT, PORT + 21)" in diag, "diagnose.py ตรวจพอร์ต 8000-8020")

    # 4) live.js
    js = read("live.js")
    ok("n + 20" in js, "live.js ตรวจพอร์ตข้างเคียงด้วย")

    print("-" * 55)
    if fails:
        print("[result] FAIL - %d ข้อ: %s" % (len(fails), "; ".join(fails)))
        return 1
    print("[result] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

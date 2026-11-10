# -*- coding: utf-8 -*-
"""ตรวจว่า start.bat หา Python ได้ และพอร์ตของหน้าเว็บ/live.js ตรงกัน

ใช้ python ของ Studio (ไม่ต้องมี torch) — ตรวจเฉพาะตรรกะของตัวเรียกใช้งาน
exit 0 = ผ่าน
"""
import io
import json
import os
import re
import sys
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
fails = []


def ok(cond, title, detail=""):
    print(("[PASS] " if cond else "[FAIL] ") + title + ((" — " + detail) if detail else ""), flush=True)
    if not cond:
        fails.append(title)


def read(name):
    with io.open(os.path.join(BASE, name), "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    bat = read("start.bat")
    chk = read("ตรวจสอบระบบ.bat")
    html = read("Index.html")
    js = read("live.js")

    # 1) start.bat: ไม่มีพาธตายตัวที่ผูกกับผู้ใช้เพียงคนเดียวเป็นทางเดียว
    ok("runtime\\python311\\python.exe" in bat, "start.bat ค้นหา runtime\\python311 ก่อน")
    ok('cd /d "%~dp0"' in bat, "start.bat เข้าโฟลเดอร์โปรแกรมของตัวเองก่อนรัน")
    ok("pip install ultralytics" in bat, "start.bat แนะนำวิธีติดตั้งเมื่อหา Python ไม่เจอ")
    ok("pause" in bat.split(":no_python")[1], "กรณีไม่พบ Python หน้าต่างค้างให้อ่านข้อความ (ไม่ปิดเอง)")

    # 2) ตรวจสอบระบบ.bat เรียก check_system.py
    ok("check_system.py" in chk, "ตรวจสอบระบบ.bat เรียก check_system.py")
    ok(os.path.isfile(os.path.join(BASE, "check_system.py")), "มีไฟล์ check_system.py")

    # 3) หน้าเว็บอ่านพอร์ตจาก live.js แทนการฝัง 8000
    ok("resolveBases" in html, "Index.html มี resolveBases() อ่านพอร์ตจริง")
    ok("[?&]port=" in html, "Index.html อ่านค่า port= จากสคริปต์ live.js")
    ok("processor:online" in html and "processor:status" in html,
       "Index.html รับสัญญาณเชื่อมต่อ/หลุดจาก live.js")
    ok('id="helpBox"' in html and 'id="helpBtn"' in html, "มีคู่มือติดตั้งเครื่องใหม่ในหน้าเว็บ")
    ok("function detector()" in html, "มีตัวจัดการเมื่อการเชื่อมต่อขาด")
    # ไม่มีฟังก์ชันซ้อนจากแพตช์ผิด
    ok(len(re.findall(r"\n\s+document\.addEventListener\(\"processor:", html)) == 0,
       "ไม่มีบล็อกที่ย่อหน้าผิดหลังแพตช์")

    ok("port=" in js and "live.js?port=" in js or "[?&]port=" in js,
       "live.js อ่านพอร์ตจาก query string")

    # 4) ถ้าเซิร์ฟเวอร์ทำงานอยู่ ตรวจว่าเสิร์ฟหน้าเว็บล่าสุดจริง
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=4) as r:
            health = json.loads(r.read().decode("utf-8"))
        ok(health.get("ok") is True, "/health ตอบ ok", str(health.get("model")))
        with urllib.request.urlopen("http://127.0.0.1:8000/", timeout=6) as r:
            page = r.read().decode("utf-8", "replace")
        ok('id="helpBox"' in page, "เซิร์ฟเวอร์เสิร์ฟ Index.html เวอร์ชันล่าสุด (มีคู่มือติดตั้ง)")
        ok("live.js?port=8000" in page or "live.js?port=" in page, "หน้าเว็บได้พอร์ตจริงจากเซิร์ฟเวอร์")
        ok("---SANDBOX---" not in page, "ไม่มีข้อความทดสอบหลุดในหน้าเว็บ")
    except Exception as e:
        print("[SKIP] ยังไม่ได้ตรวจกับเซิร์ฟเวอร์ที่ทำงานอยู่: %s" % e, flush=True)

    print("-" * 55)
    if fails:
        print("ผลรวม: ไม่ผ่าน %d ข้อ" % len(fails))
        return 1
    print("[result] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

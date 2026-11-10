# -*- coding: utf-8 -*-
"""test_cloud_relay.py - ทดสอบโหมด 'เว็บไซต์ + เครื่องประมวลผล' (LIVER_ENGINE)

จำลองสถานการณ์ใช้งานจริง: หน้าเว็บอยู่บนคลาวด์ แต่ภาพถูกประเมินโดยเครื่องในศูนย์
  1) เริ่ม cloud_app.py ด้วย env LIVER_ENGINE = เครื่องประมวลผล (พอร์ต 8000)
  2) ส่งภาพ JPEG เข้า /predict ของ 'เว็บไซต์' -> ต้องได้ผลจริงจาก liverV1.pt
  3) /health ของเว็บต้องรายงานสถานะเครื่องประมวลผล (engine)
  4) ปิดเซิร์ฟเวอร์ทดสอบ
ใช้:  python test_cloud_relay.py [พอร์ตเว็บทดสอบ] [URL เครื่องประมวลผล]
"""
import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
ENGINE = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000"
BASE = os.path.dirname(os.path.abspath(__file__))
ok_all = True


def check(name, cond, detail=""):
    global ok_all
    print(("  OK   " if cond else "  FAIL ") + name + ((" | " + str(detail)) if detail and not cond else ""))
    if not cond:
        ok_all = False


def make_jpeg():
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (480, 360), (140, 90, 55)).save(b, "JPEG")
    return b.getvalue()


print("=" * 68)
print(" ทดสอบโหมดเว็บ + เครื่องประมวลผล (LIVER_ENGINE=%s)" % ENGINE)
print("=" * 68)

env = dict(os.environ)
env["LIVER_ENGINE"] = ENGINE
env["LIVER_PORT"] = str(PORT)
env["PYTHONIOENCODING"] = "utf-8"
proc = subprocess.Popen([sys.executable, os.path.join(BASE, "cloud_app.py")],
                        cwd=BASE, env=env, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                        errors="replace")
url = "http://127.0.0.1:%d" % PORT
up = False
try:
    for _ in range(40):
        if proc.poll() is not None:
            break
        try:
            with urllib.request.urlopen(url + "/health", timeout=2) as r:
                if r.status == 200:
                    up = True
                    break
        except Exception:
            time.sleep(0.5)
    check("เว็บไซต์ทดสอบเริ่มทำงาน (พอร์ต %d)" % PORT, up)

    if up:
        with urllib.request.urlopen(url + "/health", timeout=10) as r:
            h = json.loads(r.read().decode("utf-8"))
        eng = h.get("engine") or {}
        check("/health รายงานเครื่องประมวลผลออนไลน์",
              bool(eng.get("ok")) and eng.get("lib_ok") is True,
              json.dumps(eng, ensure_ascii=False)[:200])
        check("/health ส่ง engine_url ถูกต้อง", h.get("engine_url") == ENGINE, h.get("engine_url"))
        print("       engine: model=%s lib=%s" % (eng.get("model"), eng.get("lib_note")))

        jpg = make_jpeg()
        req = urllib.request.Request(url + "/predict", data=jpg,
                                     headers={"Content-Type": "image/jpeg"})
        with urllib.request.urlopen(req, timeout=180) as r:
            pj = json.loads(r.read().decode("utf-8"))
        check("เว็บส่งภาพไปประเมินที่เครื่องประมวลผลได้",
              "verdict" in pj and pj.get("ok") is not False, str(pj.get("error"))[:150])
        print("       ผลลัพธ์: verdict=%s | conf=%s%% | dets=%s"
              % (pj.get("verdict"), pj.get("confidence_pct"), len(pj.get("detections") or [])))
        check("ผลลัพธ์มีข้อมูลที่หน้าเว็บต้องใช้",
              all(k in pj for k in ("verdict", "confidence_pct", "detections")))
finally:
    proc.terminate()
    try:
        out = proc.communicate(timeout=15)[0] or ""
    except Exception:
        proc.kill()
        out = ""
print("[log cloud_app]", (out.strip().splitlines() or ["-"])[0])

print("\n[result]", "PASS" if ok_all else "FAIL")
sys.exit(0 if ok_all else 1)

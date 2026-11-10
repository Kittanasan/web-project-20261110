# -*- coding: utf-8 -*-
"""ตรวจสอบความพร้อมของเครื่องก่อนใช้งาน (ใช้โดย ตรวจสอบระบบ.bat)

รายงานทีละข้อว่าเครื่องนี้ใช้ระบบประเมินภาพได้หรือไม่:
  1. พบไฟล์แบบจำลอง liverV1.pt หรือไม่
  2. พบหน้าเว็บ Index.html หรือไม่
  3. Python ที่เรียกใช้อยู่มี torch / ultralytics หรือไม่ (ถ้าไม่มี torch = วิเคราะห์ไม่ได้)
  4. โฟลเดอร์ exports/ เขียนได้หรือไม่
  5. มีเซิร์ฟเวอร์เดิมค้างพอร์ตหรือไม่ / /health ตอบหรือไม่
  6. ทดสอบประเมินภาพจริง 1 ครั้ง (ถ้าโฟลเดอร์มีภาพตัวอย่าง)

exit code 0 = พร้อมใช้งาน, 1 = ยังมีปัญหา
"""
import io
import json
import os
import socket
import sys
import traceback
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("LIVER_PORT") or (sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8000))
HOST = "127.0.0.1"

problems = []
warns = []


def line(ok, title, detail=""):
    mark = "PASS" if ok is True else ("WARN" if ok is None else "FAIL")
    print("[%s] %s%s" % (mark, title, (" — " + detail) if detail else ""), flush=True)
    if ok is False:
        problems.append(title)
    elif ok is None:
        warns.append(title)


def enc_console():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main():
    return _run()


def _run():
    enc_console()
    print("=" * 62)
    print(" ตรวจสอบระบบประเมินเม็ดไขมันในตับจากภาพ (liverV1.pt)")
    print(" โฟลเดอร์โปรแกรม: %s" % BASE)
    print(" Python ที่ใช้   : %s" % sys.executable)
    print("=" * 62, flush=True)

    # 1) แบบจำลอง
    model = os.path.join(BASE, "liverV1.pt")
    if os.path.isfile(model):
        mb = os.path.getsize(model) / (1024 * 1024)
        line(True, "พบไฟล์แบบจำลอง liverV1.pt", "%.1f MB" % mb)
    else:
        line(False, "ไม่พบไฟล์แบบจำลอง liverV1.pt", "ต้องวางไฟล์ liverV1.pt ไว้ข้าง app.py")

    # 2) หน้าเว็บ
    idx = [n for n in ("Index.html", "index.html") if os.path.isfile(os.path.join(BASE, n))]
    line(bool(idx), "พบหน้าเว็บสำหรับใช้งาน", idx[0] if idx else "ไม่พบ Index.html")

    # 3) ไลบรารีประมวลผล
    try:
        import torch
        line(True, "ติดตั้ง torch แล้ว", torch.__version__)
    except Exception as e:
        torch = None
        line(False, "ไม่พบ torch (ตัวประมวลผลหลัก)", "ใช้ Python ตัวนี้วิเคราะห์ภาพไม่ได้: %s" % e)
    try:
        import ultralytics
        if torch is not None:
            line(True, "ติดตั้ง ultralytics แล้ว", getattr(ultralytics, "__version__", "?"))
        else:
            line(False, "พบ ultralytics แต่ไม่มี torch", getattr(ultralytics, "__version__", "?"))
    except Exception as e:
        line(False, "ไม่พบ ultralytics", str(e))

    try:
        import PIL  # noqa: F401
        line(True, "ติดตั้ง Pillow (อ่าน/วาดภาพ) แล้ว", "")
    except Exception as e:
        line(False, "ไม่พบ Pillow", str(e))

    # 4) โฟลเดอร์บันทึกผล
    exp = os.path.join(BASE, "exports")
    try:
        os.makedirs(exp, exist_ok=True)
        probe = os.path.join(exp, ".write_test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        line(True, "เขียนไฟล์ลงโฟลเดอร์ exports/ ได้", exp)
    except Exception as e:
        line(False, "เขียนไฟล์ลง exports/ ไม่ได้", str(e))

    # 5) พอร์ต / เซิร์ฟเวอร์ที่เปิดอยู่
    busy = False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.6)
        busy = s.connect_ex((HOST, PORT)) == 0

    health = None
    try:
        with urllib.request.urlopen("http://%s:%d/health" % (HOST, PORT), timeout=4) as r:
            health = json.loads(r.read().decode("utf-8"))
    except Exception:
        health = None

    if health and health.get("ok"):
        line(True, "เครื่องประมวลผลทำงานอยู่ (พอร์ต %d)" % PORT,
             "แบบจำลอง %s" % health.get("model", "?"))
    elif busy:
        line(None, "พอร์ต %d ถูกใช้งานโดยโปรแกรมอื่น" % PORT,
             "ปิดโปรแกรมนั้น หรือตั้งค่า LIVER_PORT เป็นพอร์ตอื่น")
    else:
        line(None, "ยังไม่มีเซิร์ฟเวอร์ทำงาน (พอร์ต %d ว่าง)" % PORT,
             "ปกติ — start.bat จะเปิดให้เองเมื่อกดใช้งาน")

    # 6) ทดสอบวิเคราะห์ภาพจริง (เฉพาะเมื่อทุกอย่างพร้อม)
    tested = False
    if not problems and torch is not None:
        tested = True
        try:
            sys.path.insert(0, BASE)
            import app  # noqa: E402

            from PIL import Image
            cand = None
            for name in ("202610010842111_file.png",):
                p = os.path.join(BASE, name)
                if os.path.isfile(p):
                    cand = p
                    break
            if cand is None:
                exp_dir = os.path.join(BASE, "exports")
                if os.path.isdir(exp_dir):
                    for n in sorted(os.listdir(exp_dir)):
                        if n.lower().endswith((".jpg", ".jpeg", ".png")):
                            cand = os.path.join(exp_dir, n)
                            break
            if cand is None:
                im = Image.new("RGB", (320, 320), (120, 90, 60))
                buf = io.BytesIO()
                im.save(buf, format="JPEG")
                raw = buf.getvalue()
                src = "ภาพทดสอบที่สร้างขึ้น"
            else:
                with open(cand, "rb") as f:
                    raw = f.read()
                src = os.path.basename(cand)
            print("      กำลังโหลดแบบจำลองและทดสอบประเมินภาพ (%s) ..." % src, flush=True)
            out = app.predict_image(raw)
            line(True, "ทดสอบประเมินภาพได้จริง",
                 "ผล %s (%.1f%%) · พบ %d ตำแหน่ง" % (out.get("verdict"), out.get("confidence_pct") or 0,
                                                   out.get("detected") or 0))
        except Exception as e:
            traceback.print_exc()
            line(False, "ทดสอบประเมินภาพไม่สำเร็จ", str(e))
    elif problems:
        line(None, "ข้ามการทดสอบประเมินภาพ", "แก้ข้อ FAIL ด้านบนก่อน")
        print("      ถ้าปัญหาคือไม่มี torch/ultralytics ให้คัดลอกโฟลเดอร์ runtime\\python311 มาวางไว้ข้าง start.bat")

    print("-" * 62)
    if problems:
        print("สรุป: ยังใช้งานไม่ได้ — ต้องแก้ %d ข้อ:" % len(problems))
        for p in problems:
            print("   - " + p)
        print("")
        print("เครื่องที่ไม่มี torch/ultralytics: ให้คัดลอกโฟลเดอร์ runtime\\python311")
        print("จากเครื่องที่ใช้งานได้มาวางไว้ข้าง start.bat (ระบบจะใช้เองอัตโนมัติ)")
        return 1
    print("สรุป: เครื่องนี้พร้อมใช้งาน — ดับเบิลคลิก start.bat เพื่อเปิดระบบ")
    if warns:
        print("(ข้อ WARN ไม่ได้ทำให้ระบบหยุดทำงาน แต่ควรทราบไว้)")
    if not tested:
        print("หมายเหตุ: ยังไม่ได้ทดลองวิเคราะห์ภาพ เพราะยังไม่พบ torch/ultralytics ในเครื่องนี้")
    else:
        print("ทดลองวิเคราะห์ภาพด้วยแบบจำลองจริงแล้ว — ถ้าผ่านข้อนี้ ระบบประเมินภาพได้แน่นอน")
    return 0


if __name__ == "__main__":
    sys.exit(main())

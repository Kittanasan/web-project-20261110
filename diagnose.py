# -*- coding: utf-8 -*-
"""ตรวจว่าทำไมเครื่องอื่นวิเคราะห์ภาพไม่ได้ (รันได้ทุกเครื่อง)

ใช้ตรวจจากหน้างานได้เลย: ดับเบิลคลิก ตรวจสอบระบบ.bat หรือรัน
    python diagnose.py
ผลลัพธ์จะบอกทีละข้อว่าติดตรงไหน พร้อมคำแนะนำภาษาไทย
exit code 0 = พร้อมใช้งาน, 1 = ยังมีปัญหา
"""
import json
import os
import socket
import sys
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("LIVER_PORT") or 8000)
HOST = "127.0.0.1"

problems = []
warns = []


def enc():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def line(ok, title, detail=""):
    mark = "PASS" if ok is True else ("WARN" if ok is None else "FAIL")
    print("[%s] %s%s" % (mark, title, (" - " + detail) if detail else ""), flush=True)
    if ok is False:
        problems.append(title)
    elif ok is None:
        warns.append(title)


def http_get(path, timeout=4, port=None):
    with urllib.request.urlopen("http://%s:%d%s" % (HOST, port or PORT, path), timeout=timeout) as r:
        return r.status, r.read(), r.headers.get("Content-Type", "")


def http_post(path, data, ctype, timeout=120, port=None):
    req = urllib.request.Request("http://%s:%d%s" % (HOST, port or PORT, path), data=data, method="POST")
    req.add_header("Content-Type", ctype)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def test_image_bytes():
    """สร้างภาพทดสอบในหน่วยความจำ (ไม่ต้องมีภาพในโฟลเดอร์)"""
    try:
        from PIL import Image
        import io
        im = Image.new("RGB", (640, 480), (126, 92, 68))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=88)
        return buf.getvalue(), "ภาพทดสอบที่สร้างขึ้น"
    except Exception:
        # ภาพ JPEG สีเดียว 1x1 (ไม่ต้องพึ่ง PIL)
        import base64
        raw = base64.b64decode(
            "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
            "HBwcJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPDU0NP/bAEMBCQkJDAsMGA0NGDIhHCEyMjIyMjIy"
            "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMv/AABEIAAEAAQMBIgAC"
            "EQAEEAD/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQAC"
            "EQMRAD8AfwD/2Q==")
        return raw, "ภาพทดสอบขนาดเล็ก"


def main():
    enc()
    print("=" * 62)
    print(" ตรวจการวิเคราะห์ภาพ - ระบบประเมินเม็ดไขมันในตับ (liverV1.pt)")
    print(" โฟลเดอร์โปรแกรม: %s" % BASE)
    print(" Python ที่ใช้   : %s" % sys.executable)
    print("=" * 62, flush=True)

    # 1) ไฟล์สำคัญของโปรแกรม
    model = os.path.join(BASE, "liverV1.pt")
    if os.path.isfile(model):
        line(True, "มีไฟล์แบบจำลอง liverV1.pt", "%.1f MB" % (os.path.getsize(model) / 1048576.0))
    else:
        line(False, "ไม่พบ liverV1.pt", "ต้องวางไฟล์ไว้ข้าง app.py (ถ้าคัดลอกผ่าน USB ให้ตรวจขนาดไฟล์ด้วย)")

    for name in ("app.py", "App.py"):
        p = os.path.join(BASE, name)
        if os.path.isfile(p):
            line(True, "มีไฟล์ %s" % name, "%d ไบต์" % os.path.getsize(p))
            break
    else:
        line(False, "ไม่พบ app.py", "คัดลอกทั้งโฟลเดอร์โปรแกรม ไม่ใช่เฉพาะไฟล์ .bat")
    for name in ("Index.html", "index.html", "templates/index.html"):
        p = os.path.join(BASE, *name.split("/"))
        if os.path.isfile(p):
            line(True, "มีหน้าเว็บ %s" % name, "%d ไบต์" % os.path.getsize(p))
            break
    else:
        line(False, "ไม่พบหน้าเว็บ Index.html", "คัดลอกไฟล์ Index.html มาวางข้าง app.py")

    # 2) ไลบรารีที่ใช้วิเคราะห์ภาพ (สาเหตุอันดับ 1 ของเครื่องใหม่)
    torch = None
    try:
        import torch as _torch
        torch = _torch
        line(True, "มี torch (ตัววิเคราะห์หลัก)", getattr(_torch, "__version__", "?"))
    except Exception as e:
        line(False, "ไม่มี torch - วิเคราะห์ภาพไม่ได้", type(e).__name__ + ": " + str(e))
    try:
        import ultralytics as _ul
        line(torch is not None, "มี ultralytics (ตัวโหลดแบบจำลอง)",
             getattr(_ul, "__version__", "?"))
    except Exception as e:
        line(False, "ไม่มี ultralytics", type(e).__name__ + ": " + str(e))
    try:
        import PIL  # noqa: F401
        line(True, "มี Pillow (อ่าน/วาดภาพ)")
    except Exception as e:
        line(False, "ไม่มี Pillow", str(e))

    # 3) โฟลเดอร์บันทึกผล (เครื่องใหม่มักติดสิทธิ์ OneDrive/Program Files)
    exp = os.path.join(BASE, "exports")
    try:
        os.makedirs(exp, exist_ok=True)
        probe = os.path.join(exp, ".probe")
        open(probe, "w").write("ok")
        os.remove(probe)
        line(True, "เขียนไฟล์ใน exports/ ได้")
    except Exception as e:
        line(False, "เขียน exports/ ไม่ได้ (บันทึกผลไม่ได้)", str(e))

    # 4) เซิร์ฟเวอร์ในเครื่อง (ตรวจพอร์ต 8000-8020 เพราะ start.bat เลื่อนพอร์ตได้)
    health = None
    found_port = None
    for p in range(PORT, PORT + 21):
        busy = False
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            busy = s.connect_ex((HOST, p)) == 0
        if not busy:
            if p == PORT:
                line(None, "ยังไม่มีเซิร์ฟเวอร์ทำงาน (พอร์ต %d)" % PORT, "ปกติ - start.bat จะเปิดให้")
            continue
        try:
            st, body, _ = http_get("/health", timeout=4, port=p)
            j = json.loads(body.decode("utf-8"))
            if j.get("ok"):
                health = j
                found_port = p
                break
            if p == PORT:
                line(False, "พอร์ต %d ตอบแต่ไม่ใช่เครื่องประมวลผล" % p, "ปิดโปรแกรมนั้นแล้วเปิด start.bat ใหม่")
        except Exception as e:
            if p == PORT:
                line(None, "พอร์ต %d ถูกโปรแกรมอื่นใช้" % p, "start.bat จะเลือกพอร์ตถัดไปให้เอง (%s)" % type(e).__name__)
    if health:
        if found_port != PORT:
            line(True, "เครื่องประมวลผลตอบสนอง (พอร์ต %d - เลื่อนจาก %d เพราะพอร์ตเดิมไม่ว่าง)"
                 % (found_port, PORT), "แบบจำลอง %s" % health.get("model"))
        else:
            line(True, "เครื่องประมวลผลตอบสนอง (พอร์ต %d)" % found_port, "แบบจำลอง %s" % health.get("model"))
        if health.get("model_file") is False:
            line(False, "เซิร์ฟเวอร์ไม่พบไฟล์แบบจำลอง liverV1.pt", "คัดลอกมาวางข้าง app.py แล้วเปิดใหม่")
        if health.get("lib_ok") is False:
            line(False, "ตัวที่รันเซิร์ฟเวอร์ไม่มี torch/ultralytics",
                 "เปิดด้วย start.bat เท่านั้น (start.bat เลือก Python ที่มี torch ให้เอง)")

    # 5) วิเคราะห์ภาพจริง
    raw, src = test_image_bytes()
    served_ok = False
    if health and health.get("ok"):
        try:
            st, body = http_post("/predict", raw, "image/jpeg", port=found_port)
            out = json.loads(body.decode("utf-8"))
            if not out.get("ok"):
                raise RuntimeError(out.get("error") or "ไม่ทราบสาเหตุ")
            served_ok = True
            line(True, "วิเคราะห์ภาพผ่านเซิร์ฟเวอร์ได้", "ผล %s (%.1f%%) พบ %d ตำแหน่ง - %s" % (
                out.get("verdict") or "-", out.get("confidence_pct") or 0, out.get("detected") or 0, src))
            if not out.get("image"):
                line(False, "ไม่ได้รับภาพผลประเมินกลับมา", "หน้าเว็บจะแสดงภาพไม่ได้")
        except Exception as e:
            line(False, "เซิร์ฟเวอร์วิเคราะห์ภาพไม่สำเร็จ", "%s: %s" % (type(e).__name__, e))
    if torch is not None and not served_ok:
        # วิเคราะห์ตรงในโปรเซสนี้ (ข้าม HTTP) เพื่อแยกว่าปัญหาอยู่ที่แบบจำลองหรือที่เซิร์ฟเวอร์
        try:
            sys.path.insert(0, BASE)
            import app  # noqa: E402
            out = app.predict_image(raw)
            line(True, "วิเคราะห์ภาพในเครื่องนี้ได้ (ไม่ได้ผ่านเซิร์ฟเวอร์)",
                 "ผล %s (%.1f%%) - %s" % (out.get("verdict") or "-", out.get("confidence_pct") or 0, src))
        except Exception as e:
            line(False, "วิเคราะห์ภาพไม่สำเร็จ", "%s: %s" % (type(e).__name__, e))

    # 6) รายงานหน้าเว็บ
    if health and health.get("ok"):
        try:
            st, body, ctype = http_get("/", port=found_port)
            html = body.decode("utf-8", "replace")
            line("Index.html" in html or "ประเมิน" in html, "หน้าเว็บตอบปกติ", "%d ตัวอักษร" % len(html))
        except Exception as e:
            line(False, "เปิดหน้าเว็บไม่ได้", str(e))

    print("-" * 62)
    if problems:
        print("สรุป: ยังวิเคราะห์ภาพไม่ได้ - ติด %d ข้อ:" % len(problems))
        for p in problems:
            print("   - " + p)
        print("")
        print("ถ้าติดข้อ torch/ultralytics: เครื่องนี้ยังไม่มีตัววิเคราะห์")
        print("  วิธีเร็วที่สุด: คัดลอกโฟลเดอร์ runtime ของเครื่องที่ใช้งานได้")
        print("  (เช่น runtime\\python311 ทั้งโฟลเดอร์ ราว 5 GB) มาวางข้าง app.py")
        print("  แล้วดับเบิลคลิก start.bat อีกครั้ง - ระบบจะใช้เองอัตโนมัติ")
        print("รายละเอียดเพิ่มเติม: ดู README-ติดตั้งเครื่องใหม่.txt")
        return 1
    print("สรุป: เครื่องนี้วิเคราะห์ภาพได้ปกติ")
    if warns:
        print("(ข้อ WARN ไม่ได้ทำให้ระบบหยุด แต่ควรทราบไว้)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""ตรวจว่าเครื่องใหม่จะเห็นสาเหตุทันที: lib_ok / model_error รายงานถูกต้องหรือไม่

รันด้วย Python ที่มี torch (จะได้ lib_ok True) และคำสั่งตรวจหน้าเว็บจากเซิร์ฟเวอร์จริง
"""
import json
import os
import sys
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import app  # noqa: E402

print("[local] LIB_OK =", app.LIB_OK, "|", app.LIB_NOTE)
print("[local] LIB_ERROR_HINT =", app.LIB_ERROR_HINT[:70], "...")
print("[local] MODEL =", app.MODEL_PATH, "exists =", os.path.isfile(app.MODEL_PATH))

# 1) แบบจำลองเสีย -> ต้องได้ MODEL_ERROR ที่อ่านรู้เรื่อง
orig = app.MODEL_PATH
app.MODEL_PATH = os.path.join(BASE, "__no_model__.pt")
try:
    app.get_model()
    print("[test] FAIL: ไม่เกิด error ทั้งที่ไม่มีไฟล์แบบจำลอง")
except Exception as e:
    print("[test] model missing ->", type(e).__name__, "| MODEL_ERROR =", app.MODEL_ERROR)
app.MODEL_PATH = orig

# 2) /health จากเซิร์ฟเวอร์จริง
try:
    d = json.load(urllib.request.urlopen("http://127.0.0.1:%d/health" % app.PORT, timeout=10))
    keys = ("ok", "model", "model_file", "model_loaded", "lib_ok", "port")
    print("[health]", {k: d.get(k) for k in keys})
    print("[health] model_error =", d.get("model_error"))
except Exception as e:
    print("[health] ไม่ได้ (เซิร์ฟเวอร์ยังรันโค้ดเก่า):", type(e).__name__, e)

# 3) หน้าเว็บมีคู่มือสำหรับกรณี "ไม่มีตัววิเคราะห์" หรือไม่
try:
    html = urllib.request.urlopen("http://127.0.0.1:%d/" % app.PORT, timeout=10).read().decode("utf-8")
    checks = {
        "helpBox": 'id="helpBox"' in html,
        "คำแนะนำตัววิเคราะห์": "ไม่มีตัววิเคราะห์" in html,
        "ชี้ README": "README-ติดตั้งเครื่องใหม่.txt" in html,
        "ลิงก์ live.js": 'src="live.js' in html,
    }
    print("[page]", checks, "chars =", len(html))
    print("[result]", "PASS" if all(checks.values()) else "FAIL")
except Exception as e:
    print("[page] ไม่ได้:", type(e).__name__, e)
    print("[result] FAIL")

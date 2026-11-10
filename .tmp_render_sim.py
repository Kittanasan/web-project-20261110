# -*- coding: utf-8 -*-
"""จำลองสภาพ Render แบบเต็ม: ไม่มี torch/ultralytics/numpy/PIL, PORT จาก env,
stdout เป็น pipe ที่เข้ารหัส latin-1 (แบบที่ Render ใช้) และยิง HTTP จริงไปที่ /health /records /"""
import builtins
import json
import os
import sys
import tempfile
import threading
import traceback
import urllib.request

BLOCK = {"torch", "ultralytics", "numpy", "PIL"}
_real_import = builtins.__import__


def _imp(name, *a, **k):
    root = name.split(".")[0]
    if root in BLOCK:
        raise ModuleNotFoundError("No module named '%s'" % name)
    return _real_import(name, *a, **k)


builtins.__import__ = _imp

TMP = tempfile.mkdtemp(prefix="rendersim_")
os.environ["PORT"] = "10077"
os.environ.pop("LIVER_PORT", None)
os.environ["LIVER_DATA_DIR"] = os.path.join(TMP, "var_data")

# บังคับให้ stdout ของโปรเซสนี้เข้ารหัสแบบที่พิมพ์ไทยไม่ได้ (เหมือน Render)
try:
    sys.stdout.reconfigure(encoding="latin-1", errors="strict")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cloud_app  # noqa: E402

print("IMPORT OK, BUILD =", cloud_app.BUILD_TAG)
print("PORT =", cloud_app.PORT, "HOST =", cloud_app.HOST)
print("LIB_OK =", cloud_app.LIB_OK, "|", cloud_app.LIB_NOTE)


def run():
    cloud_app.main()


th = threading.Thread(target=run, daemon=True)
th.start()
import time  # noqa: E402
time.sleep(1.5)

base = "http://127.0.0.1:%d" % cloud_app.PORT
for path in ("/health", "/records?limit=3", "/"):
    try:
        with urllib.request.urlopen(base + path, timeout=10) as r:
            body = r.read()
            print("[HTTP] %s -> %s (%d bytes)" % (path, r.status, len(body)))
            if path == "/health":
                h = json.loads(body.decode("utf-8"))
                print("   db=%s records=%s build=%s persistent=%s"
                      % (h["db"], h["db_records"], h["build"], h["persistent"]))
    except Exception as e:
        print("[HTTP] %s FAILED: %s: %s" % (path, type(e).__name__, e))

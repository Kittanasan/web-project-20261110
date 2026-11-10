# -*- coding: utf-8 -*-
"""ดูว่าใครถือพอร์ต 8000 อยู่ และหน้าเว็บที่ได้เป็นไฟล์ไหน (ใช้ไลบรารีมาตรฐานเท่านั้น)"""
import json
import os
import sys
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

for p in range(7998, 8004):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/health" % p, timeout=3) as r:
            h = json.loads(r.read().decode("utf-8"))
        print("[health %d]" % p, {k: h.get(k) for k in ("model", "model_file", "lib_ok", "port")})
        with urllib.request.urlopen("http://127.0.0.1:%d/" % p, timeout=5) as r:
            html = r.read().decode("utf-8", "replace")
        print("[page %d] chars=%d APIDEX=%s modelMissing=%s livePort=%s"
              % (p, len(html), "APIDEX" in html,
                 "ไม่พบไฟล์แบบจำลอง liverV1.pt" in html, "live.js?port=%d" % p in html))
    except Exception as e:
        print("[%d] %s: %s" % (p, type(e).__name__, e))

import subprocess
print(subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout.count(":8000"))
out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True).stdout
for ln in out.splitlines():
    if ":8000" in ln and "LISTENING" in ln:
        print("[listen]", ln.strip())
print("[cwd]", os.getcwd())

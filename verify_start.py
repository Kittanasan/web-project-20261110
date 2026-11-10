"""ทดสอบเปิดเซิร์ฟเวอร์ด้วย path เดียวกับที่ start.bat เรียก
(เพื่อพิสูจน์ว่า start.bat ทำให้เครื่องประมวลผลเริ่มทำงานได้จริง)

ใช้: python verify_start.py
"""
import os
import subprocess
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = [
    os.path.join(BASE_DIR, "runtime", "python311", "python.exe"),
    os.path.join(os.environ.get("USERPROFILE", ""), "OneDrive", "Desktop",
                 "นับเหรียญ3", "runtime", "python311", "python.exe"),
    r"C:\Users\Admin\OneDrive\Desktop\นับเหรียญ3\runtime\python311\python.exe",
]


def pick_python():
    for p in CANDIDATES:
        if not os.path.isfile(p):
            continue
        r = subprocess.run([p, "-c", "import ultralytics, torch"], capture_output=True)
        print("[candidate]", p, "->", "OK" if r.returncode == 0 else "missing ultralytics/torch")
        if r.returncode == 0:
            return p
    return None


py = pick_python()
if not py:
    print("[FAIL] ไม่พบ Python ที่มี ultralytics/torch — start.bat จะแสดง error")
    sys.exit(1)

env = dict(os.environ, LIVER_PORT="8099", PYTHONIOENCODING="utf-8")
proc = subprocess.Popen([py, "app.py"], cwd=BASE_DIR, env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                        encoding="utf-8", errors="replace")
ok = False
try:
    for _ in range(40):
        time.sleep(0.5)
        try:
            with urllib.request.urlopen("http://127.0.0.1:8099/health", timeout=2) as r:
                body = r.read().decode("utf-8")
            print("[health] 200", body[:90])
            with urllib.request.urlopen("http://127.0.0.1:8099/", timeout=5) as r:
                page = r.read().decode("utf-8")
            print("[/] chars=", len(page), "| port injected:", "live.js?port=8099" in page)
            ok = ("live.js?port=8099" in page) and ("liverV1.pt" in body)
            break
        except Exception:
            if proc.poll() is not None:
                break
finally:
    proc.terminate()
    try:
        out, err = proc.communicate(timeout=10)
    except Exception:
        out, err = "", ""
    print("[stdout]", (out or "").strip()[:400])
    if (err or "").strip():
        print("[stderr]", err.strip()[:800])

print("\n[result]", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)

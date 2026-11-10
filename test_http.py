import sys, json, io, urllib.request, numpy as np
from PIL import Image
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
BASE = "http://127.0.0.1:8000"

# 1) health
with urllib.request.urlopen(BASE + "/health", timeout=10) as r:
    print("health:", r.status, r.read().decode("utf-8"))

# 2) page loads
with urllib.request.urlopen(BASE + "/", timeout=10) as r:
    html = r.read().decode("utf-8")
print("page:", r.status, "len=", len(html), "has verdict div:", "verdictTop" in html)

# 3) predict via HTTP with a real JPEG payload
rng = np.random.default_rng(1)
arr = (rng.random((480, 640, 3)) * 255).astype("uint8")
buf = io.BytesIO()
Image.fromarray(arr).save(buf, format="JPEG", quality=85)
data = buf.getvalue()

req = urllib.request.Request(BASE + "/predict", data=data, method="POST")
with urllib.request.urlopen(req, timeout=120) as r:
    out = json.loads(r.read().decode("utf-8"))

print("predict status ok:", out.get("ok"))
print("verdict:", out.get("verdict"), "/", out.get("verdict_th"), "/", out.get("confidence_pct"), "%")
print("level_pct:", out.get("level_pct"))
print("detected:", out.get("detected"), "image bytes b64:", len(out.get("image", "")))

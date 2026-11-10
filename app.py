import sys, os, base64, io, threading, json, webbrowser, re, datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote, parse_qs

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if os.path.basename(os.path.dirname(os.path.abspath(__file__))).lower() == "engine" else os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)   # ให้ import db ได้เสมอ แม้รันจากโฟลเดอร์อื่น
MODEL_PATH = os.path.join(BASE, "liverV1.pt")
if not os.path.isfile(MODEL_PATH):
    _alt = os.path.join(BASE, "engine", "liverV1.pt")   # รองรับกรณีวางแบบจำลองใน engine\\ ด้วย
    if os.path.isfile(_alt):
        MODEL_PATH = _alt
EXPORT_DIR = os.path.join(BASE, "exports")
ASSET_DIR = os.path.join(BASE, "assets")
DATA_DIR = os.path.join(BASE, "data")
PORT = int(os.environ.get("LIVER_PORT") or 8000)

# ป้ายเวอร์ชันของโค้ด (ใช้ยืนยันว่าเบราว์เซอร์ได้หน้า/API ชุดล่าสุด ไม่ใช่หน้าเก่าใน cache)
BUILD_TAG = "2026-11-10-db1"

# ฐานข้อมูลกลาง (SQLite ในโฟลเดอร์ data/) — ถ้าเปิดใช้ไม่ได้ ระบบยังทำงานแบบเดิมได้
try:
    import db as store
    STORE_OK = True
    STORE_NOTE = "sqlite %s" % os.path.basename(store.DB_PATH)
except Exception as _e:  # pragma: no cover
    store = None
    STORE_OK = False
    STORE_NOTE = "%s: %s" % (type(_e).__name__, _e)

# ลำดับคลาสของ liverV1.pt (ตรวจจากไฟล์จริง): 0=Hight 1=Low 2=Medium
MODEL_SPEC = {"order": [0, 1, 2], "names": {0: "Hight", 1: "Low", 2: "Medium"}}
LEVELS = ["Hight", "Medium", "Low"]  # เรียงจากดี -> แย่

# คำอธิบายผลการประเมิน (ใช้ทั้งใน API และรายงานที่บันทึก)
LEVEL_INFO = {
    "Hight": {"title": "ตรวจพบเม็ดไขมันมาก", "th": "ระดับสูง", "advice": "ตรวจพบเม็ดไขมันจำนวนมากในเนื้อตับ"},
    "Medium": {"title": "ตรวจพบเม็ดไขมันปานกลาง", "th": "ระดับปานกลาง", "advice": "ตรวจพบเม็ดไขมันในปริมาณปานกลาง"},
    "Low": {"title": "ตรวจพบเม็ดไขมันน้อย", "th": "ระดับต่ำ", "advice": "ตรวจพบเม็ดไขมันในปริมาณน้อย"},
}

MODEL = None
MODEL_LOCK = threading.Lock()

INDEX_HTML = ""


def load_index():
    """หน้าเว็บหลัก: ใช้ Index.html (ไฟล์ที่พร้อมเผยแพร่) ก่อน ถ้าไม่มีจึงใช้ templates/index.html"""
    for rel in (("Index.html",), ("index.html",), ("templates", "index.html")):
        p = os.path.join(BASE, *rel)
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
    MINIMAL_HTML = """<!doctype html><html lang="th"><meta charset="utf-8">
<title>ตรวจสอบสถานะเครื่องประมวลผล</title>
<style>body{font-family:Segoe UI,Tahoma,sans-serif;background:#0b1220;color:#e8eefc;margin:0;padding:32px}
.box{max-width:720px;margin:0 auto;background:#131c31;border:1px solid #2b3a5c;border-radius:14px;padding:24px}
h1{font-size:1.2rem;margin:0 0 12px}code{background:#0b1220;padding:2px 6px;border-radius:6px}
li{margin:6px 0;line-height:1.55}</style>
<div class="box"><h1>เครื่องประมวลผลพร้อมใช้งาน (liverV1.pt)</h1>
<p>แต่ไม่พบไฟล์หน้าเว็บ <code>Index.html</code> ในโฟลเดอร์นี้</p>
<ul><li><a style="color:#7ec8ff" href="/health">/health</a> — ตรวจสถานะเครื่องประมวลผล</li>
<li><a style="color:#7ec8ff" href="/exports">/exports</a> — รายการผลที่บันทึกไว้</li>
<li><code>POST /predict</code> — ส่งภาพเข้าแบบจำลอง</li></ul>
<p>วางไฟล์ <code>Index.html</code> ไว้ข้างไฟล์ <code>app.py</code> แล้วรีเฟรชหน้านี้</p></div>
</html>"""
    return MINIMAL_HTML


def inject_port(html):
    """ใส่พอร์ตจริงลงใน <script src="live.js"> เพื่อให้หน้าเว็บตรวจเครื่องประมวลผลถูกพอร์ต
    (สำคัญเมื่อสั่งรันด้วยพอร์ตอื่น เช่น LIVER_PORT=8100)"""
    if not html:
        return html
    return html.replace('src="live.js"', 'src="live.js?port=%d"' % PORT)


def lib_available():
    """ตรวจว่า Python ที่รันเซิร์ฟเวอร์มีตัววิเคราะห์จริง (torch + ultralytics)

    เครื่องใหม่มักรันด้วย Python ธรรมดาที่ไม่มีไลบรารีนี้ ทำให้กดประเมินแล้วขึ้น
    ข้อผิดพลาดแบบไม่รู้สาเหตุ - ค่าตัวนี้ใช้รายงานบนหน้าเว็บและ /health แทน
    """
    try:
        import ultralytics  # noqa: F401
        import torch  # noqa: F401
        return True, "torch %s / ultralytics %s" % (torch.__version__, ultralytics.__version__)
    except Exception as e:
        return False, "%s: %s" % (type(e).__name__, e)


LIB_OK, LIB_NOTE = lib_available()
MODEL_ERROR = None
LIB_ERROR_HINT = (
    "เครื่องนี้ยังไม่มีตัววิเคราะห์ (torch + ultralytics) ที่ Python นี้ใช้ได้ "
    "ให้ปิดหน้าต่างนี้ แล้วรัน ตรวจสอบระบบ.bat หรืออ่าน README-ติดตั้งเครื่องใหม่.txt"
)


def get_model():
    global MODEL, MODEL_ERROR
    if MODEL is None:
        if not LIB_OK:
            MODEL_ERROR = LIB_ERROR_HINT + " | " + LIB_NOTE
            raise RuntimeError(MODEL_ERROR)
        if not os.path.isfile(MODEL_PATH):
            MODEL_ERROR = ("ไม่พบไฟล์แบบจำลอง %s — คัดลอก liverV1.pt มาวางไว้ข้าง app.py "
                           "(โฟลเดอร์นี้: %s)" % (os.path.basename(MODEL_PATH), BASE))
            print("[error]", MODEL_ERROR, flush=True)
            raise RuntimeError(MODEL_ERROR)
        try:
            from ultralytics import YOLO
            print("[model] loading", MODEL_PATH, flush=True)
            MODEL = YOLO(MODEL_PATH)
            print("[model] ready, classes:", MODEL.names, flush=True)
            MODEL_ERROR = None
        except Exception as e:
            MODEL_ERROR = "%s: %s" % (type(e).__name__, e)
            print("[error] โหลดแบบจำลองไม่สำเร็จ:", MODEL_ERROR, flush=True)
            raise
    return MODEL


def _level_of(name):
    """แปลงชื่อคลาสจากโมเดลเป็นระดับมาตรฐาน Hight / Medium / Low"""
    n = str(name).strip().lower()
    if n.startswith("h") or "high" in n:
        return "Hight"
    if n.startswith("m"):
        return "Medium"
    if n.startswith("l"):
        return "Low"
    return None


def build_verdict(dets):
    """รวมผลทุกกล่องให้เหลือ 'ระดับเดียว' (level_scores) + กล่องหลัก (primary)

    - level_scores: ความมั่นใจสูงสุดของแต่ละระดับ (0-1) ใช้แสดงแถบเปรียบเทียบ
    - primary: กล่องที่มั่นใจที่สุด = ผลวินิจฉัยหลัก
    """
    level_scores = {lv: 0.0 for lv in LEVELS}
    level_hits = {lv: 0 for lv in LEVELS}
    for d in dets:
        lv = d.get("level")
        if lv in level_scores:
            level_hits[lv] += 1
            if d["conf"] > level_scores[lv]:
                level_scores[lv] = d["conf"]

    if dets:
        primary = dets[0]  # dets ถูกเรียงจาก conf มาก -> น้อยแล้ว
        verdict = primary.get("level") or "Medium"
        confidence = primary["conf"]
    else:
        primary = None
        verdict = None
        confidence = 0.0

    return {
        "verdict": verdict,
        "verdict_th": LEVEL_INFO.get(verdict, {}).get("title", "-"),
        "verdict_label": LEVEL_INFO.get(verdict, {}).get("title", "-"),
        "verdict_level_th": LEVEL_INFO.get(verdict, {}).get("th", "-"),
        "confidence": round(confidence, 4),
        "confidence_pct": round(confidence * 100, 1),
        "level_scores": {k: round(v, 4) for k, v in level_scores.items()},
        "level_pct": {k: round(v * 100, 1) for k, v in level_scores.items()},
        "level_hits": level_hits,
        "level_info": LEVEL_INFO,
        "detected": len(dets),
        "primary": primary,
    }


def predict_image(img_bytes):
    import numpy as np
    from PIL import Image

    img = Image.open(io.BytesIO(img_bytes))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    w, h = img.size

    model = get_model()
    with MODEL_LOCK:
        results = model.predict(np.array(img), imgsz=640, conf=0.25, verbose=False)

    r = results[0]
    names = r.names
    dets = []
    if r.boxes is not None and len(r.boxes) > 0:
        for box in r.boxes:
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
            cid = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            name = names.get(cid, str(cid))
            dets.append({
                "cls": cid,
                "name": name,
                "level": _level_of(name),
                "conf": conf,
                "box": [x1 / w, y1 / h, x2 / w, y2 / h],
            })
    dets.sort(key=lambda d: d["conf"], reverse=True)

    verdict = build_verdict(dets)

    annotated = img.convert("RGB")
    if dets:
        try:
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(annotated)
            colors = {0: (34, 211, 238), 1: (255, 95, 109), 2: (255, 176, 32)}
            px_per = min(annotated.size) / 640.0
            font_size = max(14, int(20 * (px_per if px_per > 0 else 1)))
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()
            for d in dets:
                x1, y1, x2, y2 = d["box"][0] * w, d["box"][1] * h, d["box"][2] * w, d["box"][3] * h
                is_primary = verdict["primary"] is not None and d is verdict["primary"]
                c = colors.get(d["cls"], (90, 169, 255))
                draw.rectangle([x1, y1, x2, y2], outline=c,
                               width=max(2, int((4 if is_primary else 2) * max(px_per, 1))))
                label = "%s %.0f%%" % (d["level"] or d["name"], d["conf"] * 100)
                tb = draw.textbbox((0, 0), label, font=font)
                tw, th = tb[2] - tb[0], tb[3] - tb[1]
                ty = max(0, y1 - th - 6)
                draw.rectangle([x1, ty, x1 + tw + 8, ty + th + 6], fill=c)
                draw.text((x1 + 4, ty + 2), label, fill=(10, 17, 32), font=font)
        except Exception as e:
            print("[warn] annotate failed:", e, flush=True)

    buf = io.BytesIO()
    annotated.save(buf, format="JPEG", quality=90)
    img_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    out = {"ok": True, "width": w, "height": h, "detections": dets, "image": img_b64}
    out.update(verdict)
    return out


def _safe_slug(text, fallback="report"):
    s = str(text or "").strip()
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return (s or fallback)[:80]


def list_exports(limit=200):
    """รายการรายงานที่บันทึกไว้ใน exports/ (ใหม่สุดก่อน)"""
    if not os.path.isdir(EXPORT_DIR):
        return []
    items = []
    for name in os.listdir(EXPORT_DIR):
        if not name.lower().endswith(".json"):
            continue
        full = os.path.join(EXPORT_DIR, name)
        img = os.path.splitext(full)[0] + ".jpg"
        info = {}
        try:
            with open(full, "r", encoding="utf-8") as f:
                info = json.load(f)
        except Exception:
            info = {}
        items.append({
            "report": name,
            "image": os.path.basename(img) if os.path.isfile(img) else None,
            "time": os.path.getmtime(full),
            "no": info.get("no"),
            "saved_at": info.get("saved_at"),
            "sample_id": info.get("sample_id", ""),
            "sample_name": info.get("sample_name", ""),
            "farm": info.get("farm", ""),
            "inspector": info.get("inspector", ""),
            "final_result": info.get("final_result", ""),
            "final_confidence_pct": info.get("final_confidence_pct"),
            "edited": bool(info.get("edited")),
        })
    items.sort(key=lambda i: i["time"], reverse=True)
    return items[:limit]


def _next_label():
    """ลำดับที่ของรายการ: ดูเลขมากที่สุดจากรายงานเดิม แล้ว +1"""
    top = 0
    if os.path.isdir(EXPORT_DIR):
        for name in os.listdir(EXPORT_DIR):
            if not name.lower().endswith(".json"):
                continue
            try:
                with open(os.path.join(EXPORT_DIR, name), "r", encoding="utf-8") as f:
                    n = int(json.load(f).get("no") or 0)
                top = max(top, n)
            except Exception:
                continue
    return top + 1


def save_record(payload):
    """บันทึกภาพผลประเมิน + ผลการประเมินลงโฟลเดอร์ exports/"""
    os.makedirs(EXPORT_DIR, exist_ok=True)
    img_b64 = (payload.get("image") or "").split(",")[-1]
    if not img_b64:
        raise ValueError("ไม่พบข้อมูลภาพสำหรับบันทึก")
    try:
        img_bytes = base64.b64decode(img_b64)
    except Exception:
        raise ValueError("ข้อมูลภาพไม่ถูกต้อง")
    if len(img_bytes) > 30 * 1024 * 1024:
        raise ValueError("ภาพใหญ่เกิน 30 MB")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    tag = _safe_slug(payload.get("title") or "report", "report")
    base = "%s_%s" % (stamp, tag)
    img_path = os.path.join(EXPORT_DIR, base + ".jpg")
    with open(img_path, "wb") as f:
        f.write(img_bytes)

    no = _next_label()
    record = {
        "no": no,
        "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "center": "ศูนย์วิจัยและพัฒนาการเพาะเลี้ยงสัตว์น้ำชายฝั่งฉะเชิงเทรา",
        "division": "กรมประมง กระทรวงเกษตรและสหกรณ์",
        "model": os.path.basename(MODEL_PATH),
        "sample_id": payload.get("sampleId") or "",
        "sample_name": payload.get("sampleName") or payload.get("title") or "",
        "farm": payload.get("farm") or "",
        "inspector": payload.get("inspector") or "",
        "note": payload.get("note") or "",
        "image": os.path.basename(img_path),
        "model_result": payload.get("modelResult") or {},
        "model_confidence_pct": payload.get("modelConfidence"),
        "final_result": payload.get("finalResult") or {},
        "final_confidence_pct": payload.get("finalConfidence"),
        "edited": bool(payload.get("edited")),
        "override_note": payload.get("overrideNote") or "",
        "detections": payload.get("detections") or [],
    }
    fin = record["final_result"]
    record["final_result_text"] = (LEVEL_INFO.get(fin) or {}).get("title", "") if isinstance(fin, str) else ""

    rep_path = os.path.join(EXPORT_DIR, base + ".json")
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    out = {
        "ok": True,
        "folder": EXPORT_DIR,
        "no": no,
        "image_file": os.path.basename(img_path),
        "report_file": os.path.basename(rep_path),
        "saved_at": record["saved_at"],
    }

    # 3) บันทึกลงฐานข้อมูลกลาง (data/db.sqlite) เพื่อให้เปิดจากเครื่อง/เบราว์เซอร์อื่นเห็นรายการเดียวกัน
    if STORE_OK:
        try:
            row = store.insert_sample({
                "no": no,
                "saved_at": record["saved_at"],
                "label": record["sample_name"] or record["sample_id"] or tag,
                "sampleName": record["sample_name"],
                "sampleId": record["sample_id"],
                "farm": record["farm"],
                "inspector": record["inspector"],
                "note": record["note"],
                "modelResult": record["model_result"],
                "modelConfidence": record["model_confidence_pct"],
                "finalResult": record["final_result"],
                "finalResultText": record["final_result_text"],
                "finalConfidence": record["final_confidence_pct"],
                "edited": record["edited"],
                "overrideNote": record["override_note"],
                "modelFile": record["model"],
                "detections": len(record["detections"]),
                "imageFile": os.path.basename(img_path),
                "reportFile": os.path.basename(rep_path),
                "client": "web",
            })
            out["db_id"] = row["id"]
            out["no"] = row["no"]
            out["label"] = row["sample_label"]
        except Exception as e:
            print("[warn] บันทึกลงฐานข้อมูลไม่สำเร็จ:", e, flush=True)
            out["db_warning"] = str(e)
    return out


def delete_record(name):
    """ลบรายงาน (.json) พร้อมภาพ (.jpg) ที่บันทึกไว้"""
    name = unquote(str(name or "")).replace("\\", "/")
    if not name or "/" in name or ".." in name:
        raise ValueError("ชื่อไฟล์ไม่ถูกต้อง")
    if not name.lower().endswith(".json"):
        raise ValueError("ลบได้เฉพาะไฟล์รายงาน .json")
    full = os.path.abspath(os.path.join(EXPORT_DIR, name))
    if not full.startswith(os.path.abspath(EXPORT_DIR) + os.sep):
        raise ValueError("ชื่อไฟล์ไม่ถูกต้อง")
    if not os.path.isfile(full):
        raise ValueError("ไม่พบไฟล์รายงานนี้")
    img = os.path.splitext(full)[0] + ".jpg"
    removed = [os.path.basename(full)]
    os.remove(full)
    if os.path.isfile(img):
        os.remove(img)
        removed.append(os.path.basename(img))
    if STORE_OK:
        try:
            store.delete_sample(report_file=os.path.basename(full))
        except Exception as e:
            print("[warn] ลบแถวในฐานข้อมูลไม่สำเร็จ:", e, flush=True)
    return {"ok": True, "removed": removed}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    MIME = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg", ".webp": "image/webp", ".ico": "image/x-icon",
            ".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8"}

    def _serve_file(self, root, rel):
        """ส่งไฟล์จากโฟลเดอร์ที่กำหนด (กัน path traversal)"""
        rel = unquote(rel).replace("\\", "/").lstrip("/")
        if not rel or ".." in rel.split("/"):
            return self._send(403, "forbidden", "text/plain; charset=utf-8")
        full = os.path.abspath(os.path.join(root, rel))
        if not full.startswith(os.path.abspath(root) + os.sep) or not os.path.isfile(full):
            return self._send(404, "not found", "text/plain; charset=utf-8")
        ext = os.path.splitext(full)[1].lower()
        with open(full, "rb") as f:
            self._send(200, f.read(), self.MIME.get(ext, "application/octet-stream"))

    def _serve_asset(self, rel):
        """ส่งไฟล์จากโฟลเดอร์ assets/ เท่านั้น"""
        self._serve_file(ASSET_DIR, rel)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        global INDEX_HTML
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            # อ่านไฟล์หน้าเว็บทุกครั้ง เพื่อให้แก้ Index.html แล้วเห็นผลทันทีโดยไม่ต้องรีสตาร์ต
            INDEX_HTML = load_index()
            self._send(200, inject_port(INDEX_HTML), "text/html; charset=utf-8")
        elif path == "/live.js":
            # สคริปต์ตัวเฝ้าเครื่องประมวลผล (ให้หน้าเว็บเชื่อมต่ออัตโนมัติเมื่อพร้อม)
            p = os.path.join(BASE, "live.js")
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    self._send(200, f.read(), "application/javascript; charset=utf-8")
            else:
                self._send(404, "not found", "text/plain; charset=utf-8")
        elif path == "/favicon.ico":
            self._serve_asset("logo-dof.svg")
        elif path.startswith("/assets/"):
            self._serve_asset(path[len("/assets/"):])
        elif path.startswith("/exports/"):
            # ให้หน้า HTML ดาวน์โหลดภาพผลประเมินที่บันทึกไว้ได้โดยตรง
            self._serve_file(EXPORT_DIR, path[len("/exports/"):])
        elif path in ("/standalone", "/standalone.html", "/liver-eval-standalone.html"):
            # ไฟล์ HTML เดี่ยว (เปิดได้โดยไม่ต้องพึ่งเซิร์ฟเวอร์) ก็เสิร์ฟผ่านเซิร์ฟเวอร์ได้เช่นกัน
            full = os.path.join(BASE, "liver-eval-standalone.html")
            if os.path.isfile(full):
                with open(full, "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            else:
                self._send(404, "not found", "text/plain; charset=utf-8")
        elif path == "/exports":
            self._send(200, json.dumps({"ok": True, "exports": list_exports()}))
        elif path == "/records":
            # ตารางบันทึกผลจากฐานข้อมูลกลาง (เปิดจากเครื่องไหนก็เห็นรายการเดียวกัน)
            qs = parse_qs(urlparse(self.path).query)
            if not STORE_OK:
                self._send(200, json.dumps({"ok": False, "db": False, "store_note": STORE_NOTE,
                                            "records": []}))
            else:
                rows = store.list_samples(
                    limit=int((qs.get("limit") or ["500"])[0] or 500),
                    q=(qs.get("q") or [""])[0],
                    farm=(qs.get("farm") or [""])[0],
                    result=(qs.get("result") or [""])[0])
                self._send(200, json.dumps({"ok": True, "db": True, "store_note": STORE_NOTE,
                                            "count": len(rows), "records": rows},
                                           ensure_ascii=False))
        elif path == "/stats":
            if not STORE_OK:
                self._send(200, json.dumps({"ok": False, "db": False, "store_note": STORE_NOTE}))
            else:
                self._send(200, json.dumps({"ok": True, "db": True, "stats": store.stats()},
                                           ensure_ascii=False))
        elif path == "/farmers":
            # ทะเบียนฟาร์ม (ใช้เติมช่อง "ฟาร์มที่มาของตัวอย่าง")
            qs = parse_qs(urlparse(self.path).query)
            if not STORE_OK:
                self._send(200, json.dumps({"ok": False, "db": False, "store_note": STORE_NOTE,
                                            "farmers": []}))
            else:
                rows = store.search_farmers((qs.get("q") or [""])[0],
                                            int((qs.get("limit") or ["200"])[0] or 200))
                self._send(200, json.dumps({"ok": True, "db": True, "count": len(rows),
                                            "farmers": rows}, ensure_ascii=False))
        elif path == "/health":
            _st = store.stats() if STORE_OK else None
            self._send(200, json.dumps({
                "ok": True,
                "build": BUILD_TAG,
                "model": os.path.basename(MODEL_PATH),
                "model_file": os.path.isfile(MODEL_PATH),
                "model_loaded": MODEL is not None,
                "model_error": MODEL_ERROR,
                "lib_ok": LIB_OK,
                "lib_note": LIB_NOTE,
                "lib_hint": "" if LIB_OK else LIB_ERROR_HINT,
                "port": PORT,
                "levels": LEVELS,
                "level_info": LEVEL_INFO,
                "classes": {str(k): v for k, v in MODEL_SPEC["names"].items()},
                "db": STORE_OK,
                "store": "sqlite",
                "store_note": STORE_NOTE,
                "db_path": store.DB_PATH if STORE_OK else "",
                "db_records": (_st or {}).get("total"),
                "host": os.environ.get("LIVER_HOST") or "127.0.0.1",
            }, ensure_ascii=False))
        else:
            self._send(404, "not found", "text/plain; charset=utf-8")

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/predict", "/save", "/delete", "/records", "/records-update",
                        "/records-delete", "/farmers", "/farmers-delete"):
            return self._send(404, json.dumps({"ok": False, "error": "unknown endpoint"}))
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return self._send(400, json.dumps({"ok": False, "error": "no data received"}))
            if length > 40 * 1024 * 1024:
                return self._send(413, json.dumps({"ok": False, "error": "ข้อมูลใหญ่เกิน 40 MB"}))
            raw = self.rfile.read(length)
            if path == "/predict":
                out = predict_image(raw)
            elif path == "/delete":
                out = delete_record(json.loads(raw.decode("utf-8")).get("name"))
            elif path == "/records":
                if not STORE_OK:
                    raise ValueError("ยังไม่ได้เปิดใช้ฐานข้อมูล: " + STORE_NOTE)
                out = {"ok": True, "record": store.insert_sample(json.loads(raw.decode("utf-8")))}
            elif path == "/records-update":
                if not STORE_OK:
                    raise ValueError("ยังไม่ได้เปิดใช้ฐานข้อมูล: " + STORE_NOTE)
                p = json.loads(raw.decode("utf-8"))
                row = store.update_sample(p.get("id"), p.get("patch") or p.get("fields") or {})
                if row is None:
                    raise ValueError("ไม่พบรายการที่ต้องการแก้ไข")
                out = {"ok": True, "record": row}
            elif path == "/records-delete":
                if not STORE_OK:
                    raise ValueError("ยังไม่ได้เปิดใช้ฐานข้อมูล: " + STORE_NOTE)
                p = json.loads(raw.decode("utf-8"))
                n = store.delete_sample(row_id=p.get("id"), report_file=p.get("report_file"))
                if not n:
                    raise ValueError("ไม่พบรายการที่ต้องการลบ")
                if p.get("report_file"):
                    try:
                        delete_record(p["report_file"])
                    except Exception:
                        pass
                out = {"ok": True, "removed": n}
            elif path == "/farmers":
                if not STORE_OK:
                    raise ValueError("ยังไม่ได้เปิดใช้ฐานข้อมูล: " + STORE_NOTE)
                out = {"ok": True, "farmer": store.add_farmer(json.loads(raw.decode("utf-8")))}
            else:  # /farmers-delete
                if not STORE_OK:
                    raise ValueError("ยังไม่ได้เปิดใช้ฐานข้อมูล: " + STORE_NOTE)
                n = store.delete_farmer(json.loads(raw.decode("utf-8")).get("id"))
                if not n:
                    raise ValueError("ไม่พบฟาร์มที่ต้องการลบ")
                out = {"ok": True, "removed": n}
            self._send(200, json.dumps(out, ensure_ascii=False))
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))


def _listen_busy(host, port):
    """ตรวจว่าพอร์ตถูกใช้อยู่แล้วหรือไม่ (ก่อนเปิดเซิร์ฟเวอร์)

    Windows ยอมให้สองโปรเซสผูกพอร์ตเดียวกันได้ในบางกรณี ทำให้หน้าเว็บสลับไปมาระหว่าง
    เซิร์ฟเวอร์เก่า/ใหม่ (เจอจริง: มี python 2 ตัวถือพอร์ต 8000 พร้อมกัน) จึงตรวจก่อนเสมอ
    """
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(0.5)
        return s.connect_ex((host if host != "0.0.0.0" else "127.0.0.1", port)) == 0
    finally:
        s.close()


class Server(ThreadingHTTPServer):
    # ปิด allow_reuse_address ของ Windows: ถ้าพอร์ตมีคนใช้อยู่ ต้องฟ้อง error ไม่ใช่แชร์พอร์ตกัน
    allow_reuse_address = False
    daemon_threads = True


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    # เตรียมฐานข้อมูลกลาง + นำรายงานเก่าใน exports/ เข้าฐานข้อมูลครั้งแรก
    if STORE_OK:
        try:
            store.init_db()
            added = store.import_legacy_exports(EXPORT_DIR)
            st = store.stats()
            print("[db] %s | รายการในฐานข้อมูล %d แถว | ฟาร์ม %d"
                  % (store.DB_PATH, st["total"], st["farms"]), flush=True)
            if added:
                print("[db] นำเข้ารายการเดิมจาก exports/ เพิ่ม %d รายการ" % added, flush=True)
        except Exception as e:
            print("[warn] เปิดฐานข้อมูลไม่สำเร็จ (ระบบยังใช้งานแบบเดิมได้):", e, flush=True)
    else:
        print("[warn] ไม่ได้ใช้ฐานข้อมูล:", STORE_NOTE, flush=True)
    main_original()


def main_original():
    global INDEX_HTML
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    INDEX_HTML = load_index()
    host = os.environ.get("LIVER_HOST") or "127.0.0.1"
    if not os.path.isfile(MODEL_PATH):
        print("[error] ไม่พบไฟล์แบบจำลอง %s - คัดลอก liverV1.pt มาวางข้าง app.py" % MODEL_PATH, flush=True)
    if not LIB_OK:
        print("[error] เครื่องนี้ยังไม่มีตัววิเคราะห์: %s" % LIB_NOTE, flush=True)
        print("[error] %s" % LIB_ERROR_HINT, flush=True)
        print("[error] ระบบจะเปิดหน้าเว็บให้ตรวจสถานะได้ แต่จะยังประเมินภาพไม่ได้", flush=True)
    if _listen_busy(host, PORT):
        print("[error] พอร์ต %d มีโปรแกรมอื่นใช้อยู่แล้ว - ปิดตัวนั้นก่อน" % PORT, flush=True)
        print("[error] วิธีง่ายที่สุด: ปิดหน้าต่างนี้แล้วดับเบิลคลิก start.bat "
              "(start.bat จะปิดเซิร์ฟเวอร์เก่า/เลือกพอร์ตอื่นให้เอง)", flush=True)
        sys.exit(1)
    try:
        srv = Server((host, PORT), Handler)
    except OSError as e:
        print("[error] เปิดพอร์ต %d ไม่ได้: %s" % (PORT, e), flush=True)
        print("[error] มีเซิร์ฟเวอร์เก่าค้างอยู่ หรือพอร์ตถูกใช้งาน - ปิดตัวเก่าหรือดับเบิลคลิก start.bat", flush=True)
        sys.exit(1)

    print("[server] http://127.0.0.1:%d  (host=%s)  build=%s" % (PORT, host, BUILD_TAG), flush=True)
    if LIB_OK:
        print("[hint] ถ้าหน้าเว็บขึ้นว่าต่อเครื่องประมวลผลไม่ได้ ให้ดูหน้าต่างนี้ว่ามี error หรือไม่", flush=True)
    if "--open" in sys.argv:
        threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:%d/" % PORT)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

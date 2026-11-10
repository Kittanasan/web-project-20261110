# -*- coding: utf-8 -*-
"""cloud_app.py - ตัวรัน "ฝั่งเว็บไซต์" (คลาวด์) ของระบบประเมินเม็ดไขมันในตับ

ใช้เมื่อต้องการเปิดหน้าเว็บให้เข้าจากที่ไหนก็ได้ (Render / Railway / VPS)
โดยทำงานคู่กับ app.py บนเครื่องที่มี torch + liverV1.pt

    เครื่องในศูนย์ (start.bat -> app.py)  = ตัวประเมินภาพ (GPU/CPU + liverV1.pt)
            |  ส่งภาพเข้า /predict
            v
    เว็บไซต์ (cloud_app.py)  = หน้าเว็บ + ฐานข้อมูลกลาง data/db.sqlite + เก็บ exports/

สิ่งที่ cloud_app.py ทำได้เอง
    GET  /                หน้าเว็บ Index.html
    GET  /health          สถานะเครื่อง (บอกว่าไม่ได้โหลดแบบจำลอง)
    GET  /records         ตารางผลตรวจจากฐานข้อมูลกลาง
    POST /records         เพิ่มผลตรวจ (ใช้ได้แม้ไม่เชื่อมเครื่องประมวลผล เช่นกรอกย้อนหลัง)
    POST /records-update  แก้ไขผลตรวจ
    POST /records-delete  ลบผลตรวจ
    GET  /farmers         ทะเบียนฟาร์ม
    POST /farmers         เพิ่มฟาร์ม
    POST /save            บันทึกภาพผลประเมิน + รายงานลง exports/ และฐานข้อมูล
    GET  /exports/...     ดาวน์โหลดภาพผลประเมิน
    POST /predict         ส่งต่อไปยังเครื่องประมวลผลตาม URL ใน env LIVER_ENGINE
                          (หรือใช้แบบจำลองในเครื่องนี้ ถ้ามี torch + liverV1.pt)

ใช้ในเครื่อง:  python cloud_app.py            (พอร์ตจาก LIVER_PORT หรือ 8080)
ใช้บนคลาวด์:   gunicorn แทนไม่ได้เพราะเป็น http.server -> ใช้ Procfile:
               web: python cloud_app.py       (Render กำหนดพอร์ตผ่าน env PORT)
"""
import base64
import datetime
import json
import os
import re
import shutil
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------- stdout ก่อนทุกอย่าง
# บนคลาวด์ (Render/Railway) stdout เป็น pipe ที่ไม่ใช่ UTF-8 ถ้าพิมพ์ข้อความไทยก่อน
# ตั้งค่า encoding จะได้ UnicodeEncodeError แล้วโปรเซสตายทันที (Exited with status 1)
# จึงต้องตั้งค่า และห่อ print ให้ปลอดภัย *ก่อน* คำสั่งอื่นทั้งหมด
for _stream in ("stdout", "stderr"):
    try:
        getattr(sys, _stream).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_raw_print = print


def say(*args, **kwargs):
    """print ที่ไม่ทำให้โปรเซสตายเมื่อคอนโซล/ไพป์เข้ารหัสภาษาไทยไม่ได้"""
    kwargs.setdefault("flush", True)
    try:
        _raw_print(*args, **kwargs)
    except (UnicodeEncodeError, UnicodeError):
        try:
            _raw_print(*[str(a).encode("ascii", "replace").decode("ascii") for a in args], **kwargs)
        except Exception:
            pass
    except Exception:
        pass


print = say   # ให้ print ทุกจุดในไฟล์นี้ปลอดภัย

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)   # ให้ import db / app ได้เสมอ แม้รันจากโฟลเดอร์อื่น

# ที่เก็บข้อมูลจริงบนคลาวด์ (Render Disk) — ถ้าโฮสต์ผูกดิสก์ไว้ที่ /var/data
# ต้องใช้โฟลเดอร์นั้น ไม่งั้นข้อมูลจะหายเมื่อรีสตาร์ต
# ที่เก็บข้อมูลจริงบนคลาวด์ (Render Disk) — ถ้าโฮสต์ผูกดิสก์ไว้ที่ /var/data
# ต้องใช้โฟลเดอร์นั้น ไม่งั้นข้อมูลจะหายเมื่อรีสตาร์ต
# สำคัญ: บน Render บางพาธ (เช่น /var/data บน plan ฟรีที่ไม่มีดิสก์) ดูเหมือนมีอยู่
# และดูเขียนได้ทั้งที่จริงเขียนไม่ได้ (PermissionError) จึงต้องลอง makedirs เอง
# แล้วตรวจผลจริง ถ้าเขียนไม่ได้ให้ตกกลับมาใช้โฟลเดอร์โปรเจกต์แทน (ข้อมูลไม่หาย)
def _make_data_root(preferred):
    if not preferred:
        return None
    cand = os.path.abspath(preferred)
    try:
        os.makedirs(cand, exist_ok=True)
        # ทดสอบเขียนลงจริง ไม่ใช่แค่เดา
        _probe = os.path.join(cand, ".write_probe")
        with open(_probe, "w", encoding="utf-8") as _f:
            _f.write("ok")
        os.remove(_probe)
        return cand
    except Exception:
        try:
            # ยังพอมีโอกาสเป็นจุดเช็กเขียนไม่ได้แต่โฟลเดอร์ใช้ได้ (เช่น PermissionError
            # จริงแค่ตอน makedirs) — ลองอีกครั้งแบบเงียบ ก่อนถือว่าใช้ไม่ได้
            os.makedirs(cand, exist_ok=True)
            return cand
        except Exception:
            return None


DATA_ROOT = _make_data_root(os.environ.get("LIVER_DATA_DIR") or "/var/data")
if DATA_ROOT is None:
    # เขียน /var/data ไม่ได้ (Render ฟรีไม่มีดิสก์) -> ใช้โฟลเดอร์โปรเจกต์ใน HOME
    DATA_ROOT = _make_data_root(BASE) or BASE

EXPORT_DIR = os.path.join(DATA_ROOT, "exports")
ASSET_DIR = os.path.join(BASE, "assets")
if DATA_ROOT != BASE:
    # ย้ายข้อมูลตั้งต้น (ฐานข้อมูล + ภาพผลตรวจ) ขึ้นดิสก์คลาวด์ครั้งแรกเท่านั้น
    try:
        _src_db = os.path.join(BASE, "data", "db.sqlite")
        _dst_db = os.path.join(DATA_ROOT, "data", "db.sqlite")
        if os.path.isfile(_src_db) and not os.path.isfile(_dst_db):
            os.makedirs(os.path.dirname(_dst_db), exist_ok=True)
            shutil.copy2(_src_db, _dst_db)
            print("[data] คัดลอกฐานข้อมูลตั้งต้นขึ้นดิสก์คลาวด์แล้ว", flush=True)
        _src_ex = os.path.join(BASE, "exports")
        if not os.path.isdir(EXPORT_DIR) and os.path.isdir(_src_ex):
            shutil.copytree(_src_ex, EXPORT_DIR, dirs_exist_ok=True)
            print("[data] คัดลอกภาพผลตรวจเดิมขึ้นดิสก์คลาวด์แล้ว", flush=True)
    except Exception as _e:
        print("[data] คัดลอกข้อมูลตั้งต้นไม่สำเร็จ:", _e, flush=True)

MODEL_PATH = os.path.join(BASE, "liverV1.pt")
if not os.path.isfile(MODEL_PATH):
    _alt = os.path.join(BASE, "engine", "liverV1.pt")   # แบบจำลองอาจอยู่ในโฟลเดอร์ engine/
    if os.path.isfile(_alt):
        MODEL_PATH = _alt

# พอร์ต: บนคลาวด์ (Render/Railway) ส่งมาทาง env PORT
PORT = int(os.environ.get("LIVER_PORT") or os.environ.get("PORT") or 8080)
HOST = os.environ.get("LIVER_HOST") or ("0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
# URL ของเครื่องประมวลผล (app.py) เช่น https://xxx.trycloudflare.com
ENGINE_URL = (os.environ.get("LIVER_ENGINE") or "").rstrip("/")
# รหัสผ่านสำหรับแก้/ลบข้อมูล (ถ้าตั้งไว้ หน้าเว็บจะต้องกรอก)
SECRET = os.environ.get("LIVER_SECRET") or ""

BUILD_TAG = "2026-11-11-cloud4"

try:
    import db as store
    # บนคลาวด์ (มีดิสก์ /var/data) ต้องเก็บฐานข้อมูลไว้บนดิสก์ ไม่ใช่ในโค้ดที่ deploy
    if DATA_ROOT != BASE:
        store.DATA_DIR = os.path.join(DATA_ROOT, "data")
        store.DB_PATH = os.path.join(store.DATA_DIR, "db.sqlite")
    STORE_OK = True
    STORE_NOTE = "sqlite %s" % store.DB_PATH
except Exception as _e:  # pragma: no cover
    store = None
    STORE_OK = False
    STORE_NOTE = "%s: %s" % (type(_e).__name__, _e)

LEVELS = ["Hight", "Medium", "Low"]
LEVEL_INFO = {
    "Hight": {"title": "ตรวจพบเม็ดไขมันมาก", "th": "ระดับสูง"},
    "Medium": {"title": "ตรวจพบเม็ดไขมันปานกลาง", "th": "ระดับปานกลาง"},
    "Low": {"title": "ตรวจพบเม็ดไขมันน้อย", "th": "ระดับต่ำ"},
}

_local_model = None
_local_model_error = None
_lock = threading.Lock()


# --------------------------------------------------------------------------
# ตัวช่วย
# --------------------------------------------------------------------------
def local_lib_ok():
    try:
        import ultralytics  # noqa: F401
        return True, "ultralytics %s" % getattr(ultralytics, "__version__", "?")
    except Exception as e:
        return False, "%s: %s" % (type(e).__name__, e)


LIB_OK, LIB_NOTE = local_lib_ok()


def engine_status(timeout=2.5):
    """ถามเครื่องประมวลผลปลายทาง (ถ้าตั้ง LIVER_ENGINE ไว้)"""
    if not ENGINE_URL:
        return None
    try:
        with urllib.request.urlopen(ENGINE_URL + "/health", timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}


def predict_local(img_bytes):
    """ประเมินภาพด้วยแบบจำลองในเครื่องนี้ (เฉพาะเมื่อมี torch + liverV1.pt)"""
    global _local_model, _local_model_error
    if not LIB_OK:
        raise RuntimeError("เซิร์ฟเวอร์นี้ไม่ได้ติดตั้ง torch/ultralytics: " + LIB_NOTE)
    if not os.path.isfile(MODEL_PATH):
        raise RuntimeError("ไม่พบไฟล์แบบจำลอง %s บนเซิร์ฟเวอร์นี้" % os.path.basename(MODEL_PATH))
    with _lock:
        if _local_model is None:
            from ultralytics import YOLO
            _local_model = YOLO(MODEL_PATH)
        model = _local_model
    # ใช้ตัวประมวลผลชุดเดียวกับ app.py เพื่อให้ผลตรงกัน
    import app as local_engine
    local_engine.MODEL = model
    return local_engine.predict_image(img_bytes)


def predict_remote(img_bytes):
    """ส่งภาพไปให้เครื่องประมวลผล (app.py) แล้วคืนผลลัพธ์"""
    if not ENGINE_URL:
        raise RuntimeError(
            "ยังไม่ได้เชื่อมเครื่องประมวลผล — ตั้งค่า LIVER_ENGINE ให้ชี้ไปที่เครื่องที่รัน start.bat "
            "หรือติดตั้ง torch + liverV1.pt บนเซิร์ฟเวอร์นี้")
    req = urllib.request.Request(ENGINE_URL + "/predict", data=img_bytes,
                                 headers={"Content-Type": "application/octet-stream"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError("เครื่องประมวลผลตอบ %s: %s" % (e.code, body[:300]))
    except Exception as e:
        raise RuntimeError("ติดต่อเครื่องประมวลผลไม่ได้ (%s): %s" % (ENGINE_URL, e))


def load_index():
    for rel in (("templates", "index.html"), ("index.html",), ("Index.html",)):
        p = os.path.join(BASE, *rel)
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
    return "<!doctype html><meta charset=utf-8><h1>ไม่พบไฟล์ Index.html</h1>"


def inject_config(html):
    """ใส่ค่าตั้งต้นให้หน้าเว็บ: พอร์ต + ที่อยู่เครื่องประมวลผล (ถ้ามี)"""
    if not html:
        return html
    html = html.replace('src="live.js"', 'src="live.js?port=%d"' % PORT)
    if ENGINE_URL:
        cfg = ('<script>window.LIVER_ENGINE=%s;</script>'
               % json.dumps(ENGINE_URL))
        html = html.replace("</head>", cfg + "\n</head>", 1)
    return html


def _safe_slug(text, fallback="report"):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", str(text or "").strip())
    s = re.sub(r"\s+", " ", s).strip(" .")
    return (s or fallback)[:80]


def _next_no():
    top = 0
    if os.path.isdir(EXPORT_DIR):
        for name in os.listdir(EXPORT_DIR):
            if not name.lower().endswith(".json"):
                continue
            try:
                with open(os.path.join(EXPORT_DIR, name), "r", encoding="utf-8") as f:
                    top = max(top, int(json.load(f).get("no") or 0))
            except Exception:
                continue
    if STORE_OK:
        try:
            top = max(top, store.next_no() - 1)
        except Exception:
            pass
    return top + 1


def save_report(payload):
    """บันทึกภาพ + รายงาน และเพิ่มแถวในฐานข้อมูล — ทำงานได้บนคลาวด์

    สำคัญ: ไม่ import app.py ที่นี่ เพราะ app.py ต้องใช้ numpy/PIL และอาจลาก torch
    ทำให้เซิร์ฟเวอร์คลาวด์ที่ติดตั้งแค่ Python ธรรมดาบันทึกผลไม่ได้
    """
    img_b64 = str(payload.get("image") or "").split(",")[-1].strip()
    no = _next_no()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    tag = _safe_slug(payload.get("title") or payload.get("sampleId") or "report", "report")
    saved_at = datetime.datetime.now().isoformat(timespec="seconds")
    image_file = ""
    report_file = ""

    if img_b64:
        try:
            img_bytes = base64.b64decode(img_b64)
        except Exception:
            raise ValueError("ข้อมูลภาพไม่ถูกต้อง")
        if len(img_bytes) > 30 * 1024 * 1024:
            raise ValueError("ภาพใหญ่เกิน 30 MB")
        os.makedirs(EXPORT_DIR, exist_ok=True)
        base = "%s_%s" % (stamp, tag)
        with open(os.path.join(EXPORT_DIR, base + ".jpg"), "wb") as f:
            f.write(img_bytes)
        fin = payload.get("finalResult") or ""
        record = {
            "no": no,
            "saved_at": saved_at,
            "center": "ศูนย์วิจัยและพัฒนาการเพาะเลี้ยงสัตว์น้ำชายฝั่งฉะเชิงเทรา",
            "division": "กรมประมง กระทรวงเกษตรและสหกรณ์",
            "model": os.path.basename(MODEL_PATH),
            "sample_id": payload.get("sampleId") or "",
            "sample_name": payload.get("sampleName") or payload.get("title") or "",
            "farm": payload.get("farm") or "",
            "inspector": payload.get("inspector") or "",
            "note": payload.get("note") or "",
            "image": base + ".jpg",
            "model_result": payload.get("modelResult") or "",
            "model_confidence_pct": payload.get("modelConfidence"),
            "final_result": fin,
            "final_confidence_pct": payload.get("finalConfidence"),
            "edited": bool(payload.get("edited")),
            "override_note": payload.get("overrideNote") or "",
            "detections": payload.get("detections") or [],
            "final_result_text": (LEVEL_INFO.get(fin) or {}).get("title", "") if isinstance(fin, str) else "",
        }
        with open(os.path.join(EXPORT_DIR, base + ".json"), "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        image_file = base + ".jpg"
        report_file = base + ".json"

    if not STORE_OK:
        raise ValueError("ยังไม่ได้เปิดใช้ฐานข้อมูล: " + STORE_NOTE)
    row = store.insert_sample({
        "no": no,
        "saved_at": saved_at,
        "label": payload.get("sampleName") or payload.get("sampleId") or payload.get("title"),
        "sampleName": payload.get("sampleName") or payload.get("title"),
        "sampleId": payload.get("sampleId"),
        "farm": payload.get("farm"),
        "inspector": payload.get("inspector"),
        "note": payload.get("note"),
        "modelResult": payload.get("modelResult"),
        "modelConfidence": payload.get("modelConfidence"),
        "finalResult": payload.get("finalResult"),
        "finalResultText": (LEVEL_INFO.get(payload.get("finalResult")) or {}).get("title", ""),
        "finalConfidence": payload.get("finalConfidence"),
        "edited": payload.get("edited"),
        "overrideNote": payload.get("overrideNote"),
        "modelFile": os.path.basename(MODEL_PATH),
        "detections": len(payload.get("detections") or []),
        "imageFile": image_file,
        "reportFile": report_file,
        "client": "cloud",
    })
    return {"ok": True, "folder": EXPORT_DIR, "no": row["no"], "label": row["sample_label"],
            "record": row, "image_file": image_file, "report_file": report_file,
            "saved_at": saved_at, "db_id": row["id"]}


def delete_files(name):
    """ลบรายงาน .json พร้อมภาพ .jpg ใน exports/ (ใช้ได้บนคลาวด์)"""
    name = urllib.parse.unquote(str(name or "")).replace("\\", "/")
    if not name or "/" in name or ".." in name or not name.lower().endswith(".json"):
        raise ValueError("ชื่อไฟล์ไม่ถูกต้อง (ต้องเป็นไฟล์รายงาน .json)")
    full = os.path.abspath(os.path.join(EXPORT_DIR, name))
    if not full.startswith(os.path.abspath(EXPORT_DIR) + os.sep):
        raise ValueError("ชื่อไฟล์ไม่ถูกต้อง")
    removed = []
    for p in (full, os.path.splitext(full)[0] + ".jpg"):
        if os.path.isfile(p):
            os.remove(p)
            removed.append(os.path.basename(p))
    return {"ok": True, "removed": removed}


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "LiverCloud/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[cloud] %s\n" % (fmt % args))

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Liver-Secret")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    MIME = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg", ".webp": "image/webp", ".ico": "image/x-icon",
            ".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8"}

    def _serve_file(self, root, rel):
        rel = urllib.parse.unquote(rel).replace("\\", "/").lstrip("/")
        if not rel or ".." in rel.split("/"):
            return self._send(403, "forbidden", "text/plain; charset=utf-8")
        full = os.path.abspath(os.path.join(root, rel))
        if not full.startswith(os.path.abspath(root) + os.sep) or not os.path.isfile(full):
            return self._send(404, "not found", "text/plain; charset=utf-8")
        with open(full, "rb") as f:
            self._send(200, f.read(), self.MIME.get(os.path.splitext(full)[1].lower(),
                                                    "application/octet-stream"))

    def _authorized(self):
        if not SECRET:
            return True
        return (self.headers.get("X-Liver-Secret") or "") == SECRET

    def do_OPTIONS(self):
        self._send(204, b"", "text/plain; charset=utf-8")

    def do_GET(self):
        path = urlparse(self.path).path
        qs = parse_qs(urlparse(self.path).query)
        if path in ("/", "/index.html"):
            return self._send(200, inject_config(load_index()), "text/html; charset=utf-8")
        if path == "/live.js":
            p = os.path.join(BASE, "live.js")
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    return self._send(200, f.read(), "application/javascript; charset=utf-8")
            return self._send(404, "not found", "text/plain; charset=utf-8")
        if path == "/favicon.ico":
            return self._serve_file(ASSET_DIR, "logo-dof.svg")
        if path.startswith("/assets/"):
            return self._serve_file(ASSET_DIR, path[len("/assets/"):])
        if path.startswith("/exports/"):
            return self._serve_file(EXPORT_DIR, path[len("/exports/"):])
        if path == "/health":
            eng = engine_status()
            return self._json({
                "ok": True,
                "build": BUILD_TAG,
                "mode": "cloud",
                "model": os.path.basename(MODEL_PATH),
                "model_file": os.path.isfile(MODEL_PATH),
                "model_loaded": _local_model is not None,
                "model_error": _local_model_error,
                "lib_ok": LIB_OK,
                "lib_note": LIB_NOTE,
                "lib_hint": "" if LIB_OK else
                ("เว็บไซต์นี้ทำงานแบบฐานข้อมูลกลาง ภาพจะถูกประเมินโดยเครื่องที่รัน start.bat "
                 "(ตั้งค่า LIVER_ENGINE)"),
                "engine_url": ENGINE_URL,
                "engine": eng,
                "port": PORT,
                "levels": LEVELS,
                "level_info": LEVEL_INFO,
                "db": STORE_OK,
                "store": "sqlite",
                "store_note": STORE_NOTE,
                "db_path": store.DB_PATH if STORE_OK else "",
                "data_dir": DATA_ROOT,
                "persistent": DATA_ROOT != BASE,
                "db_records": (store.stats()["total"] if STORE_OK else None),
                "need_secret": bool(SECRET),
            })
        if path == "/stats":
            if not STORE_OK:
                return self._json({"ok": False, "db": False, "store_note": STORE_NOTE})
            return self._json({"ok": True, "db": True, "stats": store.stats(),
                               "engine_url": ENGINE_URL})
        if path == "/records":
            if not STORE_OK:
                return self._json({"ok": False, "db": False, "store_note": STORE_NOTE,
                                   "records": []})
            rows = store.list_samples(
                limit=int((qs.get("limit") or ["500"])[0] or 500),
                q=(qs.get("q") or [""])[0],
                farm=(qs.get("farm") or [""])[0],
                result=(qs.get("result") or [""])[0])
            return self._json({"ok": True, "db": True, "count": len(rows), "records": rows})
        if path == "/farmers":
            if not STORE_OK:
                return self._json({"ok": False, "db": False, "farmers": []})
            rows = store.search_farmers((qs.get("q") or [""])[0],
                                        int((qs.get("limit") or ["200"])[0] or 200))
            return self._json({"ok": True, "count": len(rows), "farmers": rows})
        if path == "/exports":
            idx = []
            if os.path.isdir(EXPORT_DIR):
                for n in sorted(os.listdir(EXPORT_DIR), reverse=True):
                    if n.lower().endswith(".json"):
                        idx.append({"report": n,
                                    "image": os.path.splitext(n)[0] + ".jpg"})
            return self._json({"ok": True, "exports": idx})
        return self._send(404, "not found", "text/plain; charset=utf-8")

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return self._json({"ok": False, "error": "no data received"}, 400)
            if length > 40 * 1024 * 1024:
                return self._json({"ok": False, "error": "ข้อมูลใหญ่เกิน 40 MB"}, 413)
            raw = self.rfile.read(length)

            # ---- ประเมินภาพ: ส่งต่อเครื่องประมวลผล หรือใช้แบบจำลองในเครื่องนี้ ----
            if path == "/predict":
                if ENGINE_URL:
                    return self._json(predict_remote(raw))
                if LIB_OK and os.path.isfile(MODEL_PATH):
                    return self._json(predict_local(raw))

                raise RuntimeError(
                    "ยังไม่ได้เชื่อมเครื่องประมวลผล — เว็บนี้ทำงานแบบฐานข้อมูลกลาง "
                    "ภาพจะถูกประเมินโดยเครื่องที่รัน start.bat (LIVER_ENGINE). "
                    "ขั้นตอน: 1) เปิด start.bat บนเครื่องที่มี liverV1.pt + torch "
                    "2) รัน cloud_engine.bat เพื่อเปิดท่อส่งภาพจากเครื่องขึ้นคลาวด์ "
                    "3) ตั้งค่า LIVER_ENGINE บน Render ให้เป็น URL ที่ได้"
                    + (" (%s)" % LIB_NOTE if not LIB_OK else ""))

            if not self._authorized():
                return self._json({"ok": False, "error": "ต้องใส่รหัสผ่าน (LIVER_SECRET) ก่อนแก้/ลบข้อมูล",
                                   "need_secret": True}, 401)

            data = json.loads(raw.decode("utf-8"))

            if path == "/save":
                return self._json(save_report(data))
            if path == "/records":
                if not STORE_OK:
                    raise ValueError("ยังไม่ได้เปิดใช้ฐานข้อมูล: " + STORE_NOTE)
                return self._json({"ok": True, "record": store.insert_sample(data)})
            if path == "/records-update":
                if not STORE_OK:
                    raise ValueError("ยังไม่ได้เปิดใช้ฐานข้อมูล: " + STORE_NOTE)
                row = store.update_sample(data.get("id"), data.get("patch") or data.get("fields") or {})
                if row is None:
                    raise ValueError("ไม่พบรายการที่ต้องการแก้ไข")
                return self._json({"ok": True, "record": row})
            if path == "/records-delete":
                if not STORE_OK:
                    raise ValueError("ยังไม่ได้เปิดใช้ฐานข้อมูล: " + STORE_NOTE)
                n = store.delete_sample(row_id=data.get("id"),
                                        report_file=data.get("report_file"))
                if not n:
                    raise ValueError("ไม่พบรายการที่ต้องการลบ")
                if data.get("report_file"):
                    try:
                        delete_files(data["report_file"])
                    except Exception:
                        pass
                return self._json({"ok": True, "removed": n})
            if path == "/delete":
                return self._json(delete_files(data.get("name")))
            if path == "/farmers":
                if not STORE_OK:
                    raise ValueError("ยังไม่ได้เปิดใช้ฐานข้อมูล: " + STORE_NOTE)
                return self._json({"ok": True, "farmer": store.add_farmer(data)})
            if path == "/farmers-delete":
                if not STORE_OK:
                    raise ValueError("ยังไม่ได้เปิดใช้ฐานข้อมูล: " + STORE_NOTE)
                n = store.delete_farmer(data.get("id"))
                if not n:
                    raise ValueError("ไม่พบฟาร์มที่ต้องการลบ")
                return self._json({"ok": True, "removed": n})
            return self._json({"ok": False, "error": "unknown endpoint"}, 404)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._json({"ok": False, "error": str(e)}, 500)


def _serve_cloud_dir(port):
    """เปิดโฟลเดอร์โปรเจกต์นี้ (มุมมองจากเครื่องในศูนย์) ให้คลาวด์เรียกผ่านท่อได้

    รับเฉพาะ path ที่อยู่ในรายการขาว: /predict /health /save /delete /engine-health
    เพื่อไม่ให้เครื่องในศูนย์เปิดเผยไฟล์ทั้งหมด (เช่น .env, liverV1.pt) ออกอินเทอร์เน็ต
    """
    allowed = {"/predict", "/health", "/save", "/delete", "/engine-health", "/exports"}
    state = {"model": None, "error": None}

    def predict_local_bytes(img_bytes):
        if state["model"] is None:
            from ultralytics import YOLO
            state["model"] = YOLO(os.path.join(BASE, "liverV1.pt"))
        import app as local_engine          # ใช้ตัวประมวลผลชุดเดียวกับ app.py
        local_engine.MODEL = state["model"]
        return local_engine.predict_image(img_bytes)

    def save_bytes(payload):
        return save_report(payload)

    def delete_names(payload):
        return delete_files(payload.get("name"))

    def health():
        return {
            "ok": True, "mode": "engine", "build": BUILD_TAG,
            "host": os.uname().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", ""),
            "lib_ok": LIB_OK, "lib_note": LIB_NOTE,
            "model_file": os.path.isfile(os.path.join(BASE, "liverV1.pt")),
            "model_loaded": state["model"] is not None,
            "engine_ready": bool(LIB_OK and os.path.isfile(os.path.join(BASE, "liverV1.pt"))),
            "port": port,
        }

    class Bridge(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            say("[engine]", fmt % args)

        def _json(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            p = urlparse(self.path).path
            if p in ("/health", "/engine-health"):
                return self._json(health())
            if p == "/":
                return self._json({"ok": True, "service": "liver engine bridge",
                                   "endpoints": sorted(allowed)})
            return self._json({"ok": False, "error": "not allowed"}, 403)

        def do_POST(self):
            p = urlparse(self.path).path
            if p not in allowed:
                return self._json({"ok": False, "error": "not allowed"}, 403)
            try:
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n) if n > 0 else b""
                if p == "/predict":
                    if not raw:
                        return self._json({"ok": False, "error": "no image"}, 400)
                    return self._json(predict_local_bytes(raw))
                if p == "/save":
                    return self._json(save_bytes(json.loads(raw.decode("utf-8"))))
                if p == "/delete":
                    return self._json(delete_names(json.loads(raw.decode("utf-8"))))
                return self._json({"ok": True})
            except Exception as e:
                import traceback
                traceback.print_exc()
                return self._json({"ok": False, "error": "%s: %s" % (type(e).__name__, e)}, 500)

    srv = ThreadingHTTPServer(("0.0.0.0", port), Bridge)
    srv.daemon_threads = True
    say("[engine] ท่อส่งภาพพร้อม: http://0.0.0.0:%d  (ให้คลาวด์เรียกผ่าน URL สาธารณะ)" % port)
    h = health()
    say("[engine] lib_ok=%s model_file=%s" % (h["lib_ok"], h["model_file"]))
    if not h["engine_ready"]:
        say("[engine] ยังประเมินไม่ได้:", LIB_NOTE)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


class Server(ThreadingHTTPServer):
    allow_reuse_address = True     # บนคลาวด์ตัวจัดการพอร์ตให้แล้ว
    daemon_threads = True


def main():
    if STORE_OK:
        try:
            store.init_db()
            added = store.import_legacy_exports(EXPORT_DIR)
            st = store.stats()
            print("[db] %s | %d แถว | ฟาร์ม %d" % (store.DB_PATH, st["total"], st["farms"]), flush=True)
            if added:
                print("[db] นำเข้า exports/ เพิ่ม %d รายการ" % added, flush=True)
        except Exception as e:
            print("[warn] เปิดฐานข้อมูลไม่สำเร็จ:", e, flush=True)
    print("[cloud] http://%s:%d  build=%s" % (HOST, PORT, BUILD_TAG), flush=True)
    print("[cloud] เครื่องประมวลผล (LIVER_ENGINE): %s" % (ENGINE_URL or "ไม่ได้ตั้งค่า"), flush=True)
    if not LIB_OK and not ENGINE_URL:
        print("[cloud] หมายเหตุ: เซิร์ฟเวอร์นี้ยังไม่เชื่อมเครื่องประมวลผล "
              "-> ใช้บันทึก/แก้/ลบข้อมูลและตารางผลได้ แต่ยังประเมินภาพไม่ได้", flush=True)
    srv = Server((HOST, PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    _mode = (os.environ.get("LIVER_MODE") or "").strip().lower()
    if "--engine" in sys.argv or _mode == "engine":
        _ep = int(os.environ.get("LIVER_ENGINE_PORT") or
                  os.environ.get("ENGINE_PORT") or 9000)
        _serve_cloud_dir(_ep)
    else:
        main()

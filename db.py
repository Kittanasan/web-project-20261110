# -*- coding: utf-8 -*-
"""ฐานข้อมูลกลางของระบบประเมินเม็ดไขมันในตับ (ใช้ร่วมกับ app.py)

ทำไมต้องใช้ SQLite: ระบบเดิมเก็บรายการไว้ใน localStorage ของเบราว์เซอร์แต่ละเครื่อง
ทำให้เปิดจากเครื่องอื่น/เบราว์เซอร์อื่นแล้วไม่เห็นรายการเดิม และปิดเบราว์เซอร์ก็หาย
ไฟล์นี้ทำให้ข้อมูลอยู่ที่โฟลเดอร์กลาง data/data.db (ไม่ต้องติดตั้ง MySQL/Postgres)

มี 2 ตาราง
  samples  = ทะเบียนผลตรวจและผลการประเมิน/แก้ไข (ใช้ในตารางบันทึกผล)
  farmers  = ทะเบียนเกษตรกร (ฟาร์ม) ใช้เลือกในช่อง "ฟาร์มที่มาของตัวอย่าง"
และมีตาราง metadata เก็บเวอร์ชันสูตรฐานข้อมูล (schema) ไว้ตรวจ/อัปเดต
"""
import datetime
import os
import re
import sqlite3
import threading

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
DB_PATH = os.path.join(DATA_DIR, "db.sqlite")
SCHEMA_VERSION = 1

LOCK = threading.Lock()

LEVELS = ("Hight", "Medium", "Low")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS samples (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    no                INTEGER,
    saved_at          TEXT NOT NULL,           -- ISO8601 เวลาบันทึก
    sample_label      TEXT NOT NULL,           -- ลำดับที่ / label ตัวอย่าง (เช่น CC-AQ-2569-001)
    sample_name       TEXT,
    sample_code       TEXT,                    -- รหัสตัวอย่าง (sample id) ถ้ามี
    farm              TEXT,                    -- ฟาร์มที่มาของตัวอย่าง
    farmer_id         INTEGER,                 -- อ้างถึง farmers.id (ถ้าเลือกจากทะเบียน)
    inspector         TEXT,                    -- ชื่อผู้ตรวจวิเคราะห์
    note              TEXT,
    model_result      TEXT,                    -- ผลของแบบจำลอง (Hight/Medium/Low)
    model_confidence  REAL,                    -- % ความเชื่อมั่นของแบบจำลอง
    final_result      TEXT,                    -- ผลที่เจ้าหน้าที่ยืนยัน
    final_result_text TEXT,                    -- ข้อความไทยของผลสุดท้าย
    final_confidence  REAL,                    -- % ความเชื่อมั่นของผลสุดท้าย
    edited            INTEGER DEFAULT 0,       -- 1 = เจ้าหน้าที่แก้ผลจากที่แบบจำลองให้
    override_note     TEXT,                    -- เหตุผลการแก้ผล
    model_file        TEXT,                    -- liverV1.pt
    detections        INTEGER DEFAULT 0,       -- จำนวนจุดที่ตรวจพบ
    image_file        TEXT,                    -- ภาพผลประเมิน (.jpg ใน exports/)
    report_file       TEXT,                    -- ไฟล์รายงาน (.json ใน exports/)
    client            TEXT DEFAULT 'web',      -- ที่มาของรายการ (web / api / import)
    created_at        TEXT NOT NULL            -- เวลาที่แถวถูกสร้างในฐานข้อมูล
);

CREATE TABLE IF NOT EXISTS farmers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,         -- ชื่อฟาร์ม
    owner_name   TEXT,                         -- ชื่อเกษตรกร/ผู้ประกอบการ
    address      TEXT,
    subdistrict  TEXT,
    district     TEXT,
    province     TEXT,
    phone        TEXT,
    reg_no       TEXT,                         -- เลขทะเบียนฟาร์ม/ใบอนุญาต
    species      TEXT,                         -- ชนิดสัตว์น้ำที่เลี้ยง
    note         TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_samples_saved_at ON samples(saved_at);
CREATE INDEX IF NOT EXISTS idx_samples_farm ON samples(farm);
CREATE INDEX IF NOT EXISTS idx_samples_label ON samples(sample_label);
CREATE UNIQUE INDEX IF NOT EXISTS idx_samples_label_unique ON samples(sample_label);
"""

FARMER_SEED = [
    # ชื่อฟาร์ม, เจ้าของ, ตำบล, อำเภอ, จังหวัด, เลขทะเบียน, ชนิดสัตว์น้ำ
    ("ฟาร์มตัวอย่างทดสอบ (ศูนย์วิจัยฯ)", "ศูนย์วิจัยและพัฒนาการเพาะเลี้ยงสัตว์น้ำชายฝั่งฉะเชิงเทรา",
     "บางปะกง", "บางปะกง", "ฉะเชิงเทรา", "-", "ปลากะพงขาว"),
]


def _connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def init_db(seed=True):
    """สร้างตารางถ้ายังไม่มี + คัดลอกข้อมูลจาก exports/*.json มาใส่ครั้งแรก"""
    with LOCK:
        conn = _connect()
        try:
            conn.executescript(SCHEMA_SQL)
            cur = conn.execute("SELECT value FROM meta WHERE key='schema_version'")
            row = cur.fetchone()
            if row is None:
                conn.execute("INSERT INTO meta(key,value) VALUES('schema_version',?)",
                             (str(SCHEMA_VERSION),))
            else:
                conn.execute("UPDATE meta SET value=? WHERE key='schema_version'",
                             (str(SCHEMA_VERSION),))
            if seed:
                n = conn.execute("SELECT COUNT(*) AS c FROM farmers").fetchone()["c"]
                if n == 0:
                    for f in FARMER_SEED:
                        conn.execute(
                            "INSERT OR IGNORE INTO farmers(name,owner_name,subdistrict,district,"
                            "province,reg_no,species,created_at) VALUES(?,?,?,?,?,?,?,?)",
                            f[:6] + (f[6], _now()))
            conn.commit()
        finally:
            conn.close()
    return DB_PATH


def import_legacy_exports(export_dir):
    """นำรายงานเก่าใน exports/*.json เข้าฐานข้อมูล (ข้ามรายการที่มี label ซ้ำ)"""
    import json
    if not os.path.isdir(export_dir):
        return 0
    added = 0
    with LOCK:
        conn = _connect()
        try:
            conn.executescript(SCHEMA_SQL)
            for name in sorted(os.listdir(export_dir)):
                if not name.lower().endswith(".json"):
                    continue
                try:
                    with open(os.path.join(export_dir, name), "r", encoding="utf-8") as f:
                        rec = json.load(f)
                except Exception:
                    continue
                label = (rec.get("sample_id") or rec.get("sample_name")
                         or os.path.splitext(name)[0])
                exists = conn.execute("SELECT 1 FROM samples WHERE sample_label=?", (label,)).fetchone()
                if exists:
                    continue
                img = os.path.splitext(name)[0] + ".jpg"
                conn.execute(
                    """INSERT OR IGNORE INTO samples(no, saved_at, sample_label, sample_name,
                        sample_code, farm, inspector, note, model_result, model_confidence,
                        final_result, final_result_text, final_confidence, edited, override_note,
                        model_file, detections, image_file, report_file, client, created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (rec.get("no"), rec.get("saved_at") or _now(), label,
                     rec.get("sample_name") or label, rec.get("sample_id") or "",
                     rec.get("farm") or "", rec.get("inspector") or "", rec.get("note") or "",
                     str(rec.get("model_result") or ""), rec.get("model_confidence_pct"),
                     str(rec.get("final_result") or ""), rec.get("final_result_text") or "",
                     rec.get("final_confidence_pct"), 1 if rec.get("edited") else 0,
                     rec.get("override_note") or "", rec.get("model") or "liverV1.pt",
                     len(rec.get("detections") or []),
                     os.path.basename(img) if os.path.isfile(os.path.join(export_dir, img)) else "",
                     name, "import", _now()))
                added += 1
            conn.commit()
        finally:
            conn.close()
    return added


def _row_to_dict(r):
    d = dict(r)
    d["edited"] = bool(d.get("edited"))
    return d


def list_samples(limit=500, q="", farm="", result=""):
    with LOCK:
        conn = _connect()
        try:
            sql = "SELECT * FROM samples WHERE 1=1"
            args = []
            if q:
                sql += (" AND (sample_label LIKE ? OR sample_name LIKE ? OR farm LIKE ?"
                        " OR inspector LIKE ? OR sample_code LIKE ?)")
                like = "%" + q + "%"
                args += [like] * 5
            if farm:
                sql += " AND farm = ?"
                args.append(farm)
            if result:
                sql += " AND final_result = ?"
                args.append(result)
            sql += " ORDER BY saved_at DESC, id DESC LIMIT ?"
            args.append(int(limit))
            rows = conn.execute(sql, args).fetchall()
            return [_row_to_dict(r) for r in rows]
        finally:
            conn.close()


def next_no():
    with LOCK:
        conn = _connect()
        try:
            r = conn.execute("SELECT COALESCE(MAX(no),0) AS m FROM samples").fetchone()
            return int(r["m"] or 0) + 1
        finally:
            conn.close()


def _clean(v, limit=500):
    if v is None:
        return ""
    return str(v).strip()[:limit]


def insert_sample(data):
    """เพิ่มรายการผลตรวจ 1 แถว (ข้อมูลมาจากหน้าเว็บ /save)"""
    label = _clean(data.get("label") or data.get("sampleId") or data.get("title"), 120)
    if not label:
        label = "ตัวอย่าง-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    farm = _clean(data.get("farm"), 200)
    with LOCK:
        conn = _connect()
        try:
            conn.executescript(SCHEMA_SQL)
            no = data.get("no")
            if not no:
                r = conn.execute("SELECT COALESCE(MAX(no),0) AS m FROM samples").fetchone()
                no = int(r["m"] or 0) + 1
            # label ซ้ำ -> เติม -2, -3 ให้ไม่ชน unique index
            base_label, n = label, 2
            while conn.execute("SELECT 1 FROM samples WHERE sample_label=?", (label,)).fetchone():
                label = "%s-%d" % (base_label, n)
                n += 1
            farmer_id = None
            if farm:
                fr = conn.execute("SELECT id FROM farmers WHERE name=?", (farm,)).fetchone()
                if fr:
                    farmer_id = fr["id"]
            cur = conn.execute(
                """INSERT INTO samples(no, saved_at, sample_label, sample_name, sample_code,
                    farm, farmer_id, inspector, note, model_result, model_confidence,
                    final_result, final_result_text, final_confidence, edited, override_note,
                    model_file, detections, image_file, report_file, client, created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (int(no), data.get("saved_at") or _now(), label,
                 _clean(data.get("sampleName") or label, 200), _clean(data.get("sampleId"), 120),
                 farm, farmer_id, _clean(data.get("inspector"), 200), _clean(data.get("note"), 2000),
                 _clean(data.get("modelResult"), 20), data.get("modelConfidence"),
                 _clean(data.get("finalResult"), 20), _clean(data.get("finalResultText"), 200),
                 data.get("finalConfidence"), 1 if data.get("edited") else 0,
                 _clean(data.get("overrideNote"), 1000), _clean(data.get("modelFile") or "liverV1.pt", 60),
                 int(data.get("detections") or 0), _clean(data.get("imageFile"), 200),
                 _clean(data.get("reportFile"), 200), _clean(data.get("client") or "web", 20), _now()))
            conn.commit()
            row = conn.execute("SELECT * FROM samples WHERE id=?", (cur.lastrowid,)).fetchone()
            return _row_to_dict(row)
        finally:
            conn.close()


def update_sample(row_id, patch):
    """แก้ไขข้อมูลผลตรวจ (ใช้เมื่อเจ้าหน้าที่แก้ผล/ข้อมูลฟาร์ม)"""
    allowed = {"sample_label", "sample_name", "sample_code", "farm", "inspector", "note",
               "model_result", "model_confidence", "final_result", "final_result_text",
               "final_confidence", "edited", "override_note", "image_file", "report_file"}
    sets, args = [], []
    for k, v in (patch or {}).items():
        if k in allowed:
            sets.append("%s=?" % k)
            args.append(1 if k == "edited" and v else (0 if k == "edited" else v))
    if not sets:
        return None
    with LOCK:
        conn = _connect()
        try:
            args.append(int(row_id))
            conn.execute("UPDATE samples SET %s WHERE id=?" % ", ".join(sets), args)
            conn.commit()
            row = conn.execute("SELECT * FROM samples WHERE id=?", (int(row_id),)).fetchone()
            return _row_to_dict(row) if row else None
        finally:
            conn.close()


def delete_sample(row_id=None, report_file=None):
    with LOCK:
        conn = _connect()
        try:
            if row_id:
                cur = conn.execute("DELETE FROM samples WHERE id=?", (int(row_id),))
            elif report_file:
                cur = conn.execute("DELETE FROM samples WHERE report_file=?", (report_file,))
            else:
                return 0
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()


def stats():
    with LOCK:
        conn = _connect()
        try:
            total = conn.execute("SELECT COUNT(*) AS c FROM samples").fetchone()["c"]
            by_level = {lv: 0 for lv in LEVELS}
            for r in conn.execute("SELECT final_result AS lv, COUNT(*) AS c FROM samples "
                                  "GROUP BY final_result"):
                if r["lv"] in by_level:
                    by_level[r["lv"]] = r["c"]
            edited = conn.execute("SELECT COUNT(*) AS c FROM samples WHERE edited=1").fetchone()["c"]
            farms = conn.execute("SELECT COUNT(*) AS c FROM farmers").fetchone()["c"]
            return {"total": total, "by_level": by_level, "edited": edited, "farms": farms,
                    "db": os.path.basename(DB_PATH)}
        finally:
            conn.close()


def search_farmers(q="", limit=200):
    with LOCK:
        conn = _connect()
        try:
            if q:
                like = "%" + q + "%"
                rows = conn.execute(
                    "SELECT * FROM farmers WHERE name LIKE ? OR owner_name LIKE ? OR province LIKE ?"
                    " ORDER BY name LIMIT ?", (like, like, like, int(limit))).fetchall()
            else:
                rows = conn.execute("SELECT * FROM farmers ORDER BY name LIMIT ?",
                                    (int(limit),)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def add_farmer(data):
    name = _clean(data.get("name"), 200)
    if not name:
        raise ValueError("กรุณาระบุชื่อฟาร์ม")
    with LOCK:
        conn = _connect()
        try:
            conn.executescript(SCHEMA_SQL)
            cur = conn.execute(
                """INSERT INTO farmers(name,owner_name,address,subdistrict,district,province,
                    phone,reg_no,species,note,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (name, _clean(data.get("owner_name"), 200), _clean(data.get("address"), 300),
                 _clean(data.get("subdistrict"), 120), _clean(data.get("district"), 120),
                 _clean(data.get("province"), 120), _clean(data.get("phone"), 60),
                 _clean(data.get("reg_no"), 120), _clean(data.get("species"), 200),
                 _clean(data.get("note"), 1000), _now()))
            conn.commit()
            return dict(conn.execute("SELECT * FROM farmers WHERE id=?", (cur.lastrowid,)).fetchone())
        except sqlite3.IntegrityError:
            raise ValueError("มีฟาร์มชื่อนี้อยู่แล้ว: " + name)
        finally:
            conn.close()


def delete_farmer(fid):
    with LOCK:
        conn = _connect()
        try:
            cur = conn.execute("DELETE FROM farmers WHERE id=?", (int(fid),))
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()


def slug(text, fallback="report"):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", str(text or "").strip())
    s = re.sub(r"\s+", " ", s).strip(" .")
    return (s or fallback)[:80]

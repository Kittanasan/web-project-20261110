# -*- coding: utf-8 -*-
"""backup_db.py - สำรอง/กู้คืนฐานข้อมูลกลาง (ไม่ต้องติดตั้งโปรแกรมเพิ่ม)

สำรอง:   python backup_db.py backup     -> ได้ data/backup-<วันเวลา>.json (เปิดอ่านด้วย Notepad ได้)
กู้คืน:   python backup_db.py restore data/backup-xxxx.json
ตรวจ:    python backup_db.py check
"""
import glob
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import db  # noqa: E402


def snapshot():
    return {
        "app": "ระบบประเมินเม็ดไขมันในตับ",
        "schema_version": db.SCHEMA_VERSION,
        "db_path": db.DB_PATH,
        "stats": db.stats(),
        "farmers": db.search_farmers(limit=5000),
        "samples": db.list_samples(limit=100000),
    }


def do_backup():
    import datetime
    db.init_db()
    data = snapshot()
    name = "backup-%s.json" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    p = os.path.join(db.DATA_DIR, name)
    with io.open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("สำรองแล้ว:", p)
    print("  รายการผลตรวจ %d แถว | ฟาร์ม %d | ขนาด %.1f KB"
          % (len(data["samples"]), len(data["farmers"]), os.path.getsize(p) / 1024.0))
    return p


def do_restore(path=None):
    db.init_db()
    if not path:
        files = sorted(glob.glob(os.path.join(db.DATA_DIR, "backup-*.json")))
        if not files:
            print("ไม่พบไฟล์สำรองในโฟลเดอร์ data/")
            return 1
        path = files[-1]
        print("ใช้ไฟล์สำรองล่าสุด:", os.path.basename(path))
    with io.open(path, encoding="utf-8") as f:
        data = json.load(f)
    added = 0
    for f in data.get("farmers") or []:
        try:
            db.add_farmer(f)
            added += 1
        except Exception:
            pass
    n = 0
    for s in data.get("samples") or []:
        try:
            db.insert_sample({
                "no": s.get("no"), "saved_at": s.get("saved_at"),
                "label": s.get("sample_label"), "sampleName": s.get("sample_name"),
                "sampleId": s.get("sample_code"), "farm": s.get("farm"),
                "inspector": s.get("inspector"), "note": s.get("note"),
                "modelResult": s.get("model_result"), "modelConfidence": s.get("model_confidence"),
                "finalResult": s.get("final_result"), "finalResultText": s.get("final_result_text"),
                "finalConfidence": s.get("final_confidence"), "edited": s.get("edited"),
                "overrideNote": s.get("override_note"), "modelFile": s.get("model_file"),
                "detections": s.get("detections"), "imageFile": s.get("image_file"),
                "reportFile": s.get("report_file"), "client": "restore",
            })
            n += 1
        except Exception as e:
            print("  ข้ามแถว:", e)
    st = db.stats()
    print("กู้คืนเพิ่ม %d ผลตรวจ | %d ฟาร์ม | ในฐานข้อมูลตอนนี้ %d แถว" % (n, added, st["total"]))
    return 0


def do_check():
    db.init_db()
    st = db.stats()
    print("ไฟล์ฐานข้อมูล:", db.DB_PATH, "(%.1f KB)" % (os.path.getsize(db.DB_PATH) / 1024.0))
    print("รายการผลตรวจ %d แถว | ฟาร์ม %d | แก้ไขผล %d" % (st["total"], st["farms"], st["edited"]))
    for lv in db.LEVELS:
        print("   %-7s %d" % (lv, st["by_level"][lv]))
    rows = db.list_samples(limit=5)
    for r in rows:
        print("   ลำดับ %-3s | %-22s | %-8s | %s%% | %s"
              % (r.get("no"), (r.get("sample_label") or "")[:22],
                 r.get("final_result") or "-", r.get("final_confidence"), r.get("inspector") or "-"))
    return 0


if __name__ == "__main__":
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "backup").lower()
    if cmd == "backup":
        do_backup()
    elif cmd == "restore":
        sys.exit(do_restore(sys.argv[2] if len(sys.argv) > 2 else None))
    elif cmd == "check":
        sys.exit(do_check())
    else:
        print(__doc__)

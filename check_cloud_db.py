# -*- coding: utf-8 -*-
"""check_cloud_db.py - ตรวจฐานข้อมูลกลาง 'พร้อมยกไปเครื่องอื่น/ขึ้นเว็บ' หรือไม่

ตรวจกับไฟล์จริง data/db.sqlite (ไม่ต้องเปิดเซิร์ฟเวอร์):
  1) ไฟล์ฐานข้อมูลมีอยู่ และเนื้อหาข้างในไม่เสียหาย (integrity_check)
  2) ตาราง samples / farmers / meta ครบ + เวอร์ชัน schema
  3) ทะเบียนฟาร์ม และผลตรวจมีจริง (ไม่ใช่ไฟล์ว่าง)
  4) ไฟล์ settings ที่เว็บโฮสต์ต้องใช้ (Procfile, requirements.txt, render.yaml)
  5) ถ้ามี PROC env (พอร์ตของโฮสต์) โค้ดต้องอ่าน PORT ได้ถูก

ใช้: python check_cloud_db.py
"""
import io
import json
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

ok_all = True


def check(name, cond, detail=""):
    global ok_all
    print(("  OK   " if cond else "  FAIL ") + name + ("" if cond else " | " + str(detail)))
    if not cond:
        ok_all = False


def main():
    db_path = os.path.join(BASE, "data", "db.sqlite")
    print("=" * 68)
    print(" ตรวจฐานข้อมูลกลางสำหรับใช้งานบนเว็บ/เครื่องอื่น")
    print("=" * 68)

    print("\n=== 1) ไฟล์ฐานข้อมูล ===")
    exists = os.path.isfile(db_path)
    check("data/db.sqlite มีอยู่", exists, db_path)
    if not exists:
        print("\n[result] FAIL")
        return 1
    check("ขนาดไฟล์มากกว่า 0", os.path.getsize(db_path) > 0, os.path.getsize(db_path))

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        integ = conn.execute("PRAGMA integrity_check").fetchone()[0]
        check("integrity_check = ok", integ == "ok", integ)

        print("\n=== 2) ตารางและ schema ===")
        tables = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ("samples", "farmers", "meta"):
            check("มีตาราง %s" % t, t in tables, sorted(tables))
        ver = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        check("มี schema_version", ver is not None)
        print("       schema_version =", (ver["value"] if ver else "-"))

        print("\n=== 3) ข้อมูลข้างใน ===")
        n_s = conn.execute("SELECT COUNT(*) c FROM samples").fetchone()["c"]
        n_f = conn.execute("SELECT COUNT(*) c FROM farmers").fetchone()["c"]
        check("มีผลตรวจในฐานข้อมูล", n_s >= 1, n_s)
        check("มีทะเบียนฟาร์ม", n_f >= 1, n_f)
        print("       ผลตรวจ %d แถว | ฟาร์ม %d ราย" % (n_s, n_f))
        for r in conn.execute("SELECT sample_label, final_result, final_confidence, image_file "
                              "FROM samples ORDER BY saved_at DESC LIMIT 5"):
            check("แถว %-18s ผล %-7s ภาพ: %s" % (r["sample_label"], r["final_result"] or "-",
                                                 r["image_file"] or "(ไม่มีภาพ)"), True)
        # ภาพที่อ้างถึงต้องมีไฟล์จริง ไม่งั้นเครื่องอื่นกดดูภาพไม่ขึ้น
        missing = []
        for r in conn.execute("SELECT image_file FROM samples WHERE image_file<>''"):
            p = os.path.join(BASE, "exports", r["image_file"])
            if not os.path.isfile(p):
                missing.append(r["image_file"])
        check("ภาพผลประเมินที่อ้างถึงมีไฟล์จริงครบ", not missing, missing)

        print("\n=== 4) ไฟล์ที่เว็บโฮสต์ต้องใช้ ===")
        for rel in ("cloud_app.py", "db.py", "Index.html", "live.js", "liverV1.pt",
                    "requirements.txt", "Procfile", "render.yaml", "runtime.txt"):
            p = os.path.join(BASE, rel)
            size = os.path.getsize(p) if os.path.isfile(p) else 0
            check("%-18s (%d ไบต์)" % (rel, size), size > 0)
        gi = os.path.join(BASE, ".gitignore")
        if os.path.isfile(gi):
            with io.open(gi, encoding="utf-8") as f:
                txt = f.read()
            active = [ln.strip() for ln in txt.splitlines()
                      if ln.strip() and not ln.strip().startswith("#")]
            blocking = [ln for ln in active
                        if ln in ("*.pt", "liverV1.pt", "*.pt\n") or ln.rstrip("/") == "liverV1.pt"]
            check("liverV1.pt ไม่ถูก .gitignore กัน", not blocking, blocking)
            check("runtime/ ถูกกันไว้ (ไม่ขึ้นเว็บ)", "runtime/" in txt)

        print("\n=== 5) อ่านพอร์ตจากโฮสต์ (PORT) ได้ ===")
        old_port = os.environ.get("PORT")
        try:
            os.environ["PORT"] = "8123"
            import importlib
            import cloud_app
            importlib.reload(cloud_app)
            check("cloud_app อ่าน PORT=8123 ได้", cloud_app.PORT == 8123, cloud_app.PORT)
            check("บนโฮสต์ผูก 0.0.0.0", cloud_app.HOST == "0.0.0.0", cloud_app.HOST)
            check("ฐานข้อมูลเปิดได้จาก cloud_app", cloud_app.STORE_OK, cloud_app.STORE_NOTE)
        finally:
            if old_port is None:
                os.environ.pop("PORT", None)
            else:
                os.environ["PORT"] = old_port

        print("\n=== 6) ไฟล์สำรองข้อมูลล่าสุด ===")
        baks = sorted([n for n in os.listdir(os.path.join(BASE, "data"))
                       if n.startswith("backup-") and n.endswith(".json")])
        check("มีไฟล์สำรองอย่างน้อย 1 ไฟล์", bool(baks), baks)
        if baks:
            p = os.path.join(BASE, "data", baks[-1])
            try:
                with io.open(p, encoding="utf-8") as f:
                    b = json.load(f)
                check("ไฟล์สำรองอ่านได้ (%d ผลตรวจ / %d ฟาร์ม)"
                      % (len(b.get("samples") or []), len(b.get("farmers") or [])), True)
            except Exception as e:
                check("ไฟล์สำรองอ่านได้", False, e)
    finally:
        conn.close()

    print("\n[result]", "PASS" if ok_all else "FAIL")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())

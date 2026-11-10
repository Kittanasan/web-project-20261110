# -*- coding: utf-8 -*-
"""เตรียมโฟลเดอร์นี้ให้ "อัปโหลดขึ้นเว็บได้ทันที" (พร้อมฐานข้อมูลตั้งต้น)

ทำอะไรบ้าง
  1) สร้างฐานข้อมูลจริง data/db.sqlite (ตาราง samples / farmers / meta)
  2) ใส่ทะเบียนฟาร์มตั้งต้น + ฟาร์มของศูนย์วิจัยฯ
  3) นำรายงานเก่าใน exports/*.json เข้าฐานข้อมูล (ข้ามที่ซ้ำ)
  4) เขียนไฟล์ตั้งค่าและไฟล์บังคับให้เว็บโฮสต์รู้จัก
       requirements.txt      - รายการไลบรารีที่เว็บเซิร์ฟเวอร์ต้องติดตั้ง
       Procfile              - คำสั่งเริ่มระบบสำหรับ Render/Railway/Heroku
       runtime.txt           - เวอร์ชัน Python
       app.json              - ปุ่ม Deploy to Render
       .gitignore            - ไม่ให้ .pt / runtime / exports ขึ้น GitHub
       data/README-ฐานข้อมูล.txt - วิธีสำรอง/กู้คืนฐานข้อมูล
       data/seed_report.json - ภาพรวมข้อมูลตั้งต้น (ตรวจได้โดยไม่ต้องเปิดแอป)
       data/backup-<เวลา>.json - ข้อมูลสำรองทั้งหมด (เปิดอ่านได้ด้วย Notepad)

ใช้:  python prepare_cloud_folder.py
"""
import io
import json
import os
import sys
import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
EXPORT_DIR = os.path.join(BASE, "exports")

import db  # noqa: E402  (ใช้แฟ้มเดียวกับแอปจริง)


def main():
    print("=" * 68)
    print(" เตรียมโฟลเดอร์สำหรับนำขึ้นเว็บ + สร้างฐานข้อมูล")
    print("=" * 68)

    # 1) สร้างฐานข้อมูล
    path = db.init_db()
    print("[1/5] ฐานข้อมูล:", path, "(%d ไบต์)" % os.path.getsize(path))

    # 2) ฟาร์มตั้งต้น
    farmers = db.search_farmers()
    if len(farmers) < 2:
        extra = [
            dict(name="ฟาร์มลุงสมชาย ต.บางปะกง จ.ฉะเชิงเทรา", owner_name="นายสมชาย ใจดี",
                 subdistrict="บางปะกง", district="บางปะกง", province="ฉะเชิงเทรา",
                 species="ปลากะพงขาว", note="ตัวอย่างทดสอบระบบ"),
        ]
        for f in extra:
            try:
                db.add_farmer(f)
            except Exception as e:
                print("       ข้าม:", e)
    farmers = db.search_farmers()
    print("[2/5] ทะเบียนฟาร์ม:", len(farmers), "รายการ")
    for f in farmers:
        print("       -", f["name"])

    # 3) นำรายงานเก่าใน exports/ เข้าฐานข้อมูล
    added = db.import_legacy_exports(EXPORT_DIR)
    st = db.stats()
    print("[3/5] นำเข้าจาก exports/ เพิ่ม %d รายการ | ในฐานข้อมูลรวม %d แถว"
          % (added, st["total"]))

    # 4) ไฟล์ตั้งค่าโฮสต์
    files = {
        "requirements.txt": (
            "# ไลบรารีที่เว็บเซิร์ฟเวอร์ (Render / Railway / VPS) ต้องติดตั้ง\n"
            "# หมายเหตุ: ไม่ต้องมี torch/ultralytics ถ้าไม่ต้องประเมินภาพบนคลาวด์\n"
            "#           (ภาพจะประเมินจากเครื่องที่รัน start.bat แล้วส่งผลเข้ามาแทน)\n"
            "# เว็บเซิร์ฟเวอร์ใช้ http.server ในตัว Python (ไม่ต้องใช้ gunicorn)\n"
            "# เปิดใช้เฉพาะเมื่อต้องการประเมินภาพบนคลาวด์เอง (ไฟล์หนัก ~900 MB)\n"
            "torch==2.5.1\n"
            "ultralytics==8.3.40\n"
        ),
        "render.yaml": (
            "services:\n"
            "  - type: web\n"
            "    name: liver-fat-eval\n"
            "    runtime: python\n"
            "    plan: free\n"
            "    buildCommand: pip install -r requirements.txt\n"
            "    startCommand: python cloud_app.py\n"
            "    envVars:\n"
            "      - key: LIVER_SECRET\n"
            "        generateValue: true\n"
        ),
        "Procfile": "web: python cloud_app.py\n",
        "runtime.txt": "python-3.11.9\n",
        "app.json": json.dumps({
            "name": "liver-fat-eval",
            "description": "ระบบประเมินเม็ดไขมันในตับจากภาพถ่าย - กรมประมง",
            "repository": "",
            "keywords": ["fisheries", "yolo", "flask", "thai"],
            "env": {
                "LIVER_SECRET": {"description": "รหัสผ่านสำหรับแก้/ลบข้อมูล", "generator": "secret"},
                "LIVER_HOST": {"description": "0.0.0.0 สำหรับคลาวด์", "value": "0.0.0.0"},
            },
        }, ensure_ascii=False, indent=2) + "\n",
        ".gitignore": (
            "# ไฟล์ที่ห้ามขึ้น GitHub — liverV1.pt ต้องขึ้นเว็บด้วย จึงไม่ถูกกันไว้\n"
            "runtime/\n"
            "exports/*.jpg\n"
            "data/*.sqlite-wal\n"
            "data/*.sqlite-shm\n"
            ".deepseek-studio/\n"
            "__pycache__/\n"
        ),
        "data/README-ฐานข้อมูล.txt": (
            "ฐานข้อมูลกลางของระบบ (SQLite)\n"
            "==============================\n"
            "ไฟล์: data/db.sqlite\n"
            "  samples = ผลตรวจที่บันทึกไว้ (ลำดับที่ / label / ฟาร์ม / ผล / ความเชื่อมั่น / ผู้ตรวจ)\n"
            "  farmers = ทะเบียนฟาร์ม ใช้เติมช่อง 'ฟาร์มที่มาของตัวอย่าง'\n"
            "  meta    = เวอร์ชันสูตรฐานข้อมูล\n\n"
            "สำรองข้อมูล: ดับเบิลคลิก สำรองฐานข้อมูล.bat  (ได้ไฟล์ data/backup-<เวลา>.json)\n"
            "กู้คืนข้อมูล: วางไฟล์ backup-*.json ไว้ในโฟลเดอร์ data แล้วรัน คืนค่าฐานข้อมูล.bat\n\n"
            "ถ้าใช้บนคลาวด์ (Render free) พื้นที่เก็บไฟล์จะหายเมื่อรีสตาร์ต\n"
            "ให้ใช้ปุ่ม 'ส่งออกทั้งหมด (JSON)' บนหน้าเว็บเก็บไว้ หรือต่อฐานข้อมูลภายนอก\n\n"
            "แบบจำลอง liverV1.pt (6.3 MB) คัดลอกเข้า git แล้ว จึงขึ้นเว็บไปพร้อมโฟลเดอร์\n"
            "ถ้าเว็บติดตั้ง torch + ultralytics ตาม requirements.txt จะประเมินภาพได้เอง\n"
            "ถ้าไม่ติดตั้ง ให้ตั้ง LIVER_ENGINE ชี้ไปที่เครื่องที่รัน start.bat แทน\n"
        ),
    }
    for rel, text in files.items():
        full = os.path.join(BASE, *rel.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with io.open(full, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    print("[4/5] เขียนไฟล์ตั้งค่า:", ", ".join(sorted(files)))

    # 5) ข้อมูลสำรอง + รายงานภาพรวม
    rows = db.list_samples(limit=1000)
    seed = {
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "db_path": db.DB_PATH,
        "schema_version": db.SCHEMA_VERSION,
        "stats": st,
        "farmers": [{"name": f["name"], "province": f.get("province") or "",
                     "species": f.get("species") or ""} for f in farmers],
        "samples": rows,
    }
    for name in ("seed_report.json",
                 "backup-%s.json" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S")):
        with io.open(os.path.join(DATA_DIR, name), "w", encoding="utf-8") as f:
            json.dump(seed, f, ensure_ascii=False, indent=2)
    print("[5/5] เขียน data/seed_report.json + ไฟล์สำรองข้อมูล")
    print("\nสรุป: รายการในฐานข้อมูล %d แถว | ฟาร์ม %d | แก้ไขผล %d"
          % (st["total"], st["farms"], st["edited"]))
    print("พร้อมอัปโหลด (ยกเว้น runtime/ ที่กันไว้ใน .gitignore | liverV1.pt ขึ้นเว็บด้วย)")


if __name__ == "__main__":
    main()

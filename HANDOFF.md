# HANDOFF — ระบบประเมินเม็ดไขมันในตับ (liverV1.pt)

> ไฟล์นี้เขียนไว้ให้ **คนหรือ AI คนอื่นทำงานต่อบนเครื่องอื่นได้ทันที**
> อัปเดตล่าสุด: 11 พ.ย. 2026 · build ปัจจุบัน: `2026-11-11-cloud4`
> รีโป: `https://github.com/Kittanasan/web-project-20261110` (branch `main`)
> เว็บออนไลน์: `https://liver-fat-eval.onrender.com/`
> GitHub Pages (หน้าเปิด/ตรวจสถานะ): `https://kittanasan.github.io/web-project-20261110/`

---

## 1. สถาปัตยกรรม (อ่านก่อนแก้โค้ด)

ระบบมี 2 โหมดที่ใช้โค้ดชุดเดียวกัน แต่คนละบทบาท

```
[เครื่องในศูนย์ / เครื่องที่มี GPU-CPU + liverV1.pt]
   start.bat        ->  app.py         พอร์ต 8000  (หน้าเว็บ + ประเมินภาพ)
   cloud_engine.bat ->  cloud_app.py --engine  พอร์ต 9000 (ท่อรับภาพจากคลาวด์)
                            |
                            |  Cloudflare Tunnel (URL https://xxx.trycloudflare.com)
                            v
[Render (plan ฟรี)]
   cloud_app.py  (โหมดปกติ)  = หน้าเว็บ + ฐานข้อมูลกลาง sqlite + เก็บ exports/
                               ไม่มี torch/ultralytics -> ไม่ประเมินภาพเอง
                               POST /predict -> ส่งต่อไป ENGINE_URL (LIVER_ENGINE)
```

- **เว็บออนไลน์ประเมินภาพเองไม่ได้** เพราะ `requirements.txt` เป็นโหมดเบา (ไม่ลง torch)
- ผลประเมินจริงมาจากเครื่องในศูนย์ ผ่านท่อ `/predict`
- ถ้าไม่ได้ตั้ง `LIVER_ENGINE` เว็บจะตอบข้อความบอกขั้นตอน (ไม่ใช่ crash)

### ไฟล์สำคัญ

| ไฟล์ | หน้าที่ |
|---|---|
| `cloud_app.py` | ทั้งเว็บคลาวด์ (พอร์ตจาก env `PORT`) และท่อ engine (`--engine`, พอร์ต 9000) |
| `app.py` | ตัวประเมินภาพในเครื่อง (โหลด `liverV1.pt` ด้วย ultralytics) — ใช้ร่วมกันทั้ง 2 ฝั่ง |
| `db.py` | sqlite: samples / farmers, `init_db`, `insert_sample`, `stats`, `import_legacy_exports` |
| `templates/index.html` | หน้าเว็บโปรแกรมจริง (~959 บรรทัด) — cloud_app โหลดตัวนี้ก่อน |
| `Index_main.html` | หน้าโปรแกรมเวอร์ชันเดิม/สำรอง (ใช้ฝั่ง Pages) |
| `Index.html` | หน้า "ตัวเปิดโปรแกรม" เก่า (81 บรรทัด) — **อย่าให้ cloud_app โหลดตัวนี้** |
| `live.js` | ตัวช่วยฝั่งเบราว์เซอร์ คุยกับ API |
| `start.bat` | เปิดระบบในเครื่อง (หา Python ที่มี torch+ultralytics เอง) |
| `cloud_engine.bat` | เปิดท่อ 9000 + Cloudflare Tunnel |
| `render.yaml` | Blueprint ของ Render (plan ฟรี, ไม่มี disk) |
| `requirements.txt` | ชุดไลบรารีฝั่งคลาวด์ (เบา ไม่มี torch) |
| `runtime.txt` | `python-3.11.9` |
| `verify_engine_bridge.py` | ทดสอบท่อ engine ในเครื่อง |
| `check_cloud_db.py`, `verify_cloud_final.py` | ทดสอบฝั่งคลาวด์/ฐานข้อมูล |

---

## 2. สถานะปัจจุบัน (ทำอะไรเสร็จแล้ว)

| งาน | สถานะ | หลักฐาน |
|---|---|---|
| deploy บน Render ผ่าน | ✅ | `/health` ตอบ `"db": true`, `"db_records": 6`, build `2026-11-11-cloud4` |
| ฐานข้อมูลกลาง sqlite บน Render | ✅ | 6 ผลตรวจ / 2 ฟาร์ม |
| หน้าเว็บ root แสดง HTML (ไม่ใช่ JSON) | ✅ | `load_index()` โหลด `templates/index.html` ก่อน |
| ท่อ engine (`--engine`) | ✅ | `verify_engine_bridge.py` ผ่าน (ยิง `/predict`, `/save` ฯลฯ) |
| ความปลอดภัยของท่อ | ✅ | whitelist เฉพาะ `/predict /health /save /delete /engine-health`; path traversal → 403 |
| เชื่อม Render ↔ เครื่องในศูนย์ | ⬜ **ยังไม่ได้ทำ** | ต้องตั้ง `LIVER_ENGINE` ที่ Render (ขั้นตอนข้อ 4) |

### บั๊กที่เจอแล้วแก้แล้ว (อย่าทำซ้ำ)

1. **`UnicodeEncodeError` ทำโปรเซสตายตอน boot บน Render**
   `print()` ข้อความไทยที่ระดับบนสุดของไฟล์ ก่อนตั้ง stdout เป็น UTF-8
   → แก้: ตั้ง `stdout/stderr.reconfigure(encoding="utf-8")` เป็นบล็อกแรกสุด + ห่อ `print = say` (ห่อปลอดภัย)
   → **กฎ: ห้ามมี `print` ไทยที่ระดับบนสุดก่อนบล็อกนั้น**

2. **`PermissionError: /var/data`**
   Render plan ฟรีไม่มีดิสก์ แต่ `/var/data` มีอยู่และเขียนไม่ได้
   → แก้: `_make_data_root()` ทดสอบเขียนไฟล์จริง (`.write_probe`) ไม่ใช่แค่ `os.makedirs`
   → ถ้าเขียนไม่ได้ ตกกลับมาใช้โฟลเดอร์โปรเจกต์ (`BASE`) ซึ่ง `DATA_ROOT != BASE` เป็นเงื่อนไขของ `"persistent"`

3. **root URL แสดง JSON แทนหน้าเว็บ**
   ผู้ใช้เปิด `/health` ตรง ๆ (endpoint JSON) — ไม่ใช่บั๊ก
   → **การใช้งานจริงต้องเปิด `/` (ไม่มี `/health` ต่อท้าย)**

4. **`index.html` push ไม่ขึ้นบน Windows**
   `core.ignorecase=true` ทำให้ git มอง `index.html` = `Index.html`
   → แก้: rename ต้นฉบับเป็น `Index_main.html` แล้วสร้าง `index.html` ใหม่

5. **`render.yaml` ตั้ง `LIVER_DATA_DIR=/var/data` โดยไม่มี `disk:` block**
   → แก้: ใช้ plan ฟรี ไม่ประกาศ disk (คอมเมนต์ทางเลือก starter+disk ไว้ให้แล้ว)

---

## 3. ทำต่อบนเครื่องอื่น — ขั้นตอนครบ

### 3.1 เตรียมเครื่องใหม่

```bat
git clone https://github.com/Kittanasan/web-project-20261110.git
cd web-project-20261110
```

**ต้องคัดลอกมาเอง (ไม่ขึ้น git เพราะไฟล์ใหญ่):**
- `liverV1.pt`  (~6 MB) — วางข้าง `start.bat`  ← **ห้ามลืม**
- `runtime\python311\` (~5 GB, มี torch + ultralytics) — ถ้าเครื่องใหม่ไม่มีให้ติดตั้งแทนด้วย `pip install ultralytics` (Python 3.11 64-bit)

ตรวจว่าเครื่องพร้อม:
```bat
start.bat
```
ต้องเห็น `[1.1] torch ... / ultralytics ...` แล้วเปิด `http://127.0.0.1:8000`

### 3.2 เปิดท่อขึ้นคลาวด์ (ฝั่งเครื่องในศูนย์)

ติดตั้ง cloudflared ครั้งเดียว (Command Prompt → Run as administrator):
```bat
winget install --id Cloudflare.cloudflared
```
ถ้าไม่ได้ ใช้ดาวน์โหลด `cloudflared.exe` จาก
`https://github.com/cloudflare/cloudflared/releases/latest` มาวางข้าง `start.bat`

จากนั้น:
1. ดับเบิลคลิก `start.bat` — เปิดค้างไว้
2. ดับเบิลคลิก `cloud_engine.bat` — เปิดค้างไว้ (2 หน้าต่าง)
3. คัดลอก URL ที่ขึ้นต้น `https://....trycloudflare.com`

ตรวจท่อในเครื่องก่อนไปต่อ:
```bat
python verify_engine_bridge.py 9000
```
ต้องผ่านทุกข้อ (health / predict / save / delete / 403 path traversal)

### 3.3 ตั้งค่าที่ Render

Dashboard → service `liver-fat-eval` → **Environment** → Add Environment Variable

| Key | Value |
|---|---|
| `LIVER_ENGINE` | `https://....trycloudflare.com` (URL จาก 3.2) |
| `LIVER_SECRET` | (มีอยู่แล้ว — Render สร้างให้ ถ้าสร้างใหม่ต้องจำไว้ใช้แก้/ลบ) |

Save → Render redeploy เอง (~30–60 วิ)

### 3.4 ยืนยันว่าเชื่อมกันแล้ว

```
https://liver-fat-eval.onrender.com/health
```
ต้องเห็น:
```json
"build": "2026-11-11-cloud4",
"engine_url": "https://....trycloudflare.com",
"engine": { "ok": true, "mode": "engine", "engine_ready": true }
```
ถ้า `"engine": null` → ยังไม่ได้ตั้ง `LIVER_ENGINE`
ถ้า `"engine": {"ok": false, "error": ...}` → cloudflared ปิด หรือ URL เปลี่ยน

แล้วเปิด `https://liver-fat-eval.onrender.com/` (ไม่มี `/health`) เพื่อใช้งานจริง

---

## 4. กฎที่ต้องรู้ (ข้อผิดพลาดซ้ำบ่อย)

- **URL ของ trycloudflare เปลี่ยนทุกครั้งที่เปิด `cloud_engine.bat` ใหม่** → ต้องอัปเดต `LIVER_ENGINE` ที่ Render ทุกครั้ง
  (ถ้าต้องการ URL คงที่ ใช้ named tunnel ของ Cloudflare: `cloudflared tunnel create` + config `config.yml` — ยังไม่ได้ทำ)
- ห้ามตั้ง `LIVER_ENGINE` ชี้มาที่ Render เอง (วน loop)
- หน้าใช้งานจริงคือ `/` ไม่ใช่ `/health`
- บน Render plan ฟรี **ข้อมูลที่เพิ่มใหม่จะหายเมื่อ redeploy/รีสตาร์ต** (ไม่มีดิสก์)
  ต้องการเก็บถาวร: เปลี่ยน `render.yaml` เป็น `plan: starter` + เปิด `disk:` block (มีคอมเมนต์ไว้แล้ว) แล้วตั้ง `LIVER_DATA_DIR=/var/data`
- Render ฟรี **หลับเมื่อไม่มีคนใช้** → เปิดครั้งแรกช้า 30–60 วิ (ปกติ ไม่ใช่บั๊ก)
- ห้ามประกาศ `PYTHON_VERSION` ใน `render.yaml` (Render จะฟ้อง `blueprints cannot set PYTHON_VERSION`) — ใช้ `runtime.txt`
- Windows git ตั้ง `core.ignorecase=true` → ห้ามมีไฟล์ชื่อต่างกันแค่ตัวพิมพ์ในโฟลเดอร์เดียว

---

## 5. API ที่มีอยู่ (สำหรับแก้หน้าเว็บ)

| Method | Path | หมายเหตุ |
|---|---|---|
| GET | `/` | หน้าเว็บ (`templates/index.html` + inject `window.LIVER_ENGINE`) |
| GET | `/health` | JSON สถานะเครื่อง (ใช้ตรวจ ไม่ใช่หน้าเว็บ) |
| GET | `/records` | ผลตรวจทั้งหมด (query: `limit q farm result`) |
| POST | `/records` | เพิ่มผลตรวจแบบกรอกเอง |
| POST | `/records-update` | แก้ไข (`{id, patch}`) |
| POST | `/records-delete` | ลบ (`{id, report_file}`) |
| GET/POST | `/farmers`, `/farmers-delete` | ทะเบียนฟาร์ม |
| POST | `/predict` | อัปโหลดภาพ (binary) → ส่งต่อ engine หรือประเมินในเครื่อง |
| POST | `/save` | บันทึกผล + ภาพลง `exports/` และฐานข้อมูล |
| GET | `/exports/<name>` | ดาวน์โหลดภาพผล |

POST ที่แก้/ลบ ต้องมี header `X-Liver-Secret: <LIVER_SECRET>` (ถ้าตั้งไว้)

ท่อ engine (`cloud_app.py --engine`, พอร์ต 9000) เปิดเฉพาะ:
`GET /health`, `GET /engine-health`, `GET /`, `POST /predict`, `POST /save`, `POST /delete`
นอกจากนี้ตอบ 403 — **ห้ามเพิ่ม path ที่ให้อ่านไฟล์ดิบ** (จะเปิดเผย `liverV1.pt` / `.env` ออกอินเทอร์เน็ต)

---

## 6. ทดสอบ / ตรวจสอบ (รันเองได้ ไม่ต้องพึ่ง Render)

```bat
python verify_engine_bridge.py 9000     :: ทดสอบท่อ engine ในเครื่อง
python check_cloud_db.py                :: ตรวจฐานข้อมูล
python verify_cloud_final.py            :: ตรวจฝั่งคลาวด์ครบชุด
python test_cloud_relay.py              :: ทดสอบการส่งต่อ /predict
python verify_start.py                  :: ตรวจ start.bat / Python ที่ใช้
```

จำลอง Render ในเครื่อง (บังคับ stdout เป็น latin-1, บล็อก torch):
```bat
python .tmp_render_sim.py
```

---

## 7. งานที่ยังค้าง (ตัดสินใจก่อนทำ)

1. **ตั้ง `LIVER_ENGINE` ที่ Render** — งานเดียวที่เหลือเพื่อให้ประเมินภาพบนเว็บได้จริง
2. **ยังไม่ทดสอบเส้นทางภาพจริง end-to-end บนเครื่องที่มี torch จริง**
   (Studio เคยรันได้แต่ Python ที่ไม่มี ultralytics → ยืนยันได้แค่ JSON/HTTP ถูกต้อง)
3. **URL trycloudflare ไม่คงที่** — ถ้าต้องการใช้งานระยะยาว ควรทำ named tunnel
4. **ข้อมูลบน Render plan ฟรีหายเมื่อ redeploy** — ถ้าต้องเก็บจริงใช้ starter + disk
5. ไฟล์ทดสอบชั่วคราว `.tmp_*.py`, `.tmp_*.js`, `.tmp_*.txt` ติดอยู่ใน repo — ลบได้ ไม่กระทบการรัน (Render รันแค่ `cloud_app.py`)

---

## 8. ขั้นตอน deploy ใหม่ (เมื่อแก้โค้ด)

```bat
git add -A
git commit -m "คำอธิบายสั้น ๆ ว่าอะไรเปลี่ยน"
git push origin main
```
แล้วที่ Render: **Manual sync / Redeploy** (Blueprint) หรือรอ auto-deploy

ตรวจหลัง deploy:
```
https://liver-fat-eval.onrender.com/health
```
ต้องเห็น `"build"` ใหม่ที่ตั้งใน `cloud_app.py` (`BUILD_TAG`) — ถ้ายังเป็นค่าเก่า แปลว่า redeploy ยังไม่ขึ้น

---

## 9. บริบทของโปรเจกต์

ระบบประเมินระดับเม็ดไขมันในตับปลาจากภาพถ่ายเซลล์ ด้วยแบบจำลอง YOLO `liverV1.pt`
3 ระดับ: `Hight` / `Medium` / `Low` (สะกด `Hight` ตามแบบจำลองเดิม — **ห้ามแก้ตัวสะกด** ในข้อมูลที่บันทึกแล้ว)
ศูนย์วิจัยและพัฒนาการเพาะเลี้ยงสัตว์น้ำชายฝั่งฉะเชิงเทรา

วิธีทำให้เว็บออนไลน์ (Render) ประเมินภาพได้  (เวอร์ชัน build 2026-11-11-cloud4)
=====================================================================

สาเหตุที่ขึ้น "เซิร์ฟเวอร์นี้ไม่ได้ติดตั้ง torch/ultralytics"
  เว็บฟรีบน Render ไม่มี torch/ultralytics และไม่มีไฟล์แบบจำลองที่โหลดได้
  วิธีที่ใช้จริงคือ: เว็บออนไลน์ = หน้าเว็บ + ฐานข้อมูลกลาง
                  เครื่องในศูนย์ = ตัวประเมินภาพ (liverV1.pt)
  สองฝั่งคุยกันผ่าน "ท่อ" ที่ cloud_app.py --engine เปิดไว้บนเครื่องในศูนย์

ทำครั้งเดียว (ฝั่งเครื่องในศูนย์)
  1. ติดตั้ง Cloudflare Tunnel (ตัวสร้าง URL สาธารณะให้เครื่องในบ้าน)
       เปิด Command Prompt (Run as administrator) แล้วรัน
         winget install --id Cloudflare.cloudflared
     ถ้าใช้ winget ไม่ได้ ให้ดาวน์โหลด cloudflared.exe จาก
       https://github.com/cloudflare/cloudflared/releases/latest
     แล้ววางไฟล์ cloudflared.exe ไว้ในโฟลเดอร์เดียวกับ start.bat

  2. ดับเบิลคลิก start.bat  (เปิดระบบประเมินในเครื่องตามปกติ ใช้พอร์ต 8000)

  3. ดับเบิลคลิก cloud_engine.bat
       - หน้าต่างแรก: ท่อพอร์ต 9000 (ข้อความ "ท่อส่งภาพพร้อม")
       - หน้าต่างที่สอง: cloudflared พิมพ์ URL เช่น
           https://random-words-1234.trycloudflare.com
         คัดลอก URL นี้ไว้ (เปิดค้างทั้ง 2 หน้าต่าง ห้ามปิด)

ทำครั้งเดียว (ฝั่ง Render)
  4. เข้า dashboard.render.com -> service ของคุณ -> Environment
       Add Environment Variable
         Key   : LIVER_ENGINE
         Value : https://random-words-1234.trycloudflare.com   (URL จากข้อ 3)
       กด Save -> Render จะ redeploy เอง
  5. เปิด https://liver-fat-eval.onrender.com/health
       ต้องเห็น "engine_url" เป็น URL นั้น และ "engine": {"ok": true, ...}
     จากนั้นเปิดหน้าระบบ แล้วอัปโหลดภาพ -> ได้ผลประเมินจริง

ทุกครั้งที่ใช้งาน
  เปิด start.bat + cloud_engine.bat ไว้บนเครื่อง (URL ของ trycloudflare จะเปลี่ยนทุกครั้ง
  ที่เปิดใหม่ -> ถ้าเปลี่ยน ต้องไปแก้ค่า LIVER_ENGINE ที่ Render ตาม)

ข้อสังเกต
  - ถ้า Render หลับ (plan ฟรี) เปิดหน้าเว็บครั้งแรกจะช้า ~30-50 วินาที
  - ถ้าเครื่องในศูนย์ปิด หรือ cloudflared ปิด ภาพจะประเมินไม่ได้ แต่ยังดู/แก้/ลบตารางผลได้
  - ตรวจท่อในเครื่องได้ด้วย:  python verify_engine_bridge.py 9000
  - ห้ามตั้ง LIVER_ENGINE เป็นที่อยู่ของ Render เอง (จะวนกลับมาหาตัวเอง)

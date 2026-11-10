"""ตรวจระบบว่า start.bat / app.py / live.js ทำงานถูกหลังแก้บั๊ก

ใช้: python check_conn.py [port]
รายงานผลแบบ PASS/FAIL ทุกข้อ (ไม่พึ่งเบราว์เซอร์)
"""
import json
import sys
import urllib.request

try:  # คอนโซล Windows บางตัวเป็น cp1252 ทำให้ print ไทยพัง
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
BASE = "http://127.0.0.1:%d" % PORT
ok_all = True


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return r.status, r.read()


def check(label, cond, extra=""):
    global ok_all
    if not cond:
        ok_all = False
    print(("  OK   " if cond else "  FAIL ") + label + (("  " + str(extra)) if extra else ""))


# 1) เครื่องประมวลผล + แบบจำลอง
try:
    st, body = get("/health")
    info = json.loads(body.decode("utf-8"))
    print("[health]", st, "model=", info.get("model"), "host=127.0.0.1 port=%d" % PORT)
    check("แบบจำลองพร้อมใช้งาน", info.get("ok") is True and info.get("model") == "liverV1.pt")
    check("มีระดับผลครบ Hight/Medium/Low", info.get("levels") == ["Hight", "Medium", "Low"], info.get("levels"))
except Exception as exc:  # noqa: BLE001
    ok_all = False
    print("[health] FAILED", type(exc).__name__, exc)
    print("[connected] False")
    sys.exit(1)

# 2) หน้าเว็บที่เสิร์ฟจริง
st, body = get("/")
page = body.decode("utf-8")
print("[/ ]", st, "chars=", len(page))
check("หน้าเว็บเป็น Index.html ตัวจริง (ไม่ใช่หน้าแจ้งเตือน)",
      "ศูนย์วิจัยและพัฒนาการเพาะเลี้ยงสัตว์น้ำชายฝั่งฉะเชิงเทรา" in page)
check("โหลดตัวเชื่อมต่อเครื่องประมวลผล", "live.js" in page)
check("มีปุ่มเชื่อมต่อเครื่องประมวลผล", 'id="connectBtn"' in page)
check("มีปุ่มบันทึกผลการตรวจ", 'id="saveRecordBtn"' in page)
check("มีตารางบันทึกผล", 'id="recordBody"' in page)

# 3) live.js ใช้พอร์ตเดียวกับที่เซิร์ฟเวอร์รันจริง
st, body = get("/live.js")
js = body.decode("utf-8")
print("[/live.js]", st, "bytes=", len(js))
check("หน้าเว็บส่งพอร์ตจริงให้ live.js (?port=%d)" % PORT, ('live.js?port=%d' % PORT) in page)

print("\n[result]", "PASS" if ok_all else "FAIL")
sys.exit(0 if ok_all else 1)

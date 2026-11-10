/* =====================================================================
   ตัวเชื่อมต่อเครื่องประมวลผล (processor bridge)
   หน้าเว็บโหลดไฟล์นี้จากเซิร์ฟเวอร์ app.py โดยตรง (/live.js)
   - ตรวจว่าเครื่องประมวลผล (แบบจำลอง liverV1.pt) พร้อมใช้งานหรือไม่
   - แจ้งหน้าเว็บด้วย event "processor:online" ทันทีที่พร้อม
     ทำให้หน้าเว็บเชื่อมต่อเองโดยไม่ต้องกดปุ่มหรือรีเฟรช
   ===================================================================== */
(function () {
  "use strict";

  var TIMEOUT = 2500;
  var INTERVAL = 5000;   /* ตรวจซ้ำทุก 5 วินาทีเมื่อยังต่อไม่ได้ */
  var state = { ok: false, info: null, base: null, checkedAt: 0, error: null };
  var timer = null;
  var port = null;       /* พอร์ตของเซิร์ฟเวอร์ (อ่านจาก <script src="live.js?port=.."> หรือใช้ 8000) */

  function portHint() {
    if (port) return port;
    try {
      var s = document.querySelector('script[src*="live.js"]');
      var m = s && String(s.getAttribute("src")).match(/[?&]port=(\d+)/);
      if (m) port = m[1];
    } catch (e) { /* ignore */ }
    return port || "8000";
  }

  function bases() {
    var p = portHint();
    var list = [];
    if (location.protocol === "http:" || location.protocol === "https:") list.push(location.origin);
    list.push("http://127.0.0.1:" + p, "http://localhost:" + p);
    /* ถ้าพอร์ต 8000 ถูกโปรแกรมอื่นใช้ start.bat จะเลื่อนไปใช้พอร์ตถัดไป (8001-8020)
       จึงตรวจพอร์ตข้างเคียงด้วย จะได้เชื่อมต่อได้เองโดยไม่ต้องคัดลอก URL เอง */
    try {
      var n = parseInt(p, 10);
      if (n >= 8000 && n <= 8100) {
        for (var i = n + 1; i <= n + 20; i++) list.push("http://127.0.0.1:" + i);
      }
    } catch (e) { /* ใช้ค่าที่มี */ }
    return list.filter(function (b, i, a) { return b && b !== "null" && a.indexOf(b) === i; });
  }

  function probe(base) {
    var ctl = typeof AbortController === "function" ? new AbortController() : null;
    var t = setTimeout(function () { if (ctl) ctl.abort(); }, TIMEOUT);
    return fetch(base.replace(/\/$/, "") + "/health", {
      cache: "no-store",
      signal: ctl ? ctl.signal : undefined
    }).then(function (res) {
      if (!res.ok) return null;
      return res.json();
    }).then(function (j) {
      return j && j.ok ? j : null;
    }).catch(function () {
      return null;
    }).then(function (j) {
      clearTimeout(t);
      return j;
    });
  }

  function check(quiet) {
    var list = bases();
    var i = 0;
    function next() {
      if (i >= list.length) return Promise.resolve(null);
      var base = list[i++];
      return probe(base).then(function (info) {
        if (info) { info.__base = base; return info; }
        return next();
      });
    }
    return next().then(function (info) {
      var wasOk = state.ok;
      state.checkedAt = Date.now();
      if (info) {
        state.ok = true;
        state.info = info;
        state.base = info.__base.replace(/\/$/, "");
        state.error = null;
        if (timer) { clearInterval(timer); timer = null; }
        document.dispatchEvent(new CustomEvent("processor:online", { detail: info }));
        if (!wasOk) {
          document.dispatchEvent(new CustomEvent("processor:status", { detail: state }));
        }
      } else {
        state.ok = false;
        state.info = null;
        state.base = null;
        state.error = "ยังเชื่อมต่อเครื่องประมวลผลไม่ได้";
        document.dispatchEvent(new CustomEvent("processor:status", { detail: state }));
        if (!timer) timer = setInterval(function () { check(true); }, INTERVAL);
      }
      return state.ok;
    });
  }

  window.ProcessorBridge = {
    check: check,
    state: function () { return state; },
    get base() { return state.base; },
    get online() { return state.ok; }
  };

  /* ให้หน้าเว็บสั่งเชื่อมต่อใหม่ได้ทันที */
  window.addEventListener("online", function () { check(); });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { check(); });
  } else {
    check();
  }
})();

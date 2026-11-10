/* ---------------- บันทึกผลการตรวจ + ตารางบันทึกผล ---------------- */
const HISTORY_KEY = "liverFatEvalRecordsV4";
const FORM_KEY = "liverRecordFormV4";

function setSaveStatus(msg, kind) {
  saveStatusEl.textContent = msg;
  saveStatusEl.className = "status" + (kind ? " " + kind : "");
}
function fmtDate(iso) {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso || "-";
  const p = (n) => String(n).padStart(2, "0");
  return p(d.getDate()) + "/" + p(d.getMonth() + 1) + "/" + (d.getFullYear() + 543) + " " +
    p(d.getHours()) + ":" + p(d.getMinutes());
}
function tagClass(lv) { return lv === "Hight" ? "t-h" : lv === "Medium" ? "t-m" : "t-l"; }
function levelColor(lv) {
  const t = LEVEL_TEXT[lv];
  return t ? t.color : "#5b7288";
}
function levelShort(lv) { return LEVEL_TEXT[lv] ? LEVEL_TEXT[lv].short : "ไม่ระบุ"; }

/* ความเชื่อมั่นของระดับที่เลือก: ตรงกับผลระบบใช้ค่าจริง ถ้าเจ้าหน้าที่แก้ใช้สัดส่วนของระดับนั้น */
function confOf(level) {
  if (!currentData) return null;
  if (currentData.verdict && level === currentData.verdict) return Number(currentData.confidence_pct || 0);
  const lp = currentData.level_pct || {};
  if (lp[level] !== undefined && Number(lp[level]) > 0) return Number(lp[level]);
  return null;
}
function syncConfField() {
  const c = confOf(recResultEl.value);
  recConfEl.value = c === null ? "" : c.toFixed(1) + " %";
}
function persistHistory() {
  try {
    const plain = history.map(h => {
      const c = Object.assign({}, h);
      delete c.imageDataUrl;
      return c;
    });
    localStorage.setItem(HISTORY_KEY, JSON.stringify(plain.slice(0, 300)));
  } catch (e) { /* พื้นที่เต็ม — ไฟล์ยังถูกบันทึกในโฟลเดอร์ exports */ }
}
function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    history = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(history)) history = [];
  } catch (e) { history = []; }
}
function persistForm() {
  try {
    localStorage.setItem(FORM_KEY, JSON.stringify({
      label: recLabelEl.value, farm: farmEl.value,
      inspector: inspectorEl.value, result: recResultEl.value
    }));
  } catch (e) { /* ข้ามไป */ }
}
function restoreForm() {
  try {
    const raw = localStorage.getItem(FORM_KEY);
    if (!raw) return;
    const f = JSON.parse(raw) || {};
    if (f.label) recLabelEl.value = f.label;
    if (f.farm) farmEl.value = f.farm;
    if (f.inspector) inspectorEl.value = f.inspector;
    if (f.result) recResultEl.value = f.result;
  } catch (e) { /* ข้ามไป */ }
}

/* ---------------- วาดตารางบันทึกผล ---------------- */
function renderRecordTable(highlightTs) {
  const seen = new Set(history.map(h => h.reportFile).filter(Boolean));
  let rows = history.slice();
  serverRecords.forEach(r => {
    if (r.report && seen.has(r.report)) return;
    rows.push({
      no: r.no,
      savedAt: r.saved_at || new Date((r.time || 0) * 1000).toISOString(),
      label: r.sample_name || r.sample_id || "-",
      farm: r.farm || "",
      inspector: r.inspector || "",
      finalResult: r.final_result || "",
      finalConfidence: r.final_confidence_pct,
      edited: !!r.edited,
      reportFile: r.report,
      imageFile: r.image,
      fromServer: true
    });
  });

  const q = (recordFilter.value || "").trim().toLowerCase();
  if (q) {
    rows = rows.filter(r => [r.label, r.farm, r.inspector, r.finalResult]
      .join(" ").toLowerCase().indexOf(q) >= 0);
  }
  rows.sort((a, b) => (Number(a.no) || 0) - (Number(b.no) || 0) ||
    String(a.savedAt).localeCompare(String(b.savedAt)));

  recordCount.textContent = rows.length + " รายการ";
  clearSavedBtn.disabled = history.length === 0 && serverRecords.length === 0;
  printBtn.disabled = rows.length === 0;
  recordEmpty.style.display = rows.length ? "none" : "block";

  recordBody.innerHTML = rows.map((r, i) => {
    const lv = r.finalResult;
    const c = (r.finalConfidence === null || r.finalConfidence === undefined || r.finalConfidence === "")
      ? "—" : Number(r.finalConfidence).toFixed(1) + " %";
    const col = levelColor(lv);
    const note = r.edited
      ? '<div class="rec-num" style="font-size:.7rem;font-weight:600;color:var(--warn)">* เจ้าหน้าที่แก้ไข</div>'
      : "";
    const isNew = highlightTs && r.savedAt === highlightTs ? ' class="is-new"' : "";
    return "<tr" + isNew + ">" +
      '<td class="rec-no">' + esc(r.no || (i + 1)) + "</td>" +
      "<td><b>" + esc(r.label || "-") + "</b></td>" +
      '<td class="t-left">' + esc(r.farm || "-") + "</td>" +
      '<td><span class="rec-val" style="color:' + col + ";border-color:" + col +
        ";background:" + col + '14">' + esc(lv || "-") + "<small>" + esc(levelShort(lv)) + "</small></span></td>" +
      '<td class="rec-num">' + esc(c) + "</td>" +
      '<td class="t-left">' + esc(r.inspector || "-") + note + "</td>" +
      '<td style="font-size:.78rem;color:var(--muted)">' + esc(fmtDate(r.savedAt)) + "</td>" +
      '<td><div class="rec-actions">' +
        '<a class="act-view" data-view="' + i + '">ภาพ</a>' +
        '<a class="act-del" data-del="' + i + '">ลบ</a>' +
      "</div></td></tr>";
  }).join("");
  renderRecordTable._rows = rows;
}

/* ---------------- ลบข้อมูล ---------------- */
async function deleteReport(name) {
  if (!name) return true;
  try {
    const res = await fetch("/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name })
    });
    const j = await res.json();
    if (!res.ok || !j.ok) throw new Error(j.error || ("HTTP " + res.status));
    serverRecords = serverRecords.filter(s => s.report !== name);
    return true;
  } catch (err) {
    toast("ลบไฟล์ในโฟลเดอร์ exports ไม่สำเร็จ: " + err.message, true);
    return false;
  }
}

recordBody.addEventListener("click", async (e) => {
  const a = e.target.closest("a");
  if (!a) return;
  const rows = renderRecordTable._rows || [];
  if (a.dataset.view !== undefined) {
    const r = rows[Number(a.dataset.view)];
    if (!r) return;
    if (r.imageDataUrl) window.open(r.imageDataUrl, "_blank");
    else if (r.imageFile) window.open("/exports/" + encodeURIComponent(r.imageFile), "_blank");
    else toast("ไม่พบภาพของรายการนี้", true);
  } else if (a.dataset.del !== undefined) {
    const r = rows[Number(a.dataset.del)];
    if (!r) return;
    if (!confirm("ยืนยันการลบข้อมูลลำดับที่ " + (r.no || "-") + " (" + (r.label || "-") + ")?\n" +
      (r.reportFile ? "ไฟล์ภาพและรายงานในโฟลเดอร์ exports จะถูกลบด้วย" : ""))) return;
    const idx = history.findIndex(h =>
      (h.reportFile && h.reportFile === r.reportFile) || h.savedAt === r.savedAt);
    if (idx >= 0) history.splice(idx, 1);
    persistHistory();
    if (r.reportFile) await deleteReport(r.reportFile);
    renderRecordTable();
    setSaveStatus("ลบข้อมูลลำดับที่ " + (r.no || "-") + " แล้ว", "ok");
    toast("ลบข้อมูลแล้ว");
  }
});

clearSavedBtn.addEventListener("click", async () => {
  const total = history.length + serverRecords.length;
  if (!total) return;
  if (!confirm("ยืนยันลบข้อมูลทั้งหมด " + total + " รายการ?\n" +
    "ไฟล์ภาพและรายงานในโฟลเดอร์ exports จะถูกลบทั้งหมดด้วย")) return;
  let fail = 0;
  for (const r of serverRecords.slice()) {
    const ok = await deleteReport(r.report);
    if (!ok) fail++;
  }
  history = [];
  persistHistory();
  renderRecordTable();
  setSaveStatus(fail ? ("ลบข้อมูลแล้ว แต่ลบไฟล์ฝั่งเครื่องไม่สำเร็จ " + fail + " ไฟล์")
                     : "ลบข้อมูลทั้งหมดแล้ว", fail ? "err" : "ok");
  toast(fail ? "ลบข้อมูลแล้ว (มีไฟล์ที่ลบไม่สำเร็จ " + fail + ")" : "ลบข้อมูลทั้งหมดแล้ว", !!fail);
});

/* ---------------- โหลดรายการที่บันทึกไว้ในเครื่อง ---------------- */
async function loadServerRecords(quiet) {
  try {
    const res = await fetch("/exports", { cache: "no-store" });
    const j = await res.json();
    if (!res.ok || !j.ok) throw new Error(j.error || ("HTTP " + res.status));
    serverRecords = j.exports || [];
    if (serverRecords.length) {
      saveFolderEl.textContent = "รายงานที่บันทึกไว้ในเครื่อง: " + serverRecords.length + " ฉบับ";
    }
    renderRecordTable();
    if (!quiet) toast("โหลดรายการจากโฟลเดอร์ exports แล้ว " + serverRecords.length + " รายการ");
  } catch (err) {
    if (!quiet) toast("โหลดรายการไม่สำเร็จ: " + err.message, true);
  }
}
reloadBtn.addEventListener("click", () => loadServerRecords(false));
recordFilter.addEventListener("input", () => renderRecordTable());

/* ---------------- บันทึกผลการตรวจ ---------------- */
saveBtn.addEventListener("click", async () => {
  const label = recLabelEl.value.trim();
  const farm = farmEl.value.trim();
  const inspector = inspectorEl.value.trim();
  const final = recResultEl.value;
  if (!label) { recLabelEl.focus(); toast("กรุณากรอก Label ตัวอย่างก่อนบันทึก", true); return; }
  if (!farm) { farmEl.focus(); toast("กรุณากรอกฟาร์มที่มาของตัวอย่าง", true); return; }
  if (!inspector) { inspectorEl.focus(); toast("กรุณากรอกชื่อผู้ตรวจวิเคราะห์", true); return; }

  const modelLv = currentData && currentData.verdict ? currentData.verdict : null;
  const edited = !!modelLv && final !== modelLv;
  const conf = confOf(final);

  if (edited && !finalNoteEl.value.trim()) {
    finalNoteEl.focus();
    overrideState.textContent = "กรุณาระบุเหตุผลประกอบการแก้ไขผลก่อนบันทึก";
    toast("กรุณาระบุเหตุผลประกอบการแก้ไขผล", true);
    return;
  }

  saveBtn.disabled = true;
  setSaveStatus("กำลังบันทึก…", "busy");

  let item = null;
  try {
    const res = await fetch("/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image: currentAnnotated || "",
        title: label,
        sampleName: label,
        sampleId: label,
        farm: farm,
        inspector: inspector,
        note: noteEl.value.trim(),
        modelResult: modelLv || "",
        modelConfidence: currentData ? Number(currentData.confidence_pct || 0) : null,
        finalResult: final,
        finalConfidence: conf,
        overrideNote: finalNoteEl.value.trim(),
        edited: edited,
        detections: (currentData && currentData.detections) || []
      })
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || ("HTTP " + res.status));
    item = {
      no: data.no,
      savedAt: data.saved_at,
      label: label, farm: farm, inspector: inspector,
      finalResult: final, finalConfidence: conf,
      modelResult: modelLv,
      modelConfidence: currentData ? Number(currentData.confidence_pct || 0) : null,
      overrideNote: finalNoteEl.value.trim(),
      edited: edited,
      reportFile: data.report_file,
      imageFile: data.image_file,
      imageDataUrl: currentAnnotated
    };
    saveFolderEl.textContent = "โฟลเดอร์รายงาน: " + data.folder;
    setSaveStatus("บันทึกลำดับที่ " + data.no + " แล้ว (" + fmtDate(data.saved_at) + "): " + data.image_file, "ok");
    toast("บันทึกผลการตรวจลำดับที่ " + data.no + " เรียบร้อย");
  } catch (err) {
    /* บันทึกไฟล์ไม่สำเร็จ — เก็บในตารางของเบราว์เซอร์แทน เพื่อไม่ให้ข้อมูลหาย */
    const maxNo = Math.max(0, ...history.map(h => Number(h.no) || 0),
      ...serverRecords.map(r => Number(r.no) || 0));
    item = {
      no: maxNo + 1,
      savedAt: new Date().toISOString(),
      label: label, farm: farm, inspector: inspector,
      finalResult: final, finalConfidence: conf,
      modelResult: modelLv, edited: edited,
      overrideNote: finalNoteEl.value.trim(),
      reportFile: null, imageFile: null,
      imageDataUrl: currentAnnotated
    };
    setSaveStatus("บันทึกไฟล์ในเครื่องไม่สำเร็จ: " + err.message +
      " — เก็บไว้ในตารางของเบราว์เซอร์แทน", "err");
    toast("บันทึกไฟล์ไม่สำเร็จ: " + err.message, true);
  }

  history.unshift(item);
  persistHistory();
  renderRecordTable(item.savedAt);

  /* เตรียมฟอร์มสำหรับรายการถัดไป */
  recLabelEl.value = "";
  farmEl.value = "";
  recConfEl.value = "";
  noteEl.value = "";
  finalNoteEl.value = "";
  persistForm();
  recLabelEl.focus();
});

/* ---------------- ฟอร์ม ---------------- */
[recLabelEl, farmEl, inspectorEl].forEach(el => el.addEventListener("input", persistForm));
recResultEl.addEventListener("change", () => {
  syncConfField();
  finalLevelEl.value = recResultEl.value;
  checkOverride();
  persistForm();
});
recClearBtn.addEventListener("click", () => {
  recLabelEl.value = ""; farmEl.value = ""; inspectorEl.value = "";
  recConfEl.value = ""; noteEl.value = "";
  const lv = currentData && currentData.verdict ? currentData.verdict : "Medium";
  recResultEl.value = lv;
  finalLevelEl.value = lv;
  finalNoteEl.value = "";
  syncConfField();
  persistForm();
  toast("ล้างฟอร์มแล้ว");
  recLabelEl.focus();
});

/* ---------------- พิมพ์ / บันทึก PDF ---------------- */
printBtn.addEventListener("click", () => window.print());

/* ---------------- เริ่มต้น ---------------- */
restoreForm();
loadHistory();
syncConfField();
renderRecordTable();
loadServerRecords(true);

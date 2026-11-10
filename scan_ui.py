# -*- coding: utf-8 -*-
"""สแกนหาส่วนบันทึก/ตารางใน Index.html เพื่อดูว่าหน้ายังต้องต่อ API ตรงไหน"""
import io
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
html = io.open("Index.html", encoding="utf-8").read()
lines = html.split("\n")
pat = re.compile(r"(/save|/exports|/delete|saveImageBtn|renderRecords|loadRecords|renderHistory|"
                 r"formRecord|recTable|recordsTable|liverFatEvalRecords|HISTORY_KEY|finalLevelEl|"
                 r"saveStatus|storageBtn|backupBtn)", re.I)
for i, ln in enumerate(lines, 1):
    if pat.search(ln):
        print("%4d | %s" % (i, ln.strip()[:150]))
print("\nlines:", len(lines), "chars:", len(html))

# -*- coding: utf-8 -*-
"""แทนที่บล็อกสคริปต์บันทึก/ตาราง ใน templates/index.html ด้วยบล็อกใหม่จาก .tmp_new_block.js"""
import io, sys

sys.stdout.reconfigure(encoding="utf-8")
target = "templates/index.html"
with io.open(target, "r", encoding="utf-8") as f:
    lines = f.readlines()
with io.open(".tmp_new_block.js", "r", encoding="utf-8") as f:
    block = f.read()

start_marker = "/* ---------------- บันทึกภาพ + ผล ---------------- */"
end_marker = "loadHistory();\n"
start = next(i for i, ln in enumerate(lines) if ln.startswith(start_marker))

# หา "loadHistory();" บรรทัดสุดท้ายก่อน </script>
end = None
for i in range(len(lines) - 1, start, -1):
    if lines[i].strip() == "renderHistory();":
        end = i
        break
assert end is not None, "ไม่พบจุดสิ้นสุดของบล็อกเดิม"
new_lines = block.splitlines(True)
if not new_lines[-1].endswith("\n"):
    new_lines[-1] += "\n"
lines[start:end + 1] = new_lines

with io.open(target, "w", encoding="utf-8", newline="\n") as f:
    f.writelines(lines)
print("แทนที่บรรทัด", start + 1, "ถึง", end + 1, "->", len(new_lines), "บรรทัดใหม่")
with io.open(target, "r", encoding="utf-8") as f:
    txt = f.read()
print("ไฟล์รวม", len(txt), "ตัวอักษร /", txt.count("\n") + 1, "บรรทัด")
print("savedListEl เหลืออยู่:", txt.count("savedListEl"), "| sampleIdEl เหลืออยู่:", txt.count("sampleIdEl"))
print("renderHistory เหลืออยู่:", txt.count("renderHistory"), "| renderRecordTable:", txt.count("renderRecordTable"))

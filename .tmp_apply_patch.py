# -*- coding: utf-8 -*-
"""แทรกบล็อก JS ใหม่ของตารางบันทึกผล แทนบล็อกเดิมในหน้า standalone + index.html"""
import io, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))

with io.open(os.path.join(BASE, ".tmp_save_block.txt"), "r", encoding="utf-8") as f:
    newblock = f.read()

old_start = "/* ---------------- บันทึกภาพ + ผล ---------------- */"
old_end = "printBtn.addEventListener(\"click\", () => window.print());"


def replace_block(path):
    with io.open(path, "r", encoding="utf-8") as f:
        txt = f.read()
    i = txt.find(old_start)
    j = txt.find(old_end)
    if i < 0 or j < 0 or j < i:
        print("SKIP (markers not found):", os.path.basename(path), i, j)
        return False
    if old_start not in txt and "buildRecord" in txt:
        print("already replaced?", os.path.basename(path))
    tail_marker = "/* ---------------- เริ่มต้น ---------------- */"
    k = txt.find(tail_marker, j)
    if k < 0:
        print("SKIP (no tail):", os.path.basename(path))
        return False
    out = txt[:i] + newblock + "\n" + txt[k:]
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("PATCHED:", os.path.basename(path), "len", len(txt), "->", len(out))
    return True


for rel in ["liver-eval-standalone.html"]:
    replace_block(os.path.join(BASE, rel))

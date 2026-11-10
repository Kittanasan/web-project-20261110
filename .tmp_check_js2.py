# -*- coding: utf-8 -*-
"""ตรวจวงเล็บในสคริปต์ โดยข้ามข้อความในเครื่องหมายคำพูดและคอมเมนต์ แล้วแสดงบริบทจุดที่ผิด"""
import io, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
txt = io.open(os.path.join(BASE, "liver-eval-standalone.html"), encoding="utf-8").read()
start = txt.find("<script>")
end = txt.find("</script>", start)
js = txt[start + 8:end]

stack = []
i = 0
n = len(js)
state = None  # None, "'", '"', '`', '//', '/*'
while i < n:
    ch = js[i]
    nxt = js[i + 1] if i + 1 < n else ""
    if state in ("'", '"', "`"):
        if ch == "\\":
            i += 2
            continue
        if ch == state:
            state = None
        i += 1
        continue
    if state == "//":
        if ch == "\n":
            state = None
        i += 1
        continue
    if state == "/*":
        if ch == "*" and nxt == "/":
            state = None
            i += 2
            continue
        i += 1
        continue
    if ch == "/" and nxt == "/":
        state = "//"; i += 2; continue
    if ch == "/" and nxt == "*":
        state = "/*"; i += 2; continue
    if ch in "'\"`":
        state = ch; i += 1; continue
    if ch in "({[":
        stack.append((ch, i))
    elif ch in ")}]":
        if not stack:
            print("extra closer", ch, "at", i, repr(js[max(0, i - 60):i + 20]))
        else:
            o, oi = stack.pop()
            if "({[".index(o) != ")}]".index(ch):
                print("MISMATCH opened", o, "at", oi, "closed", ch, "at", i)
                print("   near:", repr(js[max(0, i - 120):i + 40]))
if stack:
    for o, oi in stack[:10]:
        print("UNCLOSED", o, "at", oi, "line", js.count("\n", 0, oi) + 1)
        print("   near:", repr(js[max(0, oi - 100):oi + 120]))
print("done. state at end:", state)

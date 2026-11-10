# -*- coding: utf-8 -*-
"""ตรวจความถูกต้องของสคริปต์ใน liver-eval-standalone.html แบบเบา ๆ (ไม่ต้องใช้ node)"""
import io, os, re

BASE = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(BASE, "liver-eval-standalone.html")
txt = io.open(path, encoding="utf-8").read()
print("file chars:", len(txt))

# 1) เอา JS ออกมาวิเคราะห์
start = txt.find("<script>")
end = txt.find("</script>", start)
js = txt[start + 8:end]
print("js chars:", len(js))

# 2) วงเล็บ {} () [] สมดุล
def balance(s, pairs):
    stack = []
    for i, ch in enumerate(s):
        if ch in pairs[0]:
            stack.append(ch)
        elif ch in pairs[1]:
            if not stack or pairs[0][pairs[1].index(ch)] != stack.pop():
                return "mismatch at %d" % i
    return "ok" if not stack else "unclosed %r" % (stack[:5],)

print("braces:", balance(js, ("{", "}")))
print("parens:", balance(js, ("(", ")")))
print("brackets:", balance(js, ("[", "]")))

# 3) ทุก id ที่ JS อ้างถึง ต้องมีใน HTML
ids_used = set(re.findall(r'\$\("([A-Za-z0-9_]+)"\)', js))
html = txt[:start] + txt[end:]
ids_html = set(re.findall(r'id="([A-Za-z0-9_]+)"', html))
missing = sorted(i for i in ids_used if i not in ids_html)
print("JS ids:", len(ids_used), "missing in HTML:", missing)

# 4) ฟังก์ชันที่เรียกใช้ต้องถูกประกาศ
called = set(re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\(', js))
declared = set(re.findall(r'function\s+([A-Za-z_][A-Za-z0-9_]*)', js))
builtin = set("if for while switch catch return typeof Number String JSON Math Date Object Array Set Promise fetch setTimeout clearTimeout encodeURIComponent alert confirm print".split())
print("maybe-undefined calls:", sorted(c for c in called if c not in declared and c not in builtin)[:20])

# 5) ตรวจว่าไม่มีตัวแปรหลุดแบบ printBtn/savedListEl ที่ถูกลบไปแล้ว
for bad in ["savedListEl", "renderHistory(", "buildRecord().imageDataUrl"]:
    print(bad, "->", js.count(bad))

# -*- coding: utf-8 -*-
import re, sys
src = open(sys.argv[1], encoding="utf-8").read()
keys = ("label|title|placeholder|tooltip|description|heading|subheading|subtitle"
        "|ariaLabel|menuDescription|message|header|hint|emptyText|confirmText"
        "|cancelText|primaryText|secondaryText|text|buttonLabel|caption")
pat = re.compile(r'(?:' + keys + r'):"((?:[^"\\]|\\.){2,140})"')
cjk = re.compile('[一-鿿]')
keep_single = {"hooks", "customize", "memory", "permissions", "skills",
               "plugins", "agents", "done", "close", "cancel", "back",
               "next", "save", "retry"}
seen = {}
for m in re.finditer(pat, src):
    v = m.group(1)
    if cjk.search(v):                      continue
    if not re.search(r'[A-Za-z]', v):      continue
    if '${' in v or 'http' in v or '://' in v: continue
    if re.match(r'^[a-z][a-zA-Z0-9_.-]*$', v): continue
    if re.match(r'^[A-Z][a-zA-Z0-9_]*$', v) and ' ' not in v: continue
    if len(v) < 3:                         continue
    if ' ' not in v and v.lower() not in keep_single: continue
    seen[v] = seen.get(v, 0) + 1
print("候选未汉化 UI 串:", len(seen))
for v in sorted(seen):
    print(f"  ({seen[v]})  {v}")

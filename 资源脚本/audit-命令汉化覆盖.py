#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
斜杠命令汉化覆盖审计
====================
全量列出 Claude Code 的斜杠命令（内置命令 + 技能），比对中文表，
直接输出"哪些还没汉化、它们的英文描述是什么"。取代"重载后人工截图找英文"的笨办法。

数据来源（都是机器上的真实来源，不靠猜）：
  1. 内置命令：从 claude CLI 二进制里提取（命令清单运行时由它下发，扩展里没有）。
  2. 技能命令：扫描技能目录下的 SKILL.md 前言（name + description）。
  3. 现有译文：读 斜杠命令-中文说明.json。

内置命令在二进制里有 5 种注册形态，本脚本都覆盖：
  A. type:"local|local-jsx|prompt",name:"x",...description:"..."
  B. name:"x",menuDescription:"...",description:"..."
  C. name:"x",...description:"..."         （名字在前，静态串）
  D. description:"...",name:"x"             （描述在前）
  E. name:"x",get description(){return`...`} （getter 动态描述，去掉 ${...}）
少数用工厂函数注册（name 为变量，如 vim/output-style）的，列入 KNOWN_MANUAL 白名单。
命令别名（aliases:[...]）会被解析，使别名 key 不再误报为"对不上"。

用法：
  python audit-命令汉化覆盖.py [--bin <claude二进制>] [--map <json>] [--skills <技能目录>]
默认自动定位。输出覆盖率 + 未汉化清单（含英文描述），并写出 缺口-待译.json。
"""
import re, json, os, sys, shutil, glob, argparse

# 工厂函数/文档串注册、正则抓不到、但确属命令的，手工认领（已在译表中）
KNOWN_MANUAL = {
    "vim": "Editor mode",
    "output-style": "Output style",
    "pr-comments": "Ask Claude in plain English to view pull request comments",
    "review-pr": "Review a pull request",
}

STR = r'((?:\\.|[^"\\])*)'   # 带转义的双引号字符串内容

def find_binary():
    # 优先 PATH 中的 claude;再兜底常见安装位置(各平台)
    p = shutil.which("claude")
    if p and os.path.exists(p):
        return p
    for cand in [os.path.expanduser("~/.local/bin/claude"),
                 os.path.expanduser("~/.claude/local/claude"),
                 "/usr/local/bin/claude", "/opt/homebrew/bin/claude"]:
        if os.path.exists(cand):
            return cand
    return None  # 找不到时用 --bin 显式指定

def clean(s):
    s = s.replace('\\"', '"').replace("\\\\", "\\")
    s = re.sub(r'\$\{[^}]*\}', '…', s)           # 去模板插值
    s = s.replace('\\xB7', '·').replace('\\n', ' ').replace('`', '').strip()
    return s

def extract_desc(before, after):
    """从 name 前后窗口提取描述，处理 5 种形态，取最近的。"""
    # 限定到本对象边界：after 截到下一个 name:"，before 截到上一个 name:"
    nb = re.search(r'name:"[a-z]', after)
    after_obj = after[:nb.start()] if nb else after
    pb = list(re.finditer(r'name:"[a-z]', before))
    before_obj = before[pb[-1].end():] if pb else before

    cands = []  # (距 name 的距离, 描述)
    m = re.search(r'description:"' + STR + r'"', after_obj)         # A/B/C 名字在前
    if m:
        cands.append((m.start(), clean(m.group(1))))
    for mm in re.finditer(r'description:"' + STR + r'"', before_obj):  # D 描述在前
        cands.append((len(before_obj) - mm.end(), clean(mm.group(1))))
    gp = after_obj.find('get description(){')                       # E getter
    if gp != -1:
        seg = after_obj[gp:gp + 400]
        tm = re.search(r'`([^`]*)`', seg) or re.search(r'return"' + STR + r'"', seg)
        if tm:
            cands.append((gp + 2000, clean(tm.group(1))))           # getter 优先级最低
    if not cands:
        return ""
    cands.sort(key=lambda x: x[0])
    return cands[0][1]

def extract_builtins(binpath):
    data = open(binpath, "rb").read().decode("latin1")
    cmds = {}        # name -> {desc, hidden, src, aliases}
    alias_of = {}    # alias -> canonical name
    MARK = re.compile(r'type:"(?:local|local-jsx|prompt)"|menuDescription:|isEnabled:'
                      r'|requires:\{ink|argumentHint:|allowedTools:|get description\(\)'
                      r'|aliases:\[|immediate')
    for m in re.finditer(r'name:"([a-z][a-z0-9-]{1,40})"', data):
        name = m.group(1)
        s, e = m.start(), m.end()
        before, after = data[max(0, s-220):s], data[e:e+520]
        if not MARK.search(before + after):
            continue
        desc = extract_desc(before, after)
        hidden = bool(re.search(r'isHidden:!0\b', after[:160]))
        am = re.search(r'aliases:\[([^\]]*)\]', before + after)
        aliases = re.findall(r'"([a-z][a-z0-9-]*)"', am.group(1)) if am else []
        # 跨多次出现：优先保留"有描述"的那条（避免抓到无描述的同名占位）
        if name not in cmds or (not cmds[name]["desc"] and desc):
            cmds[name] = {"desc": desc, "hidden": hidden, "src": "builtin",
                          "aliases": aliases or cmds.get(name, {}).get("aliases", [])}
        for a in aliases:
            alias_of.setdefault(a, name)
    return cmds, alias_of

def parse_frontmatter(path):
    try:
        txt = open(path, encoding="utf-8").read()
    except Exception:
        return None, None
    m = re.match(r'^\s*---\s*\n(.*?)\n---\s*\n', txt, re.S)
    if not m:
        return None, None
    fm = m.group(1)
    nm = re.search(r'^name:\s*(.+)$', fm, re.M)
    dm = re.search(r'^description:\s*(.+)$', fm, re.M)
    name = nm.group(1).strip().strip('"\'') if nm else None
    desc = re.split(r'[。\.\n]', dm.group(1).strip().strip('"\''))[0][:120] if dm else ""
    return name, desc

def extract_skills(skills_dir):
    cmds = {}
    for sk in glob.glob(os.path.join(skills_dir, "**", "SKILL.md"), recursive=True):
        name, desc = parse_frontmatter(sk)
        if name and re.match(r'^[a-z][a-z0-9:-]*$', name) and name not in cmds:
            cmds[name] = {"desc": desc, "hidden": False, "src": "skill", "aliases": []}
    return cmds

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", default=None)
    ap.add_argument("--map", default=os.path.join(here, "斜杠命令-中文说明.json"))
    ap.add_argument("--skills", default=os.path.expanduser("~/.claude/skills"))
    ap.add_argument("--plugin-skills", default=os.path.expanduser("~/.claude/plugins/cache"),
                    help="插件目录（含 superpowers 等第三方技能），递归扫 SKILL.md")
    args = ap.parse_args()

    binpath = args.bin or find_binary()
    if not binpath:
        print("✗ 找不到 claude 二进制，请用 --bin 指定"); sys.exit(1)

    builtins, alias_of = extract_builtins(binpath)
    skills = extract_skills(args.skills)
    plugin_skills = extract_skills(args.plugin_skills) if os.path.isdir(args.plugin_skills) else {}
    allcmds = dict(skills); allcmds.update(plugin_skills); allcmds.update(builtins)
    for k, v in KNOWN_MANUAL.items():
        allcmds.setdefault(k, {"desc": v, "hidden": False, "src": "manual", "aliases": []})

    zh = json.load(open(args.map, encoding="utf-8"))
    zh_keys = set(zh.keys())

    def covered(name, info):
        if name in zh_keys:
            return True
        if any(a in zh_keys for a in info.get("aliases", [])):  # 任一别名已译
            return True
        return False

    # 真实菜单命令一定带描述；空描述的多为内部项/工厂占位/误抓，剔除
    visible = {k: v for k, v in allcmds.items() if not v["hidden"] and v["desc"].strip()}
    translated = sorted(k for k, v in visible.items() if covered(k, v))
    missing = sorted(k for k, v in visible.items() if not covered(k, v))

    print("=" * 60)
    print(f"claude 二进制 : {binpath}")
    print(f"中文表        : {args.map}（{len(zh)} 条）")
    print("=" * 60)
    nb = sum(1 for v in visible.values() if v["src"] == "builtin")
    ns = sum(1 for v in visible.values() if v["src"] == "skill")
    nm = sum(1 for v in visible.values() if v["src"] == "manual")
    print(f"可见命令总数  : {len(visible)}（内置 {nb} + 技能 {ns} + 手工 {nm}）")
    print(f"已汉化        : {len(translated)}")
    print(f"未汉化        : {len(missing)}")
    print(f"覆盖率        : {len(translated)*100//len(visible) if visible else 0}%")

    if missing:
        print("\n" + "─" * 60 + "\n【未汉化命令】（英文描述可直接翻译）：")
        for k in missing:
            v = visible[k]
            tag = {"builtin": "内置", "skill": "技能", "manual": "手工"}[v["src"]]
            print(f"  /{k}  [{tag}]  {v['desc']}")
        stub = {k: visible[k]["desc"] for k in missing}
        out = os.path.join(here, "缺口-待译.json")
        json.dump(stub, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\n→ 已写出待译占位：{out}（翻译后并入中文表，重跑 inject 即可）")
    else:
        # 无缺口时清空 stub
        out = os.path.join(here, "缺口-待译.json")
        json.dump({}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("\n✅ 全部已汉化，无缺口。")

    stale = sorted(zh_keys - set(allcmds.keys()) - set(alias_of.keys()))
    if stale:
        print("\n" + "─" * 60)
        print(f"【提示】中文表里 {len(stale)} 个 key 对不上任何命令/别名（可能已下线，可清理）：")
        print("  " + ", ".join(stale))

if __name__ == "__main__":
    main()

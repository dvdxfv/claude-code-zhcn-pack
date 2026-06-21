#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动翻译斜杠命令缺口(调本机 claude CLI)
==========================================
公共译表 斜杠命令-中文说明.json 只覆盖官方内置命令 + 常见公共第三方插件
(gstack/superpowers 等)。每台机器装的私人技能不同，不可能靠一份静态译表
覆盖所有人——所以让脚本在"这台机器"上自己调用本机已安装的 claude CLI
做翻译，写到本机专属、不进 git 的 斜杠命令-中文说明.本机.json。

用法:
  python auto-translate-gaps.py [--yes|-y] [--dry-run]

流程:
  1. 跑一次 audit-命令汉化覆盖.py 拿到最新缺口(写出 缺口-待译.json)
  2. 排除"本机译表里已经翻过"的条目(幂等，不重复花钱翻译同一条)
  3. 打印待翻译条数 + 费用提示，终端确认(--yes 跳过，--dry-run 只看不翻)
  4. 把全部缺口打包成一次 `claude -p --output-format json` 调用
     (打包成一次调用是因为实测开销主要来自固定的上下文加载，不是按条数线性增长，
      逐条调用会被这部分固定开销重复收费很多次)
  5. 解析结果，只新增缺口对应的 key，合并写入本机译表(不覆盖已有条目)
  6. 提示重跑 一键汉化.py --yes --audit 应用

跑完之后:
  - inject-斜杠命令说明.cjs 和 audit-命令汉化覆盖.py 都会自动合并读取
    斜杠命令-中文说明.本机.json，无需额外操作。
  - 这份本机译表不进版本控制(见 .gitignore)，每台机器各管各的。
"""
import os, sys, json, subprocess, argparse, re

HERE = os.path.dirname(os.path.abspath(__file__))
OFFICIAL_MAP = os.path.join(HERE, "斜杠命令-中文说明.json")
LOCAL_MAP = os.path.join(HERE, "斜杠命令-中文说明.本机.json")
GAP_FILE = os.path.join(HERE, "缺口-待译.json")
GLOSSARY_MD = os.path.join(os.path.dirname(HERE), "翻译清单.md")

def load_json(path, default):
    if not os.path.isfile(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def extract_glossary():
    """从 翻译清单.md 的术语统一表里抠出 英文->中文 对照,塞进翻译提示词。
    按行扫描而不是单条正则:标题和表格之间常隔着说明段落(空行+一句话),
    单条正则锚不住表格起点,必须逐行找第一个 "|" 开头的表格行才稳。"""
    try:
        lines = open(GLOSSARY_MD, encoding="utf-8").read().splitlines()
    except Exception:
        return []

    start = next((i for i, l in enumerate(lines) if l.startswith("## 一、术语统一表")), None)
    if start is None:
        return []

    # 从标题往后找第一段连续的表格行(以 "|" 开头),直到遇到下一个标题或空段落结束
    table_lines = []
    in_table = False
    for line in lines[start + 1:]:
        s = line.strip()
        if s.startswith("##"):
            break
        if s.startswith("|"):
            in_table = True
            table_lines.append(s)
        elif in_table and not s:
            break

    if len(table_lines) < 3:  # 至少要有表头+分隔线+1条数据
        return []

    rows = []
    for line in table_lines[2:]:  # 跳过表头行 + "|---|---|" 分隔线
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) >= 2:
            en = re.sub(r"[*`]", "", cols[0]).strip()
            zh = re.sub(r"[*`]", "", cols[1]).strip()
            if en and zh:
                rows.append((en, zh))
    return rows

def run_audit():
    print("正在跑覆盖审计,定位缺口 ...")
    r = subprocess.run([sys.executable, os.path.join(HERE, "audit-命令汉化覆盖.py")],
                        capture_output=True, text=True, cwd=HERE)
    if r.stdout.strip():
        for l in r.stdout.strip().splitlines()[-6:]:
            print("  " + l)
    if r.returncode != 0 and "找不到 claude 二进制" in (r.stdout + r.stderr):
        print("❌ 找不到 claude 二进制,无法定位缺口。请确认 claude CLI 已安装并在 PATH 里。")
        sys.exit(1)

def call_claude_translate(gaps: dict, glossary: list) -> dict:
    glossary_lines = "\n".join(f"- {en} -> {zh}" for en, zh in glossary)
    prompt = f"""你是专业的软件界面本地化译者,正在给 Claude Code 的斜杠命令描述做中文化。

请把下面这些命令的英文描述,翻译成简洁、自然的中文(每条不超过 30 个汉字,意译不要逐字直译,
让中文用户一眼看懂这个命令是做什么的)。

术语约定(同一概念全程统一用法,不要混用):
{glossary_lines}

请以 JSON 对象格式输出,key 必须跟输入的命令名一字不差,value 是中文描述。
不要输出任何其他文字、不要解释、不要 markdown 代码块标记,只输出裸 JSON 对象。

待翻译命令:
{json.dumps(gaps, ensure_ascii=False, indent=2)}
"""
    r = subprocess.run(["claude", "-p", "--output-format", "json"],
                        input=prompt, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(f"❌ claude CLI 调用失败 (exit {r.returncode})")
        print(r.stderr.strip()[:500])
        sys.exit(1)
    try:
        outer = json.loads(r.stdout)
    except Exception as e:
        print(f"❌ claude CLI 输出不是合法 JSON: {e}")
        print(r.stdout[:500])
        sys.exit(1)
    if outer.get("is_error"):
        print(f"❌ claude CLI 返回错误: {outer.get('result')}")
        sys.exit(1)
    raw = outer.get("result", "")
    # 防御性剥掉可能出现的 markdown 代码块包裹
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    try:
        translated = json.loads(raw)
    except Exception as e:
        print(f"❌ 翻译结果不是合法 JSON: {e}")
        print(raw[:500])
        sys.exit(1)
    cost = outer.get("total_cost_usd")
    if cost is not None:
        print(f"💰 本次调用花费约 ${cost:.4f}")
    return translated

def main():
    ap = argparse.ArgumentParser(description="调本机 claude CLI 自动翻译斜杠命令缺口")
    ap.add_argument("--yes", "-y", action="store_true", help="跳过确认,直接调用 claude CLI 翻译")
    ap.add_argument("--dry-run", action="store_true", help="只看缺口列表,不调用 claude CLI")
    args = ap.parse_args()

    run_audit()

    gaps = load_json(GAP_FILE, {})
    local_map = load_json(LOCAL_MAP, {})

    # 幂等:已经在本机译表里的条目不重新花钱翻译
    new_gaps = {k: v for k, v in gaps.items() if k not in local_map}

    if not new_gaps:
        print("\n✅ 没有新缺口需要翻译(全部已覆盖,或本机译表已经翻过)。")
        return

    print(f"\n📋 发现 {len(new_gaps)} 条本机专属缺口待翻译(官方译表 + 本机译表都没覆盖):")
    for k, v in list(new_gaps.items())[:15]:
        print(f"  /{k}  {v[:60]}")
    if len(new_gaps) > 15:
        print(f"  ... 还有 {len(new_gaps) - 15} 条")

    if args.dry_run:
        print("\n👀 --dry-run 模式:只看列表,不调用 claude CLI,不会产生费用。")
        return

    print(f"\n⚠ 接下来会调用本机 claude CLI 翻译这 {len(new_gaps)} 条,会产生少量真实 API 费用"
          f"(实测同类批量调用约 $0.2~0.3,具体以账单为准)。")

    if not args.yes:
        if not sys.stdin.isatty():
            print("⚠ 非交互环境且未指定 --yes,为避免意外扣费,不会自动调用。加 --yes 跳过确认。")
            sys.exit(2)
        try:
            ans = input("是否现在调用 claude CLI 翻译?[y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消。")
            sys.exit(2)
        if ans not in ("y", "yes"):
            print("已取消,未调用 claude CLI,未产生费用。")
            sys.exit(2)

    glossary = extract_glossary()
    translated = call_claude_translate(new_gaps, glossary)

    # 只接受请求里真实存在的 key,防止模型幻觉出多余字段污染译表
    accepted = {k: v for k, v in translated.items() if k in new_gaps}
    missing = [k for k in new_gaps if k not in accepted]

    local_map.update(accepted)
    with open(LOCAL_MAP, "w", encoding="utf-8") as f:
        json.dump(local_map, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"\n✅ 已写入 {len(accepted)} 条到本机译表: {LOCAL_MAP}")
    if missing:
        print(f"⚠ {len(missing)} 条翻译结果里没返回(可能被模型跳过),仍是英文: {', '.join(missing[:10])}")
    print(f"\n下一步:重跑 python 一键汉化.py --yes --audit 应用到扩展面板。")

if __name__ == "__main__":
    main()

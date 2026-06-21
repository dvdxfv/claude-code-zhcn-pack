#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code 插件一键汉化
=======================
用法:
  python 一键汉化.py [--audit] [--preview] [--yes|-y] [--ext <扩展目录>] [--tui] [--no-tui]

升级扩展后跑一条命令即可: python 一键汉化.py --audit

流程分两阶段:
  阶段一 · 扫描 + 确认(纯终端文本,不进 TUI)
    1. 定位扩展、读取全部译表
    2. 生成人类可读的译文清单 汉化预览.md(可交给其他 Agent 交叉审)
    3. 终端提示确认:输入 y 才真正应用;其它任何输入(含直接 Enter)都视为取消
       --yes/-y  跳过确认,直接应用
       --preview 只生成清单,不问、不应用,不碰任何真实文件

  阶段二 · 真实应用(确认通过后才会执行,进 TUI)
    4. 备份原版 index.js 为 index.js.orig(幂等:之后每次从 .orig 还原再重打)
    5. 应用 UI 字符串汉化(精确替换 + 锚定替换 + 补漏)
    6. 注入斜杠命令中文描述(改渲染钩子 + 智能 ID 匹配 + 中文命令表)
    7. 注入 CLI spinner 汉化(写 ~/.claude/settings.json,187 动词 + 41 提示)
    8. node --check 语法校验(防白屏)
    9. 可选 --audit: 跑命令覆盖审计 + UI 串缺口审计

如果汉化结果不满意怎么办(见 README "纠错"一节):
  1. 翻 汉化预览.md(或资源脚本/map*.json、斜杠命令-中文说明.json、spinner-*.json)找到错译
  2. 改对应译表
  3. 重跑本脚本(幂等:从 index.js.orig 重新生成,不会叠加旧改动)
  4. 想完全恢复英文原版:见 README"卸载/还原"
"""
import os, sys, glob, subprocess, shutil, json, argparse, time

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "资源脚本")
INDEX = "webview/index.js"

# ============================================================
# 阶段一:扫描 + 生成 Markdown 清单 + 终端确认
# ============================================================

def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def _md_escape(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ").replace("\r", "")

def _md_table(pairs, headers=("英文", "中文")) -> str:
    lines = [f"| {headers[0]} | {headers[1]} |", "|---|---|"]
    for en, zh in pairs:
        lines.append(f"| {_md_escape(en)} | {_md_escape(zh)} |")
    return "\n".join(lines)

def generate_markdown_preview(ext_dir, target):
    """读取全部译表,生成人类可读的 汉化预览.md。纯读取,不写任何真实扩展文件。"""
    map1 = _read_json(os.path.join(RES, "map1-主批次.json"))
    map2 = _read_json(os.path.join(RES, "map2-补充批次.json"))
    map4 = _read_json(os.path.join(RES, "map4-补漏.json"))
    cmds = _read_json(os.path.join(RES, "斜杠命令-中文说明.json"))
    tips = _read_json(os.path.join(RES, "spinner-tips-zh.json"), default=[])
    verbs = _read_json(os.path.join(RES, "spinner-verbs-zh.json"), default=[])

    counts = [
        ("扩展 UI 字符串(精确替换)", len(map1)),
        ("扩展 UI 字符串(锚定替换)", len(map2)),
        ("扩展 UI 字符串(设置/对话框补漏)", len(map4)),
        ("斜杠命令描述", len(cmds)),
        ("CLI spinner 提示", len(tips)),
        ("CLI spinner 动词(趣味本地化,无对应英文)", len(verbs)),
    ]
    total = sum(c for _, c in counts)

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    p = []
    p.append("# Claude Code 汉化预览\n")
    p.append(
        f"> 由 `一键汉化.py` 于 {now} 自动生成,列出本次运行**将会**应用的全部翻译。\n"
        f"> 生成本文件**不会**修改任何真实文件(不动 index.js / index.js.orig / settings.json)。\n>\n"
        f"> 可以把这份文件交给另一个 Agent(Codex / DeepSeek / 豆包 / Gemini 等)做独立交叉审,\n"
        f"> 也可以直接看完后回到终端按 `y` 确认应用,按其它键/直接 Enter 取消(不会动任何文件)。\n"
    )
    p.append(f"- 扩展目录:`{ext_dir}`")
    p.append(f"- 目标文件:`{target}`\n")

    p.append("## 摘要\n")
    p.append("| 类别 | 条数 |")
    p.append("|---|---|")
    for name, c in counts:
        p.append(f"| {name} | {c} |")
    p.append(f"| **合计** | **{total}** |\n")

    p.append("## 一、扩展 UI 字符串 — 精确替换\n")
    p.append(f"来源:`资源脚本/map1-主批次.json`,共 {len(map1)} 条。裸字面量/JSX 文本节点替换。\n")
    p.append(_md_table(map1.items()))
    p.append("")

    p.append("## 二、扩展 UI 字符串 — 锚定替换\n")
    p.append(f"来源:`资源脚本/map2-补充批次.json`,共 {len(map2)} 条。只动 `label:`/`title:` 等显示位前缀,更安全。\n")
    p.append(_md_table(map2.items()))
    p.append("")

    p.append("## 三、扩展 UI 字符串 — 设置/对话框补漏\n")
    p.append(f"来源:`资源脚本/map4-补漏.json`,共 {len(map4)} 条。\n")
    p.append(_md_table(map4.items()))
    p.append("")

    p.append("## 四、斜杠命令描述\n")
    p.append(f"来源:`资源脚本/斜杠命令-中文说明.json`,共 {len(cmds)} 条。\n")
    p.append(_md_table(cmds.items(), headers=("命令", "中文描述")))
    p.append("")

    p.append("## 五、CLI 终端 — spinner 提示\n")
    p.append(f"来源:`资源脚本/spinner-tips-zh.json`,共 {len(tips)} 条。写入 `~/.claude/settings.json`。\n")
    p.append(_md_table([(t.get("id", ""), t.get("text", "")) for t in tips], headers=("ID", "中文提示")))
    p.append("")

    p.append("## 六、CLI 终端 — spinner 动词(节选)\n")
    p.append(
        f"来源:`资源脚本/spinner-verbs-zh.json`,共 {len(verbs)} 条趣味本地化动词"
        f"(纯装饰性文字,没有对应英文原文,这里只节选前 20 条,完整列表见 JSON 源文件)。\n"
    )
    p.append("| 序号 | 中文 |")
    p.append("|---|---|")
    for i, v in enumerate(verbs[:20], 1):
        p.append(f"| {i} | {_md_escape(v)} |")
    p.append("")

    md = "\n".join(p)
    out_path = os.path.join(HERE, "汉化预览.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    return out_path, total, counts

def ask_confirm(total, md_path, auto_yes, preview_only):
    print(f"\n📋 译文清单已生成:{md_path}")
    print(f"   共 {total} 条改动,详见上面文件里的摘要表。")
    if preview_only:
        print("👀 --preview 模式:只生成清单,不会询问,也不会应用。")
        return False
    if auto_yes:
        print("✅ --yes 已指定,跳过确认,自动继续。")
        return True
    if not sys.stdin.isatty():
        print("⚠ 当前是非交互环境(没有终端可输入),且未指定 --yes,为安全起见不会自动应用。")
        print("  想跳过确认直接应用:加 --yes;想交互确认:在真实终端里运行本脚本。")
        return False
    print("可以先把上面这份 Markdown 交给另一个 Agent 交叉审一遍,再回来确认。")
    try:
        ans = input("是否现在应用以上改动?[y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消。")
        return False
    return ans in ("y", "yes")

# ============================================================
# 阶段二 · TUI 渲染器(纯 stdlib,Windows 10+/macOS/Linux 终端)
# ============================================================
# 设计目标:
#   - 不依赖 rich/curses/blessed 等第三方库
#   - 单行进度条 + 滚动日志,ANSI 转义,能在 Win11 cmd/PowerShell/macOS Terminal 跑
#   - 每帧按终端宽度截断每一行(避免自动换行错位导致的"画面漂移")
#   - 每帧末尾清空到屏幕底部(避免新帧变短时旧帧残留)
#   - 非 TTY(被重定向/管道)时自动降级为普通 print,绝不打乱日志

class TUI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"

    HOME = "\033[H"
    ERASE_TO_END = "\033[0J"
    SHOW_CURSOR = "\033[?25h"
    HIDE_CURSOR = "\033[?25l"

    def __init__(self, enabled: bool):
        self.enabled = enabled and sys.stdout.isatty()
        self.total_steps = 8
        self.cur_step = 0
        self.cur_label = "准备中"
        self.lines_log = []
        self.start_time = time.time()
        if self.enabled:
            self._out("\033[?1049h")  # 进入备用屏幕(完成时退出,不留痕迹)
            self._out(self.HIDE_CURSOR)

    def _out(self, s: str):
        try:
            sys.stdout.write(s)
            sys.stdout.flush()
        except Exception:
            pass

    @staticmethod
    def _vislen(s: str) -> int:
        n, i = 0, 0
        while i < len(s):
            if s[i] == "\033":
                j = s.find("m", i)
                i = (j + 1) if j != -1 else len(s)
                continue
            n += 2 if ord(s[i]) > 0x1100 else 1
            i += 1
        return n

    @staticmethod
    def _clip(s: str, max_width: int) -> str:
        out, n, i = [], 0, 0
        while i < len(s):
            if s[i] == "\033":
                j = s.find("m", i)
                if j == -1:
                    break
                out.append(s[i:j+1])
                i = j + 1
                continue
            w = 2 if ord(s[i]) > 0x1100 else 1
            if n + w > max_width:
                out.append("…")
                break
            out.append(s[i])
            n += w
            i += 1
        return "".join(out)

    def _term_width(self) -> int:
        try:
            return max(40, shutil.get_terminal_size(fallback=(100, 24)).columns)
        except Exception:
            return 100

    def _redraw(self):
        if not self.enabled:
            return
        width = self._term_width()
        safe = width - 1

        elapsed = int(time.time() - self.start_time)
        mins, secs = divmod(elapsed, 60)
        overall = max(0.0, min(1.0, (self.cur_step - 1) / self.total_steps if self.total_steps else 0))

        bar_width = 36
        filled = int(overall * bar_width)
        bar = f"{self.GREEN}{'█'*filled}{self.GRAY}{'░'*(bar_width-filled)}{self.RESET}"

        lines = [
            f"{self.BOLD}{self.CYAN}Claude Code 扩展汉化{self.RESET}  {self.GRAY}{mins:02d}:{secs:02d}{self.RESET}",
            f"{bar} {overall*100:5.1f}%  {self.BOLD}{self.cur_step}/{self.total_steps}{self.RESET} {self.cur_label}",
            "",
        ]
        for line in self.lines_log[-16:]:
            lines.append(f"  {line}")

        parts = [self.HOME]
        for line in lines:
            parts.append(self._clip(line, safe))
            parts.append("\n")
        parts.append(self.ERASE_TO_END)
        self._out("".join(parts))

    def step(self, n: int, label: str):
        self.cur_step = n
        self.cur_label = label
        self._redraw()

    def set_pct(self, pct: int):
        self._redraw()

    def log(self, msg: str, kind: str = "info"):
        prefix = {
            "info": f"{self.GRAY}·{self.RESET}",
            "ok":   f"{self.GREEN}✓{self.RESET}",
            "warn": f"{self.YELLOW}!{self.RESET}",
            "err":  f"{self.RED}✗{self.RESET}",
        }.get(kind, "·")
        self.lines_log.append(f"{prefix} {msg}")
        self._redraw()

    def finish(self, ok: bool, msg: str = ""):
        if not self.enabled:
            return
        self.cur_step = self.total_steps
        self.cur_label = msg or ("完成" if ok else "失败")
        self._redraw()
        time.sleep(0.4)
        self._out(self.SHOW_CURSOR)
        self._out("\033[?1049l")
        if ok:
            print(f"{self.BOLD}{self.GREEN}✅ {msg or '汉化完成'}{self.RESET}")
        else:
            print(f"{self.BOLD}{self.RED}❌ {msg or '失败'}{self.RESET}")

_TUI: TUI = None  # type: ignore

def tui_log(msg: str, kind: str = "info"):
    if _TUI and _TUI.enabled:
        _TUI.log(msg, kind)
    else:
        prefix = {"ok": "✓", "warn": "!", "err": "✗"}.get(kind, "·")
        print(f"  {prefix} {msg}")

def find_ext():
    for base in [os.path.expanduser(p) for p in [
        "~/.cursor/extensions", "~/.vscode/extensions", "~/.vscode-insiders/extensions"]]:
        dirs = sorted(glob.glob(os.path.join(base, "anthropic.claude-code-*")),
                      reverse=True)
        if dirs:
            return dirs[0]
    return None

def find_node():
    p = shutil.which("node")
    if p:
        return p
    for cand in ["/usr/local/bin/node", "/usr/bin/node",
                 os.path.expanduser("~/.nvm/current/bin/node")]:
        if os.path.isfile(cand):
            return cand
    return "node"

def run(cmd, desc, pct: int = -1):
    tui_log(desc + " …", "info")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=RES)
    if r.stdout.strip():
        for l in r.stdout.strip().splitlines():
            tui_log(l, "info")
    if r.returncode != 0:
        tui_log(f"{desc} 失败 (exit {r.returncode})", "err")
        if r.stderr.strip():
            for l in r.stderr.strip().splitlines()[:5]:
                tui_log(l, "err")
        if _TUI:
            _TUI.finish(False, f"步骤失败:{desc}")
        sys.exit(1)
    tui_log(desc + " 完成", "ok")
    return r.stdout

def run_soft(cmd, desc, pct: int = -1):
    out = run(cmd, desc, pct)
    if "ZERO-MATCH" in out:
        tui_log("部分串 0 命中(若刚升级应为 0,请检查基线是否真·原版)", "warn")
    return out

def main():
    global _TUI
    ap = argparse.ArgumentParser(description="Claude Code 插件一键汉化")
    ap.add_argument("--audit", action="store_true", help="汉化后跑覆盖审计")
    ap.add_argument("--preview", action="store_true",
                     help="只生成译文预览 Markdown,不询问、不应用,不碰任何真实文件")
    ap.add_argument("--yes", "-y", action="store_true", help="跳过确认提示,直接应用")
    ap.add_argument("--ext", default=None, help="手动指定扩展目录(默认自动定位最新版)")
    ap.add_argument("--tui", action="store_true", help="强制启用终端进度条(交互式终端默认自动启用)")
    ap.add_argument("--no-tui", action="store_true", help="强制禁用 TUI,用普通 print")
    args = ap.parse_args()

    # ---- 阶段一:扫描 + 生成清单 + 确认(纯文本终端,不进 TUI) ----
    ext_dir = args.ext or find_ext()
    if not ext_dir or not os.path.isdir(ext_dir):
        print("❌ 找不到 claude-code 扩展目录,请用 --ext 指定")
        sys.exit(1)

    target = os.path.join(ext_dir, INDEX)
    if not os.path.isfile(target):
        print(f"❌ 目标文件不存在: {target}")
        sys.exit(1)

    print(f"扩展: {ext_dir}")
    print(f"目标: {target}")
    print("正在扫描译表 ...")
    md_path, total, _counts = generate_markdown_preview(ext_dir, target)

    proceed = ask_confirm(total, md_path, args.yes, args.preview)
    if not proceed:
        if args.preview:
            print(f"\n预览完成,未修改任何真实文件。改完译表满意后,重跑不带 --preview 即可应用。")
            sys.exit(0)
        print(f"\n已取消,未修改任何真实文件。译文清单仍保留在 {md_path},"
              f"可以编辑译表或交给其他 Agent 审完再重跑。")
        sys.exit(2)

    # ---- 阶段二:真实应用(确认通过,进 TUI) ----
    if args.no_tui:
        tui_enabled = False
    elif args.tui:
        tui_enabled = True
    else:
        tui_enabled = sys.stdout.isatty()

    _TUI = TUI(tui_enabled)

    try:
        node = find_node()
        node_cmd = node if node != "node" else "node"

        if not tui_enabled:
            print(f"\n开始应用 ...")
            print(f"node:  {node_cmd}")
            print()

        # 1) 备份/还原基线
        _TUI.step(1, "备份/还原基线")
        orig = target.replace("index.js", "index.js.orig")
        if os.path.isfile(orig):
            shutil.copy2(orig, target)
            tui_log(f"已从基线还原: {os.path.basename(orig)}", "ok")
        else:
            shutil.copy2(target, orig)
            tui_log(f"已备份原版: {os.path.basename(orig)}", "ok")

        # 2) 精确 + 锚定
        _TUI.step(2, "应用 UI 字符串汉化")
        run_soft(f'{node_cmd} apply-精确.cjs map1-主批次.json "{target}"', "精确替换(主批次)", pct=50)
        run_soft(f'{node_cmd} apply-锚定.cjs map2-补充批次.json "{target}"', "锚定替换(补充批次)", pct=100)

        # 3) UI 补漏
        _TUI.step(3, "UI 补漏(设置/对话框)")
        run(f'python apply-ui补漏.py "{target}" "{target}.post-gap"', "UI 补漏", pct=100)
        precmd = target + ".post-gap"
        if not os.path.isfile(precmd):
            tui_log("补漏后基线未生成", "err")
            if _TUI: _TUI.finish(False, "补漏失败")
            sys.exit(1)

        # 4) 斜杠命令
        _TUI.step(4, "注入斜杠命令中文描述")
        run(f'{node_cmd} inject-斜杠命令说明.cjs "{precmd}" 斜杠命令-中文说明.json "{target}"',
            "注入斜杠命令", pct=100)
        os.remove(precmd)

        # 5) CLI spinner
        _TUI.step(5, "注入 CLI spinner 汉化")
        run(f'{node_cmd} apply-spinner.cjs --merge', "写入 settings.json", pct=100)

        # 6) 语法校验
        _TUI.step(6, "node 语法校验")
        run(f'{node_cmd} --check "{target}"', "语法校验", pct=100)

        # 7) 完成基础部分
        _TUI.step(7, "汉化完成")
        tui_log("扩展 + CLI 已汉化", "ok")
        if not tui_enabled:
            print("\n✅ 汉化完成!Ctrl+Shift+P → Developer: Reload Window 生效")

        # 8) 可选审计
        if args.audit:
            _TUI.step(8, "覆盖审计")
            run("python audit-命令汉化覆盖.py", "命令覆盖审计", pct=50)
            ui_gap = os.path.join(RES, "audit-ui串缺口.py")
            if os.path.isfile(ui_gap):
                run(f"python {ui_gap} \"{target}\"", "UI 串缺口审计", pct=100)
            tui_log("命令覆盖率应 ~99%,UI 缺口应仅剩 Monaco 内部串", "info")

        if _TUI:
            _TUI.finish(True, "汉化完成!请按 Ctrl+Shift+P → Developer: Reload Window")
        else:
            print("\n🎉 全部完成。")

    except KeyboardInterrupt:
        if _TUI:
            _TUI.finish(False, "用户中断")
        else:
            print("\n⚠ 用户中断")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as e:
        tui_log(f"未捕获异常: {e}", "err")
        if _TUI:
            _TUI.finish(False, "异常退出")
        raise

if __name__ == "__main__":
    main()

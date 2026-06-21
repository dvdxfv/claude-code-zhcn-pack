#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code 插件一键汉化
=======================
用法:
  python 一键汉化.py [--audit] [--preview] [--ext <扩展目录>] [--tui] [--no-tui]

升级扩展后跑一条命令即可: python 一键汉化.py --audit

可选 --preview: 预览模式,完整跑一遍翻译流程但只写到临时文件,
   不碰真实的 index.js / index.js.orig / ~/.claude/settings.json。
   用来在正式汉化前看一眼会发生什么改动(统计 + 可选 diff)。
可选 --tui: 强制启用终端进度条(默认在交互式终端自动启用)
   --no-tui: 强制禁用,只用普通 print(便于日志重定向)

步骤:
  1. 自动定位已安装的 claude-code 扩展(或 --ext 指定)
  2. 备份原版 index.js 为 index.js.orig(幂等:之后每次从 .orig 还原再重打)
     [--preview 模式跳过此步,不动真实文件]
  3. 应用 UI 字符串汉化(精确替换 + 锚定替换)
  4. 应用 UI 补漏(设置/对话框/模板字符串等展示文案)
  5. 注入斜杠命令中文描述(改渲染钩子 + 智能 ID 匹配 + 中文命令表)
  6. 注入 CLI spinner 汉化(写 ~/.claude/settings.json,187 动词 + 41 提示)
     [--preview 模式改用 --dry-run,不写真实 settings.json]
  7. node --check 语法校验(防白屏)
  8. 可选 --audit: 跑命令覆盖审计 + UI 串缺口审计

如果汉化结果不满意怎么办(见 README "纠错"一节):
  1. 改 资源脚本/map*.json、斜杠命令-中文说明.json、spinner-*.json 里的译文
  2. 重跑本脚本(幂等:从 index.js.orig 重新生成,不会叠加旧改动)
  3. 想完全恢复英文原版:见 README"卸载/还原"
"""
import os, sys, glob, subprocess, shutil, json, argparse, time

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "资源脚本")
INDEX = "webview/index.js"

# ============================================================
# TUI 渲染器(纯 stdlib,Windows 10+/macOS/Linux 终端)
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
        """可见宽度估算:跳过 ANSI 转义,中日韩字符计 2 列"""
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
        """按可见宽度截断,保留 ANSI 转义不计入宽度"""
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
        safe = width - 1  # 留 1 列安全边界,避免恰好顶满触发自动换行

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
        # 当前版本不单独画子进度条(简化布局,避免多元素错位);
        # 保留方法签名以兼容调用点,仅用于驱动重绘节奏。
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
        self._out("\033[?1049l")  # 退出备用屏幕,回到主屏幕(不留痕迹)
        if ok:
            print(f"{self.BOLD}{self.GREEN}✅ {msg or '汉化完成'}{self.RESET}")
        else:
            print(f"{self.BOLD}{self.RED}❌ {msg or '失败'}{self.RESET}")

# 全局 TUI(主流程里所有 print 都被它接管)
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
                     help="预览模式:完整跑一遍流程,只写临时文件,不碰真实 index.js/settings.json")
    ap.add_argument("--ext", default=None, help="手动指定扩展目录(默认自动定位最新版)")
    ap.add_argument("--tui", action="store_true", help="强制启用终端进度条(交互式终端默认自动启用)")
    ap.add_argument("--no-tui", action="store_true", help="强制禁用 TUI,用普通 print")
    args = ap.parse_args()

    if args.no_tui:
        tui_enabled = False
    elif args.tui:
        tui_enabled = True
    else:
        tui_enabled = sys.stdout.isatty()

    _TUI = TUI(tui_enabled)

    try:
        if not tui_enabled:
            print("预览模式 ..." if args.preview else "扩展汉化开始 ...")

        ext_dir = args.ext or find_ext()
        if not ext_dir or not os.path.isdir(ext_dir):
            tui_log("找不到 claude-code 扩展目录,请用 --ext 指定", "err")
            if _TUI: _TUI.finish(False, "扩展目录未找到")
            sys.exit(1)

        target = os.path.join(ext_dir, INDEX)
        if not os.path.isfile(target):
            tui_log(f"目标文件不存在: {target}", "err")
            if _TUI: _TUI.finish(False, "目标文件不存在")
            sys.exit(1)

        node = find_node()
        node_cmd = node if node != "node" else "node"

        if not tui_enabled:
            print(f"扩展: {ext_dir}")
            print(f"目标: {target}")
            print(f"node:  {node_cmd}")
            print()

        orig = target.replace("index.js", "index.js.orig")

        if args.preview:
            # 预览模式:绝不碰 index.js / index.js.orig / 真实 settings.json。
            # 用一份临时副本走完整流程,只看统计输出,跑完即可删除。
            # 文件名必须保留 .js 后缀(node --check 靠后缀判断语法解析器)。
            work = target.replace("index.js", "index.preview-scratch.js")
            baseline = orig if os.path.isfile(orig) else target
            shutil.copy2(baseline, work)
            tui_log(f"预览基线: {os.path.basename(baseline)} → {os.path.basename(work)}(临时文件,不影响真实扩展)", "info")
        else:
            work = target
            if os.path.isfile(orig):
                shutil.copy2(orig, target)
                tui_log(f"已从基线还原: {os.path.basename(orig)}", "ok")
            else:
                shutil.copy2(target, orig)
                tui_log(f"已备份原版: {os.path.basename(orig)}", "ok")

        _TUI.step(1, "备份/还原基线" if not args.preview else "准备预览基线")

        # 2) 精确 + 锚定
        _TUI.step(2, "应用 UI 字符串汉化")
        run_soft(f'{node_cmd} apply-精确.cjs map1-主批次.json "{work}"', "精确替换(主批次)", pct=50)
        run_soft(f'{node_cmd} apply-锚定.cjs map2-补充批次.json "{work}"', "锚定替换(补充批次)", pct=100)

        # 3) UI 补漏
        _TUI.step(3, "UI 补漏(设置/对话框)")
        run(f'python apply-ui补漏.py "{work}" "{work}.post-gap"', "UI 补漏", pct=100)
        precmd = work + ".post-gap"
        if not os.path.isfile(precmd):
            tui_log("补漏后基线未生成", "err")
            if _TUI: _TUI.finish(False, "补漏失败")
            sys.exit(1)

        # 4) 斜杠命令
        _TUI.step(4, "注入斜杠命令中文描述")
        run(f'{node_cmd} inject-斜杠命令说明.cjs "{precmd}" 斜杠命令-中文说明.json "{work}"',
            "注入斜杠命令", pct=100)
        os.remove(precmd)

        # 5) CLI spinner(预览模式走 --dry-run,不写真实 settings.json)
        _TUI.step(5, "CLI spinner 汉化" + ("(预览,不写文件)" if args.preview else ""))
        spinner_flag = "--dry-run" if args.preview else "--merge"
        run(f'{node_cmd} apply-spinner.cjs {spinner_flag}', "spinner 处理", pct=100)

        # 6) 语法校验
        _TUI.step(6, "node 语法校验")
        run(f'{node_cmd} --check "{work}"', "语法校验", pct=100)

        # 7) 完成基础部分
        _TUI.step(7, "处理完成")
        if args.preview:
            tui_log(f"预览完成,未修改任何真实文件", "ok")
            tui_log(f"预览结果文件: {work}", "info")
            tui_log(f"想正式应用:去掉 --preview 重跑;不想保留预览文件可手动删除它", "info")
        else:
            tui_log("扩展 + CLI 已汉化", "ok")
            if not tui_enabled:
                print("\n✅ 汉化完成!Ctrl+Shift+P → Developer: Reload Window 生效")

        # 8) 可选审计(预览模式下针对临时文件审计,仍不碰真实文件)
        if args.audit:
            _TUI.step(8, "覆盖审计")
            if not args.preview:
                run("python audit-命令汉化覆盖.py", "命令覆盖审计", pct=50)
            ui_gap = os.path.join(RES, "audit-ui串缺口.py")
            if os.path.isfile(ui_gap):
                run(f"python {ui_gap} \"{work}\"", "UI 串缺口审计", pct=100)
            tui_log("命令覆盖率应 ~99%,UI 缺口应仅剩 Monaco 内部串", "info")

        if _TUI:
            msg = "预览完成!未修改任何真实文件" if args.preview else "汉化完成!请按 Ctrl+Shift+P → Developer: Reload Window"
            _TUI.finish(True, msg)
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

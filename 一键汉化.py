#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code 插件一键汉化
=======================
用法:
  python 一键汉化.py [--audit] [--ext <扩展目录>] [--tui] [--no-tui]

升级扩展后跑一条命令即可: python 一键汉化.py --audit

可选 --tui: 强制启用终端进度条(默认在交互式终端自动启用)
   --no-tui: 强制禁用,只用普通 print(便于日志重定向)

步骤:
  1. 自动定位已安装的 claude-code 扩展(或 --ext 指定)
  2. 备份原版 index.js 为 index.js.orig(幂等:之后每次从 .orig 还原再重打)
  3. 应用 UI 字符串汉化(精确替换 + 锚定替换)
  4. 应用 UI 补漏(设置/对话框/模板字符串等展示文案)
  5. 注入斜杠命令中文描述(改渲染钩子 + 智能 ID 匹配 + 中文命令表)
  6. 注入 CLI spinner 汉化(写 ~/.claude/settings.json,187 动词 + 41 提示)
  7. node --check 语法校验(防白屏)
  8. 可选 --audit: 跑命令覆盖审计 + UI 串缺口审计
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
#   - 进度条用 ANSI 转义 + \r 覆盖当前行,能在 Win11 cmd/PowerShell/macOS Terminal 跑
#   - 非 TTY(被重定向/管道)时自动降级为普通 print,绝不打乱日志
#   - 全局唯一实例,任何 print/错误都能进 TUI 状态栏

class TUI:
    # ANSI 颜色(Win10 1607+/Win11/macOS Terminal/iTerm 都支持)
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"

    def __init__(self, enabled: bool):
        self.enabled = enabled and sys.stdout.isatty()
        self.total_steps = 8
        self.cur_step = 0
        self.cur_label = "准备中"
        self.cur_pct = 0  # 当前步骤 0-100
        self.lines_log = []  # 子步骤日志(红绿黄普通文本)
        self.start_time = time.time()
        if self.enabled:
            # 切到备用缓冲区,完成时回到主缓冲区(避免中间日志残留在屏幕上)
            self._out("\033[?1049h")  # 进入备用屏幕
            self._out(self.CLEAR + self.HOME)

    HOME = "\033[H"
    CLEAR = "\033[2J"
    ERASE_LINE = "\033[2K"
    HIDE_CURSOR = "\033[?25l"
    SHOW_CURSOR = "\033[?25h"

    def _out(self, s: str):
        try:
            sys.stdout.write(s)
            sys.stdout.flush()
        except Exception:
            pass

    def _redraw(self):
        """重画整个 TUI 界面:标题 + 进度条 + 步骤列表 + 日志窗"""
        if not self.enabled:
            return
        out = []
        out.append(self.HOME)
        out.append(self.ERASE_LINE)
        # 标题
        elapsed = int(time.time() - self.start_time)
        mins, secs = divmod(elapsed, 60)
        title = f"{self.BOLD}{self.CYAN}Claude Code 扩展汉化 · TUI{self.RESET}  {self.GRAY}({mins:02d}:{secs:02d}){self.RESET}"
        out.append(title)
        out.append(self.ERASE_LINE)
        # 总进度
        overall = (self.cur_step - 1) / self.total_steps + self.cur_pct / 100 / self.total_steps
        bar = self._bar(overall, width=40)
        out.append(f"  总进度 {bar} {overall*100:5.1f}%")
        out.append(self.ERASE_LINE)
        out.append("")
        # 当前步骤
        out.append(f"  {self.BOLD}▶ {self.cur_step}/{self.total_steps}  {self.cur_label}{self.RESET}")
        # 当前步骤内进度
        sub_bar = self._bar(self.cur_pct / 100, width=30)
        out.append(f"    {sub_bar} {self.cur_pct:3d}%")
        out.append(self.ERASE_LINE)
        out.append("")
        # 日志(只显示最近 12 行)
        visible = self.lines_log[-12:]
        for line in visible:
            out.append(f"  {self.ERASE_LINE}{self.GRAY}│{self.RESET} {line}")
        # 填满剩余行(避免上一帧残留)
        for _ in range(12 - len(visible)):
            out.append(f"  {self.ERASE_LINE}")
        self._out("".join(out))

    def _bar(self, ratio: float, width: int) -> str:
        ratio = max(0.0, min(1.0, ratio))
        filled = int(ratio * width)
        return f"{self.GREEN}{'█' * filled}{self.GRAY}{'░' * (width - filled)}{self.RESET}"

    def step(self, n: int, label: str):
        """进入第 n 步(n 从 1 开始)"""
        self.cur_step = n
        self.cur_label = label
        self.cur_pct = 0
        self._redraw()

    def set_pct(self, pct: int):
        """设置当前步骤内的进度(0-100)"""
        self.cur_pct = max(0, min(100, pct))
        self._redraw()

    def log(self, msg: str, kind: str = "info"):
        """追加一行子日志"""
        prefix = {
            "info": f"{self.GRAY}·{self.RESET}",
            "ok":   f"{self.GREEN}✓{self.RESET}",
            "warn": f"{self.YELLOW}!{self.RESET}",
            "err":  f"{self.RED}✗{self.RESET}",
        }.get(kind, "·")
        # 简单去掉 msg 里的 ANSI(子进程输出可能带,我们渲染时不再加工)
        self.lines_log.append(f"{prefix} {msg}")
        self._redraw()

    def finish(self, ok: bool, msg: str = ""):
        """结束 TUI:打印结果摘要 + 切回主屏幕"""
        if not self.enabled:
            return
        self.cur_pct = 100
        self.cur_step = self.total_steps
        self.cur_label = msg or ("完成" if ok else "失败")
        self._redraw()
        # 暂停一下让用户看到结果
        time.sleep(0.5)
        self._out(self.SHOW_CURSOR)
        self._out("\033[?1049l")  # 退出备用屏幕,回到主屏幕
        # 主屏幕打印最终结果(用户能复制)
        if ok:
            print(f"{self.BOLD}{self.GREEN}✅ {msg or '汉化完成'}{self.RESET}")
            print(f"{self.GRAY}→ Ctrl+Shift+P → Developer: Reload Window 生效{self.RESET}")
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
            return dirs[0]  # 最新版
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
    """跑子命令,日志走 TUI。返回 stdout(供 run_soft 检测 ZERO-MATCH)"""
    tui_log(desc + " …", "info")
    if _TUI and _TUI.enabled and pct >= 0:
        _TUI.set_pct(pct)
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
    """温顺跑:0 命中只警告不退出"""
    out = run(cmd, desc, pct)
    if "ZERO-MATCH" in out:
        tui_log("部分串 0 命中(若刚升级应为 0,请检查 index.js.orig 是否真·原版)", "warn")
    return out

def main():
    global _TUI
    ap = argparse.ArgumentParser(description="Claude Code 插件一键汉化")
    ap.add_argument("--audit", action="store_true", help="汉化后跑覆盖审计")
    ap.add_argument("--ext", default=None, help="手动指定扩展目录(默认自动定位最新版)")
    ap.add_argument("--tui", action="store_true", help="强制启用终端进度条(交互式终端默认自动启用)")
    ap.add_argument("--no-tui", action="store_true", help="强制禁用 TUI,用普通 print")
    args = ap.parse_args()

    # TUI 启用判断: --tui 显式开 / --no-tui 显式关 / 默认 isatty 自动判断
    if args.no_tui:
        tui_enabled = False
    elif args.tui:
        tui_enabled = True
    else:
        tui_enabled = sys.stdout.isatty()

    _TUI = TUI(tui_enabled)

    try:
        if not tui_enabled:
            # 普通模式:打标题
            print(f"扩展汉化开始 ...")

        ext_dir = args.ext or find_ext()
        if not ext_dir or not os.path.isdir(ext_dir):
            tui_log(f"找不到 claude-code 扩展目录,请用 --ext 指定", "err")
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

        # 1) 备份/还原基线
        _TUI.step(1, "备份/还原基线")
        orig = target.replace("index.js", "index.js.orig")
        if os.path.isfile(orig):
            shutil.copy2(orig, target)
            tui_log(f"已从基线还原: {os.path.basename(orig)}", "ok")
        else:
            shutil.copy2(target, orig)
            tui_log(f"已备份原版: {os.path.basename(orig)}", "ok")
        _TUI.set_pct(100)

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

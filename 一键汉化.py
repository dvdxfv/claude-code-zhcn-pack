#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code 插件一键汉化
=======================
用法: python 一键汉化.py [--audit] [--ext <扩展目录>]

升级扩展后跑一条命令即可: python 一键汉化.py --audit

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
import os, sys, glob, subprocess, shutil, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "资源脚本")
INDEX = "webview/index.js"

def find_ext():
    for base in [os.path.expanduser(p) for p in [
        "~/.cursor/extensions", "~/.vscode/extensions", "~/.vscode-insiders/extensions"]]:
        dirs = sorted(glob.glob(os.path.join(base, "anthropic.claude-code-*")),
                      reverse=True)
        if dirs:
            return dirs[0]  # 最新版
    return None

def find_node():
    # 优先 PATH 中的 node(装了 claude CLI 一般就自带);再兜底常见安装位置
    p = shutil.which("node")
    if p:
        return p
    for cand in ["/usr/local/bin/node", "/usr/bin/node",
                 os.path.expanduser("~/.nvm/current/bin/node")]:
        if os.path.isfile(cand):
            return cand
    return "node"  # 交给 shell 解析;若未装 node 会有清晰报错

def run(cmd, desc):
    print(f"  [{desc}]")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=RES)
    if r.stdout.strip():
        for l in r.stdout.strip().splitlines():
            print(f"    {l}")
    if r.returncode != 0:
        print(f"  ❌ {desc} 失败 (exit {r.returncode})")
        if r.stderr.strip():
            print(f"    stderr: {r.stderr.strip()[:500]}")
        sys.exit(1)
    return r.stdout

def run_soft(cmd, desc):
    """温顺跑:0 命中只警告不退出(升级后新版纯英文必命中;重复跑则 0 命中无害)"""
    out = run(cmd, desc)
    if "ZERO-MATCH" in out:
        print(f"    ⚠ 部分串 0 命中(若刚升级应为 0,请检查 index.js.orig 是否真·原版)")
    return out

def main():
    ap = argparse.ArgumentParser(description="Claude Code 插件一键汉化")
    ap.add_argument("--audit", action="store_true", help="汉化后跑覆盖审计")
    ap.add_argument("--ext", default=None, help="手动指定扩展目录(默认自动定位最新版)")
    args = ap.parse_args()

    ext_dir = args.ext or find_ext()
    if not ext_dir or not os.path.isdir(ext_dir):
        print("❌ 找不到 claude-code 扩展目录，请用 --ext 指定")
        sys.exit(1)

    target = os.path.join(ext_dir, INDEX)
    if not os.path.isfile(target):
        print(f"❌ 目标文件不存在: {target}")
        sys.exit(1)

    node = find_node()
    # 清理 node 路径中的 .exe 后缀(传给脚本)
    node_cmd = node if node != "node" else "node"

    print(f"扩展: {ext_dir}")
    print(f"目标: {target}")
    print(f"node:  {node_cmd}")
    print()

    # 1) 备份原版(幂等:已存在则不覆盖,保护原始基线)
    orig = target.replace("index.js", "index.js.orig")
    if os.path.isfile(orig):
        # 已有基线,从它还原再重打(确保可重复,不叠层)
        shutil.copy2(orig, target)
        print(f"已从基线还原: {os.path.basename(orig)}")
    else:
        shutil.copy2(target, orig)
        print(f"✅ 已备份原版: {os.path.basename(orig)}")

    # 2) UI 字符串(144条) - 升级后新版是纯英文,全部能命中;重复跑则 0 命中(无害)
    run_soft(f'{node_cmd} apply-精确.cjs map1-主批次.json "{target}"', "精确替换(主批次)")
    run_soft(f'{node_cmd} apply-锚定.cjs map2-补充批次.json "{target}"', "锚定替换(补充批次)")

    # 3) UI 补漏(设置/对话框)
    run(f'python apply-ui补漏.py "{target}" "{target}.post-gap"', "UI 补漏(设置/对话框)")
    # 3a) 用补漏后的文件作为注入基线
    precmd = target + ".post-gap"
    if not os.path.isfile(precmd):
        print("❌ 补漏后基线未生成")
        sys.exit(1)

    # 4) 注入斜杠命令(195条)
    run(f'{node_cmd} inject-斜杠命令说明.cjs "{precmd}" 斜杠命令-中文说明.json "{target}"',
        "注入斜杠命令中文描述")
    os.remove(precmd)  # 清理临时基线

    # 5) 注入 CLI spinner 汉化(写 ~/.claude/settings.json,只增不覆盖)
    run(f'{node_cmd} apply-spinner.cjs --merge', "注入 CLI spinner(187 动词 + 41 提示)")

    # 6) 语法校验
    run(f'{node_cmd} --check "{target}"', "语法校验")

    print("\n✅ 汉化完成！Ctrl+Shift+P → Developer: Reload Window 生效")

    # 7) 可选审计
    if args.audit:
        print()
        run("python audit-命令汉化覆盖.py", "覆盖审计")
        ui_gap = os.path.join(RES, "audit-ui串缺口.py")
        if os.path.isfile(ui_gap):
            run(f"python {ui_gap} \"{target}\"", "UI 串缺口审计")
        print("\n检查上面审计输出——命令覆盖率应 ~99%，UI 缺口应仅剩 Monaco 内部串。")

if __name__ == "__main__":
    main()

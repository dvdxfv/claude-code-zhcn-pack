# -*- coding: utf-8 -*-
# UI 补漏：把设置/对话框/引导语等"非斜杠命令"的英文展示串补成中文。
# 标题/描述用唯一子串定位完整字面量；按钮用全字面量等值替换，避免子串误伤。
import re, sys, json
base_in, base_out = sys.argv[1], sys.argv[2]
src = open(base_in, encoding="utf-8").read()

# (唯一子串, 中文)：每条只会命中"包含该子串的那个完整双引号字面量"
targets = [
    # 6 个 "Continue in Terminal to …?" 对话框标题
    ("to change output style",  "在终端中继续以更改输出风格？"),
    ("to configure agents",     "在终端中继续以配置智能体？"),
    ("to configure hooks",      "在终端中继续以配置钩子？"),
    ("to edit memory",          "在终端中继续以编辑记忆？"),
    ("to manage permissions",   "在终端中继续以管理权限？"),
    ("to manage plugins",       "在终端中继续以管理插件？"),
    # 对应对话框描述
    ("After installing plugins",        "安装插件后，重新加载本扩展即可在这里使用。"),
    ("After making changes, exit Claude","改完后，退出终端里的 Claude，并重新加载 IDE 扩展即可在这里使用。"),
    ("Once agents are configured",      "在终端中配置好智能体后，重新加载本扩展，就能在这里让 Claude 使用它们。"),
    ("Once configured, memories",       "配置好后，Claude Code 会在你 IDE 里读取这些记忆。"),
    ("Once hooks are configured",       "在本仓库配置好钩子后，它们在你 IDE 里也会生效。"),
    ("Output style is set via",         "输出风格通过 /config 设置；在终端中改好并重新加载本扩展后，就能在这里使用。"),
    ("Permission settings are shared",  "权限设置在终端和本 IDE 之间共享。"),
    # 模型自动切换开关
    ("Switch models when a message is flagged", "消息被标记时切换模型"),
    ("When safety measures flag a message",     "当安全机制标记某条消息时，自动切换到另一个模型以继续对话；关闭时，会话会改为暂停。"),
    # 记忆 / 引导语 / 占位符
    ("Manage Claude",                   "管理 Claude 的记忆"),
    ("Tired of repeating yourself",     "懒得重复交代？用 CLAUDE.md 让 Claude 记住你说过的内容。"),
    ("Use Claude Code in the terminal to configure MCP", "在终端里用 Claude Code 配置 MCP 服务器，配好后这里也能用！"),
    ("come to the absolutely right place", "你来对地方了！"),
    ("GitHub repo, URL, or path",       "GitHub 仓库、URL 或路径…"),
    ("Refresh and continue",            "刷新并继续"),
    ("Terminal opened",                 "终端已打开"),
]

# 模板字符串/非引号片段：直接全等替换（含 ${...} 插值的兜底标题）
raw_replacements = [
    ("`Continue in Terminal to configure ${e}?`", "`在终端中继续以配置 ${e}？`"),
]

en2zh = {}
for sub, zh in targets:
    m = re.search(r'"([^"]*' + re.escape(sub) + r'[^"]*)"', src)
    if not m:
        print(f"⚠ 未找到: {sub}"); continue
    full = m.group(1)
    if src.count('"' + full + '"') != 1:
        print(f"⚠ '{sub}' 命中非唯一，跳过"); continue
    src = src.replace('"' + full + '"', '"' + zh + '"')
    en2zh[full] = zh

# 按钮：全字面量等值（不会误伤更长的标题，因为标题是不同的完整字面量）
btn = '"Continue in Terminal"'
if src.count(btn) == 1:
    src = src.replace(btn, '"在终端中继续"'); en2zh["Continue in Terminal"] = "在终端中继续"
else:
    print(f"⚠ 按钮 Continue in Terminal 命中 {src.count(btn)} 次")

for old, new in raw_replacements:
    c = src.count(old)
    if c == 1:
        src = src.replace(old, new); en2zh[old] = new
    else:
        print(f"⚠ 模板 '{old[:30]}...' 命中 {c} 次，跳过")

open(base_out, "w", encoding="utf-8").write(src)
json.dump(en2zh, open("map4-补漏.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"补漏 {len(en2zh)} 条 -> {base_out}")

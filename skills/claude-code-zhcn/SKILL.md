---
name: claude-code-zhcn
description: "把 Cursor / VS Code 里的 Claude Code 扩展界面中文化。一键脚本 + 完整 SOP。Use when user mentions 汉化/中文化 Claude Code 扩展、把 Claude Code 改回中文、扩展升级后汉化失效、重跑一键汉化、汉化覆盖率审计、还有哪些英文、命令没汉化、new-conversation 还是英文、Press Shift Tab 还是英文、Claude Code 中文界面。"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
metadata:
  author: claude-code-zhcn contributors
  version: "0.1.0"
  plugin: claude-code-zhcn
---

# Claude Code 扩展中文化

把 Cursor / VS Code 里的 Claude Code 扩展界面从英文改成中文的可复用工具包。

> ⚠️ **前提**：Claude Code 官方扩展**没有 i18n 开关**——所有 UI 文字是英文硬编码。要中文只能"魔改"扩展的 `webview/index.js`。本插件把魔改做得**安全、可重复、可还原、可自查**。升级后再跑一条命令即可恢复汉化。

---

## 何时触发

用户在以下任一情况下都应该自动加载本技能：

- 提到"汉化/中文化 Claude Code 扩展"、"把 Claude Code 改成中文"、"界面还是英文"
- 提到"扩展升级后汉化失效"、"升级后变英文了"
- 提到"重跑一键汉化"、"再跑一次汉化"
- 提到"汉化覆盖率"、"还有哪些英文"、"命令没汉化"、"new-conversation / Press Shift Tab 还是英文"
- 看到截图里 Claude Code 面板有英文（如 `Press Shift Tab to automatically approve code edits`），用户反馈"这块没汉化"

---

## 完整 SOP 在根目录文档

**本 SKILL.md 只做"入口 + 指针"**。完整流程、原理、故障排查在仓库根的：

- [README.md](../../README.md) — 总览 + 最快上手 + 文件夹导览
- [操作指南.md](../../操作指南.md) — 完整 SOP：三类活、智能 ID 匹配、插件目录审计、两大盲区、故障排查
- [翻译清单.md](../../翻译清单.md) — 术语表、译文约定、保留英文清单

**做汉化前先读 `操作指南.md` 第二~六节**，理解"三类活（结构化字面量 / JSX 文本节点 / 改渲染）"的区分。

---

## 最快上手（用户视角）

```bash
# 在本仓库根目录：
python 一键汉化.py --audit

# 然后 Cursor/VS Code：Ctrl+Shift+P → Developer: Reload Window
```

回退：`cp <扩展>/webview/index.js.orig <扩展>/webview/index.js`

---

## 5 阶段工作流（Agent 跑汉化任务时按此顺序）

每阶段都先**告诉用户你打算做什么**再动手；每阶段完成后**向用户汇报**结果。

### 阶段 1 · 扫描（认识战场）

**目标**：知道当前扩展里有哪些英文 UI 串、命令清单、第三方技能；建出基线。

**做什么**：

```bash
# 定位扩展
ls -d ~/.cursor/extensions/anthropic.claude-code-* 2>/dev/null

# 跑两个审计
python 资源脚本/audit-命令汉化覆盖.py
python 资源脚本/audit-ui串缺口.py <扩展>/webview/index.js
```

**汇报**给用户：可见命令数（内置 / 技能 / 插件）、UI 串缺口数。**这就是"汉化目标清单"**，不需要再做翻译计划。

### 阶段 2 · 翻译（建清单）

**目标**：把英文 → 中文，进译表文件。

**做什么**：在 `资源脚本/斜杠命令-中文说明.json` 加键值；UI 串则加进 `map1-主批次.json` / `map2-补充批次.json`。

**约束**：
- **术语统一**：`response→回复`、`effort→思考力度`、`agent→智能体`、`session→会话`、`land/landing→代码合入`（不是"上线"）。详见 `翻译清单.md`。
- **保留英文**：`Hooks`、`MCP`、`CLAUDE.md`、Monaco 内部命令、JSON Schema、斜杠命令名本身、代码标识符。
- **第三方技能**（superpowers、frontend-design 等）按需补译，可参照 `斜杠命令-第三方技能示例.json`。

### 阶段 3 · 交叉审（必须不同模型）

> ⚠️ **这一阶段必须用与当前 Agent 不同的另一个 AI/模型**。这是质量关，不是可选项。

**做什么**：

1. **询问用户**用哪个交叉审工具。可选项示例：
   - **Codex CLI**（`codex exec -s read-only ...`）
   - **DeepSeek / 豆包 / Kimi / 通义千问** 网页版对话
   - **Gemini CLI**（如果装了）
   - 任意你能调起来的不同模型
2. 把 `斜杠命令-中文说明.json` + `map1/2/3.json` + `翻译清单.md` 的内容**内嵌进提示词**（不要让对方读文件——沙箱可能拦）。
3. 让对方挑：错译、术语不统一、中英标点混用、`instead`/`without stopping` 这类易漏语义。
4. **采纳的修订改回对应 JSON / 文档**。

### 阶段 4 · 执行（重打汉化）

**目标**：在干净基线上应用全部汉化。

**做什么**：

```bash
python 一键汉化.py --audit
```

脚本会：备份原版 → 精确替换 → 锚定替换 → UI 补漏 → 注入命令描述 → node 语法校验 → 审计。

**完成后**：

- 检查 `SYNTAX_OK` 通过（防白屏）
- 提示用户 `Ctrl+Shift+P → Developer: Reload Window` 验收
- **绝对不要**让用户在没 Reload 的情况下"先看看效果"——会看不到任何变化

### 阶段 5 · 复审计（查缺补漏）

**目标**：客观验收，不靠肉眼截图。

**做什么**：

```bash
python 资源脚本/audit-命令汉化覆盖.py    # 复跑命令覆盖
python 资源脚本/audit-ui串缺口.py <扩展>/webview/index.js  # 复跑 UI 缺口
```

**通过标准**：
- 命令覆盖率 ≥ 99%（唯一未译通常为 `/stub` 内部假命令）
- UI 缺口审计剩余项**全部是 Monaco 编辑器内部命令 / JSON Schema 描述**（约定保留英文）

若未达标：回到阶段 2 翻译缺口 → 阶段 3 审 → 阶段 4 重打 → 阶段 5 复审。

---

## 常见坑（Agent 必看，避免重复踩）

1. **白屏**：替换改坏 JS 语法。立刻 `cp <扩展>/webview/index.js.orig <扩展>/webview/index.js` 还原 + Reload。
2. **覆盖率假 99%**：审计脚本默认只扫 `~/.claude/skills/`，**漏掉 `~/.claude/plugins/cache/`**——务必用更新版（默认会扫两个目录）。
3. **某命令注入后仍英文**：webview 命令 ID ≠ 译表 key（如 `clear-conversation` vs `clear`）。注入器已内置**后缀剥离 + 前缀剥离**自动匹配，不用手动加映射。
4. **JSX 文本节点漏译**：欢迎页 `What to do first? ...` 这类提示是 `{text:"..."}` 字面量，**没有 key**，结构化审计扫不到。手动 `grep -oP '\{text:"[A-Z][^"]{3,200}"\}'` 找。
5. **动态键提示误解**：`Press [Shift] [Tab] to ...` 的键名是 React 子元素（动态的），但提示文本（`to automatically approve code edits`）是死字符串字面量，**只替换文本部分即可**，键名照旧动态。

详细原理见 `操作指南.md` 第四~六节。

---

## Agent 的边界

- **本技能不负责**：Cursor Marketplace 上架流程、用户账号注册、跨平台 GUI 工具。
- **本技能负责**：按 SOP 跑汉化、解释原理、翻译校对协调、出错排查。
- **本技能的"权威文档"**：根目录 `操作指南.md`。如果本文件与它冲突，**以根文档为准**。
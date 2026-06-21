# Claude Code 扩展中文化（Cursor 插件）

把 Cursor / VS Code 里的 **Claude Code 扩展**界面从英文改成中文的一整套**可复用工具 + 完整 SOP**。
不是"翻译几个词"，而是按"扫描 → 翻译 → 交叉审 → 执行 → 复审"五阶段流水线，跑一条命令搞定。

> ⚠️ **先认清前提**：Claude Code 官方扩展**没有任何多语言（i18n）开关**，界面全英文。想看中文只能"魔改"扩展的打包文件 `webview/index.js`。魔改有两大坑：**①改错语法 → 面板白屏；②扩展一升级 → 汉化全丢**。本工具的全部价值，就是把魔改做得**安全、可重复、可还原、可自查**——升级后再跑一条命令即可。

---

## 安装（3 选 1）

### A. Cursor Marketplace（最简单）

在 Cursor 里 `Ctrl+Shift+P` → 搜 "Extensions: Install Extensions" → 搜 `claude-code-zhcn` → 一键安装。
安装后**任何项目、任何对话里**，Agent 都自动知道有这套汉化 SOP。

### B. 本地开发模式（推荐用于二次开发）

```bash
git clone https://github.com/your-org/claude-code-zhcn-pack
cd claude-code-zhcn-pack
# 在 Cursor 里打开本文件夹（File → Open Folder）
# Agent 会自动加载 skills/claude-code-zhcn/SKILL.md
```

### C. 一键汉化脚本单独跑（不需要 Cursor 加载技能）

```bash
git clone https://github.com/your-org/claude-code-zhcn-pack
cd claude-code-zhcn-pack
python 一键汉化.py --audit
# 然后 Cursor/VS Code：Ctrl+Shift+P → Developer: Reload Window
```

---

## 卸载 / 还原

任何时候想回到英文原版：

```bash
cp <扩展>/webview/index.js.orig <扩展>/webview/index.js
# 然后 Reload Window
```

`<扩展>` 路径通常是 `~/.cursor/extensions/anthropic.claude-code-<版本>-<平台>/`。

扩展升级时本工具会被覆盖（汉化失效），重跑 `一键汉化.py` 即可恢复。

---

## 快速上手

装好之后，在 Cursor 里：

1. 打开 Claude Code 面板（左侧 Claude Code 图标）
2. 在 Agent 对话框里说："**把 Claude Code 扩展汉化**" 或 "**界面还有英文怎么办**"
3. Agent 加载本插件的 `SKILL.md` → 跑 5 阶段 SOP → 全部完成
4. 你执行 `Ctrl+Shift+P → Developer: Reload Window` 验收

或者不用 Agent，直接命令行跑：

```bash
python 一键汉化.py --audit
```

---

## 5 阶段工作流

按"扫描 → 翻译 → 交叉审 → 执行 → 复审"五阶段流水线跑。Agent 跑时按顺序，每阶段先告诉用户打算做什么、每阶段后汇报结果。

| 阶段 | 目的 | 主要动作 |
|---|---|---|
| **1. 扫描** | 认识战场 | 跑 `audit-命令汉化覆盖.py` + `audit-ui串缺口.py` |
| **2. 翻译** | 建清单 | 英文 → 中文，进 `*.json` 译表 |
| **3. 交叉审** | 质量关（必须不同模型） | 用 Codex / DeepSeek / 豆包 / Gemini 等做独立第二意见 |
| **4. 执行** | 重打汉化 | `python 一键汉化.py --audit` |
| **5. 复审** | 客观验收 | 复跑审计，命令覆盖率 ≥ 99% |

详细流程、原理、坑见 [操作指南.md](操作指南.md)。

---

## 核心方法论（6 条，先看这个再看脚本）

1. **带前缀锚定替换，不裸替换。** 替换 `label:"Auto mode"` 而不是裸串 `Auto mode`——后者会误伤同名代码标识符。
2. **改前必备份，改后必语法自检。** `node --check` 必须 `SYNTAX_OK`。
3. **分清三种"活"**：结构化字面量 / JSX 文本节点 / 改渲染（斜杠命令描述）。先确认 UI 渲不渲染，再决定改数据还是改渲染。
4. **ID 对不上时靠智能匹配兜底**。webview ID `clear-conversation` ≠ 译表 key `clear`——注入器内置后缀剥离 + 前缀剥离自动处理。
5. **覆盖率靠脚本审计，不靠肉眼截图**。命令近 200 个，肉眼必漏。
6. **可重复应用 > 一次性改对**。所有脚本都"从干净基线重新生成"，改译文重跑即可。

---

## 文件夹导览

| 文件 | 作用 |
|---|---|
| `README.md`（本文件） | 总览 + 安装 + 快速上手 |
| `操作指南.md` | 完整 SOP：原理、每一步、坑、故障排查 |
| `翻译清单.md` | 术语表 + 译文约定 + 保留英文清单 |
| `一键汉化.py` | 入口脚本：自动定位扩展 → 备份 → 全部汉化 → 校验 → 审计 |
| `.cursor-plugin/plugin.json` | Cursor Marketplace 插件元数据 |
| `skills/claude-code-zhcn/SKILL.md` | Agent 加载入口（指向根 SOP 文档） |
| `资源脚本/` | 6 个 apply/inject/audit 脚本 + 6 个译表 |

### 资源脚本

| 文件 | 说明 |
|---|---|
| `apply-精确.cjs` | 精确字面量替换（`"EN"→"ZH"`，全量替换） |
| `apply-锚定.cjs` | 锚定替换（只改 `label:`/`title:` 等显示位前缀，更安全） |
| `apply-ui补漏.py` | UI 补漏（设置/对话框/模板字符串等边角） |
| `inject-斜杠命令说明.cjs` | **改渲染**注入器 + 中文命令表（含智能 ID 匹配） |
| `audit-命令汉化覆盖.py` | 命令覆盖审计（CLI + 技能 + 插件目录全量比对） |
| `audit-ui串缺口.py` | UI 串缺口审计（结构化字面量） |
| `map1/2/3/4-*.json` | UI 中英映射（精确/锚定/导航/补漏） |
| `斜杠命令-中文说明.json` | 官方内置命令中文描述表（注入器数据源） |
| `斜杠命令-第三方技能示例.json` | 第三方技能译文示例（参考） |

---

## 已知边界

- **官方命令译表覆盖官方内置命令**；你自己装的第三方技能按需补译。
- **Monaco 编辑器内部命令 / JSON Schema 描述**按约定保留英文（用户看不到）。
- **扩展升级会覆盖汉化**——正常设计，升级后重跑 `一键汉化.py`。
- 官方若日后出 i18n 开关，本套魔改即可退役。

---

## 上架到 Cursor Marketplace

把本仓库打包成 Cursor 官方插件上架，需：

1. 注册 Cursor 开发者账号（[Cursor 官方文档](https://docs.cursor.com)）
2. 准备图标、截图、README
3. 用 `cursor-plugin` CLI 打包并提交审核
4. 审核通过后，用户可在 Marketplace 搜到一键安装

具体流程参考 Cursor 官方插件开发文档。

---

## 复用说明

- 本仓库**自包含**：脚本、译表、SOP、Cursor 插件配置齐全，clone 后即可用。
- 别人机器上**唯一可能要调的**是扩展目录（升级后版本号变）——但 `一键汉化.py` 会自动定位最新版，通常无需手动指定。
- 译表是**可二次编辑的资产**，欢迎按自己口味改译文后重跑脚本。
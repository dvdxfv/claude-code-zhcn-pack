# Claude Code 扩展中文化

把 Cursor / VS Code 里的 **Claude Code 扩展**界面 + **CLI 终端**从英文改成中文。
**使用者只需 3 步**;译者/贡献者另有完整 SOP 在 [操作指南.md](操作指南.md)。

> ⚠️ **先认清前提**：Claude Code 官方扩展**没有任何多语言（i18n）开关**，界面全英文。想看中文只能"魔改"扩展的打包文件 `webview/index.js`。魔改有两大坑：**①改错语法 → 面板白屏；②扩展一升级 → 汉化全丢**。本工具的全部价值，就是把魔改做得**安全、可重复、可还原、可自查**——升级后再跑一条命令即可。
>
> **覆盖两处界面**：
> - **扩展界面**（Cursor/VS Code 面板）—— 改 `webview/index.js`
> - **CLI 终端**（终端里的 spinner 词、提示语、AI 回复语言）—— 写 `~/.claude/settings.json`（官方配置 key）

---

## 安装（使用者 3 步上手）

**前置**：装了 Claude Code 扩展、装了 `node`（装了 claude CLI 一般就有）、Python 3。

```bash
# 第 1 步：克隆/fork 仓库
git clone https://github.com/dvdxfv/claude-code-zhcn-pack
cd claude-code-zhcn-pack

# 第 2 步：跑汉化（包含覆盖审计）
python 一键汉化.py --audit

# 第 3 步：到 Cursor/VS Code 里按 Ctrl+Shift+P → Developer: Reload Window
```

**是的，fork 了之后双击启动器就是一键汉化**——`汉化启动器.bat`（Windows）只是 `一键汉化.py --tui --audit` 的窗口壳，没有"安装"这一步，clone/fork 下来的东西就是全部。

但它**不会一上来就直接改文件**——跑起来分两阶段：

1. **扫描 + 生成清单**：自动读取全部译表，生成 `汉化预览.md`（Markdown，跑完才会出现在仓库根目录，不纳入版本控制），列出本次会应用的全部翻译（界面文字、命令描述、CLI spinner 词/提示），按类别分好表格。
2. **终端确认**：打印 `是否现在应用以上改动？[y/N]:`，等你输入。**输入 `y` 才会真正改文件，任何其它输入（包括直接 Enter）都视为取消，不会动任何真实文件。**

确认前你可以做的事：
- 自己打开 `汉化预览.md` 扫一眼
- 把这份 Markdown **甩给另一个 Agent**（Codex / DeepSeek / 豆包 / Gemini 等）做独立交叉审，对方看完反馈，你再回终端按 `y`
- 直接信任译表、不想验证：按 `y` 就行

常用参数：
- `--preview`：只生成清单，不问、不应用（适合脚本化场景或纯粹想看一眼）
- `--yes` / `-y`：跳过确认提示，直接应用（适合已经审过、想省事重跑的场景）
- 非交互环境（没有终端可输入）且没给 `--yes`：为安全起见**默认不应用**，会提示你加 `--yes`

---

## 汉化完了，如果觉得某条翻译不对怎么办？

1. **找到错译的位置**：先翻 `汉化预览.md`（运行时生成，按类别列了全部译文，最容易定位）；译表本身也是明文 JSON，可以直接 `grep -r "你觉得不对的英文" 资源脚本/`。
2. **改译文**：编辑对应的 `map*.json` / `斜杠命令-中文说明.json` / `spinner-*.json`。
3. **重跑**：`python 一键汉化.py --audit`。

   脚本是**幂等**的——每次都从 `index.js.orig`（真·英文原版）重新生成，不会在旧的错误翻译上"叠加"修改，改完译表直接重跑就是干净结果，不需要先手动还原。重跑时会重新生成 `汉化预览.md`、重新问一次 `y/N`，方便你确认改对了。

---

## 卸载 / 还原

任何时候想完全回到英文原版：

```bash
# 1) 还原扩展界面
cp <扩展>/webview/index.js.orig <扩展>/webview/index.js

# 2) 还原 CLI 终端（移除 spinner 注入）
node 资源脚本/apply-spinner.cjs --remove

# 然后到 Cursor/VS Code 里 Reload Window
```

`<扩展>` 路径通常是 `~/.cursor/extensions/anthropic.claude-code-<版本>-<平台>/` 或 `~/.vscode/extensions/anthropic.claude-code-<版本>-<平台>/`。

> 升级扩展时本工具会被覆盖（汉化失效），重跑 `一键汉化.py` 即可恢复——`index.js.orig` 备份**针对的是你升级前的版本**，升级后会被脚本自动重新备份为新版本的 .orig。

---

## 文件夹导览

| 文件 | 作用 |
|---|---|
| `一键汉化.py` | **入口脚本**：扫描译表 → 生成 `汉化预览.md` → 终端确认（`y` 才继续）→ 备份 → 应用译表 → 校验 → 注入 CLI → 审计。`--preview`/`--yes` 见上文 |
| `汉化预览.md` | **运行时生成**（不在仓库里，跑完才出现），人类可读的译文清单，可交给其他 Agent 交叉审 |
| `汉化启动器.bat` | Windows TUI 启动器（双击弹窗），**只是 `一键汉化.py --tui` 的窗口壳** |
| `资源脚本/` | 7 个 apply/inject/audit 脚本 + 8 个译表(展开见下) |
| [操作指南.md](操作指南.md) | 完整 SOP：原理、每一步、坑、故障排查、译表维护工作流（**面向译表贡献者**） |
| [翻译清单.md](翻译清单.md) | 术语表 + 译文约定 + 保留英文清单 |
| `README.md`（本文件） | 使用者视角的 3 步上手 |

### `资源脚本/`

| 文件 | 说明 |
|---|---|
| `apply-精确.cjs` | 精确字面量替换（`"EN"→"ZH"`） |
| `apply-锚定.cjs` | 锚定替换（只动 `label:`/`title:` 等显示位前缀，更安全） |
| `apply-ui补漏.py` | UI 补漏（设置/对话框/模板字符串等边角） |
| `apply-spinner.cjs` | **CLI 终端汉化**（写 `~/.claude/settings.json`，187 动词 + 41 提示） |
| `inject-斜杠命令说明.cjs` | 扩展内"斜杠命令描述"的渲染钩子注入器，会合并官方表 + 本机表 |
| `auto-translate-gaps.py` | **本机自动翻译**：调本机 `claude` CLI 翻译私人技能命令缺口，写到本机表 |
| `audit-命令汉化覆盖.py` | 命令覆盖率审计（CLI + 技能 + 插件目录全量比对，会合并官方表 + 本机表） |
| `audit-ui串缺口.py` | 扩展 UI 串缺口审计 |
| `map1/2/3/4-*.json` | 扩展 UI 中英映射（精确/锚定/导航/补漏） |
| `spinner-verbs-zh.json` | CLI spinner 动词 187 条（参考 KongBai1145/claude-code-zh-cn） |
| `spinner-tips-zh.json` | CLI spinner 提示 41 条（重译版） |
| `斜杠命令-中文说明.json` | 斜杠命令中文描述表（注入器数据源） |
| `斜杠命令-第三方技能示例.json` | 第三方技能译文示例（参考） |

---

## 你机器上的私人技能命令也能自动翻译

官方译表 `斜杠命令-中文说明.json` 只覆盖内置命令 + 常见公共插件（gstack/superpowers 等）。但每台机器装的第三方技能不一样，不可能靠一份写死的表覆盖所有人——所以工具会在**这台机器上**调用**本机已安装的 `claude` CLI**，自己把扫到的缺口翻译掉：

```bash
python 资源脚本/auto-translate-gaps.py
```

跑起来会：扫描缺口 → 列出来给你看 → 提示会产生真实 API 费用（实测批量翻译几十条约 $0.1~0.3，按一次调用算，不是按条数线性计费）→ 终端确认 `y` 才真正调用。翻译结果写到 `资源脚本/斜杠命令-中文说明.本机.json`——**这份表不进 git，每台机器各管各的**，下次跑 `一键汉化.py` 时会自动合并进去。

- 已经翻过的条目不会重复花钱翻译（幂等，只翻新缺口）
- 想先看缺口不花钱：加 `--preview`
- 想跳过确认直接翻：加 `--yes` / `-y`

---

## 给译表贡献者

如果你想：
- **改现有译文** → 直接编辑 `资源脚本/map*.json` 或 `斜杠命令-中文说明.json`，然后重跑 `一键汉化.py`
- **补新译表**（比如发现新英文串）→ 跑 `资源脚本/audit-ui串缺口.py` 和 `audit-命令汉化覆盖.py` 看输出里的未汉化清单,翻译后并入对应 JSON(脚本会自动写出 `缺口-待译.json` 作占位)
- **批量补第三方技能命令** → 用上面的 `auto-translate-gaps.py`，不用自己手翻
- **更新 spinner 词** → 编辑 `spinner-verbs-zh.json` / `spinner-tips-zh.json`，重跑

完整的译表维护工作流（"扫描 → 翻译 → 交叉审 → 执行 → 复审"五阶段）、交叉审规范、故障排查见 [操作指南.md](操作指南.md)。

---

## 已知边界

- **官方命令译表覆盖官方内置命令 + 常见公共插件**；你自己装的私人技能由 `auto-translate-gaps.py` 在本机自动补译，不进公共仓库。
- **Monaco 编辑器内部命令 / JSON Schema 描述**按约定保留英文（用户看不到）。
- **扩展升级会覆盖汉化**——正常设计，升级后重跑 `一键汉化.py`。
- 官方若日后出 i18n 开关，本套魔改即可退役。

---

## 复用说明

- 本仓库**自包含**：脚本、译表、SOP 齐全，clone 后即可用。
- 别人机器上**唯一可能要调的**是扩展目录（升级后版本号变）——但 `一键汉化.py` 会自动定位最新版，通常无需手动指定。
- 译表是**可二次编辑的资产**，欢迎按自己口味改译文后重跑脚本。

---

## 致谢

- [KongBai1145/claude-code-zh-cn](https://github.com/KongBai1145/claude-code-zh-cn) @ MIT —— CLI spinner/tips 词表的灵感来源
- [TrainingSpring/claude-i18n-training](https://github.com/TrainingSpring/claude-i18n-training) —— 启发我们用官方 settings.json key 而非魔改二进制
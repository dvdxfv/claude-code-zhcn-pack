// Re-appliable injector: starts from a clean base, then injects the
// command-description render hook + Chinese map into webview/index.js.
// Usage: node inject-斜杠命令说明.cjs <baseBackup> <mapJson> <target>

const fs = require("fs");
const [, , basePath, mapPath, targetPath] = process.argv;

const map = JSON.parse(fs.readFileSync(mapPath, "utf8"));

// 补充 webview 专属命令 ID → 中文（无对应 CLI 命令的，手译）
const WEBVIEW_EXTRAS = {
  "new-conversation": "在新标签页开启新对话",
  "attach-file": "上传文件加入对话上下文",
  "mention-file": "用 @提及 引用项目内文件",
  "reset-onboarding": "重新走一遍新手引导 [内部]",
  "share": "与团队成员分享对话 [内部]",
  "issue": "向研发团队反馈模型行为问题",
  "toggle-thinking": "切换深度思考模式",
  "account-usage": "查看账户信息与用量上限",
  "plugins": "安装、启用或禁用插件",
  "slash-command-terminal": "在终端中打开新的 Claude 实例",
};
Object.assign(map, WEBVIEW_EXTRAS);

// 已知的 webview ID → CLI 名称别名（兜底匹配不到时用）
const ID_ALIASES = {
  "slash-command-terminal": "terminal-setup",
  "account-usage": "usage",
  "plugins": "plugin",
};
// 从译表拉对应的中文到 webview ID key
for (const [wid, cliName] of Object.entries(ID_ALIASES)) {
  if (!map[wid] && map[cliName]) {
    map[wid] = map[cliName];
  }
}

// Always start from the clean base so re-running updates the map cleanly.
fs.copyFileSync(basePath, targetPath);
let src = fs.readFileSync(targetPath, "utf8");

const anchor = 'className:Gp.commandLabel},ye.label,ye.labelSuffix),null),ye.trailingComponent';
const count = src.split(anchor).length - 1;
if (count !== 1) { console.log("ANCHOR_COUNT=" + count + " (expected 1) — aborting"); process.exit(1); }

const mapLiteral = JSON.stringify(map);

// 智能查找逻辑（按 webview 实际 ID 形态适配译表 key）：
// 1. ye.id 直接查（去 / 前缀）
// 2. 剥离连字符+后缀 (-conversation/-config/-command/-mode/-setup/-level/-help/-control)
// 3. 剥离前缀 slash-command-
// 4. ye.label 兜底（去 / 前缀）
// 5. ye.description 英文原文兜底（绝不让面板空白）
const desc =
  '(function(){try{' +
  'var __m=globalThis.__CCZH||(globalThis.__CCZH=' + mapLiteral + ');' +
  'var __id=(ye.id||"").toString().replace(/^\\//,"").toLowerCase();' +
  'var __d=__m[__id];' +
  // 后缀剥离: 把"ID 末尾的 -<suffix>"整段剥掉（包括连字符），如 clear-conversation → clear
  'if(!__d){' +
    'var __s=__id.replace(/[-_]?(conversation|config|command|mode|setup|level|help|control|alias)$/,"");' +
    'if(__s!==__id)__d=__m[__s];' +
  '}' +
  // 前缀剥离: slash-command-help → help
  'if(!__d&&__id.startsWith("slash-command-"))__d=__m[__id.slice(14)];' +
  // label 兜底
  'if(!__d)__d=__m[(ye.label||"").toString().replace(/^\\//,"").toLowerCase()];' +
  // 英文描述兜底
  'if(!__d)__d=(ye.description&&ye.description.value)?ye.description.value:(typeof ye.description==="string"?ye.description:"");' +
  'return __d?Zn.default.createElement("span",{className:Gp.commandDescription},__d):null' +
  '}catch(__e){return null}})()';

const replacement = 'className:Gp.commandLabel},ye.label,ye.labelSuffix),' + desc + '),ye.trailingComponent';
src = src.replace(anchor, replacement);
fs.writeFileSync(targetPath, src, "utf8");
console.log("INJECTED render hook (smart-match). map entries=" + Object.keys(map).length);

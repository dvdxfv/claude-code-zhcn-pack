// Re-appliable injector: starts from a clean base, then injects the
// command-description render hook + Chinese map into webview/index.js.
// Usage: node inject-斜杠命令说明.cjs <baseBackup> <mapJson> <target>

const fs = require("fs");
const path = require("path");
const [, , basePath, mapPath, targetPath] = process.argv;

const officialMap = JSON.parse(fs.readFileSync(mapPath, "utf8"));

// 本机专属译表(由 auto-translate-gaps.py 调 claude CLI 自动翻译产出,不进 git,
// 跟 mapPath 同目录)。每台机器装的第三方技能不同,这份表只覆盖"这台机器上
// 扫到、且本机翻译过"的命令,跟公共译表合并后参与注入。公共译表优先(若两边
// 都有同一个 key,以公共译表为准)。
const localMapPath = path.join(path.dirname(mapPath), "斜杠命令-中文说明.本机.json");
const localMap = fs.existsSync(localMapPath)
  ? JSON.parse(fs.readFileSync(localMapPath, "utf8"))
  : {};
const map = { ...localMap, ...officialMap };
if (Object.keys(localMap).length) {
  console.log(`本机译表: ${localMapPath}（${Object.keys(localMap).length} 条，已合并）`);
}

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

// 扩展每次升级都会重新打包/压缩，局部变量名（css-module 对象、循环变量、
// createElement/jsx 调用别名）几乎必然改变，甚至渲染代码本身会在
// React.createElement(classic) 和 react/jsx-runtime(automatic) 两种输出
// 形态之间切换（2.1.185→2.1.197 就是后者）。所以锚点不能再用一整条写死的
// 字面量字符串去 split/replace，改成两套按“语义结构”写的正则，用捕获组
// 现场取出当次构建实际用的变量名/调用名，缺哪种就报哪种，方便升级后排错。
//
// 结构语义（两种风格里都不变的部分）：
//   commandContent 容器 div 里放一个 commandLabel span（渲染 label+labelSuffix）
//   和一个原本为 null 的占位（我们要塞中文描述进去），紧跟着是 trailingComponent。
const ANCHOR_STYLES = [
  {
    name: "classic (React.createElement)",
    // 例: Zn.default.createElement("div",{className:Gp.commandContent},
    //      Zn.default.createElement("span",{className:Gp.commandLabel},ye.label,ye.labelSuffix),
    //      null),ye.trailingComponent
    re: /(\w+(?:\.default)?\.createElement)\("div",\{className:(\w+)\.commandContent\},\1\("span",\{className:\2\.commandLabel\},(\w+)\.label,\3\.labelSuffix\),null\),\3\.trailingComponent/,
    build: (callFn, modVar, itemVar, descExpr) =>
      `${callFn}("div",{className:${modVar}.commandContent},${callFn}("span",{className:${modVar}.commandLabel},${itemVar}.label,${itemVar}.labelSuffix),${descExpr}),${itemVar}.trailingComponent`,
  },
  {
    name: "jsx-runtime (jsx/jsxs automatic)",
    // 例: E("div",{className:Jh.commandContent,children:[
    //      E("span",{className:Jh.commandLabel,children:[we.label,we.labelSuffix]}),
    //      null]}),we.trailingComponent
    re: /(\w+)\("div",\{className:(\w+)\.commandContent,children:\[\1\("span",\{className:\2\.commandLabel,children:\[(\w+)\.label,\3\.labelSuffix\]\}\),null\]\}\),\3\.trailingComponent/,
    build: (callFn, modVar, itemVar, descExpr) =>
      `${callFn}("div",{className:${modVar}.commandContent,children:[${callFn}("span",{className:${modVar}.commandLabel,children:[${itemVar}.label,${itemVar}.labelSuffix]}),${descExpr}]}),${itemVar}.trailingComponent`,
  },
];

let matched = null;
for (const style of ANCHOR_STYLES) {
  const g = new RegExp(style.re.source, "g");
  const hits = src.match(g) || [];
  if (hits.length === 1) { matched = { style, m: style.re.exec(src) }; break; }
  if (hits.length > 1) {
    console.log(`ANCHOR_COUNT=${hits.length} (expected 1) for style "${style.name}" — aborting`);
    process.exit(1);
  }
}
if (!matched) {
  console.log(
    "ANCHOR_COUNT=0 — no known anchor style matched (both classic 和 jsx-runtime 结构都没找到)。\n" +
    "扩展这次升级可能把斜杠命令面板的渲染代码结构改得更彻底了，需要人工在新 index.js 里\n" +
    "重新定位 commandLabel/commandContent/trailingComponent 附近代码，更新本文件里的 ANCHOR_STYLES。\n" +
    "— aborting"
  );
  process.exit(1);
}

const { style, m } = matched;
const [, callFn, modVar, itemVar] = m;
console.log(`锚点匹配: ${style.name} (callFn=${callFn}, modVar=${modVar}, itemVar=${itemVar})`);

const mapLiteral = JSON.stringify(map);

// 智能查找逻辑（按 webview 实际 ID 形态适配译表 key）：
// 1. <itemVar>.id 直接查（去 / 前缀）
// 2. 剥离连字符+后缀 (-conversation/-config/-command/-mode/-setup/-level/-help/-control)
// 3. 剥离前缀 slash-command-
// 4. <itemVar>.label 兜底（去 / 前缀）
// 5. <itemVar>.description 英文原文兜底（绝不让面板空白）
//
// 用 {className,children} 对象形式传给 callFn：无论 callFn 是
// React.createElement(type,config,...children) 还是 jsx-runtime 的
// jsx/jsxs(type,config)，只传两个参数时 children 都会从 config.children 里取，
// 两种调用签名都认，不用按 style 分别生成两套描述元素代码。
const desc =
  '(function(){try{' +
  'var __m=globalThis.__CCZH||(globalThis.__CCZH=' + mapLiteral + ');' +
  `var __id=(${itemVar}.id||"").toString().replace(/^\\//,"").toLowerCase();` +
  'var __d=__m[__id];' +
  // 后缀剥离: 把"ID 末尾的 -<suffix>"整段剥掉（包括连字符），如 clear-conversation → clear
  'if(!__d){' +
    'var __s=__id.replace(/[-_]?(conversation|config|command|mode|setup|level|help|control|alias)$/,"");' +
    'if(__s!==__id)__d=__m[__s];' +
  '}' +
  // 前缀剥离: slash-command-help → help
  'if(!__d&&__id.startsWith("slash-command-"))__d=__m[__id.slice(14)];' +
  // label 兜底
  `if(!__d)__d=__m[(${itemVar}.label||"").toString().replace(/^\\//,"").toLowerCase()];` +
  // 英文描述兜底
  `if(!__d)__d=(${itemVar}.description&&${itemVar}.description.value)?${itemVar}.description.value:(typeof ${itemVar}.description==="string"?${itemVar}.description:"");` +
  `return __d?${callFn}("span",{className:${modVar}.commandDescription,children:__d}):null` +
  '}catch(__e){return null}})()';

const replacement = style.build(callFn, modVar, itemVar, desc);
src = src.replace(style.re, () => replacement); // 用函数形式避免 $&/$1 等被当作特殊替换语法解析
fs.writeFileSync(targetPath, src, "utf8");
console.log("INJECTED render hook (smart-match). map entries=" + Object.keys(map).length);

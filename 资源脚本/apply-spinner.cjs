// Claude Code CLI 汉化注入器
// ==================================
// 把 spinner 动词、提示语、AI 回复语言三个 key 写入 ~/.claude/settings.json。
// 基于 KongBai1145/claude-code-zh-cn @ MIT 的思路,术语表用我们的翻译清单。
//
// 用法:
//   node apply-spinner.cjs --merge                  写入/合并(默认,幂等)
//   node apply-spinner.cjs --remove                 移除本工具注入的 4 个 key,恢复备份
//   node apply-spinner.cjs --dry-run                只打印会做什么,不真写(默认动作 merge)
//   node apply-spinner.cjs --remove --dry-run       只打印会移除什么,不真删
//
// --dry-run 和 --remove/--merge 是两个独立维度(只读预览 vs 真实动作),
// 可以任意组合传参,--dry-run 永远只读不写。
//
// 设计要点:
//   - 只增不覆盖:用户已有的其他 key 一律不动
//   - 幂等:重复跑结果字节级一致
//   - 可逆:--merge 前自动备份为 settings.json.bak-<timestamp>
//   - 移除:--remove 删除注入的 4 个 key,还原备份
//
// settings.json 里 spinnerVerbs / spinnerTipsOverride 的形状已用真实
// 用户报错案例核实(anthropics/claude-code issue #33379):
//   spinnerVerbs        = {mode:"replace", verbs:[...]}   ← 对象,不是裸数组
//   spinnerTipsOverride = {excludeDefault:true, tips:[...]} ← tips 是纯字符串数组,不是 {id,text}

const fs = require("fs");
const os = require("os");
const path = require("path");

// --dry-run 和 --remove/--merge 是两个独立维度(动作 vs 是否真写),
// 不能用单一三元表达式合并判断,否则 --remove --dry-run 同传会被
// 误判成 mode="remove" 直接真删(--dry-run 形同虚设,真实 bug)。
const args = process.argv.slice(2);
const isDryRun = args.includes("--dry-run");
const isRemove = args.includes("--remove");
const action = isRemove ? "remove" : "merge";

// 文件路径
const HERE = path.dirname(process.argv[1]);
const VERBS_JSON = path.join(HERE, "spinner-verbs-zh.json");
const TIPS_JSON = path.join(HERE, "spinner-tips-zh.json");
const SETTINGS_JSON = path.join(os.homedir(), ".claude", "settings.json");

// 本工具注入的 4 个 key(--remove 时用来精确删除)
const INJECTED_KEYS = ["language", "spinnerTipsEnabled", "spinnerVerbs", "spinnerTipsOverride"];

function ts() {
  // Windows 文件名友好的时间戳: 20260622-003456
  const d = new Date();
  const pad = n => String(n).padStart(2, "0");
  return d.getFullYear() + pad(d.getMonth()+1) + pad(d.getDate()) +
         "-" + pad(d.getHours()) + pad(d.getMinutes()) + pad(d.getSeconds());
}

function readJSON(p, fallback) {
  try {
    return JSON.parse(fs.readFileSync(p, "utf8"));
  } catch (e) {
    if (e.code === "ENOENT") return fallback;
    throw e;
  }
}

function atomicWrite(p, content) {
  // Node 原子写:写到 .tmp 再 rename,避免半写文件
  const tmp = p + ".tmp-" + process.pid;
  fs.writeFileSync(tmp, content, "utf8");
  fs.renameSync(tmp, p);
}

function backup(p) {
  if (!fs.existsSync(p)) return null;
  const bak = p + ".bak-" + ts();
  fs.copyFileSync(p, bak);
  return bak;
}

function findLatestBackup(p) {
  // 找本工具最近一次的备份(settings.json.bak-<timestamp>)
  const dir = path.dirname(p);
  const base = path.basename(p);
  const bak = fs.readdirSync(dir)
    .filter(f => f.startsWith(base + ".bak-"))
    .map(f => ({ name: f, time: fs.statSync(path.join(dir, f)).mtimeMs }))
    .sort((a, b) => b.time - a.time);
  return bak.length ? path.join(dir, bak[0].name) : null;
}

function doMerge() {
  const verbs = readJSON(VERBS_JSON, []);
  const tips = readJSON(TIPS_JSON, []);
  if (!verbs.length || !tips.length) {
    console.log("❌ spinner-verbs-zh.json 或 spinner-tips-zh.json 为空");
    process.exit(1);
  }

  // 确保 ~/.claude 目录存在
  const dir = path.dirname(SETTINGS_JSON);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

  const before = readJSON(SETTINGS_JSON, {});
  console.log(`📂 目标: ${SETTINGS_JSON}`);
  console.log(`   已有 key: ${Object.keys(before).length} 个(${Object.keys(before).join(", ") || "空"})`);

  // dry-run:只打印,不写
  if (isDryRun) {
    console.log("\n[dry-run] 将合并以下 4 个 key:");
    console.log(`  language            = "Chinese"`);
    console.log(`  spinnerTipsEnabled  = true`);
    console.log(`  spinnerVerbs        = {mode:"replace", verbs:[${verbs.length} 条]}`);
    console.log(`  spinnerTipsOverride = {excludeDefault:true, tips:[${tips.length} 条字符串]}`);
    console.log("\n不修改任何文件。");
    return;
  }

  // 备份(仅当文件存在)
  let bak = null;
  if (fs.existsSync(SETTINGS_JSON)) {
    bak = backup(SETTINGS_JSON);
    console.log(`💾 已备份: ${path.basename(bak)}`);
  } else {
    console.log(`💾 目标文件不存在,直接创建`);
  }

  // 合并(只增不覆盖,但本工具自己的 4 个 key 永远用新值,以保持幂等)
  //
  // 形状依据官方真实 schema(已用真实用户的 settings.json 报错案例核实,
  // 见 anthropics/claude-code issue #33379):
  //   spinnerVerbs        是对象 {mode, verbs},不是裸数组——
  //     之前误把 KongBai1145 项目里 {mode,verbs} 的外层拆掉只留了数组,
  //     这正是 Cursor 内置插件报 "Expected object, but received array" 的根因。
  //   spinnerTipsOverride.tips 是纯字符串数组,不是 {id,text} 对象数组。
  const after = { ...before };
  after.language = "Chinese";
  after.spinnerTipsEnabled = true;
  after.spinnerVerbs = { mode: "replace", verbs: verbs };
  after.spinnerTipsOverride = {
    excludeDefault: true,
    tips: tips.map(t => t.text),
  };

  atomicWrite(SETTINGS_JSON, JSON.stringify(after, null, 2) + "\n");

  // 报告差异
  const newKeys = Object.keys(after).filter(k => !(k in before));
  const updatedKeys = INJECTED_KEYS.filter(k => k in before);
  console.log(`✅ 已写入`);
  console.log(`   新增 key: ${newKeys.length ? newKeys.join(", ") : "(无)"}`);
  console.log(`   更新 key: ${updatedKeys.length ? updatedKeys.join(", ") : "(无)"}`);
  console.log(`   spinnerVerbs: ${verbs.length} 条`);
  console.log(`   spinnerTips:  ${tips.length} 条`);
  if (bak) console.log(`   还原备份: cp "${bak}" "${SETTINGS_JSON}"`);
  console.log(`\n🎉 CLI 终端汉化已生效。下次启动 claude 时: spinner 词/提示/AI 回复语言均为中文。`);
}

function doRemove() {
  if (!fs.existsSync(SETTINGS_JSON)) {
    console.log(`❌ ${SETTINGS_JSON} 不存在,无需移除`);
    return;
  }

  const before = readJSON(SETTINGS_JSON, {});
  const hasAny = INJECTED_KEYS.some(k => k in before);
  if (!hasAny) {
    console.log(`ℹ ${SETTINGS_JSON} 没有本工具注入的 key,无需移除`);
    return;
  }

  // dry-run
  if (isDryRun) {
    const toRemove = INJECTED_KEYS.filter(k => k in before);
    console.log(`[dry-run] 将从 ${SETTINGS_JSON} 移除:`);
    console.log(`  ${toRemove.join("\n  ")}`);
    console.log("\n不修改任何文件。");
    return;
  }

  // 备份当前状态
  const bak = backup(SETTINGS_JSON);
  console.log(`💾 已备份当前状态: ${path.basename(bak)}`);

  // 删除注入的 4 个 key
  const after = { ...before };
  const removed = [];
  for (const k of INJECTED_KEYS) {
    if (k in after) { delete after[k]; removed.push(k); }
  }

  atomicWrite(SETTINGS_JSON, JSON.stringify(after, null, 2) + "\n");
  console.log(`✅ 已移除 ${removed.length} 个 key: ${removed.join(", ")}`);
  console.log(`   剩余 key: ${Object.keys(after).length} 个(原 ${Object.keys(before).length - removed.length} 个未注入的保留)`);

  // 提示用户最新的 .bak 是还原点
  const restoreFrom = findLatestBackup(SETTINGS_JSON);
  if (restoreFrom) {
    console.log(`\n💡 想完全回到移除前,可用:`);
    console.log(`   cp "${restoreFrom}" "${SETTINGS_JSON}"`);
  }
}

console.log(`[apply-spinner.cjs] action=${action}${isDryRun ? " (dry-run)" : ""}`);
if (action === "remove") doRemove();
else doMerge();

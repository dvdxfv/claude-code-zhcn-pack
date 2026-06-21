const fs = require("fs");
const [, , mapPath, targetPath] = process.argv;
const map = JSON.parse(fs.readFileSync(mapPath, "utf8"));
let src = fs.readFileSync(targetPath, "utf8");

const zero = [];
const multi = [];
let applied = 0;

// Replace exact double-quoted string literals: "EN" -> "ZH".
for (const [en, zh] of Object.entries(map)) {
  const needle = '"' + en + '"';
  const repl = '"' + zh + '"';
  // count occurrences
  let count = 0;
  let idx = 0;
  while ((idx = src.indexOf(needle, idx)) !== -1) { count++; idx += needle.length; }
  if (count === 0) { zero.push(en); continue; }
  if (count > 1) multi.push(en + " (" + count + ")");
  src = src.split(needle).join(repl);
  applied += count;
}

fs.writeFileSync(targetPath, src, "utf8");
console.log("APPLIED replacements: " + applied);
console.log("ENTRIES matched: " + (Object.keys(map).length - zero.length) + "/" + Object.keys(map).length);
if (multi.length) console.log("MULTI-MATCH (replaced all):\n  " + multi.join("\n  "));
if (zero.length) console.log("ZERO-MATCH (NOT found, check manually):\n  " + zero.join("\n  "));

const fs = require("fs");
const [, , mapPath, targetPath] = process.argv;
const map = JSON.parse(fs.readFileSync(mapPath, "utf8"));
let src = fs.readFileSync(targetPath, "utf8");

const KEYS = ["label", "title", "placeholder", "tooltip", "heading", "ariaLabel", "text", "menuDescription"];
const zero = [];
let applied = 0;

for (const [en, zh] of Object.entries(map)) {
  let total = 0;
  for (const k of KEYS) {
    const needle = k + ':"' + en + '"';
    const repl = k + ':"' + zh + '"';
    let count = 0, idx = 0;
    while ((idx = src.indexOf(needle, idx)) !== -1) { count++; idx += needle.length; }
    if (count > 0) { src = src.split(needle).join(repl); total += count; }
  }
  if (total === 0) zero.push(en);
  else applied += total;
}

fs.writeFileSync(targetPath, src, "utf8");
console.log("ANCHORED replacements: " + applied);
console.log("ENTRIES matched: " + (Object.keys(map).length - zero.length) + "/" + Object.keys(map).length);
if (zero.length) console.log("ZERO-MATCH:\n  " + zero.join("\n  "));

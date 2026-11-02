import fs from "node:fs";
import path from "node:path";
const QA = path.resolve(import.meta.dirname, "..", "..", "qa");
const which = process.argv[2];
const o = JSON.parse(fs.readFileSync(path.join(QA, `audit-${which}.json`)));
if (which === "layout") {
  const agg = {};
  for (const r of o.layout) {
    const add = (k, v) => { const key = k + " | " + String(v).replace(/-?\d+/g, "#").slice(0, 140); (agg[key] ??= []).push(r.tag); };
    if (r.overflow) add("OVERFLOW", r.overflow);
    r.outside.forEach((x) => add("OUTSIDE", x));
    r.unnamed.forEach((x) => add("UNNAMED", x));
    r.lowContrast.forEach((x) => add("CONTRAST", x));
    r.console.forEach((x) => add("CONSOLE", x));
    r.net.forEach((x) => add("NET", x));
    r.pageerr.forEach((x) => add("PAGEERR", x));
    if (r.items !== undefined) add("PALETTEITEMS", r.items);
  }
  for (const [k, v] of Object.entries(agg)) console.log(k, "  x" + v.length, v.slice(0, 3).join(","));
} else if (which === "flows") {
  for (const r of o.flows) console.log(JSON.stringify({ ...r, console: undefined, dlPath: undefined }).slice(0, 700), r.console?.length ? "CONSOLE:" + r.console.join(";").slice(0, 200) : "", r.net?.length ? "NET:" + r.net.join(";").slice(0, 200) : "");
} else {
  for (const r of o.kbd) console.log(JSON.stringify(r).slice(0, 1500));
}

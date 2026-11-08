import fs from "node:fs";
import path from "node:path";
const QA = path.resolve(import.meta.dirname, "..", "..", "qa");
const j = (n) => JSON.parse(fs.readFileSync(path.join(QA, n)));
const a = j("office-run-a.json");
const x = a.find((r) => r.variant === "dpi5000");
console.log("dpi5000", JSON.stringify({ ...x, run: { ...x.run, statuses: x.run.statuses.length } }));
const c = j("office-run-c.json");
for (const r of c.filter((r) => r.lang === "en" && r.scheme === "light" && r.vp === "390x800"))
  console.log(r.tool, "note", r.empty.note, "small", JSON.stringify(r.empty.smallTargets), JSON.stringify(r.withFile.smallTargets));
console.log("total with note", c.filter((r) => r.empty.note).length, "of", c.length);

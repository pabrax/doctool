import fs from "node:fs";
import path from "node:path";
const QA = path.resolve(import.meta.dirname, "..", "..", "qa");
const o = JSON.parse(fs.readFileSync(path.join(QA, "audit-flows.json")));
for (const r of o.flows) {
  const net = (r.net ?? []).filter((x) => !/download net::ERR_ABORTED/.test(x));
  console.log(r.tag, "|", r.dropRejected ? "DROP:" + r.dropRejected : "", r.runDisabled ? "RUNDISABLED" : "", r.timeout ? "TIMEOUT" : "", "|", r.alert ? "ALERT:" + r.alert : "", "|", r.result ?? "", "|", r.download ?? r.downloadErr ?? "", r.posts ?? "", r.newPosts ?? "", "|", net.join(";"), (r.console ?? []).join(";").slice(0, 160));
}

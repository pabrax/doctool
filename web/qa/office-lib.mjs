import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
export const QA = path.resolve(import.meta.dirname, "..", "..", "qa");
export const BASE = "http://127.0.0.1:8000";
export const FX = (n) => path.join(QA, "fixtures-office", n);
export const SRC = (n) => path.join(QA, "..", "web", "e2e", ".fixtures", n);
export const SHOTS = path.join(QA, "shots");
export const DL = path.join(QA, "dl-office");
fs.mkdirSync(DL, { recursive: true });
export const launch = () => chromium.launch({ channel: "msedge" });
export async function mk(b, { w = 1280, h = 900, lang = "en", scheme = "light" } = {}) {
  const ctx = await b.newContext({ viewport: { width: w, height: h }, locale: lang === "es" ? "es-ES" : "en-US", colorScheme: scheme, acceptDownloads: true });
  await ctx.addInitScript((l) => localStorage.setItem("doctool.lang", l), lang);
  const page = await ctx.newPage();
  page.__log = [];
  page.on("console", (m) => ["error", "warning"].includes(m.type()) && page.__log.push(`console.${m.type()}: ${m.text().slice(0, 200)}`));
  page.on("pageerror", (e) => page.__log.push(`pageerror: ${e.message.slice(0, 200)}`));
  page.on("response", (r) => r.status() >= 400 && page.__log.push(`HTTP ${r.status()} ${r.request().method()} ${r.url().replace(BASE, "")}`));
  page.on("requestfailed", (r) => page.__log.push(`reqfailed ${r.url().replace(BASE, "")} ${r.failure()?.errorText}`));
  return { ctx, page };
}
export async function open(page, tool) {
  await page.goto(`${BASE}/tools/${tool}`);
  await page.waitForLoadState("networkidle");
  await page.waitForSelector("input[type=file]", { state: "attached" });
}
const txt = async (loc) => (await loc.count()) ? (await loc.allInnerTexts()).join(" || ").replace(/\s+/g, " ").trim() : "";
export async function addFile(page, file) {
  await page.locator("input[type=file]").first().setInputFiles(file);
  await page.waitForTimeout(600);
  return { alerts: await txt(page.locator("[role=alert]")), files: await txt(page.locator("main ul, main li").first()) };
}
export async function run(page, { maxMs = 90000, sample = true } = {}) {
  const btn = page.locator("button[type=submit]").first();
  const label0 = (await btn.innerText()).trim();
  const enabled = await btn.isEnabled();
  if (!enabled) return { skipped: "run disabled", label0 };
  const t0 = Date.now();
  await btn.click();
  const statuses = [];
  let outcome = null;
  while (Date.now() - t0 < maxMs) {
    await page.waitForTimeout(700);
    if (sample) {
      const s = await txt(page.locator("[role=status]"));
      if (s && statuses.at(-1) !== s) statuses.push(`${((Date.now() - t0) / 1000).toFixed(1)}s: ${s.slice(0, 200)}`);
    }
    if (await page.locator("#result-h").count()) { outcome = "result"; break; }
    if ((await page.locator("[role=alert]").count()) && !(await btn.isDisabled())) { outcome = "alert"; break; }
  }
  const ms = Date.now() - t0;
  await page.waitForTimeout(400);
  const alerts = await txt(page.locator("[role=alert]"));
  const resultText = outcome === "result" ? await txt(page.locator("#result-h").locator("xpath=ancestor::*[self::section or self::div][1]")) : "";
  const focus = await page.evaluate(() => { const a = document.activeElement; return `${a?.tagName}[${(a?.textContent || a?.id || "").trim().slice(0, 30)}]`; });
  return { label0, outcome, ms, statuses, alerts, resultText: resultText.slice(0, 900), focus, btnAfter: (await btn.innerText()).trim() };
}
export async function download(page, name) {
  const dl = page.locator("a[href*='/download'], button").filter({ hasText: /download|descargar/i }).first();
  if (!(await dl.count())) return { err: "no download control" };
  const [d] = await Promise.all([page.waitForEvent("download", { timeout: 20000 }).catch(() => null), dl.click()]);
  if (!d) return { err: "no download event" };
  const p = path.join(DL, name + "__" + d.suggestedFilename());
  await d.saveAs(p);
  const buf = fs.readFileSync(p);
  const head = buf.subarray(0, 4).toString("latin1");
  const o = { file: d.suggestedFilename(), size: buf.length, magic: head.replace(/[^\x20-\x7e]/g, "?") };
  if (head === "%PDF") {
    const s = buf.toString("latin1");
    o.mediaBox = (s.match(/\/MediaBox\s*\[[^\]]+\]/) || [])[0];
    o.pages = (s.match(/\/Type\s*\/Page[^s]/g) || []).length;
  }
  return o;
}
export const shot = (page, n) => page.screenshot({ path: path.join(SHOTS, n + ".png"), fullPage: true });
export const out = (n, d) => fs.writeFileSync(path.join(QA, n), JSON.stringify(d, null, 1));

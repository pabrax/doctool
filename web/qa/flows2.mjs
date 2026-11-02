// Second flow pass: imageconvert with an explicit format, invalid files, oversize, double submit, focus, size line.
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
const BASE = "http://127.0.0.1:5173";
const QA = path.resolve(import.meta.dirname, "..", "..", "qa");
const fx = (n) => path.join(QA, "fixtures", n);
const b = await chromium.launch({ channel: "msedge" });
const res = [];
for (const lang of ["en", "es"]) {
  const ctx = await b.newContext({ viewport: { width: 390, height: 800 }, locale: lang === "es" ? "es-ES" : "en-US" });
  await ctx.addInitScript((l) => localStorage.setItem("doctool.lang", l), lang);
  const page = await ctx.newPage();
  const net = [];
  page.on("response", (r) => { if (r.status() >= 400) net.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`); });
  const posts = [];
  page.on("request", (r) => { if (r.method() === "POST") posts.push(new URL(r.url()).pathname); });
  for (const bad of ["fake.jpg", "empty.jpg", "truncated.jpg", "anim.gif", "hugepx.png", "oversize.png", "photo.jpg"]) {
    await page.goto(`${BASE}/tools/imageconvert`);
    await page.waitForLoadState("networkidle");
    net.length = 0; posts.length = 0;
    await page.setInputFiles('[data-testid="file-input"]', fx(bad));
    await page.waitForTimeout(400);
    await page.locator("aside form select").first().selectOption("jpg");
    const run = page.locator('form button[type="submit"]');
    if (bad === "photo.jpg") await run.dblclick(); else await run.click();
    await page.waitForSelector("#result-h, div[role=alert]", { timeout: 120000 }).catch(() => {});
    await page.waitForTimeout(1000);
    const alert = (await page.locator("div[role=alert]").allTextContents()).join("|");
    const result = (await page.locator('section[aria-labelledby="result-h"]').allInnerTexts()).join("|").replace(/\s+/g, " ");
    const focus = await page.evaluate(() => { const a = document.activeElement; return `${a.tagName}[${(a.textContent || "").trim().slice(0, 20)}]`; });
    const runState = await run.isDisabled();
    await page.screenshot({ path: path.join(QA, "shots", `G_${lang}_convert_${bad}.png`), fullPage: true });
    res.push({ lang, bad, alert, result, focus, runDisabledAfter: runState, posts: [...posts], net: [...net] });
    console.log(JSON.stringify(res.at(-1)));
  }
  // same run on a PDF tool for focus comparison
  await page.goto(`${BASE}/tools/compress`);
  await page.waitForLoadState("networkidle");
  await page.setInputFiles('[data-testid="file-input"]', path.resolve(QA, "..", "web", "e2e", ".fixtures", "alpha.pdf"));
  await page.locator('form button[type="submit"]').click();
  await page.waitForSelector("#result-h, div[role=alert]", { timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(1000);
  console.log(lang, "PDF compress focus:", await page.evaluate(() => `${document.activeElement.tagName}[${(document.activeElement.textContent || "").trim().slice(0, 20)}]`), "|", (await page.locator('section[aria-labelledby="result-h"]').allInnerTexts()).join("|").replace(/\s+/g, " "));
  await ctx.close();
}
fs.writeFileSync(path.join(QA, "audit-flows2.json"), JSON.stringify(res, null, 1));
await b.close();

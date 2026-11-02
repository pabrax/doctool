import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
const BASE = "http://127.0.0.1:5173";
const QA = path.resolve(import.meta.dirname, "..", "..", "qa");
const fx = (n) => path.join(QA, "fixtures", n);
const b = await chromium.launch({ channel: "msedge" });
const mk = async (w, h, lang, scheme = "light") => {
  const ctx = await b.newContext({ viewport: { width: w, height: h }, locale: lang === "es" ? "es-ES" : "en-US", colorScheme: scheme });
  await ctx.addInitScript((l) => localStorage.setItem("doctool.lang", l), lang);
  return { ctx, page: await ctx.newPage() };
};
for (const lang of ["en", "es"]) {
  // keyboard-only run
  const { ctx, page } = await mk(1280, 480, lang);
  await page.goto(BASE + "/tools/imagecompress"); await page.waitForLoadState("networkidle");
  const desc = () => page.evaluate(() => { const a = document.activeElement; const cs = getComputedStyle(a); return `${a.tagName.toLowerCase()}[${(a.getAttribute("aria-label") || a.textContent || a.id || "").trim().slice(0, 24)}] outline=${cs.outlineStyle}/${cs.outlineWidth} shadow=${cs.boxShadow !== "none"}`; });
  const trail = [];
  let found = false;
  for (let i = 0; i < 30 && !found; i++) { await page.keyboard.press("Tab"); trail.push(await desc()); found = await page.evaluate(() => /select files|elegir archivos/i.test(document.activeElement?.textContent || "")); }
  console.log(lang, "to Select button:", trail.length, "tabs; last:", trail.at(-1));
  const [fc] = await Promise.all([page.waitForEvent("filechooser", { timeout: 5000 }).catch(() => null), page.keyboard.press("Enter")]);
  console.log(lang, "chooser via Enter:", !!fc);
  if (fc) {
    await fc.setFiles(fx("photo.jpg")); await page.waitForTimeout(500);
    console.log(lang, "focus after file add:", await desc());
    const t2 = []; let onRun = false;
    for (let i = 0; i < 20 && !onRun; i++) { await page.keyboard.press("Tab"); t2.push(await desc()); onRun = await page.evaluate(() => document.activeElement?.getAttribute("type") === "submit"); }
    console.log(lang, "tabs to Run:", t2.join(" > "));
    await page.keyboard.press("Enter");
    await page.waitForSelector("#result-h, div[role=alert]", { timeout: 60000 }).catch(() => {});
    await page.waitForTimeout(800);
    console.log(lang, "focus after result:", await desc(), "| result visible in viewport:", await page.evaluate(() => { const r = document.getElementById("result-h")?.getBoundingClientRect(); return r ? `${Math.round(r.top)}..${Math.round(r.bottom)} of ${innerHeight}` : "none"; }));
    await page.keyboard.press("Tab");
    console.log(lang, "next Tab from body:", await desc());
    await page.screenshot({ path: path.join(QA, "shots", `K_${lang}.png`) });
  }
  await ctx.close();
}
// form behaviour on phone
for (const lang of ["en", "es"]) {
  const { ctx, page } = await mk(390, 800, lang);
  for (const id of ["imageconvert", "imageresize", "imagecrop"]) {
    await page.goto(`${BASE}/tools/${id}`); await page.waitForLoadState("networkidle");
    const modes = id === "imageconvert" ? ["jpg", "png", "webp"] : id === "imageresize" ? ["fit_box", "exact", "percent"] : ["ratio", "box"];
    for (const m of modes) {
      await page.locator("aside form select").first().selectOption(m);
      await page.waitForTimeout(200);
      const labels = await page.evaluate(() => [...document.querySelectorAll("aside form > div, aside form > label")].map((e) => e.innerText.trim().replace(/\s+/g, " ").slice(0, 100)).join(" || "));
      const inputs = await page.evaluate(() => [...document.querySelectorAll("aside input")].map((i) => `${i.type}/inputmode=${i.inputMode || "-"}/${Math.round(i.getBoundingClientRect().width)}x${Math.round(i.getBoundingClientRect().height)}/req=${i.required}`).join(", "));
      const ov = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
      console.log(`${lang} ${id} ${m}: overflow=${ov}\n   ${labels}\n   inputs: ${inputs}`);
      await page.screenshot({ path: path.join(QA, "shots", `M_${lang}_${id}_${m}.png`), fullPage: true });
    }
  }
  await ctx.close();
}
await b.close();

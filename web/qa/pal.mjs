import { chromium } from "playwright-core";
import path from "node:path";
const SH = path.resolve(import.meta.dirname, "..", "..", "qa", "shots");
const b = await chromium.launch({ channel: "msedge" });
for (const lang of ["en", "es"]) {
  const ctx = await b.newContext({ viewport: { width: 1280, height: 480 }, locale: lang === "es" ? "es-ES" : "en-US" });
  await ctx.addInitScript((l) => localStorage.setItem("doctool.lang", l), lang);
  const p = await ctx.newPage();
  await p.goto("http://127.0.0.1:5173/");
  await p.waitForLoadState("networkidle");
  await p.keyboard.press("Control+k");
  await p.waitForTimeout(400);
  console.log(lang, "total items", await p.locator("[cmdk-item]").count());
  for (const q of ["image", "imagen", "photo", "foto", "jpg", "exif", "crop", "recort", "resize", "peso", "privacy"]) {
    await p.keyboard.press("Control+a");
    await p.keyboard.type(q);
    await p.waitForTimeout(250);
    console.log(lang, q, "=>", (await p.locator("[cmdk-item]").allInnerTexts()).map((t) => t.replace(/\s+/g, " ")).join(" ; "));
  }
  await p.keyboard.press("Control+a"); await p.keyboard.type("crop"); await p.waitForTimeout(200); await p.keyboard.press("Enter"); await p.waitForTimeout(500);
  console.log(lang, "after Enter url:", p.url(), "focus:", await p.evaluate(() => document.activeElement.tagName + ":" + (document.activeElement.id || document.activeElement.textContent.slice(0, 20))));
  await ctx.close();
}
await b.close();

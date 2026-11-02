import { chromium } from "playwright-core";
import path from "node:path";
const SH = path.resolve(import.meta.dirname, "..", "..", "qa", "shots");
const b = await chromium.launch({ channel: "msedge" });
for (const [n, w, h] of [["short", 1280, 480], ["tablet", 768, 1024], ["phone", 390, 800]]) {
  const ctx = await b.newContext({ viewport: { width: w, height: h } });
  const p = await ctx.newPage();
  await p.goto("http://127.0.0.1:5173/tools/imagecrop");
  await p.waitForLoadState("networkidle");
  const info = await p.evaluate(() => {
    const nav = document.querySelector("nav") ?? document.querySelector("aside");
    const out = [];
    for (const el of document.querySelectorAll("nav, aside")) {
      const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
      out.push(`${el.tagName} ${el.getAttribute("aria-label") || ""} top=${Math.round(r.top)} h=${Math.round(r.height)} sh=${el.scrollHeight} ch=${el.clientHeight} ovY=${s.overflowY} pos=${s.position} vis=${s.display}`);
    }
    const link = [...document.querySelectorAll("a")].find((a) => /Crop image/.test(a.textContent) && a.getBoundingClientRect().width > 0);
    return { out, link: link ? JSON.stringify(link.getBoundingClientRect()) : "no visible Crop link" };
  });
  console.log(n, JSON.stringify(info));
  await p.screenshot({ path: path.join(SH, `S_${n}.png`) });
  // can keyboard focus reach Crop image link & is it scrolled into view?
  const link = p.getByRole("link", { name: "Crop image" }).first();
  if (await link.isVisible().catch(() => false)) { await link.focus(); await p.waitForTimeout(200); console.log(n, "crop link in view:", JSON.stringify(await link.boundingBox())); await p.screenshot({ path: path.join(SH, `S_${n}_focus.png`) }); }
  await ctx.close();
}
await b.close();

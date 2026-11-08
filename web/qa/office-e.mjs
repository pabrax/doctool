import { launch, mk, open, addFile, shot, SRC, BASE } from "./office-lib.mjs";
const b = await launch();
const log = (...a) => console.log(...a);
for (const lang of ["en", "es"]) {
  for (const [w, h] of [[1280, 800], [390, 800]]) {
    const { ctx, page } = await mk(b, { lang, w, h });
    await page.goto(BASE + "/"); await page.waitForLoadState("networkidle");
    log(lang, w, "home tiles:", JSON.stringify(await page.locator("main a[href^='/tools/']").evaluateAll((a) => a.map((x) => x.getAttribute("href").replace("/tools/", "") + ":" + x.innerText.replace(/\s+/g, " ").trim().slice(0, 60)))));
    if (w === 1280) {
      log(lang, "sidebar groups:", JSON.stringify(await page.locator("nav, aside").first().evaluate((n) => [...n.querySelectorAll("h2,h3,[data-group-label],p,span,summary")].map((e) => e.textContent.trim()).filter(Boolean).slice(0, 60))));
      await shot(page, `OE_${lang}_home_${w}`);
    } else {
      await page.getByRole("button", { name: /menu|menú/i }).first().click().catch(() => log("menu button not found"));
      await page.waitForTimeout(500);
      log(lang, "drawer text:", (await page.locator("body").innerText()).replace(/\s+/g, " ").slice(0, 700));
      await shot(page, `OE_${lang}_drawer_${w}`);
    }
    await ctx.close();
  }
  // palette
  const { ctx, page } = await mk(b, { lang });
  await page.goto(BASE + "/"); await page.waitForLoadState("networkidle");
  await page.keyboard.press("Control+k"); await page.waitForTimeout(400);
  const qs = lang === "en" ? ["word", "docx", "excel", "powerpoint", "html", "pdf to word", "tabla", "diapositivas", "csv", "ofimática", "office"] : ["word", "documento", "hoja de cálculo", "presentación", "página web", "tabla", "diapositivas", "pdf a word", "office", "ofimática"];
  for (const q of qs) {
    await page.keyboard.press("Control+a"); await page.keyboard.type(q); await page.waitForTimeout(300);
    log(lang, "palette", JSON.stringify(q), "->", JSON.stringify(await page.locator("[role=option]").allInnerTexts().then((t) => t.map((s) => s.replace(/\s+/g, " ")).slice(0, 8))));
  }
  await page.keyboard.press("Control+a"); await page.keyboard.type(lang === "en" ? "word to pdf" : "word a pdf"); await page.waitForTimeout(300);
  await shot(page, `OE_${lang}_palette`);
  await page.keyboard.press("Enter"); await page.waitForTimeout(800);
  log(lang, "enter navigates to:", page.url());
  await ctx.close();
}
// Dropzone accept lists via client rejection (drop of wrong files) – real dropzone behaviour
await b.close();

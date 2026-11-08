import { launch, mk, open, addFile, shot, SRC, FX, BASE } from "./office-lib.mjs";
const b = await launch();
const log = (...a) => console.log(...a);
for (const lang of ["en", "es"]) {
  for (const [tool, file] of [["word2pdf", SRC("letter.docx")], ["pdf2excel", SRC("table.pdf")]]) {
    const { ctx, page } = await mk(b, { lang, w: 1280, h: 480 });
    await open(page, tool);
    const desc = () => page.evaluate(() => { const a = document.activeElement; const cs = getComputedStyle(a); return `${a.tagName.toLowerCase()}[${(a.getAttribute("aria-label") || a.textContent || a.id || "").trim().slice(0, 22)}] ring=${cs.outlineStyle !== "none" || cs.boxShadow !== "none"}`; });
    const trail = [];
    let sel = false;
    for (let i = 0; i < 40 && !sel; i++) { await page.keyboard.press("Tab"); trail.push(await desc()); sel = await page.evaluate(() => /select files|elegir archivos|seleccionar archivos/i.test(document.activeElement?.textContent || "")); }
    log(lang, tool, "tabs to Select:", trail.length, "| trail:", trail.join(" > "));
    const [fc] = await Promise.all([page.waitForEvent("filechooser", { timeout: 5000 }).catch(() => null), page.keyboard.press("Enter")]);
    log(lang, tool, "chooser via Enter:", !!fc);
    if (!fc) { await ctx.close(); continue; }
    await fc.setFiles(file); await page.waitForTimeout(600);
    log(lang, tool, "focus after file add:", await desc());
    const t2 = []; let onRun = false;
    for (let i = 0; i < 20 && !onRun; i++) { await page.keyboard.press("Tab"); t2.push(await desc()); onRun = await page.evaluate(() => document.activeElement?.getAttribute("type") === "submit"); }
    log(lang, tool, "tabs to Run:", t2.join(" > "));
    await page.keyboard.press("Enter");
    await page.waitForSelector("#result-h, [role=alert]", { timeout: 60000 }).catch(() => {});
    await page.waitForTimeout(800);
    log(lang, tool, "focus after result:", await desc(), "| result in viewport:", await page.evaluate(() => { const r = document.getElementById("result-h")?.getBoundingClientRect(); return r ? `${Math.round(r.top)}..${Math.round(r.bottom)} of ${innerHeight}` : "none"; }));
    const t3 = [];
    for (let i = 0; i < 6; i++) { await page.keyboard.press("Tab"); t3.push(await desc()); }
    log(lang, tool, "next tabs:", t3.join(" > "));
    await shot(page, `OF_${lang}_${tool}`);
    await ctx.close();
  }
}
// Library: outputs saved?
{
  const { ctx, page } = await mk(b, {});
  await page.goto(BASE + "/"); await page.waitForLoadState("networkidle");
  const r = await page.request.get(BASE + "/api/v1/documents");
  log("library docs:", r.status(), (await r.text()).slice(0, 1500));
  await ctx.close();
}
await b.close();

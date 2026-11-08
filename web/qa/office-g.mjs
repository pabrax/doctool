import { launch, mk, open, addFile, run, download, shot, SRC, FX, BASE } from "./office-lib.mjs";
const b = await launch();
const log = (...a) => console.log(...a);
{
  const { ctx, page } = await mk(b, { lang: "es", w: 1280, h: 480 });
  await open(page, "pdf2excel");
  for (let i = 0; i < 31; i++) await page.keyboard.press("Tab");
  log("es focus:", await page.evaluate(() => document.activeElement.textContent.trim()));
  const [fc] = await Promise.all([page.waitForEvent("filechooser", { timeout: 8000 }).catch(() => null), page.keyboard.press("Enter")]);
  log("es pdf2excel chooser retry:", !!fc);
  await ctx.close();
}
{
  const r = await (await (await b.newContext()).request.get(BASE + "/api/v1/documents")).json();
  const m = {}; for (const d of r) { const k = `${d.latest_version.tool}:${d.latest_version.filename.split(".").pop()}`; m[k] = (m[k] || 0) + 1; }
  log("library by tool:ext", JSON.stringify(m));
}
for (const [lang, scheme, w] of [["es", "dark", 390], ["en", "dark", 390]]) {
  const { ctx, page } = await mk(b, { lang, scheme, w, h: 800 });
  await open(page, "excel2pdf"); await addFile(page, SRC("book.xlsx"));
  const r = await run(page); await shot(page, `OG_${lang}_${scheme}_${w}_excel_result`);
  log(lang, scheme, "excel result:", r.resultText.slice(0, 200));
  await ctx.close();
}
{ // password flow on pdf2word
  const { ctx, page } = await mk(b, { lang: "en", w: 1280, h: 900 });
  await open(page, "pdf2word"); await addFile(page, SRC("locked.pdf"));
  const r = await run(page); await shot(page, "OG_pdf2word_locked");
  log("locked fields:", await page.locator("main input[type=password]").count(), r.alerts);
  await page.locator("main input[type=password]").first().fill("wrong");
  const r2 = await run(page); log("locked wrong pw:", r2.outcome, r2.alerts);
  await ctx.close();
}
{ // Open in library navigates, docx not in library; pdf tool input "From library" for office tools?
  const { ctx, page } = await mk(b, {});
  for (const t of ["word2pdf", "html2pdf", "pdf2word"]) { await open(page, t); log(t, "From library button:", await page.getByRole("button", { name: /from library/i }).count()); }
  await ctx.close();
}
await b.close();

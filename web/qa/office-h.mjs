import { launch, mk, open, SRC } from "./office-lib.mjs";
const b = await launch();
for (const [tool, lang] of [["pdf2excel", "es"], ["pdf2excel", "es"], ["pdf2excel", "en"], ["pdf2excel", "en"], ["pdf2word", "en"], ["pdf2word", "en"], ["compress", "es"], ["compress", "es"]]) {
  const { ctx, page } = await mk(b, { lang, w: 1280, h: 480 });
  await open(page, tool);
  await page.waitForTimeout(1500);
  let ok = false;
  for (let i = 0; i < 40 && !ok; i++) { await page.keyboard.press("Tab"); ok = await page.evaluate(() => /^(select files|elegir archivos)/i.test(document.activeElement?.textContent?.trim() || "")); }
  const [fc] = await Promise.all([page.waitForEvent("filechooser", { timeout: 6000 }).catch(() => null), page.keyboard.press("Enter")]);
  console.log(tool, lang, "on button:", ok, "chooser:", !!fc);
  await ctx.close();
}
await b.close();

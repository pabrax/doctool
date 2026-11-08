import { launch, mk, open, addFile, run, shot, out, FX, SRC, BASE } from "./office-lib.mjs";
const b = await launch();
const log = (...a) => console.log(...a);
for (const lang of ["en", "es"]) {
  // 1 progress UI while pending
  const { ctx, page } = await mk(b, { lang, w: 390, h: 800 });
  await open(page, "word2pdf");
  await addFile(page, SRC("letter.docx"));
  await page.locator("button[type=submit]").click();
  for (const t of [300, 1500, 3000]) {
    await page.waitForTimeout(t === 300 ? 300 : 1200);
    const info = await page.evaluate(() => ({
      live: [...document.querySelectorAll("[aria-live],[role=status]")].map((e) => `${e.tagName}[role=${e.getAttribute("role")},live=${e.getAttribute("aria-live")}]:"${e.textContent.trim().slice(0, 120)}"`),
      progressText: (document.body.innerText.match(/(Converting your document|Convirtiendo tu documento|Still working|Sigue trabajando|Working|Trabajando)[^\n]*/g) || []),
      runBtn: document.querySelector("button[type=submit]")?.innerText,
      disabled: document.querySelector("button[type=submit]")?.disabled,
    }));
    log(lang, "pending@", t, JSON.stringify(info));
    if (t === 300) await shot(page, `OD_${lang}_pending_390`);
  }
  await page.waitForSelector("#result-h", { timeout: 30000 });
  log(lang, "after result focus:", await page.evaluate(() => `${document.activeElement.tagName}[${(document.activeElement.textContent || "").trim().slice(0, 20)}]`), "live regions:", await page.evaluate(() => [...document.querySelectorAll("[aria-live]")].map((e) => e.textContent.trim().slice(0, 80))));
  await shot(page, `OD_${lang}_result_390`);
  // second run (repeat submit) with result still shown
  const r2 = await run(page);
  log(lang, "second run:", r2.outcome, r2.ms, r2.alerts, "result:", (r2.resultText || "").slice(0, 120));
  await shot(page, `OD_${lang}_result2_390`);
  // New task
  const nt = page.getByRole("button", { name: /new task|nueva tarea/i });
  await nt.click(); await page.waitForTimeout(500);
  log(lang, "after New task focus:", await page.evaluate(() => `${document.activeElement.tagName}#${document.activeElement.id}`), "files left:", await page.locator("main").innerText().then((t) => /letter\.docx/.test(t)));
  log(lang, "console:", JSON.stringify(page.__log.filter((l) => !/ERR_ABORTED/.test(l))));
  await ctx.close();
}
// 2 double-click submit
{
  const { ctx, page } = await mk(b, {});
  await open(page, "word2pdf"); await addFile(page, SRC("letter.docx"));
  const btn = page.locator("button[type=submit]");
  await btn.dblclick();
  await page.waitForTimeout(8000);
  const posts = [];
  log("dblclick: result?", await page.locator("#result-h").count(), "alerts:", await page.locator("[role=alert]").allInnerTexts(), "log:", JSON.stringify(page.__log.filter((l) => !/ERR_ABORTED/.test(l))));
  await ctx.close();
}
// 3 busy: two clients at once
{
  const A = await mk(b, {}), B = await mk(b, {}), C = await mk(b, { lang: "es" });
  for (const p of [A.page, B.page, C.page]) { await open(p, "excel2pdf"); await addFile(p, SRC("book.xlsx")); }
  await Promise.all([A.page, B.page, C.page].map((p) => p.locator("button[type=submit]").click()));
  await A.page.waitForTimeout(9000);
  for (const [n, o] of [["A", A], ["B", B], ["C(es)", C]]) {
    log("busy", n, "result:", await o.page.locator("#result-h").count(), "alerts:", JSON.stringify(await o.page.locator("[role=alert]").allInnerTexts()), "btn:", await o.page.locator("button[type=submit]").innerText(), "log:", JSON.stringify(o.page.__log.filter((l) => !/ERR_ABORTED/.test(l))));
    await shot(o.page, `OD_busy_${n.replace(/\W/g, "")}`);
  }
}
await b.close();

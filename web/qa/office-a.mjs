import { launch, mk, open, addFile, run, download, shot, out, FX, SRC } from "./office-lib.mjs";
const b = await launch();
const R = [];
const sel = (page, i, v) => page.locator("main select").nth(i).selectOption(v);
const chk = (page, i) => page.locator("main input[type=checkbox]").nth(i).click();
const fill = (page, i, v) => page.locator("main input:not([type=checkbox]):not([type=file]):not([hidden])").nth(i).fill(v);
const T = [
  ["word2pdf", SRC("letter.docx"), [["default", async () => {}], ["a4", (p) => sel(p, 0, "a4")], ["letter", (p) => sel(p, 0, "letter")]]],
  ["word2pdf", FX("notes.txt"), [["txt", async () => {}]]],
  ["excel2pdf", SRC("book.xlsx"), [["default", async () => {}], ["sheets=1", (p) => fill(p, 0, "1")], ["sheets=Nope", (p) => fill(p, 0, "Nope")], ["landscape", (p) => sel(p, 0, "landscape")], ["portrait", (p) => sel(p, 0, "portrait")], ["fit_sheet", (p) => chk(p, 1)], ["fit_width off", (p) => chk(p, 0)]]],
  ["excel2pdf", FX("data.csv"), [["csv", async () => {}]]],
  ["ppt2pdf", SRC("deck.pptx"), [["default", async () => {}], ["h2", (p) => sel(p, 0, "h2")], ["h9", (p) => sel(p, 0, "h9")], ["notes", (p) => chk(p, 0)], ["hidden", (p) => chk(p, 1)]]],
  ["html2pdf", SRC("page.html"), [["default", async () => {}], ["letter", (p) => sel(p, 0, "letter")], ["landscape", (p) => sel(p, 1, "landscape")], ["no backgrounds", (p) => chk(p, 0)]]],
  ["html2pdf", FX("page-ext.html"), [["external refs", async () => {}]]],
  ["pdf2word", SRC("table.pdf"), [["default", async () => {}], ["keep_look", (p) => sel(p, 0, "keep_look")], ["no images", (p) => chk(p, 0)]]],
  ["pdf2excel", SRC("table.pdf"), [["default", async () => {}], ["one_sheet", (p) => sel(p, 0, "one_sheet")], ["pages=1", (p) => fill(p, 0, "1")], ["pages=99", (p) => fill(p, 0, "99")], ["pages=abc", (p) => fill(p, 0, "abc")]]],
  ["pdf2ppt", SRC("table.pdf"), [["default", async () => {}], ["picture_text", (p) => sel(p, 0, "picture_text")], ["dpi72", (p) => fill(p, 0, "72")], ["dpi300", (p) => fill(p, 0, "300")], ["dpi5000", (p) => fill(p, 0, "5000")]]],
];
for (const lang of ["en"]) {
  for (const [tool, file, variants] of T) {
    for (const [vn, fn] of variants) {
      const { ctx, page } = await mk(b, { lang });
      const rec = { lang, tool, file: file.split(/[\\/]/).pop(), variant: vn };
      try {
        await open(page, tool);
        rec.add = await addFile(page, file);
        await fn(page);
        rec.run = await run(page);
        if (rec.run.outcome === "result") rec.dl = await download(page, `${tool}-${vn.replace(/\W+/g, "_")}`);
        await shot(page, `OA_${lang}_${tool}_${vn.replace(/\W+/g, "_")}`);
      } catch (e) { rec.exception = String(e).slice(0, 300); }
      rec.log = page.__log;
      console.log(JSON.stringify(rec));
      R.push(rec);
      await ctx.close();
    }
  }
}
out("office-run-a.json", R);
await b.close();

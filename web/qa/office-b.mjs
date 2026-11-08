import { launch, mk, open, addFile, run, shot, out, FX, SRC } from "./office-lib.mjs";
const b = await launch();
const R = [];
const F = (n) => (n.includes("/") ? n : FX(n));
const T = {
  word2pdf: ["macro.docm", "fake.exe", "docx-as.rtf", "docx-as.txt", "empty.docx", "truncated.docx", "garbage.docx", "hidden-macro.docx", "bomb.docx", "cfb-as.docx", "wrong:table.pdf", "big.docx"],
  excel2pdf: ["macro.xlsm", "empty.xlsx", "wrong:letter.docx"],
  ppt2pdf: ["macro.pptm", "fake.exe", "wrong:letter.docx"],
  html2pdf: ["wrong:letter.docx", "macro.docm"],
  pdf2word: ["empty.pdf", "truncated.pdf", "garbage.pdf", "notext.pdf", "wrong:letter.docx", "SRC:locked.pdf"],
  pdf2excel: ["notext.pdf", "empty.pdf", "wrong:letter.docx", "SRC:locked.pdf"],
  pdf2ppt: ["empty.pdf", "notext.pdf", "wrong:letter.docx", "SRC:locked.pdf"],
};
const only = process.argv[2];
for (const lang of ["en", "es"]) {
  for (const [tool, files] of Object.entries(T)) {
    if (only && only !== tool) continue;
    for (let f of files) {
      let file;
      if (f.startsWith("wrong:")) file = SRC(f.slice(6)); else if (f.startsWith("SRC:")) file = SRC(f.slice(4)); else file = FX(f);
      if (f.startsWith("big") && lang === "es") continue;
      const { ctx, page } = await mk(b, { lang });
      const rec = { lang, tool, file: f };
      try {
        await open(page, tool);
        rec.add = await addFile(page, file);
        rec.listed = await page.locator("main").innerText().then((t) => /No files yet|Aún no hay|Todavía no/i.test(t) ? "empty-list" : "file-listed");
        rec.run = await run(page, { maxMs: 120000 });
        await shot(page, `OB_${lang}_${tool}_${f.replace(/\W+/g, "_")}`);
      } catch (e) { rec.exception = String(e).slice(0, 300); }
      rec.log = page.__log;
      console.log(JSON.stringify(rec));
      R.push(rec);
      await ctx.close();
    }
  }
}
out("office-run-b.json", R);
await b.close();

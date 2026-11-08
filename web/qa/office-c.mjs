import { launch, mk, open, addFile, shot, out, SRC, FX, BASE } from "./office-lib.mjs";
const b = await launch();
const R = [];
const TOOLS = ["word2pdf", "excel2pdf", "ppt2pdf", "html2pdf", "pdf2word", "pdf2excel", "pdf2ppt"];
const VP = [[390, 800], [768, 1024], [1280, 480]];
const probe = () => {
  const iw = innerWidth, o = {};
  o.overflowX = document.documentElement.scrollWidth > iw ? `${document.documentElement.scrollWidth}>${iw}` : null;
  const bad = [];
  document.querySelectorAll("main *").forEach((e) => {
    const r = e.getBoundingClientRect(); if (!r.width || !r.height) return;
    const cs = getComputedStyle(e); if (cs.visibility === "hidden" || cs.display === "none") return;
    if (r.right > iw + 1 || r.left < -1) bad.push(`${e.tagName}.${(e.className + "").slice(0, 30)}[${(e.textContent || "").trim().slice(0, 25)}] ${Math.round(r.left)}..${Math.round(r.right)}`);
  });
  o.outside = bad.slice(0, 5);
  const unnamed = [];
  document.querySelectorAll("button,a,input,select,textarea").forEach((e) => {
    if (e.type === "hidden" || e.hidden) return;
    const r = e.getBoundingClientRect(); if (!r.width && !r.height && e.type !== "file") return;
    const id = e.id; const lab = id && document.querySelector(`label[for="${CSS.escape(id)}"]`);
    const name = (e.getAttribute("aria-label") || e.getAttribute("aria-labelledby") || (lab && lab.textContent) || e.textContent || e.title || "").trim();
    if (!name && !(e.closest("label") && e.closest("label").textContent.trim())) unnamed.push(`${e.tagName}${e.type ? "[" + e.type + "]" : ""}#${id}`);
  });
  o.unnamed = unnamed;
  const small = [];
  document.querySelectorAll("main button, main a, main select, main input:not([type=file])").forEach((e) => { const r = e.getBoundingClientRect(); if (r.width && (r.height < 24 || r.width < 24)) small.push(`${e.tagName}[${(e.textContent || e.id).trim().slice(0, 20)}] ${Math.round(r.width)}x${Math.round(r.height)}`); });
  o.smallTargets = small.slice(0, 5);
  // contrast
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return { r: p[0], g: p[1], b: p[2], a: p[3] ?? 1 }; };
  const lum = ({ r, g, b }) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const bg = (e) => { let a = e; while (a) { const c = parse(getComputedStyle(a).backgroundColor); if (c && c.a > 0.9) return c; a = a.parentElement; } return { r: 255, g: 255, b: 255, a: 1 }; };
  const low = [];
  document.querySelectorAll("main *").forEach((e) => {
    if (![...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) return;
    const r = e.getBoundingClientRect(); if (!r.width || !r.height) return;
    const cs = getComputedStyle(e); if (cs.visibility === "hidden") return;
    const fg = parse(cs.color), bk = bg(e); if (!fg) return;
    const l1 = lum(fg), l2 = lum(bk); const cr = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    const fs = parseFloat(cs.fontSize), big = fs >= 24 || (fs >= 18.66 && +cs.fontWeight >= 700);
    if (cr < (big ? 3 : 4.5)) low.push(`${cr.toFixed(2)} ${cs.color} on ${bk.r},${bk.g},${bk.b} "${e.textContent.trim().slice(0, 30)}"`);
  });
  o.lowContrast = [...new Set(low)].slice(0, 6);
  o.note = !!document.querySelector("[role=note]");
  o.h1 = [...document.querySelectorAll("h1")].map((h) => h.textContent.trim());
  return o;
};
for (const lang of ["en", "es"]) for (const scheme of ["light", "dark"]) for (const [w, h] of VP) {
  const { ctx, page } = await mk(b, { w, h, lang, scheme });
  for (const tool of TOOLS) {
    const rec = { lang, scheme, vp: `${w}x${h}`, tool };
    try {
      await open(page, tool);
      rec.empty = await page.evaluate(probe);
      const f = tool.startsWith("pdf2") ? SRC("table.pdf") : tool === "word2pdf" ? SRC("letter.docx") : tool === "excel2pdf" ? SRC("book.xlsx") : tool === "ppt2pdf" ? SRC("deck.pptx") : SRC("page.html");
      await addFile(page, f);
      rec.withFile = await page.evaluate(probe);
      if (lang === "en" && scheme === "light" || w === 390) await shot(page, `OC_${lang}_${scheme}_${w}_${tool}`);
    } catch (e) { rec.exception = String(e).slice(0, 200); }
    rec.log = page.__log.splice(0);
    R.push(rec);
  }
  await ctx.close();
}
out("office-run-c.json", R);
const flag = R.filter((r) => r.exception || r.log.length || ["empty", "withFile"].some((k) => r[k] && (r[k].overflowX || r[k].outside.length || r[k].unnamed.length || r[k].lowContrast.length)));
console.log(R.length, "records;", flag.length, "flagged");
for (const r of flag) console.log(JSON.stringify(r).slice(0, 600));
await b.close();

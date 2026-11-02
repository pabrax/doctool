// QA audit script. Run from web/:  node qa/audit.mjs [fixtures|layout|flows|kbd|all]
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

const BASE = "http://127.0.0.1:5173";
const QA = path.resolve(import.meta.dirname, "..", "..", "qa");
const FIX = path.join(QA, "fixtures");
const SHOTS = path.join(QA, "shots");
fs.mkdirSync(FIX, { recursive: true });
fs.mkdirSync(SHOTS, { recursive: true });
const out = { layout: [], flows: [], kbd: [] };
const what = process.argv[2] ?? "all";
const TOOLS = ["imageconvert", "imagecompress", "imageresize", "imagecrop", "imageclean"];
const VPS = [
  { n: "phone", width: 390, height: 800 },
  { n: "tablet", width: 768, height: 1024 },
  { n: "short", width: 1280, height: 480 },
];

const browser = await chromium.launch({ channel: "msedge" });

// ---------- fixtures ----------
async function makeFixtures() {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto("about:blank");
  const files = await page.evaluate(async () => {
    const mk = (w, h, draw) => {
      const c = document.createElement("canvas");
      c.width = w; c.height = h;
      const g = c.getContext("2d");
      draw(g, w, h);
      return c;
    };
    const toB64 = (c, type, q) =>
      new Promise((res) => c.toBlob((b) => { const r = new FileReader(); r.onload = () => res(String(r.result).split(",")[1]); r.readAsDataURL(b); }, type, q));
    const noisy = (g, w, h) => {
      const id = g.createImageData(w, h);
      for (let i = 0; i < id.data.length; i += 4) {
        const x = (i / 4) % w, y = Math.floor(i / 4 / w);
        id.data[i] = (x * 255) / w + Math.random() * 60;
        id.data[i + 1] = (y * 255) / h + Math.random() * 60;
        id.data[i + 2] = 128 + Math.random() * 100;
        id.data[i + 3] = 255;
      }
      g.putImageData(id, 0, 0);
    };
    const photo = mk(1600, 1200, noisy);
    const alpha = mk(400, 300, (g) => { g.clearRect(0, 0, 400, 300); g.fillStyle = "rgba(200,30,30,0.7)"; g.beginPath(); g.arc(200, 150, 100, 0, 7); g.fill(); });
    const small = mk(48, 48, (g) => { g.fillStyle = "#336"; g.fillRect(0, 0, 48, 48); });
    return {
      "photo.jpg": await toB64(photo, "image/jpeg", 0.92),
      "alpha.png": await toB64(alpha, "image/png"),
      "pic.webp": await toB64(photo, "image/webp", 0.8),
      "tiny.jpg": await toB64(small, "image/jpeg", 0.3),
      "tiny.png": await toB64(small, "image/png"),
    };
  });
  for (const [n, b] of Object.entries(files)) fs.writeFileSync(path.join(FIX, n), Buffer.from(b, "base64"));
  const photo = fs.readFileSync(path.join(FIX, "photo.jpg"));
  fs.writeFileSync(path.join(FIX, "truncated.jpg"), photo.subarray(0, Math.floor(photo.length / 3)));
  fs.writeFileSync(path.join(FIX, "fake.jpg"), "this is just text, not an image\n");
  fs.writeFileSync(path.join(FIX, "empty.jpg"), "");
  fs.writeFileSync(path.join(FIX, "wrongtype.pdf"), "%PDF-1.4 hello");
  // animated GIF (2 frames, 2x2)
  const gif = Buffer.from(
    "R0lGODlhAgACAPAAAP8AAAAAACH/C05FVFNDQVBFMi4wAwEAAAAh+QQJCgAAACwAAAAAAgACAAACAoRRACH5BAkKAAAALAAAAAACAAIAAAIChFEAOw==",
    "base64",
  );
  fs.writeFileSync(path.join(FIX, "anim.gif"), gif);
  // huge-dimension PNG (1-bit gray 20000x20000, small on disk, 400 Mpx)
  const W = 20000, H = 20000, rowLen = 1 + Math.ceil(W / 8);
  const deflate = zlib.createDeflate({ level: 9 });
  const chunks = [];
  deflate.on("data", (d) => chunks.push(d));
  const row = Buffer.alloc(rowLen);
  for (let y = 0; y < H; y++) deflate.write(row);
  deflate.end();
  await new Promise((r) => deflate.on("end", r));
  const crcT = (() => { const t = []; for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  const crc = (b) => { let c = 0xffffffff; for (const x of b) c = crcT[(c ^ x) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  const chunk = (type, data) => { const len = Buffer.alloc(4); len.writeUInt32BE(data.length); const td = Buffer.concat([Buffer.from(type), data]); const cr = Buffer.alloc(4); cr.writeUInt32BE(crc(td)); return Buffer.concat([len, td, cr]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(W, 0); ihdr.writeUInt32BE(H, 4); ihdr[8] = 1; ihdr[9] = 0;
  fs.writeFileSync(path.join(FIX, "hugepx.png"), Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", ihdr), chunk("IDAT", Buffer.concat(chunks)), chunk("IEND", Buffer.alloc(0))]));
  // 201 MB oversized upload (zeros, png header name)
  const big = Buffer.alloc(201 * 1024 * 1024);
  Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]).copy(big);
  fs.writeFileSync(path.join(FIX, "oversize.png"), big);
  await ctx.close();
  console.log("fixtures:", fs.readdirSync(FIX).map((f) => `${f}=${fs.statSync(path.join(FIX, f)).size}`).join(", "));
}

// ---------- helpers ----------
async function newPage({ vp = VPS[2], scheme = "light", lang = "en", acceptDownloads = true } = {}) {
  const ctx = await browser.newContext({
    viewport: { width: vp.width, height: vp.height },
    colorScheme: scheme,
    locale: lang === "es" ? "es-ES" : "en-US",
    acceptDownloads,
  });
  await ctx.addInitScript((l) => { try { localStorage.setItem("doctool.lang", l); } catch {} }, lang);
  const page = await ctx.newPage();
  const log = { console: [], net: [], pageerr: [] };
  page.on("console", (m) => { if (["error", "warning"].includes(m.type())) log.console.push(`${m.type()}: ${m.text()}`.slice(0, 300)); });
  page.on("pageerror", (e) => log.pageerr.push(String(e).slice(0, 300)));
  page.on("response", (r) => { if (r.status() >= 400) log.net.push(`${r.status()} ${r.request().method()} ${r.url()}`); });
  page.on("requestfailed", (r) => log.net.push(`FAILED ${r.method()} ${r.url()} ${r.failure()?.errorText}`));
  return { ctx, page, log };
}

const CHECK = () => {
  const res = { overflow: null, outside: [], unnamed: [], lowContrast: [] };
  const de = document.documentElement;
  if (de.scrollWidth > window.innerWidth) res.overflow = `scrollWidth ${de.scrollWidth} > innerWidth ${window.innerWidth}`;
  const vis = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none"; };
  const desc = (el) => `${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}[${(el.textContent || el.getAttribute("aria-label") || "").trim().slice(0, 30)}]`;
  for (const el of document.querySelectorAll("body *")) {
    if (!vis(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.right > window.innerWidth + 1 || r.left < -1) {
      // ignore if inside an overflow container that scrolls
      let p = el.parentElement, scroll = false;
      while (p) { const o = getComputedStyle(p).overflowX; if (["auto", "scroll", "hidden"].includes(o) && p.scrollWidth > p.clientWidth) { scroll = true; break; } p = p.parentElement; }
      if (!scroll && res.outside.length < 8) res.outside.push(`${desc(el)} l=${Math.round(r.left)} r=${Math.round(r.right)}`);
    }
  }
  const name = (el) => {
    if (el.getAttribute("aria-label")) return true;
    if (el.getAttribute("aria-labelledby")) return true;
    if ((el.textContent || "").trim()) return true;
    if (el.title) return true;
    if (el.labels && el.labels.length) return true;
    return false;
  };
  for (const el of document.querySelectorAll("button, a[href], input:not([type=hidden]), select, textarea")) {
    if (el.closest("[hidden]") || (el.hidden)) continue;
    if (!name(el)) res.unnamed.push(desc(el) + " " + el.outerHTML.slice(0, 80));
  }
  const cv = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  const rgba = (c) => { cv.clearRect(0, 0, 1, 1); cv.fillStyle = "#000"; cv.fillStyle = c; cv.fillRect(0, 0, 1, 1); const d = cv.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255]; };
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const bgOf = (el) => {
    let layers = [];
    for (let p = el; p; p = p.parentElement) { const c = rgba(getComputedStyle(p).backgroundColor); if (c[3] > 0) layers.push(c); if (c[3] >= 1) break; }
    let base = [255, 255, 255];
    if (!layers.length || layers[layers.length - 1][3] < 1) base = rgba(getComputedStyle(document.body).backgroundColor).slice(0, 3);
    for (const c of layers.reverse()) base = base.map((v, i) => c[i] * c[3] + v * (1 - c[3]));
    return base;
  };
  const seen = new Set();
  for (const el of document.querySelectorAll("body *")) {
    if (!vis(el)) continue;
    const own = [...el.childNodes].filter((n) => n.nodeType === 3 && n.textContent.trim()).map((n) => n.textContent.trim()).join(" ");
    if (!own) continue;
    const s = getComputedStyle(el);
    const fg = rgba(s.color); const bg = bgOf(el);
    const fgm = fg.slice(0, 3).map((v, i) => v * fg[3] + bg[i] * (1 - fg[3]));
    const L1 = lum(fgm), L2 = lum(bg);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const px = parseFloat(s.fontSize), bold = parseInt(s.fontWeight) >= 700;
    const need = px >= 24 || (px >= 18.66 && bold) ? 3 : 4.5;
    const disabled = el.closest("button:disabled,[disabled]");
    if (ratio < need && !disabled && !seen.has(own) && res.lowContrast.length < 8) { seen.add(own); res.lowContrast.push(`${ratio.toFixed(2)}<${need} "${own.slice(0, 40)}"`); }
  }
  return res;
};

async function waitSettled(page) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(300);
}

// ---------- layout ----------
async function layout() {
  for (const vp of VPS)
    for (const scheme of ["light", "dark"])
      for (const lang of ["en", "es"]) {
        const { ctx, page, log } = await newPage({ vp, scheme, lang });
        const pages = [["home", "/"], ...TOOLS.map((t) => [t, `/tools/${t}`])];
        for (const [name, url] of pages) {
          log.console.length = log.net.length = log.pageerr.length = 0;
          await page.goto(BASE + url);
          await waitSettled(page);
          const r = await page.evaluate(CHECK);
          const tag = `${name}_${vp.n}_${scheme}_${lang}`;
          await page.screenshot({ path: path.join(SHOTS, `L_${tag}.png`), fullPage: true });
          out.layout.push({ tag, ...r, console: [...log.console], net: [...log.net], pageerr: [...log.pageerr] });
        }
        // palette + sidebar (open via Ctrl+K)
        log.console.length = log.net.length = 0;
        await page.goto(BASE + "/");
        await waitSettled(page);
        await page.keyboard.press("Control+k");
        await page.waitForTimeout(500);
        const tag = `palette_${vp.n}_${scheme}_${lang}`;
        const r = await page.evaluate(CHECK);
        const items = await page.locator("[cmdk-item]").count();
        await page.screenshot({ path: path.join(SHOTS, `L_${tag}.png`) });
        out.layout.push({ tag, items, ...r, console: [...log.console], net: [...log.net], pageerr: [] });
        await ctx.close();
      }
}

// ---------- flows ----------
const fx = (n) => path.join(FIX, n);
async function openTool(page, id) {
  await page.goto(`${BASE}/tools/${id}`);
  await waitSettled(page);
}
async function runOnce(page, { files, setup, tag, expectDownload = true }) {
  const rec = { tag, files: files.map((f) => path.basename(f)) };
  await page.setInputFiles('[data-testid="file-input"]', files);
  await page.waitForTimeout(300);
  rec.dropRejected = (await page.locator('p[role="alert"]').allTextContents()).join(" | ");
  if (setup) await setup(page);
  const run = page.locator('form button[type="submit"]');
  rec.runDisabled = await run.isDisabled();
  if (rec.runDisabled) { await page.screenshot({ path: path.join(SHOTS, `F_${tag}.png`), fullPage: true }); return rec; }
  await run.click();
  const t0 = Date.now();
  await page.waitForSelector('#result-h, [role="alert"]:not(p)', { timeout: 60000 }).catch(() => (rec.timeout = true));
  await page.waitForTimeout(1200);
  rec.ms = Date.now() - t0;
  rec.alert = (await page.locator('div[role="alert"]').allTextContents()).join(" | ");
  if (await page.locator("#result-h").count()) {
    const sec = page.locator('section[aria-labelledby="result-h"]');
    rec.result = (await sec.innerText()).replace(/\s+/g, " ").slice(0, 400);
    rec.focus = await page.evaluate(() => { const a = document.activeElement; return a ? `${a.tagName}[${(a.textContent || "").trim().slice(0, 20)}]` : null; });
    if (expectDownload) {
      try {
        const [dl] = await Promise.all([page.waitForEvent("download", { timeout: 15000 }), sec.locator("a").first().click()]);
        const p = path.join(SHOTS, "dl_" + dl.suggestedFilename());
        await dl.saveAs(p);
        rec.download = `${dl.suggestedFilename()} ${fs.statSync(p).size}B`;
        const b = fs.readFileSync(p);
        rec.magic = b.subarray(0, 12).toString("latin1").replace(/[^\x20-\x7e]/g, ".");
        rec.dlPath = p;
      } catch (e) { rec.downloadErr = String(e).slice(0, 150); }
    }
  }
  await page.screenshot({ path: path.join(SHOTS, `F_${tag}.png`), fullPage: true });
  return rec;
}
const fill = (label, v) => async (page) => { await page.getByLabel(label, { exact: false }).first().fill(String(v)); };

async function flows() {
  for (const lang of ["en", "es"]) {
    const { ctx, page, log } = await newPage({ vp: VPS[0], lang });
    const R = async (id, opts) => {
      await openTool(page, id);
      log.console.length = log.net.length = 0;
      const rec = await runOnce(page, { ...opts, tag: `${lang}_${id}_${opts.tag}` });
      rec.console = [...log.console]; rec.net = [...log.net];
      out.flows.push(rec);
      console.log(rec.tag, "->", rec.alert || rec.result || rec.dropRejected || "?", "|", rec.download ?? "");
    };
    const sel = (lbl, val) => async (p) => { await p.getByLabel(lbl).first().selectOption(val); };
    // convert
    await R("imageconvert", { tag: "jpg2png", files: [fx("photo.jpg")], setup: sel(/Convert|Convertir|Format/i, "png") });
    await R("imageconvert", { tag: "png2jpg", files: [fx("alpha.png")], setup: sel(/Convert|Convertir|Format/i, "jpg") });
    await R("imageconvert", { tag: "webp2png", files: [fx("pic.webp")], setup: sel(/Convert|Convertir|Format/i, "png") });
    await R("imageconvert", { tag: "jpg2webp", files: [fx("photo.jpg")], setup: sel(/Convert|Convertir|Format/i, "webp") });
    await R("imageconvert", { tag: "default", files: [fx("photo.jpg")] });
    await R("imageconvert", { tag: "multi", files: [fx("photo.jpg"), fx("alpha.png")], setup: sel(/Convert|Convertir|Format/i, "webp") });
    // compress
    await R("imagecompress", { tag: "photo", files: [fx("photo.jpg")] });
    await R("imagecompress", { tag: "tiny", files: [fx("tiny.jpg")] });
    await R("imagecompress", { tag: "tinypng", files: [fx("tiny.png")] });
    await R("imagecompress", { tag: "alpha", files: [fx("alpha.png")] });
    await R("imagecompress", { tag: "webp", files: [fx("pic.webp")] });
    // resize
    await R("imageresize", { tag: "fitbox", files: [fx("photo.jpg")], setup: fill(/Width|Ancho/i, 800) });
    await R("imageresize", { tag: "exact_nohgt", files: [fx("photo.jpg")], setup: sel(/Mode|Modo/i, "exact") });
    await R("imageresize", { tag: "exact", files: [fx("photo.jpg")], setup: async (p) => { await sel(/Mode|Modo/i, "exact")(p); await fill(/Width|Ancho/i, 300)(p); await fill(/Height|Alto/i, 300)(p); } });
    await R("imageresize", { tag: "percent", files: [fx("alpha.png")], setup: async (p) => { await sel(/Mode|Modo/i, "percent")(p); await fill(/Percent|Porcentaje/i, 25)(p); } });
    await R("imageresize", { tag: "upscale", files: [fx("tiny.png")], setup: fill(/Width|Ancho/i, 1000) });
    // crop
    await R("imagecrop", { tag: "ratio", files: [fx("photo.jpg")] });
    await R("imagecrop", { tag: "box", files: [fx("alpha.png")], setup: async (p) => { await sel(/Mode|Modo/i, "box")(p); await fill(/^Width|^Ancho/i, 100)(p); await fill(/^Height|^Alto/i, 100)(p); } });
    await R("imagecrop", { tag: "box_outside", files: [fx("alpha.png")], setup: async (p) => { await sel(/Mode|Modo/i, "box")(p); await fill(/^X|^Left|^Izq/i, 5000)(p); await fill(/^Width|^Ancho/i, 100)(p); await fill(/^Height|^Alto/i, 100)(p); } });
    await R("imagecrop", { tag: "box_toobig", files: [fx("alpha.png")], setup: async (p) => { await sel(/Mode|Modo/i, "box")(p); await fill(/^Width|^Ancho/i, 9000)(p); await fill(/^Height|^Alto/i, 9000)(p); } });
    await R("imagecrop", { tag: "box_nosize", files: [fx("alpha.png")], setup: sel(/Mode|Modo/i, "box") });
    // clean
    await R("imageclean", { tag: "photo", files: [fx("photo.jpg")] });
    await R("imageclean", { tag: "png", files: [fx("alpha.png")] });
    // invalid inputs on each tool
    for (const id of TOOLS) {
      for (const bad of ["fake.jpg", "empty.jpg", "truncated.jpg", "anim.gif", "hugepx.png", "wrongtype.pdf"]) {
        await R(id, { tag: "bad_" + bad.replace(".", "_"), files: [fx(bad)], setup: id === "imagecrop" || id === "imageresize" ? undefined : undefined });
      }
    }
    // oversize (once per lang, convert only)
    await R("imageconvert", { tag: "oversize", files: [fx("oversize.png")] });
    // repeated submit: double-click run
    await openTool(page, "imageconvert");
    await page.setInputFiles('[data-testid="file-input"]', [fx("photo.jpg")]);
    const reqs = [];
    page.on("request", (r) => { if (r.method() === "POST") reqs.push(r.url()); });
    const run = page.locator('form button[type="submit"]');
    await run.dblclick();
    await page.waitForSelector("#result-h, div[role=alert]", { timeout: 60000 }).catch(() => {});
    await page.waitForTimeout(800);
    out.flows.push({ tag: `${lang}_repeat_dblclick`, posts: reqs.join(" ; ") });
    // second run on same page
    const before = reqs.length;
    if (await run.isEnabled()) { await run.click(); await page.waitForTimeout(3000); }
    out.flows.push({ tag: `${lang}_repeat_second_run`, newPosts: reqs.length - before, result: (await page.locator('section[aria-labelledby="result-h"]').allInnerTexts()).join("|").replace(/\s+/g, " ") });
    await ctx.close();
  }
}

// ---------- keyboard ----------
async function kbd() {
  for (const lang of ["en", "es"]) {
    const { ctx, page, log } = await newPage({ vp: VPS[2], lang });
    await openTool(page, "imagecompress");
    const seq = [];
    const desc = () => page.evaluate(() => { const a = document.activeElement; if (!a) return "none"; const cs = getComputedStyle(a); return `${a.tagName.toLowerCase()}[${(a.getAttribute("aria-label") || a.textContent || a.id || "").trim().slice(0, 24)}] outline=${cs.outlineStyle}/${cs.outlineWidth} shadow=${cs.boxShadow !== "none"}`; });
    for (let i = 0; i < 12; i++) { await page.keyboard.press("Tab"); seq.push(await desc()); }
    out.kbd.push({ lang, tabOrderBeforeFile: seq });
    // keyboard only: focus Select files button, Enter -> file chooser
    await page.goto(BASE + "/tools/imagecompress"); await waitSettled(page);
    let found = false;
    for (let i = 0; i < 25 && !found; i++) { await page.keyboard.press("Tab"); found = await page.evaluate(() => /select|elegir|seleccion/i.test(document.activeElement?.textContent || "")); }
    const [fc] = await Promise.all([page.waitForEvent("filechooser", { timeout: 5000 }).catch(() => null), page.keyboard.press("Enter")]);
    const rec = { lang, foundSelect: found, chooser: !!fc };
    if (fc) {
      await fc.setFiles(fx("photo.jpg"));
      await page.waitForTimeout(500);
      let onRun = false;
      const trail = [];
      for (let i = 0; i < 25 && !onRun; i++) { await page.keyboard.press("Tab"); trail.push(await desc()); onRun = await page.evaluate(() => document.activeElement?.getAttribute("type") === "submit"); }
      rec.trail = trail; rec.reachedRun = onRun;
      if (onRun) {
        await page.keyboard.press("Enter");
        await page.waitForSelector("#result-h, div[role=alert]", { timeout: 60000 }).catch(() => {});
        await page.waitForTimeout(800);
        rec.afterFocus = await desc();
        rec.result = (await page.locator('section[aria-labelledby="result-h"]').allInnerTexts()).join("|").replace(/\s+/g, " ");
        await page.screenshot({ path: path.join(SHOTS, `K_${lang}.png`), fullPage: true });
      }
    }
    out.kbd.push(rec);
    // Number inputs on phone: attributes
    await ctx.close();
  }
  // number input attrs + show_when + hints on phone
  for (const lang of ["en", "es"]) {
    const { ctx, page } = await newPage({ vp: VPS[0], lang });
    for (const id of ["imageconvert", "imageresize", "imagecrop"]) {
      await openTool(page, id);
      const modes = id === "imageconvert" ? [null] : id === "imageresize" ? ["fit_box", "exact", "percent"] : ["ratio", "box"];
      for (const m of modes) {
        if (m) await page.locator("select").first().selectOption(m);
        if (id === "imageconvert") await page.locator("select").first().selectOption("jpg");
        await page.waitForTimeout(200);
        const info = await page.evaluate(() => [...document.querySelectorAll("aside form label, aside form p")].map((e) => e.textContent.trim().replace(/\s+/g, " ").slice(0, 110)).join(" || "));
        const inputs = await page.evaluate(() => [...document.querySelectorAll("aside input")].map((i) => `${i.type}:${i.inputMode || "-"}:h=${Math.round(i.getBoundingClientRect().height)}:w=${Math.round(i.getBoundingClientRect().width)}:${i.min || ""}-${i.max || ""}`).join(", "));
        out.kbd.push({ lang, id, mode: m, info, inputs });
        await page.screenshot({ path: path.join(SHOTS, `M_${lang}_${id}_${m ?? "x"}.png`), fullPage: true });
      }
      if (id === "imageconvert") {
        await page.locator("select").first().selectOption("png");
        out.kbd.push({ lang, id, mode: "png", info: await page.evaluate(() => [...document.querySelectorAll("aside form label")].map((e) => e.textContent.trim().slice(0, 60)).join(" || ")) });
      }
    }
    await ctx.close();
  }
}

if (what === "fixtures" || what === "all") await makeFixtures();
if (what === "layout" || what === "all") await layout();
if (what === "flows" || what === "all") await flows();
if (what === "kbd" || what === "all") await kbd();
fs.writeFileSync(path.join(QA, `audit-${what}.json`), JSON.stringify(out, null, 1));
await browser.close();
console.log("done", what);

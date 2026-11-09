// Re-audit 2: verify fixes + dark/tablet runs, EXIF, batch with invalid, keyboard.
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
const BASE = "http://127.0.0.1:5173";
const QA = path.resolve(import.meta.dirname, "..", "..", "qa");
const fx = (n) => path.join(QA, "fixtures", n);
const out = path.join(QA, "dl3"); fs.mkdirSync(out, { recursive: true });
// EXIF fixture: insert APP1 Exif with Orientation=6 after SOI of photo.jpg
const src = fs.readFileSync(fx("photo.jpg"));
const tiff = Buffer.from([0x4d,0x4d,0,0x2a,0,0,0,8, 0,1, 0x01,0x12,0,3,0,0,0,1,0,6,0,0, 0,0,0,0]);
const body = Buffer.concat([Buffer.from("Exif\0\0"), tiff]);
const app1 = Buffer.concat([Buffer.from([0xff,0xe1,(body.length+2)>>8,(body.length+2)&255]), body]);
const exifJpg = path.join(out, "exif6.jpg");
fs.writeFileSync(exifJpg, Buffer.concat([src.subarray(0,2), app1, src.subarray(2)]));
const dims = (buf) => { // JPEG / PNG / WEBP-lite
  if (buf[0]===0x89) return [buf.readUInt32BE(16), buf.readUInt32BE(20)];
  if (buf[0]===0xff) { let i=2; while(i<buf.length){ if(buf[i]!==0xff){i++;continue;} const m=buf[i+1]; const l=buf.readUInt16BE(i+2); if(m>=0xc0&&m<=0xcf&&m!==0xc4&&m!==0xc8&&m!==0xcc) return [buf.readUInt16BE(i+7), buf.readUInt16BE(i+5)]; i+=2+l; } }
  return ["?","?"];
};
console.log("photo dims", dims(src));
const b = await chromium.launch({ channel: "msedge" });
const mk = async (w, h, lang, scheme = "light") => {
  const ctx = await b.newContext({ viewport: { width: w, height: h }, locale: lang === "es" ? "es-ES" : "en-US", colorScheme: scheme, acceptDownloads: true });
  await ctx.addInitScript((l) => localStorage.setItem("doctool.lang", l), lang);
  const page = await ctx.newPage();
  page.cons = []; page.net = []; page.posts = [];
  page.on("console", (m) => { if (["error","warning"].includes(m.type())) page.cons.push(m.text().slice(0,160)); });
  page.on("response", (r) => { if (r.status() >= 400) page.net.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`); });
  page.on("request", (r) => { if (r.method()==="POST" && r.url().includes("/api/v1/tasks")) page.posts.push(r.url().replace(/^.*\/api\//, "")); });
  return { ctx, page };
};
const log = (...a) => console.log(...a);
async function run(page, tool, files, { setup, dbl, key, shot } = {}) {
  await page.goto(`${BASE}/tools/${tool}`); await page.waitForLoadState("networkidle");
  page.posts.length = 0;
  await page.setInputFiles('[data-testid="file-input"]', files); await page.waitForTimeout(400);
  if (setup) await setup(page);
  const btn = page.locator('form button[type="submit"]');
  if (dbl) await btn.dblclick(); else await btn.click();
  await page.waitForSelector("#result-h, div[role=alert]", { timeout: 120000 }).catch(() => {});
  await page.waitForTimeout(700);
  const alert = (await page.locator("div[role=alert]").allTextContents()).join("|");
  const result = (await page.locator('section[aria-labelledby="result-h"]').allInnerTexts()).join("|").replace(/\s+/g, " ");
  let dl = null;
  const a = page.locator('section[aria-labelledby="result-h"] a').first();
  if (await a.count()) { const [d] = await Promise.all([page.waitForEvent("download"), a.click()]); const p = path.join(out, `${Date.now()}_${d.suggestedFilename()}`); await d.saveAs(p); dl = { p, name: d.suggestedFilename(), size: fs.statSync(p).size }; }
  if (shot) await page.screenshot({ path: path.join(QA, "shots", `R2_${shot}.png`), fullPage: true });
  return { alert, result, dl, posts: page.posts.join(",") };
}
const sel = (v) => async (p) => p.locator("aside form select").first().selectOption(v);

// A. IMG-01/02/03/07 en+es at phone
for (const lang of ["en","es"]) {
  const { ctx, page } = await mk(390, 800, lang);
  let r = await run(page, "imageconvert", fx("photo.jpg"), { shot: `${lang}_convert_default` });
  log(lang, "IMG01 default convert:", JSON.stringify(r), r.dl && dims(fs.readFileSync(r.dl.p)), r.dl && fs.readFileSync(r.dl.p).subarray(0,3).toString("hex"));
  r = await run(page, "imageconvert", fx("photo.jpg"), { setup: sel("png"), shot: `${lang}_convert_png` });
  log(lang, "IMG02 jpg->png:", JSON.stringify(r));
  r = await run(page, "imagecompress", fx("photo.jpg"), { shot: `${lang}_compress` });
  log(lang, "IMG02 compress photo:", JSON.stringify(r));
  r = await run(page, "imagecompress", fx("tiny.jpg"), { shot: `${lang}_compress_tiny` });
  log(lang, "IMG02 compress tiny:", JSON.stringify(r));
  r = await run(page, "imageresize", fx("photo.jpg"), { shot: `${lang}_resize` });
  log(lang, "IMG02 resize:", JSON.stringify(r), r.dl && dims(fs.readFileSync(r.dl.p)));
  r = await run(page, "imagecompress", [fx("photo.jpg"), fx("tiny.jpg")], { shot: `${lang}_compress_multi` });
  log(lang, "IMG02 multi:", JSON.stringify(r));
  r = await run(page, "imagecompress", [fx("photo.jpg"), fx("fake.jpg")], { shot: `${lang}_batch_invalid` });
  log(lang, "BATCH valid+invalid:", JSON.stringify(r));
  for (const bad of ["fake.jpg","empty.jpg","hugepx.png","truncated.jpg","anim.gif","oversize.png"]) {
    r = await run(page, "imageconvert", fx(bad), { shot: `${lang}_bad_${bad}` });
    log(lang, "IMG03", bad, "alert=", r.alert, "result=", r.result.slice(0,60));
  }
  r = await run(page, "imageconvert", fx("photo.jpg"), { dbl: true });
  log(lang, "IMG07 dbl click POSTs:", r.posts);
  // IMG-04
  r = await run(page, "imagecrop", fx("photo.jpg"), { setup: async (p) => { await p.locator("aside form select").first().selectOption("box"); }, shot: `${lang}_crop_nobox` });
  log(lang, "IMG04 crop box empty:", JSON.stringify(r));
  // IMG-05/06 form dumps
  for (const [id, modes] of [["imageresize",["fit_box","exact","percent"]],["imagecrop",["ratio","box"]],["imageconvert",["jpg","png","webp"]]]) {
    await page.goto(`${BASE}/tools/${id}`); await page.waitForLoadState("networkidle");
    await page.setInputFiles('[data-testid="file-input"]', fx("photo.jpg"));
    for (const m of modes) { await page.locator("aside form select").first().selectOption(m); await page.waitForTimeout(150);
      log(lang, "IMG05/06", id, m, "=>", await page.evaluate(() => document.querySelector("aside form").innerText.replace(/\s+/g, " ").slice(0, 400))); }
  }
  // IMG-09
  await page.goto(`${BASE}/tools/imagecompress`); await page.waitForLoadState("networkidle");
  log(lang, "IMG09 dropzone:", await page.evaluate(() => document.querySelector('[data-testid="file-input"]').closest("div").parentElement.innerText.replace(/\s+/g," ").slice(0,250)));
  log(lang, "console", page.cons, "net", page.net);
  await ctx.close();
}
// B. IMG-11 sidebar at 1280x480
{ const { ctx, page } = await mk(1280, 480, "en");
  await page.goto(`${BASE}/tools/imageconvert`); await page.waitForLoadState("networkidle"); await page.waitForTimeout(500);
  log("IMG11", await page.evaluate(() => { const a = document.querySelector('nav a[aria-current="page"], aside a[aria-current="page"]'); if (!a) return "no active"; const r = a.getBoundingClientRect(); return `active "${a.innerText.trim()}" top=${Math.round(r.top)} bottom=${Math.round(r.bottom)} vh=${innerHeight}`; }));
  await page.screenshot({ path: path.join(QA, "shots", "R2_sidebar.png") }); await ctx.close(); }
// C. Dark tablet functional, 5 tools + EXIF
{ const { ctx, page } = await mk(768, 1024, "en", "dark");
  for (const t of ["imageclean","imagecompress","imageresize","imagecrop","imageconvert"]) {
    const r = await run(page, t, t==="imageclean" ? exifJpg : fx("photo.jpg"), { setup: t==="imagecrop" ? async (p)=>{ await p.locator("aside form select").first().selectOption("ratio"); } : undefined, shot: `dark_${t}` });
    log("DARK768", t, JSON.stringify(r), r.dl && dims(fs.readFileSync(r.dl.p)));
    const ov = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth); log("  overflow", ov);
  }
  // EXIF
  let r = await run(page, "imageclean", exifJpg, {});
  let buf = fs.readFileSync(r.dl.p); log("EXIF clean result dims", dims(buf), "hasExif", buf.includes(Buffer.from("Exif\0\0")), "input hasExif", fs.readFileSync(exifJpg).includes(Buffer.from("Exif\0\0")), "name", r.dl.name);
  for (const t of ["imagecompress","imageresize","imageconvert"]) { r = await run(page, t, exifJpg, {}); buf = fs.readFileSync(r.dl.p); log("EXIF via", t, r.dl.name, dims(buf), "hasExif", buf.includes(Buffer.from("Exif\0\0"))); }
  log("dark console", page.cons, "net", page.net); await ctx.close(); }
// D. Keyboard imageconvert
for (const lang of ["en","es"]) {
  const { ctx, page } = await mk(768, 1024, lang);
  await page.goto(`${BASE}/tools/imageconvert`); await page.waitForLoadState("networkidle");
  const desc = () => page.evaluate(() => { const a = document.activeElement; const cs = getComputedStyle(a); return `${a.tagName.toLowerCase()}[${(a.getAttribute("aria-label") || a.textContent || a.id || "").trim().slice(0, 22)}] ol=${cs.outlineStyle}/${cs.outlineWidth} sh=${cs.boxShadow !== "none"}`; });
  const tr = []; let hit = false;
  for (let i=0;i<30&&!hit;i++){ await page.keyboard.press("Tab"); tr.push(await desc()); hit = await page.evaluate(()=>/select files|elegir archivos|seleccion/i.test(document.activeElement?.textContent||"")); }
  log(lang,"KBD tabs:",tr.join(" > "));
  const [fc] = await Promise.all([page.waitForEvent("filechooser",{timeout:5000}).catch(()=>null), page.keyboard.press("Enter")]);
  log(lang,"KBD chooser", !!fc);
  if (fc) { await fc.setFiles(fx("photo.jpg")); await page.waitForTimeout(500); log(lang,"KBD focus after add", await desc());
    const t2=[]; let on=false; for(let i=0;i<20&&!on;i++){ await page.keyboard.press("Tab"); t2.push(await desc()); on=await page.evaluate(()=>document.activeElement?.getAttribute("type")==="submit"); }
    log(lang,"KBD to Run:", t2.join(" > "));
    await page.keyboard.press("Enter");
    await page.waitForSelector("#result-h, div[role=alert]",{timeout:60000}).catch(()=>{}); await page.waitForTimeout(800);
    log(lang,"KBD focus after result", await desc(), "posts", page.posts.join(","));
    await page.keyboard.press("Tab"); log(lang,"KBD next tab", await desc()); }
  log(lang,"kbd console", page.cons, "net", page.net); await ctx.close();
}
await b.close();

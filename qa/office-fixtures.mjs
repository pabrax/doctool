import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
const QA = path.resolve(import.meta.dirname);
const FX = path.join(QA, "fixtures-office");
const SRC = path.join(QA, "..", "web", "e2e", ".fixtures");
fs.mkdirSync(FX, { recursive: true });
const w = (n, d) => fs.writeFileSync(path.join(FX, n), d);
const docx = fs.readFileSync(path.join(SRC, "letter.docx"));
w("macro.docm", docx);
w("macro.xlsm", fs.readFileSync(path.join(SRC, "book.xlsx")));
w("macro.pptm", fs.readFileSync(path.join(SRC, "deck.pptx")));
w("fake.exe", Buffer.concat([Buffer.from("MZ"), Buffer.alloc(2000, 7)]));
w("docx-as.rtf", docx);
w("docx-as.txt", docx);
w("empty.docx", Buffer.alloc(0));
w("empty.pdf", Buffer.alloc(0));
w("empty.xlsx", Buffer.alloc(0));
w("truncated.docx", docx.subarray(0, Math.floor(docx.length / 2)));
w("truncated.pdf", fs.readFileSync(path.join(SRC, "table.pdf")).subarray(0, 400));
w("garbage.docx", Buffer.from("this is not a docx at all"));
w("garbage.pdf", Buffer.from("this is not a pdf at all"));
w("notes.txt", "Hola mundo\nSegunda línea con acentos áéíóú ñ\n");
w("data.csv", "a,b,c\n1,2,3\n4,5,6\n");
w("page-ext.html", '<html><body><h1>Hi</h1><img src="http://127.0.0.1:9/x.png"><link rel="stylesheet" href="https://example.com/a.css"></body></html>');
w("cfb-as.docx", Buffer.concat([Buffer.from("D0CF11E0A1B11AE1", "hex"), Buffer.alloc(4000)]));
// no-text PDF (graphics only)
{
  const objs = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R >>",
  ];
  const content = "0 0 1 rg 20 20 100 100 re f";
  objs.push(`<< /Length ${content.length} >>\nstream\n${content}\nendstream`);
  let out = "%PDF-1.4\n"; const off = [];
  objs.forEach((o, i) => { off.push(out.length); out += `${i + 1} 0 obj\n${o}\nendobj\n`; });
  const x = out.length;
  out += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n` + off.map((o) => String(o).padStart(10, "0") + " 00000 n \n").join("");
  out += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${x}\n%%EOF\n`;
  w("notext.pdf", Buffer.from(out, "latin1"));
}
// append an entry to a zip (raw-copy existing entries)
function addEntry(zip, name, data, deflate) {
  const eocd = zip.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  const cdOff = zip.readUInt32LE(eocd + 16), cdSize = zip.readUInt32LE(eocd + 12), count = zip.readUInt16LE(eocd + 10);
  const body = zip.subarray(0, cdOff), cd = zip.subarray(cdOff, cdOff + cdSize);
  const comp = deflate ? zlib.deflateRawSync(data, { level: 9 }) : data;
  const crc = zlib.crc32(data) >>> 0;
  const nm = Buffer.from(name);
  const lh = Buffer.alloc(30); lh.writeUInt32LE(0x04034b50, 0); lh.writeUInt16LE(20, 4); lh.writeUInt16LE(deflate ? 8 : 0, 8);
  lh.writeUInt32LE(crc, 14); lh.writeUInt32LE(comp.length, 18); lh.writeUInt32LE(data.length, 22); lh.writeUInt16LE(nm.length, 26);
  const ch = Buffer.alloc(46); ch.writeUInt32LE(0x02014b50, 0); ch.writeUInt16LE(20, 4); ch.writeUInt16LE(20, 6); ch.writeUInt16LE(deflate ? 8 : 0, 10);
  ch.writeUInt32LE(crc, 16); ch.writeUInt32LE(comp.length, 20); ch.writeUInt32LE(data.length, 24); ch.writeUInt16LE(nm.length, 28); ch.writeUInt32LE(body.length, 42);
  const newBody = Buffer.concat([body, lh, nm, comp]);
  const newCd = Buffer.concat([cd, ch, nm]);
  const e = Buffer.alloc(22); e.writeUInt32LE(0x06054b50, 0); e.writeUInt16LE(count + 1, 8); e.writeUInt16LE(count + 1, 10);
  e.writeUInt32LE(newCd.length, 12); e.writeUInt32LE(newBody.length, 16);
  return Buffer.concat([newBody, newCd, e]);
}
w("hidden-macro.docx", addEntry(docx, "word/vbaProject.bin", Buffer.from("fake vba"), false));
w("bomb.docx", addEntry(docx, "word/bomb.bin", Buffer.alloc(300 * 1024 * 1024), true));
if (process.argv[2] === "big") {
  const fd = fs.openSync(path.join(FX, "big.docx"), "w"); fs.ftruncateSync(fd, 210 * 1024 * 1024); fs.closeSync(fd);
} else { try { fs.unlinkSync(path.join(FX, "big.docx")); } catch {} }
console.log(fs.readdirSync(FX).map((f) => `${f} ${fs.statSync(path.join(FX, f)).size}`).join("\n"));

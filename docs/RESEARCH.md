# doctool research (2026-10-21)

Method: public documentation and page text fetched with WebSearch/WebFetch. **Not done:** live network/DevTools inspection of ilovepdf.com (the fetch tool returns converted text, no scripts or XHR). Items marked *(unverified)* come from secondary sources.

## 1. How iLovePDF works

### 1.1 Product surface (ilovepdf.com, merge page)
- Tool pages are plain routes (`/merge_pdf`, `/split_pdf`, `/compress_pdf`, ...), 26 locale-prefixed variants.
- Catalogue by group: Organize (merge, split, remove/extract pages, organize, scan), Optimize (compress, repair, OCR), Convert to PDF (JPG, Word, PowerPoint, Excel, HTML), Convert from PDF (JPG, Word, PowerPoint, Excel, PDF/A), Edit (rotate, page numbers, watermark, crop, edit, forms), Security (unlock, protect, sign, redact, compare), Intelligence (AI summarizer, translate, PDF to Markdown).
- Single-page flow per tool: pick/drag files (also Drive/Dropbox) -> upload progress (speed, time left) -> reorder/options -> "processing" state -> download. Connectivity error state exists.
- Sister products: iLoveIMG (image tools), iLoveSign, iLoveAPI.

### 1.2 Processing model (from the official iLoveAPI reference, which exposes the same engine)
Task lifecycle, 4 steps, token = JWT (1 h):
1. `GET /v1/start/{tool}/{region}` -> returns `server` (a worker host) + `task` id.
2. `POST {server}/v1/upload` (multipart or `cloud_file` URL; chunked upload supported) -> `server_filename`.
3. `POST {server}/v1/process` (`tool`, `files[]`, options; synchronous unless `webhook`).
4. `GET {server}/v1/download/{task}` (single file, or ZIP when multiple outputs).
Extras: `task/next` chains tasks (output of one is input of the next); `debug=true` echoes params; task states `Waiting/Processing/Success/SuccessWithWarnings/Error/Deleted/NotFound`; per-file states (`WrongPassword`, `DamagedFile`, `OutOfRange`, `TimeOut`...); `try_pdf_repair` on by default; `ignore_errors`; `packaged_filename` templates (`{date}`,`{n}`,`{filename}`,`{tool}`); results and tasks auto-deleted after ~1-2 h (docs are inconsistent); 7 regions; worker-per-task assignment; 10% open-task cap.
Takeaway: it is **stateless, task-scoped, ephemeral** processing behind a uniform 4-step contract. Internal queues/storage/scaling are not public *(unknown)*.

### 1.3 Tool parameter catalogue (useful as our parameter model)
split (`ranges`/`fixed_range`/`remove_pages`/`filesize`, `merge_after`), compress (`extreme|recommended|low`), OCR (`ocr_languages`), pdfjpg (`pages|extract`), imagepdf (`orientation`,`margin`,`pagesize`), pagenumber (position grid, font, `{n}/{p}`), watermark (text|image, position, `mosaic`, rotation, transparency 1-100, layer above|below), protect (`password`), pdfa (`pdfa-1b..3a`), editpdf (elements: text/image/svg with coords, zindex, opacity), extract text, summarize, markdown. Image tools: resize, crop, compress, convert (jpg/png/gif/heic), rotate, watermark, upscale, remove background, repair.

### 1.4 What it does NOT give you (our differentiators)
Quotas (250 files/mo free), uploads to a third party, ephemeral results (no memory), no versioning, no library, no local automation beyond paid API.

## 2. Open-source landscape

| Project | Model | Stack | Notes |
|---|---|---|---|
| Stirling-PDF | Self-hosted server, 50-60+ tools, REST API, no-code pipelines, desktop | Java/Spring Boot backend; v2 React+TypeScript+Vite+Mantine SPA, Tauri desktop; wraps LibreOffice, Tesseract, qpdf | Open-core (check LICENSE; has paid enterprise features). ~1 GB image. Closest reference for scope. |
| BentoPDF | 100% client-side (WASM), no upload | Vite+TypeScript+Tailwind; pdf-lib, PDF.js, qpdf-wasm, LibreOffice-WASM, Tesseract, wasm-vips; AGPL engines (PyMuPDF, Ghostscript, CoherentPDF) loaded from CDN | AGPL-3.0 + paid commercial license. LibreOffice-WASM needs SharedArrayBuffer (cross-origin isolation). No PDF->Word. |
| EmbedPDF | Embeddable viewer/editor | PDFium WASM, MIT wrapper (PDFium Apache-2.0) | Annotations, true redaction. A forum claims the PDFium fork source is not fully public *(unverified)*. |

Lessons: (a) a tool registry + REST API per tool is the proven shape; (b) pure-WASM is private but hits limits (Office, Ghostscript, OCR size, AGPL); (c) pipelines are a valued feature; (d) licensing of engines (AGPL) drives architecture.

## 3. Engines considered

| Need | Pick | License | Why / caveat |
|---|---|---|---|
| Structure ops (merge, split, rotate, encrypt, metadata, repair, linearize) | **pikepdf (qpdf)** | MPL-2.0 | Robust, no rendering needed |
| Render thumbnails/previews | **pypdfium2** (server), **pdfjs-dist** (browser) | Apache-2.0/BSD | Fast, permissive |
| Compress | **Ghostscript** (subprocess) + qpdf | AGPL (external binary) | Best size reduction; called as a process, not linked |
| Overlay (watermark, page numbers, stamps) | **reportlab** + pikepdf merge | BSD | Deterministic |
| Images -> PDF | **img2pdf** + Pillow | LGPL / HPND | Lossless embedding |
| OCR (v0.2) | **OCRmyPDF** + Tesseract | MPL-2.0 (verify pinned version) | Adds text layer, needs Ghostscript+qpdf |
| Office -> PDF (v0.2) | **LibreOffice headless** | MPL-2.0 | Standard approach |
| PDF -> Word (v0.2) | **pdf2docx** or LibreOffice | verify (depends on PyMuPDF, AGPL) | No benchmark found; test on own docs. Docling exports MD/JSON, not DOCX |
| Browser JS editing (optional) | **@cantoo/pdf-lib** (maintained fork; Stirling migrated to it) | MIT | Upstream pdf-lib maintenance unverified |
| Avoid in core | PyMuPDF | AGPL-3.0 | Would force AGPL on the whole app |

## 4. Skills and tooling available in this environment
- `anthropic-skills:pdf` (PDF read/merge/split/OCR recipes): use as a reference for edge cases while building.
- `design:design-system`, `design:accessibility-review`, `design:ux-copy`, `design:design-critique`: apply to the UI at each milestone.
- `engineering:testing-strategy`, `engineering:architecture` (ADR): for test plan and ADRs.
- `claude-in-chrome` / built-in browser: can be used later for a real DevTools-level inspection of ilovepdf.com network calls if deeper reverse engineering is wanted (needs owner OK for site access).

## Sources
- iLoveAPI REST reference: https://www.iloveapi.com/docs/api-reference , https://www.iloveapi.com/docs/pdf-guides/common
- iLovePDF merge page: https://www.ilovepdf.com/merge_pdf
- Stirling-PDF: https://github.com/Stirling-Tools/Stirling-PDF ; self-host overview https://blog.elest.io/self-host-stirling-pdf-50-private-pdf-tools-on-your-server/
- BentoPDF: https://github.com/alam00000/bentopdf
- EmbedPDF: https://cdn.jsdelivr.net/npm/@embedpdf/pdfium@2.14.3/README.md
- @cantoo/pdf-lib: https://unpkg.com/@cantoo/pdf-lib@2.7.1/README.md
- pdf2docx / Docling: https://pypi.org/project/pdf2docx , https://arxiv.org/abs/2501.17887
- OCRmyPDF: https://pypi.org/project/ocrmypdf/

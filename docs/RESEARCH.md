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

## Office module spikes (2026-11-08)
- S1 DONE (command output, scratch dir, throwaway profile via `-env:UserInstallation`): LibreOffice 26.8.1.1 (`soffice.com --version`). Headless conversions OK: html->docx 23.7 s (cold start, first run creates the profile), csv->xlsx 2.1 s, docx->pdf 3.6 s then 2.4 s, xlsx->pdf 2.5 s. Output PDFs open in pikepdf (1 page each) and pdfium extracts the text, accents included. Stderr noise: "Could not find platform independent libraries <prefix>" (harmless; do not treat stderr as failure, check exit code + output file). => cold start is the cost: reuse one persistent profile dir per worker (not per job) or accept ~20 s first call; decide in O3.
- S5 PARTIAL (PyPI search results, not pip metadata): python-docx 1.2.0 MIT, python-pptx 1.0.2 MIT, openpyxl 3.1.5 MIT, msoffcrypto-tool 6.1.0 MIT. pdfplumber license UNVERIFIED (official page not returned; a third-party README says MIT) -> confirm from pip metadata at install time.
- S6 DONE (site search results): iLovePDF has PDF->PowerPoint (one slide per page, OCR variant paid), PDF->Excel (tables to .xlsx, one table per sheet or all on one sheet, OCR option), Redact PDF (permanent removal; "Smart" AI variant is credit-based), Compare PDF (text mode with search + visual overlay in red, downloadable PDF report). Smallpdf: 30+ tools incl. Redact (removes content then black boxes), PDF<->Excel/Word, Unlock, Edit, Sign; OCR (PDF->Word/Excel/PPT) is paid. => the 1:1 matrix in the plan is confirmed for compare, redact, pdf2ppt, pdf2excel; add the "one table per sheet vs all on one sheet" option and the compare "overlay + report" mode.
- S2, S3, S4 PENDING: need python-docx/openpyxl/python-pptx/pdfplumber in a venv and Tesseract (installs, owner approval). Sources: https://www.ilovepdf.com/blog/how-to-compare-pdf , https://www.ilovepdf.com/blog/free-online-convert-pdf-tools-ultimate-guide , https://smallpdf.com/pdf-tools , https://pypi.org/project/python-docx/ , https://pypi.org/project/openpyxl/ , https://pypi.org/project/python-pptx/ , https://pypi.org/project/msoffcrypto-tool/

### S2/S3/S4 results (2026-11-08, scratch venv, owner PDFs read locally, metrics only, no content stored)
- Setup: scratch venv (python-docx 1.2.0, openpyxl 3.1.5, python-pptx 1.0.2, pdfplumber 0.11.10 [pdfminer.six MIT; pdfplumber `pip show` License field empty -> still confirm from repo LICENSE], ocrmypdf 17.13.0 MPL-2.0). Tesseract 5.4.0.20240606 (UB-Mannheim) installed with winget; ships eng+osd only, `spa.traineddata` fetched from tessdata_fast into a scratch dir. No Ghostscript on this PC.
- S2 PDF->DOCX, first 6 pages of 5 real PDFs (docx form with tables, guide with images, 1-page design menu, PPT exported to PDF, bitacora with tables). Script: scratchpad `bench_pdf2docx.py`. LibreOffice `writer_pdf_import`: text recall 0.96-1.00 but ZERO real Word tables on all 5 files and 75-442 drawing/text-frame objects per file (text lives in positioned frames, not flowing paragraphs); output 47 KB-1.9 MB; 3-9 s. Own pdfplumber extractor: recall 1.00 on all, token precision 0.92-1.00, real tables 16/6/0/3/12, 0.2-2 s, 36-42 KB, but NO images and no fonts/colours. (LO "precision 0.5" is a counting artefact: each text frame appears twice in the XML via AlternateContent; do not read it as quality.) Metric is order-insensitive token recall: it proves text is not lost, NOT that reading order or table cell boundaries are right. => Decision: own extractor as the editable-DOCX engine (paragraphs + real tables), adding images next; LibreOffice import only as an optional "keep layout" mode (frames, looks right, hard to edit). Reading-order and table-accuracy checks on the owner's files are still a TODO for O6 (visual diff by rendering both to PNG).
- S3 table detection: pdfplumber `find_tables` found tables in 4/5 files (25 in the first 10 pages of the docx-form, 10 in the guide, 6 in the pptx-pdf, 19 in the bitacora); ground-truth cell accuracy NOT measured. It prints a harmless "Could not get FontBBox" warning on some fonts.
- S4 OCR: scanned phone PDF (3 pages, 0 text chars, images only). Tesseract spa+eng page 1: 192 words, mean confidence 52.9 (low: photo-quality scan; tesseract warned "lots of diacritics"). => OCR needs preprocessing options (deskew, rotate, contrast) and a quality warning. OCRmyPDF 17.13 WITHOUT Ghostscript: `--output-type pdf --skip-text` produced a searchable PDF in 5.9 s (text layer on pages 1 and 3: 818 and 670 chars; page 2 got none). So OCR does not require Ghostscript on Windows; PDF/A output does (keep `pdfa` as gs-optional). Gotcha: a custom TESSDATA_PREFIX must also contain `configs/` and `tessconfigs/` or OCRmyPDF fails with "Can't open hocr".

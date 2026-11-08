---
feature: doctool-office-module
status: proposed      # plan only; no source edits until the owner approves
lane: L3 (spawns a native subprocess, LibreOffice, on hostile documents; macros, external links, new engine licensing) -> L2 flow + owner approval before apply + independent security review
repo: C:/Users/Laura/Documents/Pablo/proyectos/doctool (Apache-2.0)
base: branch feat/office-module from main (after feat/image-module is merged, owner decides)
---
# Doctool Office module ("ofimatica")

## Evidence so far (this session)
- Tool contract: `api/doctool/tools/base.py` (id, title, group, Params, min/max_files, accepts = "pdf"|"image", check_input, run -> bytes in/out). Register by import in `tools/__init__.py`. `accepts` must grow to accept `office` (docx/xlsx/pptx/odt/csv/...). Verified by reading the files.
- Installed on this PC: LibreOffice (`C:\Program Files\LibreOffice\program\soffice.exe`, version string NOT yet captured, spike S1). Not installed: Tesseract, Ghostscript, pandoc, Docker. Venv has pikepdf 10.17, pypdfium2 5.14, lxml 6.1.3. No python-docx/openpyxl/python-pptx yet.
- `process_task` is synchronous (image-module spike S4). LibreOffice conversions take 2-30 s: acceptable sync with a timeout for v1, but needs the same slot semaphore pattern as images (503 "busy").
- iLovePDF premium page (web search, partial): Word/PowerPoint/Excel -> PDF, PDF -> Word, PDF -> Word with OCR, OCR, PDF/A, digital signatures, batch, larger limits. Compare/redact/PDF->PPT/XLSX could NOT be confirmed from search results; verify on ilovepdf.com before copying 1:1.
- Stirling-PDF: Office->PDF through LibreOffice; eBook via Calibre; Markdown->PDF; license reported inconsistently (MIT core + proprietary Pro vs GPLv3). Treat as reference only, copy nothing.
- pdf2docx = AGPL (PyMuPDF dependency), confirmed by its docs. Doctool is Apache-2.0 and excluded PyMuPDF (SPEC D1) -> pdf2docx is OUT as a bundled dependency.
- Existing SPEC.md section 7 already slates for v0.2: OCR, Word/Excel/PPT/HTML -> PDF, PDF -> Word, PDF/A, compare. This module executes that slice.

## Engine decision (criterion 1 safety, then 5 maintainability)
| Need | Engine | License | Note |
|---|---|---|---|
| Office -> PDF | LibreOffice headless, external process only | MPL-2.0 | never linked; per-job profile dir `-env:UserInstallation`; no shell; timeout; kill tree |
| PDF -> Word/Excel/PPT | LibreOffice Draw import (weak) vs own extractor (pdfium text + layout -> python-docx/openpyxl/python-pptx) | MPL / MIT / BSD | SPIKE S2 benchmarks on 5 real PDFs; ship "good enough" text+tables+images honestly labelled, not "perfect layout" |
| Read/write docx/xlsx/pptx directly | python-docx (MIT), openpyxl (MIT), python-pptx (MIT), lxml | MIT | verify versions at install (S5) |
| OCR | Tesseract + OCRmyPDF (MPL-2.0) as OPTIONAL external binaries, feature-detected like AVIF | Apache-2.0 / MPL | needs Ghostscript for OCRmyPDF: spike whether `--output-type pdf` with pdfium rasterising avoids it |
| Office <-> text/markdown/HTML | own thin code on python-docx + `markdown-it-py` (MIT) | MIT | no pandoc (GPL) |
| Compare | `difflib` + pdfium text per page | stdlib | side-by-side highlight |
Rejected: pdf2docx/PyMuPDF (AGPL), Aspose/Spire (proprietary), OnlyOffice (AGPL), pandoc (GPL as bundled), Word COM automation (Windows+Office only, not portable).

## Tool catalogue (new group `office`, own colour, needs ADR like `images`)
Tier A: parity with iLovePDF free (v0.2-a, ship first)
1. `word2pdf` (docx/doc/odt/rtf/txt -> PDF)
2. `excel2pdf` (xlsx/xls/ods/csv -> PDF; options: fit-to-width, landscape, one sheet per page, sheet selection)
3. `ppt2pdf` (pptx/ppt/odp -> PDF; options: handouts per page, include notes, hidden slides)
4. `pdf2word` (PDF -> DOCX; text, headings guess, tables, images; honest "reflow, not pixel-perfect" note)
5. `pdf2excel` (PDF tables -> XLSX, one sheet per detected table)
6. `pdf2ppt` (one slide per page, page image + optional text layer)
7. `html2pdf` (local HTML/URL-less upload; no network fetch, SSRF safe)
Tier B: "premium-in-iLovePDF" replicated locally (v0.2-b)
8. `ocr` (searchable PDF, language packs, deskew) and `pdf2word-ocr` (scan -> DOCX)
9. `pdfa` (PDF/A-1b/2b conversion + validation report)
10. `compare` (two docs: text diff, per-page highlights, summary; docx vs docx and pdf vs pdf)
11. Batch: many files -> ZIP, same options (Doctool already has task multi-file)
12. Recipes/pipelines: "docx -> pdf -> compress -> watermark" saved chain (SPEC v0.2 recipes)
Tier C: Office-native utilities no iLove has, cheap and useful (v0.3)
13. `docx-extract` (text/markdown/images/tables from docx/pptx/xlsx)
14. `office-merge` (merge several docx or xlsx sheets; via LibreOffice or python libs)
15. `office-clean` (strip metadata, comments, tracked changes, hidden sheets/slides, author) with a "what was removed" report (reuses the imageclean pattern)
16. `office-protect/unlock` (password on docx/xlsx via msoffcrypto-tool BSD; verify license)
17. `csv-tools` (csv <-> xlsx, encoding/delimiter detection, dedupe)
18. `redact` (true redaction on PDF text + docx text, not just black boxes) - L3, own plan
19. `sign` (visual signature now; certificate signing later) - L3, own plan
Out of scope: online co-editing, macros/VBA execution (always stripped/blocked), cloud connectors, AI summarisation (maybe later as local-model option).

## Security & robustness (L3)
- Office files are hostile: macros never run (LibreOffice `-env` profile with macro security "very high"/disabled; reject `.docm/.xlsm/.pptm` by default or convert after stripping), no external links/OLE/remote images fetched (block network at process level where possible; HTML tool has no fetch), zip-bomb guard on OOXML (entry count, uncompressed size ratio), XML entity expansion off (defusedxml / lxml `resolve_entities=False`).
- Subprocess: argv list, no shell, per-job temp dir, timeout (default 60 s), kill process tree on timeout, output size cap, one LibreOffice at a time (global semaphore, 503 busy) because soffice profiles do not tolerate concurrency; stale `soffice` cleanup.
- Magic-byte + extension allowlist; filenames never reach argv unsanitised; password never logged.
- Honest results: output validated (PDF opens in pikepdf/pdfium, DOCX/XLSX reopen with python libs), "never return garbage", warnings when fonts are substituted.
- LibreOffice discovery: `DOCTOOL_SOFFICE` env or PATH or default install dir; if absent the Office tools show as "needs LibreOffice" instead of failing (same as AVIF feature detection).

## Spikes (read-only / scratch, before any source edit)
- S1 LibreOffice version + a headless docx->pdf and xlsx->pdf run in a scratch dir with a throwaway profile; timing, cold vs warm, fonts. Accept: output PDFs open in pikepdf; times recorded.
- S2 PDF->DOCX quality: LibreOffice vs own extractor on 5 real PDFs (text, table, scan, multi-column, form). Accept: table with scores, decision on engine.
- S3 PDF table extraction candidates (pdfplumber MIT vs pdfium geometry) on 3 PDFs.
- S4 OCR path: is Tesseract installable without admin (portable/winget) and OCRmyPDF viable without Ghostscript? Needs owner approval to install anything.
- S5 License check of python-docx, openpyxl, python-pptx, msoffcrypto-tool, pdfplumber, markdown-it-py at the exact pinned versions (pip metadata output recorded in `docs/RESEARCH.md`).
- S6 Verify iLovePDF/Smallpdf/Adobe premium tool lists directly from their sites (compare, redact, PDF->PPT/XLSX) to finish the 1:1 matrix.

## Tasks (ids stable; one Conventional Commit per task on `feat/office-module`)
- [ ] O0 Branch from main; copy this plan; ADR for `office` group colour (SPEC one-accent rule) - owner decides
- [ ] O1 Spikes S1-S6, results in `docs/RESEARCH.md` "Office" - accept: each question answered with command output or marked unresolved
- [ ] O2 ui-ux-designer: `design/office-tools.md` (group, icons, per-tool options, "engine missing" state, warnings display, before/after for compare)
- [ ] O3 `officecore.py`: soffice discovery, sandboxed runner (profile dir, timeout, tree kill, semaphore), OOXML zip/XML guards + tests (bomb, macro file, corrupt, password-protected, huge sheet) - accept: pytest + ruff green
- [ ] O4 extend `Tool.accepts` to `office` + Dropzone/accept lists + upload allowlist; existing 624 pytest stay green
- [ ] O5 Tier A tools 1-3 (Office->PDF), one implementer each, tester after the group
- [ ] O6 Tier A tools 4-7 (PDF->Office, html2pdf) per S2/S3 decisions, tester after
- [ ] O7 web: group, icons, i18n es/en, tool options UI, engine-missing state, e2e per tool
- [ ] O8 reviewer + security-reviewer on the branch, qa-auditor on the running app - accept: `VERDICT: pass`, `SECURITY: pass`, 0 open
- [ ] O9 Tier B (ocr, pdfa, compare, batch, recipes) - only after O8 and owner approval; each becomes its own short odd doc
- [ ] O10 Tier C utilities in order of owner priority; redact/sign get separate L3 plans
- [ ] O12 Linux server deployment (owner-approved 2026-11-08): Dockerfile on Debian slim with `libreoffice-{core,writer,calc,impress}`, `fonts-liberation`, `fonts-crosextra-carlito/caladea`, optional tesseract-ocr-{spa,eng} + ghostscript, non-root user, `tini`, memory/concurrency limits; run the full pytest suite inside Linux (WSL or GitHub CI); `soffice` discovery without Windows paths; font-substitution warning in UI; deployment doc with auth/reverse proxy as a PREREQUISITE for any non-localhost exposure (SPEC section 9, L3); decide Ghostscript AGPL handling before publishing any image - accept: image builds, suite green on Linux, one docx->pdf smoke in the container
- [ ] O11 README/docs: tool matrix vs iLovePDF, install notes for LibreOffice/Tesseract, limits (`DOCTOOL_OFFICE_*`)

## Decisions needed from the owner
1. Is LibreOffice as a required external install acceptable (Office tools greyed out without it)? Recommended: yes.
2. Order: ship Tier A (7 tools) first, then Tier B? Recommended: yes, A -> OCR -> compare -> pdfa.
3. PDF->Word: accept "good text/table reflow" instead of pixel-perfect (no AGPL engine)? Recommended: yes, decided after S2 numbers.
4. May I install Tesseract (and its languages spa+eng) for spike S4, and python-docx/openpyxl/python-pptx in the project venv? (new installs need your approval)
5. Merge `feat/image-module` into main first, or branch the office module from it?

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
| PDF -> Word/Excel/PPT | DECIDED by S2: own pdfplumber extractor -> python-docx/openpyxl/python-pptx (real paragraphs + real tables, recall 1.00 on 5 owner PDFs); LibreOffice PDF import only as optional "keep layout" mode (no real tables, 75-442 text frames per file) | MIT / MPL | images still to add; reading order and table cells to verify visually in O6 |
| Read/write docx/xlsx/pptx directly | python-docx (MIT), openpyxl (MIT), python-pptx (MIT), lxml | MIT | verify versions at install (S5) |
| OCR | Tesseract + OCRmyPDF (MPL-2.0) as OPTIONAL external binaries, feature-detected like AVIF | Apache-2.0 / MPL | S4 verified: OCRmyPDF 17.13 works WITHOUT Ghostscript with `--output-type pdf`; only PDF/A needs gs. Scan quality drives accuracy (mean conf 52.9 on a phone scan) -> deskew/contrast options + quality warning |
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
- [x] O0 (2026-11-08) Branch `feat/office-module` created from the image-module tip (office edits share `tools/__init__.py`, `toolIcons.ts`, i18n with it); plan already in `odd/tasks/`; ADR D2b in `docs/adr-ui-identity.md` (teal, contrast computed 4.67-10.05:1, owner may veto); the 2 doc commits moved off `feat/image-module`, which is back at 25c0ede
- [ ] O1 Spikes S1-S6, results in `docs/RESEARCH.md` "Office" - accept: each question answered with command output or marked unresolved
- [x] O2 (2026-11-08) `design/office-tools.md` written by ui-ux-designer (7 Tier A tools, 12 contracts, 5 open owner decisions in its section 15); field names `available`/`requires`/`warnings` are proposals for O4; es.ts/index.css not read by the designer, re-check in O7
- [x] O3 (2026-11-08) `api/doctool/officecore.py` + `tests/test_officecore.py` (33 tests, TDD: red on ImportError first): soffice discovery, extension allowlist, macro/zip-bomb/XML-entity/encrypted-package guards, macro-locked persistent profile, process-tree kill on timeout, single slot (busy), settings `DOCTOOL_OFFICE_*`. Real-LibreOffice tests pass (csv->pdf, job dirs cleaned). Not yet wired to any router/tool (O4/O5); independent security review is O8. Known limit: external links are only DETECTED (warning), network blocking is a deployment concern (O12)
- [x] O4 (2026-11-08) generic office contract: `Tool.accepts=office` + `requires/extensions/available()/check_upload`, `OfficeTool` base (`lo_convert` under the single slot), `/tools` reports available/requires/extensions, `ToolOutput.warnings` -> `Task.warnings` (ALTER migration for old DBs), `ToolError busy` -> 503 retryable, Dropzone office/disabled (macro files never accepted), office tools not offered as next step for a PDF. Evidence: full pytest 671 passed, ruff clean, vitest 170, tsc clean, vite build ok. Group order/CSS tokens/banner stay in O7
- [x] O5 (2026-11-08) word2pdf, excel2pdf, ppt2pdf, html2pdf on `OfficeTool` + helpers `ooxml.py` (surgical OOXML edits: external rels neutralised, xlsx page setup/sheet selection via XML, fonts, hidden slides, legacy macros), `pdflayout.py` (fit to A4/Letter, framed n-up handouts, font substitution), `htmlsafe.py` (no scripts, no network/file URLs, CSS @page in mm). Spike: SinglePageSheets prints hidden sheets -> replaced by fitToWidth/Height XML; LO ignores CSS size keyword `letter` -> mm. Tests: test_office_helpers 18, test_office_tools 17 (real LO)
- [x] O6 (2026-11-08) pdf2word (editable via own `pdfextract.py`: headings, paragraphs, real tables, pictures, scanned pages kept as pictures + `no_text_layer` warning; `keep_look` via LibreOffice PDF import), pdf2excel (tables per sheet or stacked, numbers typed, `=` text never a formula), pdf2ppt (picture slides, optional text layer). `LibreOfficeMixin` split from `OfficeTool`. Bug found and fixed: `run_process` hung on PDF import because xpdfimport inherits the stdout pipe -> output now goes to a log file (fail-before: timeout 60 s; after: pass). Tests: test_pdf2office 13. Full suite 719 passed, ruff clean
- [x] O7 (2026-11-08) web: group `office` after Convert (owner), teal tokens (ADR D2b) light/dark, 7 icons, palette keywords, es/en copy from `design/office-tools.md`, honest-quality note (role=note), engine-missing banner + disabled Dropzone/Run + launcher/palette badge, warnings list with OCR action link, office wording for errors, Retry on busy (office only; image contract keeps Run). Evidence: vitest 205, tsc, build, Playwright 42/42 incl. `e2e/office.spec.ts` (7 tools on the real API + LibreOffice). e2e fixes: identity group list, sidebar C3 sub-pixel rounding, palette test waits for cmdk selection (was flaky 1/3)
- [x] O8 (2026-11-08) reviewer: round 1 fail (7 MAJOR) -> round 2 PASS (0 open, 3 MINOR fixed after). security-reviewer: round 1 fail (3 MAJOR) -> round 2 fail (1 MAJOR: in-process parse of big sheet parts / unchecked intermediate xlsx) -> fixed in 5043bab (MAX_EDITED_PART, intermediate checked); no round 3 run (2-loop limit) -> residual list below. Empirical fetch measurement + regression test (RESEARCH.md "O8 security spike"). qa-auditor QA1 on the live app: 0 BLOCKER/HIGH, 6 MEDIUM, 8 LOW (qa/office-qa1.md); fixed O1 progress status, O2 focus back to Run, O3/O4 named rejections, O5 no library internals in upload errors (contract change: detail {state,message}), O9 no dead-end OCR advice, O11 plurals. Evidence: pytest 761+, vitest 208, Playwright 43/43
- [ ] O9 Tier B (ocr, pdfa, compare, batch, recipes) - only after O8 and owner approval; each becomes its own short odd doc
- [ ] O10 Tier C utilities in order of owner priority; redact/sign get separate L3 plans
- [x] O12 (2026-11-08, PARTIAL) Dockerfile: LibreOffice + Liberation/Carlito/Caladea fonts + tini, DOCTOOL_SOFFICE, HOME=/data; compose: mem/cpu/pids caps; NOT built (no Docker here). Linux suite run in WSL Ubuntu blocked: no python3-venv (needs sudo) and installing virtualenv in WSL user space was denied by the permission classifier -> owner decision
- [x] O11 (2026-11-08) docs/office-setup.md, docs/office-module.md (3 Mermaid diagrams: components, word2pdf sequence, LibreOffice lane states), docs/deployment.md, README Office section; written by the new `doc-writer` agent (~/.claude/agents/doc-writer.md), links and env vars verified by script

## Decisions needed from the owner
1. Is LibreOffice as a required external install acceptable (Office tools greyed out without it)? Recommended: yes.
2. Order: ship Tier A (7 tools) first, then Tier B? Recommended: yes, A -> OCR -> compare -> pdfa.
3. PDF->Word: accept "good text/table reflow" instead of pixel-perfect (no AGPL engine)? Recommended: yes, decided after S2 numbers.
4. May I install Tesseract (and its languages spa+eng) for spike S4, and python-docx/openpyxl/python-pptx in the project venv? (new installs need your approval)
5. Merge `feat/image-module` into main first, or branch the office module from it?

## Residual risks and backlog (2026-11-08)
- Security residual: profile defences measured only on LibreOffice 26.8 Windows (unknown registry keys are ignored silently: no minimum-version check yet); Calc area links, web queries (xl/connections.xml), DDE/OLE links not tested; container egress still recommended; Writer/Calc LinkUpdateMode keys not set (semantics unverified).
- QA1 LOW backlog: O6 size/limit in too_large messages; O7 empty file / renamed valid docx wording; O8 separate messages for unknown sheet vs bad page syntax; O10 result stats (tables found, slides, sheets); O13 palette fuzzy noise and es 'página web'; O14 single-file tools still show reorder handle and plural copy.
- Next features (Tier B): OCR (Tesseract installed; OCRmyPDF works without Ghostscript), PDF/A, compare, batch, recipes.

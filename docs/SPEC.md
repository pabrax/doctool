# doctool SPEC v0.1 (MVP: PDF only)

Status: PROPOSED, awaiting owner approval (see section 12). Lane for the build: L1+ (L3 for any auth/network exposure change).

## 1. Purpose and principles
Personal, open-source, non-monetized document workbench: do everything iLovePDF does, locally, **and remember**. Principles, in priority order: (1) files never leave the machine, (2) every output verified valid, (3) simple enough for one maintainer to understand, (4) permissive engines, no AGPL linked into the app, (5) every tool is also an API call and a CLI call.

## 2. Scope
**MVP (v0.1-v0.2 below): PDF only.** Out of MVP: Office editing, image tools, signatures with certificates, AI features, multi-user, cloud sync. They are planned milestones (section 11), not forgotten.

## 3. Differentiators vs iLovePDF
| iLovePDF | doctool |
|---|---|
| Upload to third party, quotas | Local, unlimited |
| Ephemeral (deleted in ~1-2 h) | **Library**: documents persist, searchable, tagged |
| Each result is a dead end | **Version history**: every output is a child version of its input, with tool+params recorded ("recordar") |
| One tool per visit | **Chains/pipelines**: reuse the output as the next input; saved recipes (v0.2) |
| Web only | Web UI + REST API + CLI |

## 4. Architecture
```
Browser (React SPA) --HTTP--> FastAPI (localhost) --> Tool registry --> engines (pikepdf, pypdfium2, Ghostscript, ...)
                                   |--> SQLite (metadata)    |--> disk store (content-addressed blobs)
                                   `--> job runner (asyncio + process pool)
```
Decision D-ARCH-1: **local server + web UI**, not pure WASM and not Java. Why: Ghostscript/OCR/LibreOffice are needed and heavy; persistence needs a backend; Python is the owner's strongest stack (criteria 3, 5). Browser-side code is limited to previews and page-organize thumbnails (PDF.js).

### 4.1 Task contract (borrowed from iLoveAPI, simplified for local)
1. `POST /api/v1/tasks` `{tool, params}` -> `{task_id}`
2. `POST /api/v1/tasks/{id}/files` (multipart, or `{document_id}` of a library doc) -> `{file_id}`
3. `POST /api/v1/tasks/{id}/process` -> runs (sync for small, background + SSE progress for big)
4. `GET /api/v1/tasks/{id}` (state: `waiting|processing|success|success_with_warnings|error`), `GET /api/v1/tasks/{id}/download` (file or ZIP)
Per-file states: `ok|wrong_password|damaged|out_of_range|timeout`. Param error -> HTTP 422 with field paths. `debug=true` echoes params without processing.
Library: `GET/POST/DELETE /api/v1/documents`, `GET /documents/{id}/versions`, `GET /documents/{id}/thumbnail/{page}`.

### 4.2 Tool registry (the key design)
Each tool is one class: `id`, `Params` (Pydantic model), `run(inputs, params, ctx) -> outputs`, `validate_output()`. The registry generates (a) the OpenAPI schema, (b) the CLI subcommand, (c) the UI options form from JSON Schema. Adding a tool = one file + tests, no UI code for plain options.

### 4.3 Data model (SQLite via SQLAlchemy/Alembic)
- `document(id, name, tags, created_at)`
- `version(id, document_id, parent_version_id, sha256, size, pages, tool, params_json, created_at)`; blob stored at `data/blobs/ab/cd/<sha256>`
- `task(id, tool, params_json, state, error, created_at, finished_at)`, `task_file(task_id, version_id, role in|out, state)`
- (v0.2) `recipe(id, name, steps_json)`
Retention: temp/task files purged after 24 h (configurable); library versions kept until the owner deletes.

## 5. Stack
| Layer | Choice | Rejected (why) |
|---|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, uvicorn, SQLAlchemy+Alembic, `uv` for deps | Java/Stirling stack (heavier, less familiar); Node backend (weaker PDF ecosystem) |
| Jobs | in-process asyncio + `ProcessPoolExecutor` | Redis/Celery (overkill single user); revisit if needed |
| Frontend | React + TypeScript + Vite, Tailwind, shadcn/ui (Radix), TanStack Query, react-router, dnd-kit, pdfjs-dist, react-i18next (es/en) | Mantine (fine, but shadcn gives owned code); HTMX (rich drag-drop page editor is easier in React) |
| Storage | SQLite + disk blobs | Postgres (no need) |
| Packaging | `docker compose` (api+web, bound to 127.0.0.1) and `uv run` for dev; Tauri desktop wrapper is a later option | Electron |
| Quality | pytest, ruff, mypy, vitest, Playwright, GitHub Actions, pre-commit | |
Versions: pin latest stable at scaffold time (M0) via lockfiles; do not hardcode versions in this spec.

## 6. Engines (MVP)
pikepdf (merge, split, rotate, delete/reorder pages, encrypt/decrypt, metadata, repair, linearize), pypdfium2 (thumbnails, PDF->image), Ghostscript subprocess (compress), reportlab (watermark, page numbers), img2pdf+Pillow (images->PDF). v0.2: OCRmyPDF+Tesseract, LibreOffice headless, pdf2docx (license check first). PyMuPDF is excluded from the core (AGPL).

## 7. Feature list and priority
**Must (v0.1)**: merge; split (ranges / every N / by size / extract / remove pages); organize (visual reorder, rotate, delete, duplicate, insert blank); rotate; compress (3 levels); protect/unlock; images->PDF; PDF->images (PNG/JPG); watermark (text/image); page numbers; metadata viewer/editor; library + version history; drag-and-drop upload; preview; ZIP download for multi-output.
**Should (v0.2)**: OCR (searchable PDF); Word/Excel/PowerPoint/HTML -> PDF; PDF -> Word; repair; PDF/A; crop; compare; saved recipes/pipelines; full-text search across the library; CLI.
**Later (v0.3+)**: annotate/edit text and shapes; fill/create forms; redact; sign (drawn + certificate); image tools (convert, resize, crop, compress, rotate, watermark; background removal, upscale as optional local models); DOCX/XLSX/PPTX edit; local-LLM summarize/translate/chat with a document; file watcher "inbox" folder; Tauri desktop.

## 8. UI direction
- Layout: left rail tool groups (Organize / Optimize / Convert / Edit / Security) mirroring iLovePDF mental model + **Library** as home; command palette (Ctrl+K) to jump to any tool; each tool page = dropzone -> file cards (reorder, per-file options) -> options side panel -> big primary action -> result card with "Download", "Save to library", "Use as input for another tool".
- Page organizer: thumbnail grid (pypdfium2 server thumbs, lazy), dnd-kit reorder, multi-select, keyboard operable.
- Visual: neutral palette + one accent, tokens as CSS variables, light/dark/system, 8-pt spacing, one icon set (Lucide), generous empty states, skeleton loaders, optimistic progress via SSE.
- Quality gates: WCAG 2.1 AA (focus rings, contrast, keyboard drag alternative, ARIA live for progress), es/en copy. Apply `design:design-system` for tokens, `design:ux-copy` for microcopy, `design:accessibility-review` and `design:design-critique` at each milestone.

## 9. Security and robustness (treat every input PDF as hostile)
- Bind to 127.0.0.1 only by default; any LAN exposure requires a token and is an L3 change.
- Upload: magic-byte check, size cap, page cap, sanitized filenames (never used as paths), per-task temp dir, blobs addressed by hash.
- Subprocesses: argument lists (no shell), timeouts, CPU/memory limits (container), no network in the worker container.
- PDFs with JavaScript/embedded files are never executed; rendering via PDFium/PDF.js with scripting disabled.
- Decompression-bomb guards (max pages, max pixels for rasterization).
- Strict CSP, CORS locked to the UI origin, dependency audit in CI (`pip-audit`, `npm audit`).
- Passwords are never logged or persisted.

## 10. Testing strategy (every tool ships with its check)
- Unit: generated fixture PDFs (reportlab) at test time; plus a small corpus of tricky files (encrypted, damaged, scanned, huge page count, rotated, forms).
- Properties/oracles: merge pages = sum of inputs; split then merge = original page count and text; compress output passes `qpdf --check` and is <= input for the recommended level; protect->unlock round trip; rotate x4 = identity; watermark leaves text extractable.
- API contract tests from the OpenAPI schema; error cases (wrong password, damaged, out of range) return the documented state.
- E2E (Playwright): upload -> merge -> download -> library shows a new version.
- CI gates: ruff, mypy, pytest with coverage threshold, vitest, build, audit.

## 11. Milestones
- **M0 Scaffold**: repo, uv, FastAPI hello, Vite app, CI, docker compose, ADRs for D1-D3. Check: CI green, `docker compose up` serves UI.
- **M1 Core engine**: task contract, registry, storage, merge/split/rotate/organize + library/versions. Check: contract + property tests green.
- **M2 Optimize/Secure/Convert-in**: compress, protect/unlock, images->PDF, PDF->images, watermark, page numbers, metadata. Check: oracles above.
- **M3 UI polish + a11y**: organizer, command palette, i18n, dark mode, a11y audit. Check: Playwright e2e + axe checks.
- **v0.1 release (MVP)** = M0-M3.
- **M4 (v0.2)**: OCR, Office->PDF, PDF->Word, repair, PDF/A, recipes, search, CLI.
- **M5+**: edit/forms/redact/sign, image tools, Office editing, AI, desktop.

## 12. Decisions needed from the owner
- **D1 Project license**: MIT/Apache-2.0 (permissive, requires keeping engines permissive or external binaries) vs AGPL-3.0 (lets us use PyMuPDF). Recommendation: **Apache-2.0**.
- **D2 Architecture**: local server + web UI (recommended) vs fully in-browser WASM (more private-by-construction, but no Ghostscript/OCR/Office without AGPL CDN tricks).
- **D3 Process**: continue as ODD feature-by-feature (recommended; each milestone = one `odd/tasks/` doc) vs enroll OpenSpec SDD for the API contract.
Answers are recorded here once given.

## 13. Risks
| Risk | Mitigation |
|---|---|
| PDF->Word quality is mediocre in open source | v0.2; benchmark pdf2docx vs LibreOffice on owner's real docs before committing |
| Engine licenses (AGPL, unverified pdf2docx/OCRmyPDF versions) | license check ADR per engine before adoption; PyMuPDF excluded |
| Scope creep ("everything iLovePDF does") | strict MVP list; milestones gated by checks |
| Hostile PDFs | section 9 |
| ilovepdf internals only partially known | we copy the public contract, not unknown internals; optional DevTools study later |

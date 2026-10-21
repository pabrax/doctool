# doctool

A personal, open-source PDF toolbox that runs on your own machine. Think iLovePDF, but your files
never leave your computer, there are no limits, and every result is **remembered**: each document
keeps a version history you can browse, download and build on.

Status: **MVP v0.1 (PDF only)**. Specification: [`docs/SPEC.md`](docs/SPEC.md) ·
research: [`docs/RESEARCH.md`](docs/RESEARCH.md) · feature summary: [`docs/SUMMARY.md`](docs/SUMMARY.md).

## What it does today

| Group | Tools |
|---|---|
| Organize | Merge, Split (ranges, every N pages, by size, extract, remove), Rotate, **visual page organizer** (drag to reorder, rotate, duplicate, delete, blank pages) |
| Optimize | Compress (3 levels) |
| Convert | Images → PDF, PDF → images (PNG/JPG) |
| Edit | Watermark (text or image), page numbers, metadata editor |
| Security | Protect (AES-256), Unlock |
| Library | Every output is a new *version* of its document; history, preview, tags, rename |
| UX | Ctrl+K command palette, English/Spanish, light/dark, keyboard accessible (axe-checked) |

## Run it (Windows, PowerShell)

Requirements: Python 3.12+, Node 22+.

```powershell
# 1. backend dependencies (once)
python -m venv .venv
.\.venv\Scripts\python -m pip install -e "api[dev]"

# 2. build the web UI (once, and after UI changes)
cd web; npm ci; npm run build; cd ..

# 3. start (http://127.0.0.1:8000)
cd api; ..\.venv\Scripts\python -m doctool
```

Data lives in `api/data/` (SQLite + content-addressed blobs) unless `DOCTOOL_DATA_DIR` says otherwise.

### Settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `DOCTOOL_DATA_DIR` | `data` | where the database and files are stored |
| `DOCTOOL_PORT` | `8000` | port |
| `DOCTOOL_HOST` | `127.0.0.1` | bind address. Anything else needs `DOCTOOL_ALLOW_LAN=1` |
| `DOCTOOL_ALLOWED_HOSTS` | `127.0.0.1,localhost` | accepted `Host` headers (anti DNS-rebinding) |
| `DOCTOOL_WEB_DIR` | `web/dist` if present | built UI to serve |

## Develop

```powershell
# API with reload + UI dev server (proxy to :8000)
cd api; ..\.venv\Scripts\python -m uvicorn doctool.main:app_factory --factory --reload
cd web; npm run dev            # http://127.0.0.1:5173
```

### Checks (all must pass)

```powershell
cd api; ..\.venv\Scripts\python -m ruff check .; ..\.venv\Scripts\python -m pytest -q
cd web; npx tsc -b --noEmit; npx vitest run; npx playwright test   # e2e uses the installed Edge
```

## How it is built

* **API**: FastAPI. Every tool is one class (`doctool/tools/*.py`): an id, a Pydantic `Params`
  model and `run()`. The registry exposes it as `POST /api/v1/tasks` (the same
  start → upload → process → download contract iLovePDF's API uses) and publishes its JSON Schema
  at `GET /api/v1/tools`.
* **UI**: React + TypeScript + Tailwind. Tool pages are **generated from that schema**, so adding a
  tool needs no UI code unless it wants a custom screen (like the organizer).
* **Engines**: pikepdf/qpdf (structure), pypdfium2 (rendering), reportlab (stamps), img2pdf, Pillow.
  PyMuPDF is deliberately not used (AGPL).
* **Storage**: SQLite + blobs addressed by SHA-256 (identical files are stored once).
* Add a tool: copy `doctool/tools/rotate.py`, register it in `tools/__init__.py`, write its test.

## Security model

doctool is a single-user local app with **no login**, so exposure is what protects it:

* binds to `127.0.0.1` only (LAN needs an explicit opt-in);
* rejects foreign `Host` headers and cross-origin writes (DNS-rebinding / CSRF);
* strict CSP on the UI, `nosniff` everywhere, filenames sanitised and never used as paths;
* passwords are never written to disk (held in memory until the task runs; history shows `***`);
* uploaded PDFs are parsed, never executed (no JavaScript engine involved).

## Known limits (honest list)

* **Compression** recompresses images with Pillow; Ghostscript (stronger) is not integrated yet.
* **Tools output unprotected files**: if you give a password to a tool, the result is not encrypted
  again; use *Protect* as the last step.
* Watermark / page-number text supports Latin characters (built-in PDF fonts).
* There is no page-count cap yet (only a 200 MB upload cap): a huge PDF can use a lot of memory.
* The Docker files and CI workflow are written but **have not been run** (no Docker/GitHub on the
  development machine).
* PDF → Word, OCR and Office → PDF are planned for v0.2 (see the spec).

## License

Apache-2.0, see [`LICENSE`](LICENSE).

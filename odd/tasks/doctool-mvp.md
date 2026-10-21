---
feature: doctool-mvp
status: active
lane: L1+
tdd: on
branch: feat/doctool-mvp
---
# doctool MVP v0.1 (PDF only)
## Specs
- S1 "podemos proceder en la creacion de este primer MVP presentado" — accept: SPEC.md section 7 "Must (v0.1)" features work end to end — check: pytest + vitest + playwright green
- S2 "tu plan propuesto es correcto" — accept: stack/architecture of docs/SPEC.md followed; deviations recorded in SPEC section 12 — check: review
## Objective
Build M0-M3 of docs/SPEC.md. Owner reviews after the first sprint.
## Problem
See odd/tasks/doctool-planning.md.
## Scope
In: SPEC section 7 Must list, library+versions, task API, React UI. Out: v0.2+ features, auth/LAN exposure, push/merge.
## Constraints
Localhost only. Pip installs only inside project .venv; npm inside web/. No system installs (Ghostscript/Docker) without owner approval. TDD on: failing test first for each tool.
## Tasks
- [x] T1 Backend scaffold: venv, pyproject, FastAPI app, health endpoint, ruff, pytest (S1) — accept: `pytest` and `ruff check` pass
- [x] T2 Storage + DB: blob store, SQLite models, library/versions API (S1) — accept: tests for dedupe by sha256, version parentage
- [x] T3 Tool registry + task API contract (S1) — accept: create/upload/process/download tests incl. 422 and states
- [x] T4 Tools merge, split (ranges/every-N/size/extract/remove), rotate, organize (S1) — accept: property tests (page sums, rotate x4 identity)
- [x] T5 Tools protect, unlock, metadata, watermark, page numbers (S1) — accept: round trip + text extractable tests
- [x] T6 Tools compress, images->pdf, pdf->images (S1) — accept: output valid, compress <= input on fixture
- [x] T7 Preview: thumbnails, ZIP multi-output, original download (S1) — accept: endpoint tests
- [ ] T8 Frontend scaffold: Vite+React+TS+Tailwind+shadcn, schema-driven tool pages, library view (S1) — accept: vitest + build pass
- [ ] T9 Organizer UI, command palette, i18n es/en, dark mode, a11y (S1) — accept: axe check + vitest
- [ ] T10 E2E (Playwright), Dockerfile/compose, README, CI workflow (S1) — accept: e2e green locally; docker untested noted
## Verification evidence
- T1-T7 (backend): `cd api && ../.venv/Scripts/python -m pytest -q` -> 124 passed; `ruff check .` -> All checks passed (2026-10-21, HEAD 495b4ba). Each tool written test-first (red observed before green).
- Real bugs caught by tests: overlay double rotation (pixel test), pikepdf API names, Content-Disposition for non-Latin names.
- Deviation: no Ghostscript/Docker/uv here; compress is pikepdf+Pillow only; Docker files will be untested.
## Progress
## Next step
T8 (frontend scaffold)
## Log
- L1 "podemos proceder en la creacion de este primer MVP presentado, me parece que esta OK, luego hacemos un primer sprint donde te digo que encuentro bien y que encuentro mal, pero tu plan propuesto es correcto"

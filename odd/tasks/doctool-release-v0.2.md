---
feature: doctool-release-v0.2
status: active          # owner: "realiza los 4 puntos ... principalmente el 4 con lo que consideres mas adecuado" (2026-11-09)
lane: L1+
branch: release/v0.2 (= feat/office-module @ bbc1975, which already contains feat/image-module)
tdd: on
audience: owner testing locally on Windows; Docker/Linux later, only if packages are cross-platform
---
# Doctool v0.2 stable candidate
## Goal
A tagged-ready `main` candidate (images + office modules) so the owner can start user tests on their own PC.
## Decisions (owner delegated; criterion 2 verified result, then 5 simplicity)
- D1 pdf2ppt default stays `picture` (already the code default; never looks broken). Single file in v1.
- D2 Macros: .docm/.xlsm/.pptm rejected up front; legacy .doc/.xls/.ppt accepted, macros never run, `macros_removed` warning. Keep as is.
- D3 Sheet selection: free text in v1 (already implemented); checkboxes later.
- D4 `home.subtitle` must not claim "Everything stays on this computer" (false for web deployments; same rule as image-module D8). New copy is accurate for local and hosted use.
- D5 imageclean "what was removed" report and MPO multi-frame: NOT in v0.2 (new features, not stability). Moved to v0.3 backlog; MPO current behaviour is checked in R4 so it is safe, not silent.
- D6 No tag and no merge to `main` here: owner approves (main is FF-able, see handoff).
## Tasks
- [x] R1 Housekeeping: ignore `qa/dl3/` (27 MB generated downloads), commit the two audit scripts - check: `git status` clean
- [x] R2 `home.subtitle` es/en accurate - check: vitest asserting the old claim is gone (fails before)
- [~] R3 Dependency audit: `npm audit`; `pip-audit` only if the owner allows installing it (new install) - check: command output recorded
- [x] R4 MPO / multi-frame behaviour verified (safe rejection or defined result) - check: test or script output
- [x] R5 Full gates on `release/v0.2`: ruff, pytest, tsc, vitest, build, Playwright - check: counts recorded
- [x] R6 Version bump 0.2.0 (pyproject, package.json), cross-platform dependency notes for the later Docker step - check: build + tests green
- [ ] R7 Docs, vault `_project.md`, handoff
## Evidence
- R1 commit "chore(qa)": status clean. R2: vitest failed before, 209 pass after (subtitle es/en no longer says "este equipo / this computer").
- R3: `npm audit` 0 vulnerabilities. `pip-audit` NOT run: not installed, installing needs owner approval.
- R4: real 2-frame MPO is rejected with state `unsupported` (message says "animated", wording imprecise; backlog). Characterization test added (test_image_clean.py), passes before and after: it locks the policy, it does not fix a bug.
- R5: ruff clean; pytest 765 passed (7m09s); tsc ok; build ok; vitest 209; Playwright 43/43.
- R6: 0.2.0 in pyproject, package.json, package-lock, `doctool.__version__`. Cross-platform: all runtime deps (pikepdf, pypdfium2, pillow, lxml, reportlab, img2pdf, pdfplumber, python-docx/pptx, openpyxl) publish manylinux wheels, so Docker is plausible; but pyproject deps are UNPINNED (no lockfile) and the Dockerfile comment claims a Linux run that the office plan says was blocked: reconcile before the Docker step. Local versions: pikepdf 10.17.0, pypdfium2 5.14.0, pillow 13.0.0, lxml 6.1.3.
## v0.3 backlog
imageclean "what was removed" report; MPO wording; Tier B (OCR, PDF/A, compare); QA1 LOW items; pip-audit; pin dependencies; Linux/Docker run.

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
- [ ] R1 Housekeeping: ignore `qa/dl3/` (27 MB generated downloads), commit the two audit scripts - check: `git status` clean
- [ ] R2 `home.subtitle` es/en accurate - check: vitest asserting the old claim is gone (fails before)
- [ ] R3 Dependency audit: `npm audit`; `pip-audit` only if the owner allows installing it (new install) - check: command output recorded
- [ ] R4 MPO / multi-frame behaviour verified (safe rejection or defined result) - check: test or script output
- [ ] R5 Full gates on `release/v0.2`: ruff, pytest, tsc, vitest, build, Playwright - check: counts recorded
- [ ] R6 Version bump 0.2.0 (pyproject, package.json), cross-platform dependency notes for the later Docker step - check: build + tests green
- [ ] R7 Docs, vault `_project.md`, handoff
## Evidence
(filled per task)

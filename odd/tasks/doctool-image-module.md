---
feature: doctool-image-module
status: active          # owner approved 2026-11-02 ("aprobado el plan, solo AVIF opcional, solo usa pillow")
lane: L2
branch: feat/image-module (from main @ 89fde42)
tdd: on
audience: end users (local install from the repo, or a web deployment behind a domain); today only the owner uses it
---
# Doctool image module (v0.3-a)
## Specs (owner's words)
- S1 "solo AVIF opcional, solo usa pillow" - accept: engine is Pillow only (no new dependency, no external binary, no ffmpeg in this module); AVIF is offered only when `PIL.features.check("avif")` is true, never required - check: pytest with AVIF present and with it monkeypatched off
- S2 "realiza el proyecto pensando en un publico final" - accept: every tool has hard limits, clear error messages (es/en), accessible UI, privacy by default (metadata stripped unless asked), safe on untrusted files, no data leaves the machine - check: security-reviewer pass + e2e + a11y checklist
- S3 "un agente que revise la app por si hay posibles bugs y los corrija" - accept: `qa-auditor` agent + gate after each slice, findings fixed through implementer -> tester -> reviewer, never by the auditor - check: `qa/findings.md` per slice
- S4 "servidor en vivo" - accept: API :8000 + Vite HMR :5173 running during the work
## Evidence (verified this session)
- Tool contract `api/doctool/tools/base.py` (Tool: id/title/group/Params/min_files/max_files/accepts/check_input/run; ToolInput(name,data,password), ToolOutput(name,data), ToolError(state,message,retryable)); registered by import in `tools/__init__.py`; pattern `tools/imagepdf.py`; guard `tools/imageutil.py` (MAX_PIXELS 100M, `verify_image`).
- Pillow 13.0.0 on the venv: webp, avif (libavif 1.4.2), jpg, jpg_2000, libtiff; no libimagequant/mozjpeg.
- `process_task` is synchronous and in-memory (`routers/tasks.py:146-214`): fine for images; non-PDF outputs are download-only.
- `pdfimage` (PDF -> images) and `imagepdf` already exist: not rebuilt.
## Decisions (this plan)
- D1 Engine: Pillow only. Rejected: pyvips, oxipng, pngquant, ImageMagick (owner decision; also licences). Criterion 5 simplicity + 1 safety.
- D2 AVIF is feature-detected at import: the `target` enum of the Params only lists formats the install can encode; an install without AVIF simply does not show it.
- D3 Animated inputs (GIF/WebP/APNG with >1 frame) are rejected with a clear message in v0.3-a (no silent frame dropping).
- D4 Privacy default: EXIF/GPS/XMP removed after applying orientation; ICC profile kept (colour fidelity); option `keep_metadata=false` default.
- D5 Never grow: compress returns the original bytes when the result is not smaller.
- D6 New tool group `images` with its own colour token (needs an ADR amending the SPEC one-accent rule, same pattern as `docs/adr-ui-identity.md`); owner can fold it into convert/optimize later.
- D7 Video / GIF -> WebM and the async runner are OUT of this feature (a later feature with L3 review; ffmpeg only as external binary).
- D8 (designer spec `design/image-tools.md`, defaults chosen by the orchestrator, owner may veto): group colour magenta `#c2257f`/`#f07cc0`, `images` ordered last; preset `max` = best quality with the smallest lossless/near-lossless size (never bigger); exact resize keeps aspect unless an explicit `stretch` option is on; a bad file fails the whole task with the file name in the message (task contract has no per-file result); enum values avoid `fit`, `1:1` and numbers (i18n/generic form limits, spec l.52); crop default mode `ratio`; home subtitle must stop claiming "stays on this computer" for web deployments.
## Tasks
- [x] I1 ui-ux-designer: `design/image-tools.md` (group/colour/icons, options UI for the 5 tools, before/after sizes, states, es/en copy, a11y, phone) - accept: spec written, owner confirms 3 decisions
- [x] I2 vertical slice (backend): `api/doctool/tools/imagecore.py` (safe load with orientation, mode handling RGBA/P/CMYK/16-bit, encode per format, format availability, limits) + tool `imageconvert` + tests (bomb, truncated, animated, CMYK, transparency->JPEG, EXIF stripped, AVIF on/off, never-grow n/a) - accept: pytest + ruff green, new tests failed first
- [x] I3 tester (found 3 bugs, fixed in I2b) on I2 (independent): spec gaps and edge cases - accept: `QA: pass`
- [x] I4 backend tools `imagecompress` (presets web/email/max), `imageresize` (fit/exact/percent, no_upscale), `imagecrop` (box/aspect), `imageclean` (metadata strip), one implementer task each reusing imagecore - accept per tool: pytest + ruff
- [x] I5 web: group `images` (GROUP_ORDER, colour tokens, icons, i18n es/en, Dropzone accept, result facts with size before/after), ADR - accept: vitest + tsc + build + e2e per tool
- [x] I6 qa-auditor gate on the live app (`qa/findings.md`), fixes through implementer/tester/reviewer - accept: `QA-AUDIT: clean`
- [x] I7 reviewer (opus) + security-reviewer on `main..feat/image-module`; README/SPEC updated - accept: `VERDICT: pass`, `SECURITY: pass`, Open findings 0
- D8 correction: preset `max` = strongest compression (designer copy "Maximum (smallest file)"), NOT best quality; presets web q82/2560px, email q72/1600px, max q60/1280px. Exact resize may change proportions (stated in its hint); nothing is ever enlarged.
## Tasks added during the work
- [x] I2b align `imageconvert` with design/image-tools.md: param `format` (not `target`), values `jpg|png|webp|avif` (not `jpeg`), `quality`, `background`, `keep_metadata`; fix F-b if the tester confirms it; update tests (after I3 report)
- [x] I4m merge feat/i4a and feat/i4b into feat/image-module (orchestrator), resolve the `__init__.py` imports, run full suite + ruff
## Findings carried to later tasks (orchestrator review of a213280)
- F-a `ToolError` state `unsupported` is new: add to docs/SPEC.md per-file states (line 33) and to web i18n error keys es/en (`too_large` already exists) in I5.
- F-b `keep_metadata` likely loses EXIF when `to_target_mode` converts the image (new object has no exif): tester/reviewer to confirm; fix in imagecore if so.
- F-c Public-facing memory: MAX_PIXELS 100M x RGBA = ~400 MB per decode plus copies; security-reviewer to judge a lower cap for the images tools (e.g. 50M) and a total-per-task cap.
## Out of scope
ffmpeg/video/GIF->WebM, background removal, SVG, batch zip beyond what tasks already do, drag-crop UI (v0.3-b), external binaries, Docker changes.

## Status 2026-11-02
Merged into feat/image-module: imageconvert (hardened), imagecompress, imageresize, imagecrop, imageclean + web group/i18n/result line. Full pytest 478 passed, vitest 133, ruff clean. Pending: I6 qa-auditor findings, then fixes via implementer/tester/reviewer; I7 reviewer + security-reviewer. Review notes still open: F-d (never-grow returns original incl. GPS), F-e (duplicated helpers), F-f (suite 210 s), home.subtitle wording for web deployments, imageclean 'Removed: ...' report needs a backend field, e2e for images flows not yet written.

## Final status 2026-11-02 (branch head 75d4e34)
Verified: pytest 624 (last full run at d411c6d; later commits re-ran 78 targeted tests), vitest 165, Playwright 33/33, ruff and typecheck clean. Independent verdicts on the last candidates: security-reviewer `SECURITY: pass` (0 open, candidate e36d71d), reviewer `VERDICT: pass` (0 open, candidate d411c6d). qa-auditor: 2 sweeps, 11 + 3 findings, all fixed except backlog (IMG-08 focus after result, R2-03 imageclean comparison line) and owner decision IMG-10 (home subtitle). Known residuals (non-blocking): multi-frame MPO phone photos are rejected as animated; AVIF metadata scan is conservative and untested with real AVIF Exif; imageclean lacks a 'what was removed' report (needs a backend field); the test suite takes ~4.5 min.
Ready for the owner to merge feat/image-module into main (not pushed anywhere).

# QA findings: images module (audit 1, 2026-11-02)
Source: `qa-auditor` agent run on the live app (Vite :5173 + API :8000), scripts in `web/qa/`, raw data `qa/audit-*.json`, screenshots `qa/shots/` (not committed). The agent could not write this file (harness refusal), the orchestrator transcribed its report and VERIFIED the items marked [verified].
Contract line: `QA-AUDIT: findings 11` (0 BLOCKER, 1 HIGH, 6 MEDIUM, 4 LOW)

Not covered: functional runs at tablet / short desktop and in dark theme (layout checks did cover them), EXIF stripping and output pixel dimensions through the UI, AVIF, batch per-file errors, screen readers, keyboard-only run of tools other than imagecompress.
Layout/console/network checks passed: home + 5 tools + palette at 3 viewports x 2 themes x 2 languages: no overflow, no unnamed controls, no contrast failures, no console errors. Downloads (png, jpg, webp, zip) correct. Magenta group OK in both themes.

| ID | Sev | Finding | Status |
|---|---|---|---|
| IMG-01 | HIGH | imageconvert: pressing Run with defaults returns 422 `format: Field required`; the select shows a value but `format` has no default in the Pydantic model (spec default `jpg`). [verified with curl `params: {}`] | open |
| IMG-02 | MEDIUM | before/after size line never appears for any image tool (en/es, larger and never-bigger cases too): the line requires `outVersion` (library version) and image outputs have none (`ToolPage.tsx:138-153`). [verified in code] | open |
| IMG-03 | MEDIUM | bad files: raw English `not a supported image` in es for fake/0-byte/huge-pixel files; truncated file shows PDF wording; animated GIF generic message; 201 MB shows English `file too large`. Cause: upload check raises plain ValueError -> 422 string without a state code (`routers/tasks.py:129-132`). | open |
| IMG-04 | MEDIUM | crop mode `box` without width/height says "outside the picture" instead of "enter width and height". | open |
| IMG-05 | MEDIUM | `show_when` not applied: all fields always visible (resize percent+width+height, crop ratio+box, convert quality+background). Cause: image tools declare no `json_schema_extra={"show_when": ...}` (split.py/watermark.py do). [verified in code] | open |
| IMG-06 | MEDIUM | many hints and validation texts stay English in Spanish (only 4 `hints.*` keys exist; Pydantic 422 messages shown raw). | open |
| IMG-07 | MEDIUM | double-click on Run creates two tasks (also true for PDF tools: pre-existing, fix in ToolPage). | open |
| IMG-08 | LOW | focus drops to BODY after a run (same on the PDF tools, pre-existing). | backlog |
| IMG-09 | LOW | dropzone copy for image tools lists GIF/BMP; spec says "JPG, PNG, WebP (still pictures only)". | open |
| IMG-10 | LOW | home subtitle "Everything stays on this computer" is false for a web deployment. | owner decision |
| IMG-11 | LOW | at 1280x480 the Images group and the active item sit below the fold of the scrolling sidebar. | backlog (scroll active item into view) |

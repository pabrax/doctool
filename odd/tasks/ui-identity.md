---
feature: ui-identity
status: active        # approved by owner; executing
lane: L1+
tdd: off
branch: feat/ui-identity   # on top of feat/doctool-mvp (unmerged)
---
# doctool UI identity: color by tool group, real icons, a print-shop voice

## Specs
- S1 "que todos estos desarrollos no se parecen o tienen mas alegria y no se sienten tan planos" — accept: tools are recognizable at a glance by group color and per-tool icon; the home is no longer just a grey library grid — check: screenshots of home, tool page, document page, organizer, palette (T0 vs T7).
- S2 "no tengo lio con que cambie un poco la identidad" — accept: palette/type approved by owner (D1); SPEC deviation recorded as a Decision (D2) — check: `docs/SPEC.md` still says "one accent" at lines 66-69, so a Decisions note must exist before T2.
- S3 (inherited from doctool-mvp) — accept: WCAG 2.1 AA (axe clean on the 5 views), strict CSP unchanged (no external requests), es/en and light/dark/system all work, all existing tests green — check: `npx vitest run`, `npx tsc -b --noEmit`, `npx playwright test`, request log in e2e shows only same-origin.

## Objective
Give doctool a friendly "print shop" identity: ink-on-paper base, one color per tool group, expressive headings, and visible state feedback, while keeping it a calm, fast, local tool.

## Problem
Audit (2026-10-24): palette is neutral + one blue accent (`src/index.css:5-56`); `--font-sans: Inter` is declared at `index.css:71` but no font file is bundled, so users get system fonts; every tool shows the same `FileText` icon (`App.tsx:40`); the home (`LibraryPage.tsx`) is only a library grid with no tool launcher; no animation anywhere.

## Design brief (frontend-design process; reviewed against its defaults list)
- Direction: "Print shop": tidy, tactile, a little playful. Group color works like colored folder tabs. Rejected defaults: cream + terracotta, blue SaaS cards, ALL-CAPS eyebrows, numbered markers.
- Color (light / dark, proposed; derive and contrast-check in T1):
  - paper `#F7F8FA` / graphite `#14161C`; surface `#FFFFFF` / `#1D2029`; ink text `#14172A` / `#ECEEF4`
  - group colors (identity device, via `--group-*` vars): organize cobalt `#3355FF`, optimize jade `#0E9F78`, convert amber `#E39A00`, edit vermilion `#E5484D`, security violet `#7A4DFF`
  - the app accent stays one neutral-ink; only group surfaces carry color.
- Type: headings = Fraunces (soft serif variable, gives the "print" voice), body = Inter. BOTH self-hosted (see Constraints). Tabular numerals for page counts and sizes.
- Layout: home gets a tool launcher on top (tiles grouped by color, per-tool Lucide icon, one-line description) and the library below; tool page gets a colored header band and a larger drop zone; sidebar group headers get a color marker.
- Motion (all with reduced-motion fallbacks): drop zone reacts to drag-over, a result card eases in after processing, organizer thumbnails lift when selected; nothing loops.

## Scope
In: `web/src/index.css`, `web/src/App.tsx`, `web/src/pages/*`, `web/src/components/*`, `web/src/lib/` (new `toolIcons.ts`, group-color helper), `web/public/fonts/` (vendored woff2 + licenses), `docs/SPEC.md` amendment, `docs/` decision note.
Out: API and tool logic, new tools (OCR/Office is v0.2), push/merge, Docker/CI.

## Constraints
- CSP (`api/doctool/main.py:17-27`): `font-src 'self'`, `style-src 'self' 'unsafe-inline'`, `script-src 'self'`. No Google Fonts or CDN. Fonts are vendored as woff2 in `web/public/fonts/` with their OFL licenses (no npm font package, to avoid new supply-chain surface). Downloading the font files is an outward fetch: owner approval first.
- SPEC.md:66-69 says one accent and Lucide only. Lucide stays (per-tool icons are Lucide). "One accent" is amended by D2 (recorded Decision) to "one neutral accent plus group colors".
- Do not break the e2e selectors in `web/e2e/mvp.spec.ts`: accessible names "Run", "Open: alpha.pdf", "Rotate PDF", list "Files", /Version 1/, list "Organize pages", "Delete page: Page 1", "Apply changes", "Open in library", label "Language", /Tema/, `html[data-theme]`, combobox, test id `file-input`. Rename only with the matching test update in the same commit.
- No new runtime npm dependency is planned.
- Skills: `frontend-design`, `web-design-guidelines`, `accessibility`, `webapp-testing`.

## Tasks
- [x] T0 Baseline: create branch; run vitest, tsc, e2e (record counts); screenshots of the 5 views, light + dark, es + en — accept: numbers in evidence, no source change — commit: n/a
- [x] T1 Decision note D2 + vendored fonts + tokens (S2, S3) — accept: Decisions note exists, SPEC amended, Fraunces + Inter load from `/fonts/` with no external request, tokens for both themes, contrast >= 4.5:1 — commit:
- [ ] T2 Shell: brand wordmark, sidebar group color markers, header (S1) — accept: nav roles/labels unchanged; e2e still green — commit:
- [ ] T3 Per-tool icons and group colors: `toolIcons.ts`, used in sidebar, palette and tiles (S1) — accept: every registered tool has an icon and a group color (unit test iterating `/api/v1/tools`) — commit:
- [ ] T4 Home launcher + library (S1) — accept: tiles link to `/tools/:id`; library grid unchanged in behavior; empty state present — commit:
- [ ] T5 Tool page: colored header band, drop zone states, result card (S1, S3) — accept: schema-generated forms still render; `file-input` test id kept; focus visible — commit:
- [ ] T6 Document page and organizer: selection and lift states using group color (S1) — accept: `OrganizerPage` tests and e2e organizer flow pass — commit:
- [ ] T7 Verification (S3) — accept: vitest/tsc/e2e green, axe clean on the 5 views, e2e request log same-origin only, screenshots vs T0, es/en and 3 theme modes checked — commit:

## Delegation
`implementer` per task; T5 and T6 touch disjoint files and can run in parallel after T3. `reviewer` on T7.

## Verification evidence
- T0 (baseline, branch feat/ui-identity from feat/doctool-mvp): `npx vitest run` 5 files / 44 tests passed (first cold run hit 5 timeout errors on a slow machine; rerun clean); `npx tsc -b --noEmit` exit 0; `npm run build` ok (528 kB js); `npx playwright test` 6 passed (1.0m). Screenshots (5 views x light/dark x es/en) in scratchpad `doctool/before/`; request log: no foreign requests.
- T1: fonts Fraunces (latin, full axes, 121 kB) + Inter (latin wght, 48 kB) vendored in `web/public/fonts/` with OFL texts from fontsource 5.3.0 packages (npm pack, not a dependency). `npm run build` ok, `dist/fonts/` has all 5 files; `document.fonts` shows Inter loaded from `/fonts/`, no CSP/failed requests. Contrast computed (script): text/bg 16.7 light, 15.6 dark; muted >= 5.5 both; group `-ink` on surface/soft >= 4.95 light, dark solids >= 5.28 on surfaces; `-fg` on solid >= 4.5 (edit solid darkened to #D6353B for white text, 4.74).

## Progress
Plan only. 0/8 tasks done. Waiting for owner approval of the brief and D2.

## Next step
Owner approves or edits the brief and approves the font download, then T0.

## Log
- Decision: edit group solid changed from brief #E5484D to #D6353B so white text on it passes 4.5:1 (#E5484D+white = 3.9).
- Decision: group colors are exposed through a `data-group` attribute that re-points `--g/--g-fg/--g-ink/--g-soft`; components use `bg-g`, `text-g-ink`, etc., so one wrapper recolors a whole subtree.
- Decision: backend serves woff2 as application/octet-stream (no mimetype for woff2 in the host). Fonts still load (verified); backend is out of scope so left unchanged.
- Decision: ADR written as `docs/adr-ui-identity.md` (docs has no decisions folder).
- L1 "puedes dentro de cada proyecto hacer una propuesta de diseño ... aprovecha las skills para hacer el plan de mejora ... crea un plan para los 3 proyectos"
- Lane/method: ODD (see portfolio-redesign in the Portafolio repo for the shared reasoning).

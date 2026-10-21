---
feature: doctool-planning
status: done
lane: L1+
tdd: off
branch: feat/doctool-planning
---
# doctool: research, stack decision and MVP spec
## Specs
- S1 "revisa en la web, realiza ingenieria inversa al detalle de como funciona [ilovepdf]" — accept: docs/RESEARCH.md documents the task model, tool catalogue, limits and what could not be verified — check: file exists, every claim cites a source or is marked unverified
- S2 "define el stack, la UI, las herramientas que mejor se adecuen" — accept: docs/SPEC.md sections Stack, UI, Engines with rationale and rejected alternatives — check: file exists
- S3 "un spec con todos los cambios y propuestas" — accept: docs/SPEC.md has requirements, API, data model, security, testing, milestones — check: file exists
- S4 "un resumen de cara al usuario ... features ... mas necesarias" — accept: docs/SUMMARY.md prioritized feature list (Must/Should/Later) — check: file exists
- S5 "enfoquemonos unicamente para un primer MVP en documentos PDF" — accept: MVP scope = PDF only, images/Office are later milestones — check: SPEC.md scope section
## Objective
Planning package for doctool, a personal, open-source, non-monetized, iLovePDF-style document toolbox with full local control. No application code in this feature.
## Problem
Owner wants control over documents (create, modify, update, add, remember) without third-party uploads or limits.
## Rationale
Criteria: 1 safety (local, no upload), 3 learning (Python/React stack the owner can maintain), 5 simplicity.
## Scope
In: research, stack, UI direction, spec, user summary. Out: any source code, installing dependencies, git remote/push.
## Constraints
Owner approval required before the build phase starts. Network research is read-only.
## Tasks
- [x] T1 Research iLovePDF behaviour and public API (S1) — accept: docs/RESEARCH.md written
- [x] T2 Research open-source alternatives and engines (S1,S2) — accept: landscape section written
- [x] T3 Write SPEC.md (S2,S3,S5) — accept: all sections present
- [x] T4 Write SUMMARY.md (S4) — accept: prioritized list present
- [x] T5 Owner review and decisions D1-D3 (S2) — accept: owner answers recorded in SPEC.md section 12
## Verification evidence
- Files written; sources are from WebSearch/WebFetch in this session. Browser-level inspection of ilovepdf.com network traffic was NOT done (WebFetch returns text only).
## Progress
T1-T4 done in session 1.
## Next step
Owner reviews docs/SUMMARY.md, answers D1-D3, then plan M0 (scaffold) as a new ODD feature.
## Log
- L1 "para este proyecto quiero que me ayudes a planificar y aterrizar una idea ... herramienta robusta por el estilo de ilovepdf ... enfoquemonos unicamente para un primer MVP en documentos PDF"

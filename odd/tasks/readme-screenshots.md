---
feature: readme-screenshots
status: done
lane: L1+
tdd: off
branch: docs/readme-screenshots
---
# README screenshots (doctool)
## Specs
- S1 "actualizar los readmes, sobretodo las imagenes que son capturas de la app, con playwright" - accept: README images are fresh Playwright captures of the running app, reproducible by script - check: images exist, README links resolve, visual review
## Scope
In: README(s), docs/screenshots/, capture script (outside repo tools dir). Out: app code, dependencies.
## Constraints
Commits authored by owner identity only, no Co-Authored-By. No push without approval (doctool: owner-created repo, push approved).
## Tasks
- [x] T1 Run app and capture screenshots with Playwright (Edge) - accept: PNGs non-empty and reviewed
- [x] T2 Update README(s) to use them, fix stale text - accept: every image link resolves
- [x] T3 Commit on docs/readme-screenshots

# ADR: UI identity - ink-neutral accent plus tool-group colors

Status: accepted (owner approved the direction on 2026-10-24)
Feature: odd/tasks/ui-identity.md

## Context
SPEC section 8 says "neutral palette + one accent". The result was flat and looked like the owner's other projects. The owner asked for a visibly different, more joyful identity and accepts the change.

## Decision (D2)
- The app accent stays one neutral ink (near-black on light, near-white on dark) for primary chrome.
- Color is carried by five tool groups (organize cobalt, optimize jade, convert amber, edit vermilion, security violet), used for group markers, tool icons/tiles, the tool-page header band and the primary action of a tool page.
- Headings use Schibsted Grotesk (newspaper grotesk; replaced Fraunces on 2026-10-25 because the soft serif read as Times New Roman), body uses Inter; both self-hosted from `web/public/fonts/` (SIL OFL), so the strict CSP (`font-src 'self'`) is unchanged.
- Lucide remains the only icon set; each tool gets its own Lucide icon.

## D2 addendum
**D2a (2026-11-02, owner approved the plan; colour and order are defaults the owner may veto):** Tool groups grow from five to six. `images` (magenta) is added for the IMAGE module (convert, compress, resize, crop, clean). The rule is unchanged: the app accent stays one neutral ink; colour is carried only by tool groups, never by chrome. Each group still supplies `-fg/-ink/-soft` tokens verified >= 4.5:1 for text and >= 3:1 for non-text in both themes (now WCAG 2.2 AA; this ADR cites 2.1, same ratios). Group order places `images` last so existing tile positions do not move. Color is never the only signal. SPEC section 8 ("one color per tool group") is amended to "one color per tool group (six)".

Tokens (light / dark): `--images` #c2257f / #f07cc0, `--images-fg` #ffffff / #14161c, `--images-ink` #b01f72 / #f07cc0, `--images-soft` #fce7f3 / #3a1830.

Contrast, computed with the WCAG relative-luminance formula by a script (not by hand):

| Pair | Ratio | Need |
|---|---|---|
| light fg on fill | 5.43:1 | 4.5 |
| light ink on surface #ffffff | 6.39:1 | 4.5 |
| light ink on soft | 5.44:1 | 4.5 |
| light ink on bg #f7f8fa | 6.02:1 | 4.5 |
| light fill vs surface (non-text) | 5.43:1 | 3 |
| dark fg on fill | 7.19:1 | 4.5 |
| dark ink on surface #1d2029 | 6.47:1 | 4.5 |
| dark ink on soft | 6.17:1 | 4.5 |
| dark ink on bg #14161c | 7.19:1 | 4.5 |
| dark fill vs surface (non-text) | 6.47:1 | 3 |

Magenta is the nearest neighbour of vermilion (`--edit`) for colour-blind users; group and tool names stay as text on every tile and header.

## Why / Criterion
Why: group color lets users locate a tool by scanning (like colored folder tabs) and gives the product a personality; the neutral accent keeps it calm. Criterion: user experience first, bounded by WCAG 2.1 AA, keyboard use, reduced motion and the strict CSP.

## Consequences
- Color is never the only signal: group names and tool names stay as text.
- Text on group colors uses per-group `-ink` / `-fg` tokens verified at >= 4.5:1 in both themes.
- SPEC section 8 amended accordingly.

**D2b (2026-11-08, owner approved the office-module plan; colour is a default the owner may veto):** Tool groups grow from six to seven. `office` (teal) is added for the OFFICE module (Word/Excel/PowerPoint/HTML to PDF, PDF to Word/Excel/PowerPoint, OCR, compare, office utilities). Teal sits at hue ~190, the one free gap between jade (optimize, ~160) and cobalt (organize, ~230); the other candidates were rejected as too close to an existing group. The rule is unchanged: the app accent stays neutral ink, color only marks the group.

Tokens (light / dark): `--office` #0e7490 / #5fd0e8, `--office-fg` #ffffff / #14161c, `--office-ink` #0e7490 / #5fd0e8, `--office-soft` #dff3f8 / #12313a. To be added to `web/src/index.css` in task O7, not before.

Contrast, computed with the WCAG relative-luminance formula by a script (not by hand):

| Pair | Light | Dark | Need |
|---|---|---|---|
| fg on fill | 5.36:1 | 10.05:1 | 4.5 |
| ink on surface | 5.36:1 | 9.04:1 | 4.5 |
| ink on soft | 4.67:1 | 7.65:1 | 4.5 |
| ink on bg | 5.04:1 | 10.05:1 | 4.5 |
| fill vs surface (non-text) | 5.36:1 | 9.04:1 | 3 |

Teal is the nearest neighbour of jade for colour-blind users; group and tool names stay as text on every tile and header.

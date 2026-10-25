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

## Why / Criterion
Why: group color lets users locate a tool by scanning (like colored folder tabs) and gives the product a personality; the neutral accent keeps it calm. Criterion: user experience first, bounded by WCAG 2.1 AA, keyboard use, reduced motion and the strict CSP.

## Consequences
- Color is never the only signal: group names and tool names stay as text.
- Text on group colors uses per-group `-ink` / `-fg` tokens verified at >= 4.5:1 in both themes.
- SPEC section 8 amended accordingly.

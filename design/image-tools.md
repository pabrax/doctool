# Image module (group `images`): UI spec

Status: proposal. Platform: web, 390px first. Everything below that names a file was read in this run; contrast numbers were hand-computed (sRGB relative luminance), not tool-verified (`unverified` until re-run with a checker). Backend param names are proposals (Pydantic not read).

## 1. Goal and primary task
A non-technical person with one or more photos/screenshots wants to convert, shrink, resize, crop or clean them, and download the result in under 3 taps after choosing the file. Primary task: drop image, accept sensible defaults, press Run, download.

## 2. Flow (happy path)
1. Home launcher or Ctrl+K -> pick an image tool (`/tools/<id>`, generic `ToolPage`).
2. Drop/select image(s) in `Dropzone` (accepts `image`).
3. File row appears with name and size; options card shows defaults (works with zero edits).
4. Run (`common.run`) -> button shows spinner + "Working..." (existing).
5. Result card: before -> after size, Download. Optional "New task".
Alternate: change an option (visible fields follow `show_when`), then Run.

## 3. Group colour token `images` (magenta, hue ~325)
Pattern from `web/src/index.css`: per group `--x`, `--x-fg`, `--x-ink`, `--x-soft`. Must be added in FOUR places: `:root` (l.41-60), the `@media (prefers-color-scheme: dark)` block (l.80-99), `:root[data-theme="dark"]` (l.119-138), and the two `data-group` rules (l.150-164: add `images` to the selector list and one `[data-group="images"]` line).

| Token | Light | Dark |
|---|---|---|
| --images | #c2257f | #f07cc0 |
| --images-fg | #ffffff | #14161c |
| --images-ink | #b01f72 | #f07cc0 |
| --images-soft | #fce7f3 | #3a1830 |

Contrast (hand-computed, recheck with a tool):
- Light fg on fill: #fff on #c2257f = 5.4:1 (AA text 4.5).
- Light ink on surface #fff = 6.4:1; ink on soft #fce7f3 = 5.4:1.
- Dark fg #14161c on fill #f07cc0 = ~7.2:1; ink #f07cc0 on surface #1d2029 = ~6.5:1; on soft #3a1830 ~6:1 (estimate).
- Non-text (border-l-4 band, icon tile) needs 3:1 vs surface: light 5.4, dark 6.5. OK.
Distinguishability: magenta is the nearest neighbour of vermilion (`--edit` #d6353b) for colour-blind users; the group name and tool name remain visible text on every tile and header (ADR already requires this), so colour is never the only signal.

### ADR text (amend `docs/adr-ui-identity.md`, new section "D2 addendum")
> **D2a (date, owner approved):** Tool groups grow from five to six. `images` (magenta) is added for the IMAGE module (convert, compress, resize, crop, clean). The rule is unchanged: the app accent stays one neutral ink; colour is carried only by tool groups, never by chrome. Each group still supplies `-fg/-ink/-soft` tokens verified >= 4.5:1 in both themes (now WCAG 2.2 AA; the ADR cites 2.1, same ratios). Group order places `images` last so existing tile positions do not move. Color is never the only signal. SPEC section 8 (`docs/SPEC.md:68`, "one color per tool group") amended to "one color per tool group (six)".

## 4. Icons (lucide-react 1.61.0; files confirmed in `web/node_modules/lucide-react/dist/esm/icons/`)
| Tool id | Icon | Why / not clashing with |
|---|---|---|
| imageconvert | `ArrowRightLeft` | format swap; `pdfimage` already uses FileImage |
| imagecompress | `ImageDown` | image + shrink; PDF compress uses Minimize2 |
| imageresize | `Scaling` | dimensions |
| imagecrop | `Crop` | universal |
| imageclean | `ShieldCheck` | privacy; (`BrushCleaning`, `Eraser` also exist but suggest erasing content) |
Add to `TOOL_ICONS` and `GROUPS` in `web/src/lib/toolIcons.ts`, and `GROUP_ORDER` in `web/src/lib/useTools.ts` (both hold the group list: keep in sync). Export names are PascalCase of the file names (`unverified`; compile will confirm).

## 5. Per-tool options
Generic form (`SchemaForm`) supports: boolean, enum -> select, integer/number -> number input, string, `#RRGGBB` pattern -> colour input, `show_when`. Labels: `params.<name>`, option labels: `values.<value>`, hints: `prop.description` (NOT translated, see 5.0). No custom form piece is needed.

### 5.0 Constraints found in the code (must handle)
1. `values.*` is a global namespace. `values.fit` already means "Fit to image" (PDF), so resize mode values must not be `fit`: use `fit_box`, `exact`, `percent`.
2. Numeric enums render as `${v}°` (SchemaForm l.101-102): never use numeric enums.
3. Aspect-ratio enum values must not contain `:` (i18next namespace separator breaks `values.1:1`): use `1-1`, `4-3`, `3-2`, `16-9`; labels carry the colon.
4. `params.quality` is already "JPEG quality" (en l.76): relabel to "Quality" / "Calidad" (check the PDF-to-image form still reads right). `params.format` ("Format") is reusable. `width/height/percent/preset` have no entry in en.ts today; add.
5. Hints come straight from the Pydantic `description` (English only). Needed: in SchemaForm use `t("hints.<toolId>.<name>", {defaultValue: prop.description})`. Small code change; otherwise Spanish users see English hints.
6. AVIF "only when server supports it": backend must omit `avif` from the schema enum when unsupported (tools query is `staleTime: Infinity`, so decide at startup). The UI then needs nothing.

### imageconvert
| Param | Control | Default | EN label / values | ES label / values |
|---|---|---|---|---|
| format | select | `jpg` | Convert to: JPG, PNG, WebP, (AVIF) | Convertir a: JPG, PNG, WebP, (AVIF) |
| quality (show_when format in jpg, webp, avif) | number 1-100 | 85 | Quality | Calidad |
| background (show_when format = jpg; `#RRGGBB`) | colour | #ffffff | Background for transparent areas | Fondo para zonas transparentes |
| keep_metadata | boolean | false | Keep photo info (location, camera) | Conservar datos de la foto (ubicación, cámara) |
Hint format: "JPG works everywhere. WebP is smaller but some old apps cannot open it." / "JPG funciona en todas partes. WebP pesa menos, pero algunos programas antiguos no lo abren."
Title/desc EN: "Convert image" / "Change a picture to JPG, PNG or WebP." ES: "Convertir imagen" / "Cambia una imagen a JPG, PNG o WebP."

### imagecompress
| Param | Control | Default | EN | ES |
|---|---|---|---|---|
| preset | select | `web` | Use: Web (balanced), Email (smaller), Maximum (smallest file) | Uso: Web (equilibrado), Correo (más pequeño), Máxima (el archivo más pequeño) |
Hint EN: "We never return a file bigger than the original." ES: "Nunca te devolvemos un archivo más grande que el original."
Title/desc EN: "Compress image" / "Make photos lighter to share or upload." ES: "Comprimir imagen" / "Haz las fotos más ligeras para enviarlas o subirlas."
Assumption: `max` means strongest compression (see open question 2).

### imageresize
| Param | Control | Default | EN | ES |
|---|---|---|---|---|
| mode | select | `fit_box` | Fit inside a size / Exact size / Percentage | Ajustar dentro de un tamaño / Tamaño exacto / Porcentaje |
| width (show_when fit_box, exact) | number px, >=1 | 1920 | Width (px) | Ancho (px) |
| height (show_when fit_box, exact) | number px, >=1 | empty (fit_box: optional; exact: required) | Height (px) | Alto (px) |
| percent (show_when percent) | number 1-100 | 50 | Percentage | Porcentaje |
Hint EN: "Pictures are never enlarged, only reduced." ES: "Las imágenes nunca se agrandan, solo se reducen."
Title/desc EN: "Resize image" / "Change the width and height of a picture." ES: "Redimensionar imagen" / "Cambia el ancho y el alto de una imagen."

### imagecrop
| Param | Control | Default | EN | ES |
|---|---|---|---|---|
| mode | select | `ratio` | Aspect ratio (centered) / Exact box in pixels | Proporción (centrada) / Recuadro exacto en píxeles |
| ratio (show_when ratio) | select | `1-1` | 1:1 square, 4:3, 3:2, 16:9 | 1:1 cuadrado, 4:3, 3:2, 16:9 |
| x, y, width, height (show_when box) | numbers px | x=0, y=0, others empty | Left, Top, Width, Height (px) | Izquierda, Arriba, Ancho, Alto (px) |
Hint ratio EN: "Keeps the biggest area from the center." ES: "Conserva la zona más grande desde el centro."
Title/desc EN: "Crop image" / "Cut a picture to a shape or a pixel box." ES: "Recortar imagen" / "Recorta una imagen a una proporción o a un recuadro."
Drag-crop is out of scope; with no preview, "box" is hard for non-technical users, hence `ratio` is default.

### imageclean
No fields (form shows only Run). The header description carries the explanation, so no custom piece is needed.
Title/desc EN: "Remove photo info" / "Strips hidden data such as location, camera and date." ES: "Quitar datos de la foto" / "Elimina datos ocultos como ubicación, cámara y fecha."
Note: metadata is stripped by default across all five tools (`keep_metadata` false). The backend must apply EXIF orientation BEFORE stripping, otherwise phone photos come out sideways (`unverified`, backend).

## 6. Screens
Only the generic `ToolPage` is used (header band uses `data-group="images"`; header and Run button pick up the new colours via `g` tokens).
- Purpose: one tool, one file set. Hierarchy: header band (icon, group name "Images", title, description) -> Dropzone -> file list -> Options card -> result.
- Primary action: Run (`Button variant=primary`, group colour). After success: Download.
- Dropzone text: replace `dropzone.image` ("Images (JPG, PNG, WEBP, GIF, BMP)"): EN "Images: JPG, PNG, WebP (still pictures only)" / ES "Imágenes: JPG, PNG, WebP (solo imágenes fijas)". No "From library" button (`acceptsPdf` false, ToolPage l.54), so images do not enter the library via this path: confirm (open question 5).

## 7. Result: before/after and the "never bigger" case
Today the size line only appears for `tool.id === "compress"` (ToolPage l.299). Generalise to a set `{compress, imagecompress, imageresize, imageconvert, imageclean}` (code change for implementer). Reuse `toolPage.smaller` and `toolPage.notSmaller` and `savedPercent`.
- Smaller: "62% smaller: 3.4 MB -> 1.3 MB" (existing string, es "62 % más pequeño").
- Not smaller, imagecompress (the "never bigger" case): this is a success, not an error, with neutral styling (no danger colour). New key `toolPage.imageKept`: EN "This picture was already as light as it gets, so we kept it as it was: {{after}}." ES "Esta imagen ya era lo más ligera posible, así que la dejamos como estaba: {{after}}." Download still offered (file equals original).
- Larger, imageconvert/imageresize (allowed): new key `toolPage.larger`: EN "{{pct}}% larger: {{before}} -> {{after}}. This is normal when converting to PNG." ES "{{pct}} % más grande: {{before}} → {{after}}. Es normal al convertir a PNG." Plain text, `text-muted`, no warning icon.
- imageclean: if the backend reports what it found: EN "Removed: location, camera, date." / "No hidden data found." ES "Eliminado: ubicación, cámara, fecha." / "No se encontraron datos ocultos." (needs backend field, open question 4).
- Format: `tabular` figures, arrow glyph as existing. Single file only (ToolPage shows size only when `outputs.length === 1`); multi-file shows "{{count}} files created" + ZIP.

## 8. States
| State | Behaviour |
|---|---|
| Empty | Dropzone full size + `toolPage.noFiles`. Options visible with defaults; Run disabled (`missing > 0`), hint "Add 1 more file to continue." (existing `needMore`). |
| Loading | Run shows `Loader2` + "Working..." (existing); button disabled. Spinner uses `animate-spin`: the global reduced-motion rule shortens it to ~0 (index.css l.244-251); the text label keeps meaning. `aria-live="polite"` region already wraps results. |
| Error: animated image | `role="alert"`. New `errors.animated`: EN "Animated images are not supported. Use a still picture (this file has several frames)." ES "Las imágenes animadas no se admiten. Usa una imagen fija (este archivo tiene varios fotogramas)." Names the file when several were added (open question 3). |
| Error: not an image | New `errors.not_image`: EN "This file is not a picture we can read. Try JPG, PNG or WebP." ES "Este archivo no es una imagen que podamos leer. Prueba con JPG, PNG o WebP." The Dropzone currently shows `errors.damaged` ("damaged or not a valid document") for rejected files, which is wrong for images: add `dropzone.rejectedImage`. |
| Error: too large | Existing `errors.too_large` says "file or page"; add `errors.too_large_image`: EN "This picture is too large to process. Try a smaller one." ES "Esta imagen es demasiado grande. Prueba con una más pequeña." Backend limit must be stated in the hint (value unknown, `NEEDS: limit`). |
| Error: crop box outside image / empty required size | New `errors.out_of_image`: EN "The crop area is outside the picture." ES "El recuadro queda fuera de la imagen." (existing `out_of_range` mentions pages). `errors.invalid` for missing width/height. |
| Error: AVIF | Not reachable (option absent). |
| Success | Existing result card (`border-ok/50`, "Done", Download in group colour). |
| Disabled | Run disabled with no file or while pending; number inputs hidden (not disabled) by `show_when`, so no greyed fields. |
Errors keep the file and options so the user can fix and press "Retry"/Run again.

## 9. Keyboard order and focus
Skip link -> header nav -> (page) Dropzone "Select files" -> file row controls (remove, move) -> options fields in DOM order (select -> numbers -> colour -> checkbox) -> Run -> (after success) Download link -> Open in library -> "Use result in another tool" select -> "New task". Enter in a number field submits the form (form `onSubmit`). Focus stays on Run after success (ToolPage l.143-146) so "run again" is one key; result announced by the live region. "New task" moves focus to `#main`. Focus ring: existing `:focus-visible` 2px `--ring`; ring vs group fill needs 3:1 (cobalt/ring #3355ff on white 5.7 approx; dark #8aa2ff). Labels: every field has a `<label htmlFor>`; hints via `aria-describedby` (SchemaForm). Touch targets: buttons `min-h-10` (40px), checkbox is 16px (`h-4 w-4`) but its label is clickable; WCAG 2.2 AA target size minimum 24px passes only via the label row, so make the label row `min-h-6` (code note). Reduced motion: no new animation introduced.

## 10. Phone layout (390px)
`ToolPage` stacks: header band (icon 56px + text), Dropzone (`py-14` full, compact when a file is set), file list, Options card (full width, single column), Run full width, result below (scrolls into view if hidden). Number fields stack one per row (no side-by-side width/height) to keep inputs >= 44px wide with `inputmode="numeric"` (add; currently `type=number` only). Use the OS file picker (`accept="image/*"` opens Photos on phones). Resize/crop have 4 fields in box mode: still one column, ~5 screens-heights is not reached (fits ~1.5 screens).

## 11. Ctrl+K palette and home launcher with 17 tools / 6 groups
- Launcher (`ToolLauncher.tsx`): tiles flow by `sortByGroup`; with `images` last, existing PDF tiles keep their positions, five new tiles append (2 columns on phone: 9 rows, 3 more than now; the "Show descriptions" toggle still applies). Each tile already shows the group name in text. Recommend a heading is NOT added to keep the component unchanged; if scanning becomes slow, add group filter chips (open question 6).
- Home copy mentions PDFs only: `home.title` "What shall we do with your PDFs?" -> "What shall we do with your files?" / "¿Qué hacemos con tus archivos?"; subtitle "Everything stays on this computer." needs checking for the web deployment (open question 7).
- Palette (`CommandPalette.tsx`): items are filtered by `value = "${title} ${id}"`; typing "compress" matches both "Compress PDF" and "Compress image", ordered by group (images last). Titles must contain the word "image"/"imagen" (done above). Add cmdk `keywords` (photo, foto, jpg, png, exif, gps, privacy, privacidad, tamaño, peso) so non-technical wording finds tools. 22 rows in a 50vh list scroll; group label shown right-aligned, so "Images" appears on each row. Palette is keyboard-only, so phones depend on the launcher.
- i18n: `groups.images` = "Images" / "Imágenes"; `tools.<id>` entries for all five.

## 12. Accessibility summary (WCAG 2.2 AA)
Contrast numbers in section 3; errors use `role="alert"` plus icon plus text (not colour alone); `notSmaller`/`larger` info is plain text; no time limits; no drag-only interaction (drag-crop excluded; Dropzone has a button); target size note in section 9; reduced motion respected by existing global rule.

## 13. Open questions for the owner
1. Group colour: magenta `#c2257f` and `images` last in order: OK? (Alternative: teal; closer to jade.)
2. Preset `max`: strongest compression or highest quality? Copy depends on it.
3. Several files at once: does one animated/invalid file fail the whole batch or only that file? (Recommend per-file results; ToolPage currently shows one error for the task.)
4. Can imageclean return what it removed ("location, camera") or "nothing found"? Trust-critical.
5. Are image outputs stored in the library (`outVersion`, "Open in library", "Use result in another tool" currently lists only non-image tools, ToolPage l.338) and can results chain image -> image (nextSteps not read)?
6. Is `exact` resize allowed to distort the picture, or does it crop? (No-upscale also needs a rule when exact is larger than the original.)
7. Web deployment: "Everything stays on this computer" (`home.subtitle`) is false for a hosted server. Needs different copy, `NEEDS: deployment wording`.
8. Max upload size/pixels (`NEEDS: limit`) for the too-large message.
9. CSP and thumbnails: a before-preview needs `img-src blob:` (CSP not read, `unverified`); worthwhile for crop.

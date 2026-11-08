# Office module (group `office`): UI spec

Status: proposal (task O2). Platform: web, 390px first. Files read in this run: `odd/tasks/doctool-office-module.md`, `design/image-tools.md`, `docs/adr-ui-identity.md` (D2b), `docs/SPEC.md` s.8, `web/src/lib/toolIcons.ts`, `web/src/lib/useTools.ts`, `web/src/lib/types.ts`, `web/src/lib/errors.ts`, `web/src/pages/ToolPage.tsx`, `web/src/components/{Dropzone,SchemaForm,ToolLauncher,CommandPalette}.tsx`, `web/src/i18n/en.ts` (es.ts, index.css, FileList, Button, nextSteps.ts, App.tsx body NOT read: marked `unverified`). Icon existence was confirmed by listing `web/node_modules/lucide-react/dist/esm/icons/*.mjs`. Contrast figures are copied from the ADR (script-computed there), not recomputed here. Backend field and param names are proposals (Pydantic not read). `NEEDS:` = value I will not guess.

## 1. Goal and primary task
A non-technical person has a Word/Excel/PowerPoint/HTML file and needs a PDF (to send or print), or has a PDF and needs something editable. Primary task: drop file, accept defaults, Run, download, in 3 taps after choosing the file. The module must never fail silently or look frozen: the engine (LibreOffice) is slow, single-lane and may be absent.

## 2. Flow (happy path first)
1. Home launcher, sidebar group "Office" or Ctrl+K -> pick tool (`/tools/<id>`, generic `ToolPage`; no custom page needed).
2. Read the one-line header description; for `pdf2*` tools read the quality note (shown above the Dropzone, section 6).
3. Drop/select one file in `Dropzone` (extension list per tool, section 4).
4. File row shows name and size; options card shows defaults (zero edits must work).
5. Run -> button shows spinner + "Working..." and a progress status line appears (section 8.3).
6. Result card: output name, size/pages, warnings list (if any), Download. Optional "Open in library" (PDF outputs only), "New task".
Alternates: change options then Run; engine missing (8.1) -> tool page explains, Run disabled; busy (8.2) -> "Try again"; error -> alert, files and options kept.

## 3. Group token `office` (teal, hue ~190; ADR D2b)
Tokens exist only in the ADR; to be added in `web/src/index.css` in task O7 in the same four places as `images` (`:root`, `prefers-color-scheme: dark`, `[data-theme="dark"]`, the `data-group` selector list + one `[data-group="office"]` line; line numbers per image-tools.md, `unverified` now).
| Token | Light | Dark |
|---|---|---|
| --office | #0e7490 | #5fd0e8 |
| --office-fg | #ffffff | #14161c |
| --office-ink | #0e7490 | #5fd0e8 |
| --office-soft | #dff3f8 | #12313a |
Contrast (ADR, script-computed): fg on fill 5.36 / 10.05; ink on surface 5.36 / 9.04; ink on soft 4.67 / 7.65 (tight in light: keep `g-ink` text >= 12px semibold only on `g-soft`, as ToolPage l.221 already does); ink on bg 5.04 / 10.05; fill vs surface (non-text) 5.36 / 9.04 (needs 3). Teal is nearest to jade (optimize) for colour-blind users; group and tool name stay as text on every tile/header. No warning colour token was found in the files read: warnings use `text-muted`/`text` + icon + words (never colour alone); `NEEDS: --warn token?` only if the owner wants amber.

## 4. Icons and file types (lucide-react; all confirmed as files; none is in `TOOL_ICONS`)
| Tool id | Icon (export) | Dropzone accepts | Max files |
|---|---|---|---|
| word2pdf | `FileType` | .docx .doc .odt .rtf .txt | 1 |
| excel2pdf | `FileSpreadsheet` | .xlsx .xls .ods .csv | 1 |
| ppt2pdf | `Presentation` | .pptx .ppt .odp | 1 |
| pdf2word | `FilePenLine` | .pdf | 1 |
| pdf2excel | `Table2` | .pdf | 1 |
| pdf2ppt | `FileChartColumn` | .pdf | 1 |
| html2pdf | `CodeXml` | .html .htm (one file) | 1 |
Single file in v1 (batch is a Tier B slot, section 11). Export names are PascalCase of file names (`unverified`; `tsc` confirms; the `Table2` file is `table-2.mjs`). Alternatives that exist if one reads badly: `Sheet`, `FileCode`, `BookOpenText`, `Table`.
Add to `TOOL_ICONS`, `GROUPS` (`toolIcons.ts`) and `GROUP_ORDER` (`useTools.ts`; `App.tsx` l.40 iterates it for the sidebar), keep in sync.

## 5. Per-tool options
Generic `SchemaForm` supports boolean, enum -> select, integer/number, string, `show_when`; hints come from `hints.<toolId>.<name>` (SchemaForm l.63, already translated, falls back to Pydantic `description`). Constraints from the code, honoured below: `params.*` and `values.*` are global namespaces, so names are unique per meaning (`fidelity`, `table_layout`, `slide_content`, `handout` instead of generic `layout`/`mode`); numeric enums render as `N°` (l.101) so all enums are strings; enum values contain no `:`. Reused existing labels: `params.page_size` ("Page size"), `params.orientation` ("Orientation") with existing values `auto/portrait/landscape`, `params.pages` ("Pages"), `params.dpi` ("Resolution (dpi)"). Values `a4`, `letter` fall back to humanize ("A4", "Letter") so they need no key.

### word2pdf (minimal)
| Param | Control | Default | show_when | EN label / help | ES label / help |
|---|---|---|---|---|---|
| page_size | select: original, a4, letter | `original` | always | Page size / "Keeps the size set in the document. Change it only if the receiver needs A4 or Letter." | Tamaño de página / "Mantiene el tamaño del documento. Cámbialo solo si te piden A4 o Carta." |
Values: `original` "Keep the document's size" / "Mantener el tamaño del documento"; a4 "A4"; letter "Letter" / "Carta" (add `values.letter` for es).
Title/desc EN "Word to PDF" / "Convert Word, ODT, RTF or text documents to PDF." ES "Word a PDF" / "Convierte documentos Word, ODT, RTF o de texto a PDF."
Result: `<name>.pdf`, "N pages · size". Warnings possible: font_substituted, macros_removed (legacy .doc), external_links_blocked.

### excel2pdf
| Param | Control | Default | show_when | EN label / help | ES label / help |
|---|---|---|---|---|---|
| sheets | text, optional | empty = all | always | Sheets to include / "Sheet names or numbers separated by commas, for example 1,3 or Summary. Leave empty for all sheets. Hidden sheets are skipped." | Hojas a incluir / "Nombres o números de hoja separados por comas, por ejemplo 1,3 o Resumen. Vacío = todas. Las hojas ocultas se omiten." |
| orientation | select: auto, portrait, landscape | `auto` | always | Orientation / "Auto picks landscape for wide sheets." | Orientación / "Automática elige horizontal para hojas anchas." |
| fit_width | boolean | true | always | Fit columns to the page width / "Shrinks wide sheets so no column is cut off to another page." | Ajustar las columnas al ancho de la página / "Reduce las hojas anchas para que ninguna columna pase a otra página." |
| fit_sheet | boolean | false | always | Put each sheet on one page / "Each sheet becomes a single page. Large sheets get very small text." | Cada hoja en una sola página / "Cada hoja ocupa una página. Las hojas grandes quedan con letra muy pequeña." |
Note: `fit_sheet` on implies `fit_width`; when on, disable nothing but explain in help (no hidden coupling). CSV: delimiter/encoding auto-detected; no option in v1.
Title/desc EN "Excel to PDF" / "Turn spreadsheets (XLSX, XLS, ODS, CSV) into a PDF." ES "Excel a PDF" / "Convierte hojas de cálculo (XLSX, XLS, ODS, CSV) en PDF."
Result: `<name>.pdf`, "N pages · size", plus `{{count}} sheets converted` (`toolPage.sheetsDone`: "{{count}} sheets converted" / "{{count}} hojas convertidas"). Sheet names are unknown before upload, hence free text (open decision 4).

### ppt2pdf
| Param | Control | Default | show_when | EN label / help | ES label / help |
|---|---|---|---|---|---|
| handout | select: slides, h2, h3, h4, h6, h9 | `slides` | always | Slides per page / "One slide per page is the normal PDF. Handouts fit several small slides on each page for printing." | Diapositivas por página / "Una por página es el PDF normal. Los folletos juntan varias diapositivas pequeñas por página para imprimir." |
| include_notes | boolean | false | handout in slides | Include speaker notes / "Adds each slide's notes under it." | Incluir las notas del orador / "Añade las notas de cada diapositiva debajo de ella." |
| include_hidden | boolean | false | always | Include hidden slides / "Hidden slides are skipped unless you tick this." | Incluir diapositivas ocultas / "Las diapositivas ocultas se omiten salvo que marques esto." |
Values: slides "One slide per page" / "Una diapositiva por página"; h2 "Handout: 2 per page" / "Folleto: 2 por página"; h3 "3 per page"/"3 por página"; h4 "4"; h6 "6"; h9 "9" (same pattern, "Handout:" / "Folleto:" prefix).
Title/desc EN "PowerPoint to PDF" / "Turn presentations into a PDF, as slides or handouts." ES "PowerPoint a PDF" / "Convierte presentaciones en PDF, como diapositivas o en folletos."
Result: `<name>.pdf`, "N pages · size". Warnings: font_substituted, hidden_skipped, macros_removed (legacy .ppt), external_links_blocked (linked media).

### pdf2word (engine decided by S2: own extractor, no LibreOffice needed in default mode)
| Param | Control | Default | show_when | EN label / help | ES label / help |
|---|---|---|---|---|---|
| fidelity | select: editable, keep_look | `editable` | always | Result type / "Editable text flows like a normal Word document. Keep the look follows the page more closely but is harder to edit." | Tipo de resultado / "El texto editable fluye como un documento Word normal. Mantener el aspecto sigue más la página pero es más difícil de editar." |
| include_images | boolean | true | always | Include pictures / "Pictures that can be extracted are placed in the document." | Incluir imágenes / "Las imágenes que se puedan extraer se colocan en el documento." |
Values: editable "Editable text (recommended)" / "Texto editable (recomendado)"; keep_look "Keep the look (harder to edit)" / "Mantener el aspecto (más difícil de editar)". `keep_look` needs LibreOffice: omit it from the schema enum when the engine is missing (AVIF pattern in image-tools.md 5.0.6; `staleTime: Infinity`, `useTools.ts` l.19, so decide at startup).
Title/desc EN "PDF to Word" / "Make an editable Word copy of a PDF." ES "PDF a Word" / "Crea una copia editable en Word de un PDF."
Quality note (before running, section 6): EN "Reflowed editable text and real tables, not pixel-perfect. Pictures and some styles may be missing, and the layout can change. Check the result before you send it." ES "Texto editable que se reajusta y tablas reales, no una copia idéntica. Pueden faltar imágenes y estilos, y la maquetación puede cambiar. Revisa el resultado antes de enviarlo."
Result: `<name>.docx` (not in library, like images: download only), size, warnings: no_text_layer (page list), images_skipped.

### pdf2excel
| Param | Control | Default | show_when | EN label / help | ES label / help |
|---|---|---|---|---|---|
| table_layout | select: per_sheet, one_sheet | `per_sheet` | always | Put tables / "One table per sheet keeps each table clean. All tables on one sheet stacks them top to bottom." | Colocar las tablas / "Una tabla por hoja mantiene cada tabla limpia. Todas en una hoja las apila de arriba abajo." |
| pages | text, optional | empty = all | always | Pages / "Pages to search for tables, for example 1-3, 5. Leave empty for all pages." | Páginas / "Páginas donde buscar tablas, por ejemplo 1-3, 5. Vacío = todas." |
Values: per_sheet "One table per sheet" / "Una tabla por hoja"; one_sheet "All tables on one sheet" / "Todas las tablas en una hoja".
Title/desc EN "PDF to Excel" / "Pull the tables of a PDF into a spreadsheet." ES "PDF a Excel" / "Pasa las tablas de un PDF a una hoja de cálculo."
Quality note: EN "Finds real tables and puts each value in its own cell. Tables without clear lines, merged cells and tables that continue on the next page may come out wrong. Pictures and styles are not carried over." ES "Encuentra tablas reales y coloca cada valor en su propia celda. Las tablas sin líneas claras, las celdas combinadas y las tablas que siguen en la página siguiente pueden salir mal. No se conservan imágenes ni estilos."
Result: `<name>.xlsx`, size, plus `toolPage.tablesFound`: EN "{{count}} tables found on {{pages}} pages" / ES "{{count}} tablas encontradas en {{pages}} páginas". Zero tables = error `no_tables` (never an empty workbook).

### pdf2ppt
| Param | Control | Default | show_when | EN label / help | ES label / help |
|---|---|---|---|---|---|
| slide_content | select: picture, picture_text | `picture` | always | Slide content / "Picture looks exactly like the page but cannot be edited. Picture and text also adds the page text behind the picture so it can be searched and copied." | Contenido de la diapositiva / "Imagen se ve igual que la página pero no se puede editar. Imagen y texto añade además el texto de la página detrás de la imagen, para buscar y copiar." |
| dpi | number 72-300 | 150 | slide_content in picture, picture_text | Resolution (dpi) (existing key) / "Higher is sharper but makes a bigger file." | (existing es) / "Más alto es más nítido pero el archivo pesa más." |
Values: picture "Page picture" / "Imagen de la página"; picture_text "Picture and text" / "Imagen y texto".
Title/desc EN "PDF to PowerPoint" / "Make a presentation with one slide per PDF page." ES "PDF a PowerPoint" / "Crea una presentación con una diapositiva por página del PDF."
Quality note: EN "One slide per page. By default each slide is a picture of the page, so it looks the same but its text is not editable. Fonts and effects are not rebuilt." ES "Una diapositiva por página. Por defecto cada diapositiva es una imagen de la página: se ve igual, pero su texto no se puede editar. No se reconstruyen fuentes ni efectos."
Result: `<name>.pptx` (download only), size, "N slides" (`toolPage.slidesDone`: "{{count}} slides" / "{{count}} diapositivas").

### html2pdf
| Param | Control | Default | show_when | EN label / help | ES label / help |
|---|---|---|---|---|---|
| page_size | select: a4, letter | `a4` | always | Page size (existing key) / "Paper size of the PDF." | (existing es) / "Tamaño de papel del PDF." |
| orientation | select: auto, portrait, landscape | `auto` | always | Orientation (existing key) | (existing es) |
| print_backgrounds | boolean | true | always | Print background colors and images / "Turn off to save ink when printing." | Imprimir colores e imágenes de fondo / "Desactívalo para ahorrar tinta al imprimir." |
Title/desc EN "HTML to PDF" / "Print a saved web page (HTML file) as PDF. Nothing is downloaded from the internet." ES "HTML a PDF" / "Imprime una página web guardada (archivo HTML) como PDF. No se descarga nada de internet."
Help line on the page (hints.html2pdf.page_size is not the place; put it in the description above): pictures and styles that live in other files or online are not loaded (warning external_links_blocked: "{{count}} outside files (pictures, styles) were not loaded, so the page may look plainer."). No URL field, by design (SSRF).
Engine assumption: LibreOffice renders HTML; `NEEDS: confirm engine`. If it is not LibreOffice, html2pdf drops out of the engine-missing group.

## 6. Screens (generic `ToolPage`; header band `data-group="office"`)
Hierarchy: header band (icon, "Office", title, description) -> [quality note, pdf2* only] -> [engine banner, if missing] -> Dropzone -> file list -> Options card (right column >= lg, stacked on phone) -> progress status -> result/alert.
- Primary action: Run (`Button variant=primary`, group colour). After success: Download.
- Quality note (contract 5): new optional i18n key `tools.<id>.note`; ToolPage renders it full width between header and the grid when present: `role="note"`, `Info` icon (lucide name `unverified`; fallback `AlertCircle`, already imported), border-l neutral on `surface-2`, text colour `text` (not muted), always visible, not dismissible, not a tooltip. Seen before Dropzone on desktop and phone, so it is read before the user spends time. Same pattern is reusable for ocr/pdfa later.
- Header uses `tools.<id>.description` (one sentence); the note carries the caveat.

## 7. Result display
Extends the existing result card (ToolPage l.328-405).
- Order: title -> output file name -> "pages · size" (or sheets/tables/slides stat) -> warnings list -> actions. Warnings sit BEFORE the Download button so they are read first.
- Output name: input base name + new extension (`report.docx` -> `report.pdf`); backend supplies it; shown with `break-all` on phone.
- Size line: no "x% smaller" (different format; `SIZE_LINE_TOOLS` l.35 untouched). Show `formatBytes` and pages (`outVersion.pages` for PDFs). DOCX/XLSX/PPTX outputs have no library version (like images, l.158), so size comes from the task file; "Open in library" and "Use result in another tool" are hidden for them.
- Title: `toolPage.resultTitle` "Done" when no warnings; with warnings `toolPage.resultWarn_one/_other` "Done, with {{count}} heads-up" / "Hecho, con {{count}} aviso" (_other "avisos"). Still a success (green check): the file exists and is valid.
- Warnings list (contract 4): `<ul aria-labelledby="warn-h">` under `<h3 id="warn-h">` "Check these things" / "Revisa estas cosas"; each `<li>`: `TriangleAlert` icon (name `unverified`) + sentence + optional action link. Data model proposal (`NEEDS: backend`): `Task.warnings: {code: string, params?: Record<string, unknown>, file?: string, action?: {tool: string}}[]`. `file` is reserved for batch; `action.tool` for OCR. Unknown codes fall back to `warnings.generic` "Something may look different from the original." / "Algo puede verse distinto del original."
| code | EN | ES |
|---|---|---|
| font_substituted | Some fonts are not installed here, so similar ones were used: {{fonts}}. Line breaks and the page count may differ from the original. | Algunas fuentes no están instaladas aquí y se usaron otras parecidas: {{fonts}}. Los saltos de línea y el número de páginas pueden variar. |
| macros_removed | This file contained macros. They were not run and are not in the result. | Este archivo contenía macros. No se ejecutaron y no están en el resultado. |
| external_links_blocked | {{count}} links to outside content (pictures, data, files) were not loaded. Those parts may be empty. | No se cargaron {{count}} enlaces a contenido externo (imágenes, datos, archivos). Esas partes pueden aparecer vacías. |
| hidden_skipped | {{count}} hidden slides or sheets were skipped. | Se omitieron {{count}} diapositivas u hojas ocultas. |
| no_text_layer (some pages) | Pages {{pages}} look scanned: they are pictures with no text, so nothing could be converted from them. Text recognition (OCR) will be able to read them. | Las páginas {{pages}} parecen escaneadas: son imágenes sin texto, así que no se pudo convertir nada de ellas. El reconocimiento de texto (OCR) podrá leerlas. |
| images_skipped | {{count}} pictures could not be carried over. | No se pudieron pasar {{count}} imágenes. |
When `action.tool = "ocr"` exists in the tool list, add a link "Open OCR" / "Abrir OCR"; otherwise omit the link (no dead link). A PDF with no text on ANY page is an error (`no_text`, section 8.6), not a warning.

## 8. Contracts and states
### 8.1 Engine missing (contract 1)
- Backend: `GET /tools` adds `available: boolean` and `requires: string[]` (e.g. `["libreoffice"]`; reused later by ocr/pdfa with `tesseract`/`ghostscript`) to each tool. `Tool` in `types.ts` gains both (`NEEDS: backend`). Detection at startup (`DOCTOOL_SOFFICE` / PATH / default dir per plan).
- Affected: word2pdf, excel2pdf, ppt2pdf, html2pdf. pdf2word/pdf2excel/pdf2ppt stay available (own extractor); only `fidelity=keep_look` disappears.
- Tools stay visible everywhere (sidebar, launcher, palette); never removed.
- Tool page (`/tools/<id>` still opens, no redirect): banner above the Dropzone, `role="status"`, one line: EN "LibreOffice is not available here, so this tool is off. How to set it up" (link) / ES "LibreOffice no está disponible aquí, así que esta herramienta está desactivada. Cómo configurarlo". Link target `docs/office-setup.md` (`NEEDS: path`, created in O11), opens in the same tab, link `min-h-6`.
- Dropzone disabled (new `disabled` prop: not clickable, `aria-disabled`, picker button `disabled`), Run `disabled` (existing `disabled={!canRun}`; add `engineOk` to `canRun`); the options form stays visible with defaults.
- Launcher tile: stays a link; adds text badge "Needs LibreOffice" / "Requiere LibreOffice" under the group name (text, not colour only), title keeps 4.5:1 text colour (not a faded disabled look; use a dashed left border + badge). Palette row: same badge right-aligned replacing nothing; row still selectable and opens the page.
- Race (engine disappears after start): backend state `engine_missing` -> same sentence as an alert `errors.engine_missing`.

### 8.2 Busy (contract 2)
- 503 with state `busy` (one LibreOffice job at a time). `errors.busy` exists ("The server is busy right now. Wait a moment and press Run again."). For office tools override with `errors.busy_office`: EN "Another document is being converted right now. Yours was not started. Try again in a few seconds." ES "Se está convirtiendo otro documento ahora mismo. El tuyo no se ha iniciado. Vuelve a intentarlo en unos segundos." (key chosen via an `OFFICE_TOOLS` list in `errors.ts`, same mechanism as `IMAGE_STATE_KEY` l.8-12).
- Retry affordance: after a busy error the Run button label becomes `common.retry` ("Retry"/"Reintentar"; the code already swaps to Retry for password, ToolPage l.306: extend the condition). Files and options are kept (`onError` does not clear them). No auto-retry loop in v1 (avoids surprise uploads); `NEEDS: owner` only if wanted.
- Idempotent: the task is deleted on failure (l.115), so retry creates a clean task.

### 8.3 Progress and cold start (contract 3)
`process` is synchronous: the request stays open for 2-30 s (up to ~25 s on the first conversion after start). No percentages are shown (none are real).
- Run button: existing `Loader2` + "Working..." (spinner stops under reduced motion, text remains).
- New status line under the form, appears at once while `run.isPending`, `role="status"` `aria-live="polite"`; text changes by elapsed time, announced only on stage changes (not every second):
| Elapsed | EN | ES |
|---|---|---|
| 0-4 s | Converting your document... | Convirtiendo tu documento... |
| 4-12 s | Still working. Conversions usually take a few seconds. | Sigue trabajando. Las conversiones suelen tardar unos segundos. |
| 12-40 s | Still working. The first conversion after doctool starts can take up to 30 seconds. Please keep this page open. | Sigue trabajando. La primera conversión tras iniciar doctool puede tardar hasta 30 segundos. Mantén esta página abierta. |
| over 40 s | Still working. Large files can take up to a minute. | Sigue trabajando. Los archivos grandes pueden tardar hasta un minuto. |
A visible elapsed counter ("0:12", `tabular`, `aria-hidden`) proves the page is alive; thresholds are `NEEDS: align with the backend timeout (plan default 60 s)`. pdf2* tools use only the first two rows' wording (no LibreOffice cold start) unless `keep_look`.
- Timeout error `errors.timeout`: EN "This took too long and was stopped. Try again, or use a smaller file." ES "Tardó demasiado y se detuvo. Inténtalo de nuevo o usa un archivo más pequeño."
- Cancel button: not in v1 (would need request abort + process kill; `NEEDS: backend`). Navigating away aborts the client request only.

### 8.4 Macro-enabled files (contract 6)
`.docm .xlsm .pptm .dotm .xltm .potm` are not in the accept lists. The Dropzone (today: counts only, `errors.damaged` text, l.111-115) must name the reason and the files:
- `dropzone.rejectedMacro`: EN "{{names}}: files with macros (.docm, .xlsm, .pptm) are not accepted because macros can hide harmful code. Open it in Office, save a copy as .docx, .xlsx or .pptx, and add that copy." ES "{{names}}: no se aceptan archivos con macros (.docm, .xlsm, .pptm) porque las macros pueden esconder código dañino. Ábrelo en Office, guarda una copia como .docx, .xlsx o .pptx y añade esa copia."
- Names: first 2, then "and {{n}} more"; `role="alert"`, icon + text.
- Backend double check (renamed file that holds `vbaProject.bin`): `errors.macro_file` same sentence without names.
- Legacy .doc/.xls/.ppt can also hold macros: they are accepted, macros never run, warning `macros_removed` when present (consistency question: open decision 3).

### 8.5 Password-protected office files (contract 7)
- v1 behaviour: reject with `errors.office_encrypted`: EN "This file is protected with a password and cannot be converted. Remove the password in Word, Excel or PowerPoint, save, and add the file again." ES "Este archivo está protegido con contraseña y no se puede convertir. Quita la contraseña en Word, Excel o PowerPoint, guarda y vuelve a añadirlo."
- The existing password UI (FileList field, `needPassword`) is PDF-only: ToolPage l.130 keys on `file.type === "application/pdf"`. Office files must NOT trigger it in v1, so the state name must differ from `wrong_password` (use `office_encrypted`). For pdf2* tools, encrypted PDFs keep the existing flow unchanged (heading `toolPage.passwordNeeded`, field per file).
- Later (Tier C `msoffcrypto-tool`): switch to the PDF flow by emitting `wrong_password` and extending l.130 to office extensions.

### 8.6 Errors, limits, empty (contract 8)
All errors: `role="alert"` + `AlertCircle` + text, file and options kept (existing l.317-327). `errorText` today passes only `max`; add generic `err.params` pass-through (ApiError reads `state/message/file/field` only, api.ts l.20-34) so the numbers below can be shown (`NEEDS: backend` to send them).
| State | EN | ES |
|---|---|---|
| too_large_office (bytes) | This file is too large ({{size}}). The limit is {{max}} MB. Try saving a lighter copy. | Este archivo es demasiado grande ({{size}}). El límite es {{max}} MB. Prueba a guardar una copia más ligera. |
| too_many_pages | This document has {{pages}} pages and the limit is {{max}}. Split it into parts first. | Este documento tiene {{pages}} páginas y el límite es {{max}}. Divídelo primero en partes. |
| too_many_sheets | This workbook has {{count}} sheets and the limit is {{max}}. Use "Sheets to include" to pick some. | Este libro tiene {{count}} hojas y el límite es {{max}}. Usa "Hojas a incluir" para elegir algunas. |
| too_many_cells | The sheet "{{sheet}}" is too big to convert (more than {{max}} rows). Remove empty rows or split the data. | La hoja "{{sheet}}" es demasiado grande para convertirla (más de {{max}} filas). Quita filas vacías o divide los datos. |
| damaged_office | This file could not be opened. It may be damaged, or it is not really a {{kind}} file. | No se pudo abrir este archivo. Puede estar dañado o no ser realmente un archivo {{kind}}. |
| zip_bomb / unsupported content | This file looks unsafe to open (it expands to an unusual size) and was stopped. | Este archivo parece inseguro (se expande a un tamaño anómalo) y se detuvo. |
| sheets_not_found | No sheet matches "{{value}}". Check the names or numbers. | Ninguna hoja coincide con "{{value}}". Revisa los nombres o números. |
| no_tables (pdf2excel) | We found no tables in this PDF. Tables drawn without lines can be missed. A scanned PDF has none to read. | No encontramos tablas en este PDF. Las tablas dibujadas sin líneas pueden pasar desapercibidas. Un PDF escaneado no tiene nada que leer. |
| no_text (pdf2word, pdf2excel) | This PDF has no text: it is a scan (pictures of pages). There is nothing to convert yet. Text recognition (OCR) is planned for doctool. | Este PDF no tiene texto: es un escaneo (imágenes de páginas). Todavía no hay nada que convertir. El reconocimiento de texto (OCR) está previsto en doctool. |
| engine_failed | The converter stopped unexpectedly. Try again; if it happens again, try a smaller or simpler file. | El conversor se detuvo de forma inesperada. Inténtalo de nuevo; si se repite, prueba con un archivo más pequeño o más simple. |
`{{kind}}` = "Word", "Excel", "PowerPoint", "HTML", "PDF". Limit values: `NEEDS: DOCTOOL_OFFICE_* defaults` (never invent in copy; they interpolate). Dropzone rejection of an unsupported extension: `dropzone.rejectedOffice` EN "{{names}}: not a supported file for this tool. Accepted: {{list}}." ES "{{names}}: no es un archivo admitido en esta herramienta. Se aceptan: {{list}}."

### 8.7 State table
| State | Behaviour |
|---|---|
| Empty | Dropzone full size, `toolPage.noFiles`, options with defaults, Run disabled with `needMore` hint. Dropzone line lists the formats (below). |
| Engine missing | 8.1. |
| Loading | 8.3; Run disabled; status line. |
| Busy | 8.2. |
| Error | 8.4-8.6; alert above result area; Retry on Run. |
| Success | Result card (section 7); focus stays on Run. |
| Disabled | Run disabled with no file, extra files, pending, or engine missing; `show_when` hides (not greys) fields. |
Dropzone format lines (new keys `dropzone.kind.<toolId>`): word2pdf EN "Word documents: DOCX, DOC, ODT, RTF, TXT" / ES "Documentos de Word: DOCX, DOC, ODT, RTF, TXT"; excel2pdf "Spreadsheets: XLSX, XLS, ODS, CSV" / "Hojas de cálculo: XLSX, XLS, ODS, CSV"; ppt2pdf "Presentations: PPTX, PPT, ODP" / "Presentaciones: PPTX, PPT, ODP"; html2pdf "A saved web page: HTML or HTM" / "Una página web guardada: HTML o HTM"; pdf2* reuse `dropzone.pdf` "PDF files".

## 9. Components and tokens used (all exist in the files read)
`ToolPage`/`ToolWorkspace`, `Dropzone`, `FileList`, `SchemaForm`, `Button`, `ToolIcon`, `cardClass`, `hintClass`, `ToolLauncher`, `CommandPalette`, `LibraryPicker` (PDF tools only), Tailwind group utilities `bg-g`, `text-g-fg`, `text-g-ink`, `bg-g-soft`, `border-l-g` (driven by `data-group`), `text-muted`, `text-danger`, `bg-danger-soft`, `border-ok/50`, `rise-in`. New small pieces (inline in ToolPage, no new file required): tool note block, engine banner, progress status line, warnings list.

## 10. Required code changes found (so O4/O7 do not lose time)
1. Dropzone accepts only `pdf | image | pdf+image` (`types.ts` l.29; `Dropzone.tsx` l.7-22). Add `"office"` to the union and a per-tool `extensions: string[]` on `Tool` (backend-supplied) so one `office` value serves word/excel/ppt/html with different lists. `acceptsFile(file, accepts, extensions)` matches on extension (browsers report odd MIME for .doc/.csv/.rtf; backend still does magic bytes). `acceptAttr` for office is built from the extensions (`.docx,.doc,...`), not `image/*`. `kind` text uses `dropzone.kind.<toolId>`. Rejection message: choose by reason (macro / unsupported / pdf-image as now) and list names. Add a `disabled` prop.
2. `ToolPage.tsx`: l.57 `acceptsPdf = tool.accepts !== "image"` would show "From library" for office inputs (library is PDF-only): make it `accepts === "pdf" || "pdf+image"`. l.297 `tooManyImages` branch fine (single file). l.130 password set stays PDF-only. l.374 and `nextSteps.ts` l.23 and `DocumentPage.tsx` l.154 filter `x.accepts !== "image"`: would list word2pdf etc. as PDF next steps and feed a PDF to a Word input. Change to "accepts includes pdf" (`nextSteps.ts` body `unverified`). Suggested chain for office->PDF results: compress, protect.
3. `errors.ts`: add `OFFICE_TOOLS` and state mapping (`busy` -> `busy_office`), `params` pass-through.
4. Result: warnings, stats, `resultWarn` title (section 7). Tool note and engine banner (sections 6, 8.1). Progress status (8.3).
5. `useTools.ts`/`toolIcons.ts`: group + icons. `TOOL_KEYWORDS` in `CommandPalette.tsx` l.21.
6. Guard tests exist for icons/groups (`toolIcons.test.ts`, `groupTokens.test.ts` exist; contents not read): expect them to need the new group and icons.

## 11. Sidebar order, launcher, palette, home (contracts 10, 11)
- Order proposal: `organize, optimize, convert, office, edit, security, images`. Why: iLovePDF's mental model puts Word/Excel/PowerPoint -> PDF under "Convert", and `office` is the same job family, so adjacency matters more than tile stability; `office` is the only other conversion group, and Edit/Security are unrelated. Cost: edit, security, images tiles shift down by 7 positions in the launcher (images is unreleased on main, `unverified`). Alternative: last (zero shift, but conversion tools split across the page). See open decision 1.
- Sidebar: `App.tsx` l.40 maps `GROUP_ORDER`; adding the entry plus `groups.office` ("Office" / "Ofimática") is enough. Sidebar width/phone drawer behaviour `unverified` (App.tsx not fully read).
- Launcher (24 tiles after this module, 2 columns on phone = 12 rows): no group headings today; if scanning slows, add group filter chips (carried over from the image spec). The launcher renders one tile per tool, so "the group tile" is seven teal-banded tiles in sequence, each showing the group name as text; unavailable ones show the "Needs LibreOffice" badge (8.1). `home.title` is already "What shall we do with your files?" (en.ts l.237).
- Palette (Ctrl+K): items use `value = "${title} ${id}"`; titles are "Word to PDF", "PDF to Word", etc. so typing "pdf to word" works. Add `keywords` (es/en): word2pdf [word, docx, doc, odt, rtf, documento, texto, convertir]; excel2pdf [excel, xlsx, xls, csv, ods, hoja, cálculo, spreadsheet]; ppt2pdf [powerpoint, pptx, ppt, odp, presentación, diapositivas, slides]; pdf2word [word, docx, editar, edit]; pdf2excel [excel, xlsx, tabla, table, hoja]; pdf2ppt [powerpoint, pptx, diapositivas, slides]; html2pdf [html, htm, web, página]. Engine-missing rows show the badge and stay selectable. 24 rows in the 50vh list scroll; group label already right-aligned.
- i18n: `groups.office`, `tools.<id>.{title,description,note?}` for 7 tools, `params.*`, `values.*`, `hints.<id>.*`, `warnings.*`, new `errors.*`, `dropzone.*`, `toolPage.*` keys above, all en and es.

## 12. Accessibility (WCAG 2.2 AA; SPEC s.8 and the plan say 2.1 AA, same or stricter)
- Contrast: section 3 (ADR). Group-coloured text only as `g-ink` on surface/soft, fg on fill. Note block, banner and warnings use `text` colour on neutral surfaces, with icon + words.
- Keyboard order: skip link -> header nav/sidebar -> (quality note, not focusable) -> engine-banner link -> Dropzone "Select files" (and "From library" for PDF tools) -> file row controls -> option fields in DOM order -> Run/Retry -> after success: warnings (not focusable; read via live region) -> Download -> Open in library -> "Use result in another tool" -> "New task". Enter in a text/number field submits (form `onSubmit`).
- Focus: after success focus stays on Run (ToolPage l.143-146 comment; scroll-into-view only if off screen, honouring reduced motion l.186) so "run again" is one key; announcement via the existing `aria-live="polite"` container (l.316), whose heading carries the warning count first. After an error focus also stays on Run (now "Retry"). "New task" moves focus to `#main`. Disabled Dropzone (engine missing): picker button `disabled`, banner precedes it in reading order and Run references it with `aria-describedby`.
- Progress: `role="status"` text changes only at stage boundaries; the elapsed counter is `aria-hidden`; no per-second announcements; no percentage.
- Labels: every field has `<label htmlFor>`; help via `aria-describedby` (SchemaForm). Placeholder is never the only label (`sheets`, `pages` have a label and example in help).
- Target size >= 24 px: buttons `min-h-10`; checkboxes are 16 px but the label row is `min-h-6` (SchemaForm l.70) = 24 px, passes only via the row; banner link `min-h-6`; badge is not interactive.
- Reduced motion: no new animation; spinner is covered by the global rule (image-tools.md cites `index.css` l.244-251, `unverified` now); tile hover lift already `motion-reduce:transform-none`.
- Not colour alone: warnings, badge, errors, note all carry icon + text. No time limit besides server timeout (stated in text). No drag-only interaction (picker button exists).

## 13. Phone layout (390px)
`ToolPage` stacks: header band (56px icon + text) -> note (3-5 lines, full width) -> banner -> Dropzone (py-14, compact once a file is set) -> file row (name truncates; size visible) -> Options card, single column, one control per row (inputs full width, `inputmode` numeric for `dpi`, text for `sheets`/`pages`) -> Run full width -> progress line directly under Run (so the user sees it without scrolling) -> result card (scrolls into view if hidden) with warnings above the Download button. Longest option set (excel2pdf, 4 fields; ppt2pdf, 3) fits in ~1.5 screens. Output file names wrap (`break-all`). File picker: extension `accept` list opens Files/Drive on phones. Launcher 2 columns: tile = icon + title + group + badge; long titles ("PowerPoint to PDF") wrap to two lines at ~180px: acceptable, no truncation.

## 14. Future slots (Tier B; do not redo layout later)
- ocr (group office): single PDF in, options language/deskew, `requires: ["tesseract"]` uses the same engine-missing banner/badge; `warnings[].action.tool = "ocr"` already wires "Open OCR" from no_text_layer / no_text; honest-quality note via `tools.ocr.note`.
- pdfa: `requires: ["ghostscript"]`; result adds a validation report: reuse the warnings list for failed checks.
- compare: two inputs (`min_files` 2) and a wide result. Reserve: result area may go full width (ToolPage's `lg:grid-cols-[1fr_20rem]` is only for inputs/options; result card is already outside the grid, l.316). Side-by-side before/after needs two columns from `sm`, stacked on phone with a tab/segmented control; highlights must not rely on colour alone (underline + marker text).
- batch: `max_files` > 1 already supported (`multipleOutputs`, ZIP); needs per-file warnings, hence the optional `file` key in the warnings model now, and `errors.in_file` (exists) per file.
- recipes: a saved chain reuses `nextSteps` UI pattern; no layout change.

## 15. Open decisions for the owner (max 5)
1. Group order: `office` right after `convert` (shifts edit/security/images tiles) or last. Recommend after `convert`, for mental model.
2. Password-protected Word/Excel/PowerPoint: reject with instructions in v1, or accept a password. Recommend reject in v1 (LibreOffice password handoff is `unverified`; PDF password flow stays), accept later with `msoffcrypto-tool`.
3. Macros: .docm/.xlsm/.pptm rejected up front, but legacy .doc/.xls/.ppt (which can hold macros) accepted with macros never run plus a `macros_removed` warning. Recommend keep both, as the warning is honest and rejecting legacy formats would block many users.
4. excel2pdf "Sheets to include": free-text names/numbers in v1, or an inspect step that lists the sheets as checkboxes after upload. Recommend free text in v1 (generic form needs no new UI), checkboxes as a follow-up.
5. pdf2ppt default: page pictures (identical look, not editable) or editable text frames (editable, looks different). Recommend `picture` default with the note shown, since it is the only result that never looks broken; also confirm single-file only in v1.

# Set up LibreOffice for the Office tools

This guide shows you how to install LibreOffice so doctool's Office tools work, and how to fix the
usual problems.

**Who this is for:** anyone running doctool on their own machine who sees "LibreOffice is not
available here, so this tool is off" on an Office tool page.

**What needs LibreOffice:**

| Tool | Needs LibreOffice |
|---|---|
| Word to PDF (`word2pdf`), Excel to PDF (`excel2pdf`), PowerPoint to PDF (`ppt2pdf`), HTML to PDF (`html2pdf`) | Yes, always |
| PDF to Word (`pdf2word`) | Only for the "Keep the look" result type. "Editable text" (the default) does not |
| PDF to Excel (`pdf2excel`), PDF to PowerPoint (`pdf2ppt`) | No |

doctool never links LibreOffice. It starts the `soffice` program as a separate process, one
conversion at a time. See [office-module.md](office-module.md) for how that works.

> Text recognition (OCR) for scanned PDFs is **not shipped yet**. Installing Tesseract does not
> enable anything today.

## Prerequisites

- doctool runs on your machine (see the [README](../README.md#run-it-windows-powershell)).
- Permission to install software.
- A LibreOffice version that supports JSON PDF export options (7.4 or newer). The PowerPoint
  options "Include speaker notes" and "Include hidden slides" use them. Development used
  LibreOffice 26.8.

## 1. Install LibreOffice

### Windows

```powershell
winget install --id TheDocumentFoundation.LibreOffice -e
```

The installer puts `soffice.exe` in `C:\Program Files\LibreOffice\program\`. doctool looks there
on its own, so you do not need to change `PATH`.

### Debian / Ubuntu

Install the same packages the [Dockerfile](../Dockerfile) installs:

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  libreoffice-core libreoffice-writer libreoffice-calc libreoffice-impress \
  libreoffice-draw libreoffice-pdfimport \
  fonts-liberation fonts-crosextra-carlito fonts-crosextra-caladea fonts-dejavu-core
```

- `libreoffice-pdfimport` is needed for PDF to Word with "Keep the look".
- The font packages keep line breaks close to the Windows originals (see
  [Fonts were substituted](#fonts-were-substituted)).

### macOS

Download LibreOffice from <https://www.libreoffice.org/download/> and drag it to
`/Applications`, or use Homebrew:

```bash
brew install --cask libreoffice
```

doctool finds `/Applications/LibreOffice.app/Contents/MacOS/soffice` without extra setup.

## 2. How doctool finds LibreOffice

doctool checks these places in order and uses the first file that exists
(`find_soffice` and `_default_locations` in `api/doctool/officecore.py`):

1. The `DOCTOOL_SOFFICE` environment variable: the full path to the `soffice` program.
2. `soffice`, then `libreoffice`, on your `PATH`.
3. The usual install folders:

| System | Folders checked |
|---|---|
| Windows | `%ProgramFiles%\LibreOffice\program\soffice.exe`, `%ProgramFiles(x86)%\LibreOffice\program\soffice.exe` |
| Linux / macOS | `/usr/bin/soffice`, `/usr/lib/libreoffice/program/soffice`, `/opt/libreoffice/program/soffice`, `/Applications/LibreOffice.app/Contents/MacOS/soffice` |

The check runs on every request (`api/doctool/engines.py`), so a fresh install is picked up
without restarting doctool. Reload the tool page.

If LibreOffice lives somewhere else, point doctool at it before you start the server:

```powershell
$env:DOCTOOL_SOFFICE = "D:\Apps\LibreOffice\program\soffice.exe"
cd api; ..\.venv\Scripts\python -m doctool
```

```bash
DOCTOOL_SOFFICE=/opt/custom/libreoffice/program/soffice python -m doctool
```

If `DOCTOOL_SOFFICE` points at a file that does not exist, doctool ignores it and keeps looking.

## 3. The first conversion is slower

A brand-new LibreOffice profile takes much longer on its first run, because LibreOffice builds the
profile and fills its font cache (about 24 s in the development spike, `docs/RESEARCH.md`).
doctool handles this in two ways (`api/doctool/officecore.py`):

- **Warm-up at start.** When the server starts it converts a tiny CSV file in the background, so
  your first real conversion is not the slow one. While the warm-up runs, requests wait for it
  instead of getting a "busy" reply.
- **Longer first timeout.** Until one conversion has succeeded, the timeout is at least 180 s
  instead of the normal 60 s. After a success doctool writes a `.ready` marker file in the profile
  folder and the normal timeout applies.

The profile lives in `<data dir>/office/profile` (by default `api/data/office/profile`) and is
reused by every conversion. It carries a version marker (`doctool-profile.version`,
`PROFILE_VERSION` in `officecore.py`). When a doctool update changes the profile settings, the
next conversion rewrites the locked settings of an older profile, so you do not need to delete it.

To skip the warm-up (for example in tests), set `DOCTOOL_OFFICE_WARMUP=0`.

## 4. Settings

All settings are environment variables read at start (`Settings.from_env` in
`api/doctool/config.py`). An invalid value (not a number, or zero or less) is ignored with a log
warning and the default is used.

| Variable | Type | Default | Meaning |
|---|---|---|---|
| `DOCTOOL_SOFFICE` | path | not set | Full path to `soffice`; overrides the search |
| `DOCTOOL_OFFICE_WARMUP` | `0` | warm-up on | `0` turns off the start-up warm-up |
| `DOCTOOL_OFFICE_TIMEOUT_SECONDS` | float | `60` | Longest a single conversion may run before it is stopped (at least 180 s before the first success) |
| `DOCTOOL_OFFICE_SLOT_WAIT_SECONDS` | float | `0.5` | How long a request waits for the LibreOffice lane before it gets "busy" |
| `DOCTOOL_OFFICE_MAX_ENTRIES` | int | `5000` | Most parts a DOCX/XLSX/PPTX/ODT/ODS/ODP package may hold |
| `DOCTOOL_OFFICE_MAX_UNCOMPRESSED_BYTES` | int | `524288000` (500 MiB) | Largest unpacked size of a package |
| `DOCTOOL_OFFICE_MAX_RATIO` | int | `200` | Largest unpacked/packed size ratio (zip-bomb guard) |
| `DOCTOOL_OFFICE_MAX_PDF_PAGES` | int | `300` | Most pages PDF to Word/Excel/PowerPoint will process |
| `DOCTOOL_OFFICE_MAX_OUTPUT_BYTES` | int | `524288000` (500 MiB) | Largest file LibreOffice may produce; a bigger result fails with `too_large` |
| `DOCTOOL_OFFICE_RENDER_BUDGET_PIXELS` | int | `1500000000` | Most pixels PDF to PowerPoint renders for all pages together at the chosen dpi; more fails with `too_large` |

The upload limit (200 MB) applies to every tool and is not configurable.

## Verify it worked

1. Check that LibreOffice runs on its own:

   ```bash
   soffice --version
   ```

   On Windows use the console launcher: `& "C:\Program Files\LibreOffice\program\soffice.com" --version`.

2. With doctool running, ask the API which Office tools are available:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8000/api/v1/tools | Where-Object group -eq office | Select-Object id, available, requires
   ```

   `word2pdf`, `excel2pdf`, `ppt2pdf` and `html2pdf` should show `available: True`.

3. Optional: run the tests that use the real LibreOffice (they are skipped when it is missing):

   ```powershell
   cd api; ..\.venv\Scripts\python -m pytest -m office -q
   ```

## Troubleshooting

### The Office tools are greyed out

**Symptom:** the tool page shows "LibreOffice is not available here, so this tool is off", the
drop area and the Run button are disabled, and the launcher shows "Needs LibreOffice".

**Cause:** none of the places in [step 2](#2-how-doctool-finds-libreoffice) holds a `soffice`
file. `GET /api/v1/tools` reports `available: false` for those tools.

**Fix:** install LibreOffice, or set `DOCTOOL_SOFFICE` to the right path and restart doctool. If
LibreOffice disappears while doctool runs, a conversion fails with the error state
`engine_missing` ("LibreOffice is not available on the server, so this conversion cannot run").

### "Another document is being converted right now" (busy, HTTP 503)

**Cause:** LibreOffice profiles do not tolerate concurrent use, so doctool runs one conversion at
a time. A second request waits `DOCTOOL_OFFICE_SLOT_WAIT_SECONDS` (0.5 s) and then gets a
retryable `503` with state `busy`. Your file was not touched.

**Fix:** press **Retry** after a few seconds. If you are the only user and this happens often,
another conversion may be stuck; it will be stopped at the timeout.

### "The conversion took too long and was stopped" (timeout)

**Cause:** the conversion ran past `DOCTOOL_OFFICE_TIMEOUT_SECONDS` (60 s by default). doctool
kills the whole LibreOffice process tree and deletes the job folder.

**Fix:**

- Try a smaller file, or split it.
- On a slow machine, raise the limit, for example `DOCTOOL_OFFICE_TIMEOUT_SECONDS=120`.
- If it only happens on the very first conversion, the warm-up may have failed: check the log for
  `LibreOffice warm-up skipped`. Make sure the data folder is writable.

### Fonts were substituted

**Symptom:** the result shows "Some fonts are not installed here, so similar ones were used:
…". Line breaks and the page count may differ from the original.

**Cause:** the DOCX/XLSX/PPTX asks for fonts that are not installed, so LibreOffice used others.
doctool compares the fonts the document asks for with the fonts in the PDF and lists up to five.

**Fix:** install the missing fonts, or metric-compatible replacements that keep the same widths:

| Original fonts | Replacement package (Debian/Ubuntu) |
|---|---|
| Arial, Times New Roman, Courier New | `fonts-liberation` |
| Calibri | `fonts-crosextra-carlito` |
| Cambria | `fonts-crosextra-caladea` |
| General fallback | `fonts-dejavu-core` |

On Windows and macOS, install the font files the document uses. Then convert again (the warning
appears on each conversion until the fonts are present).

### Other error states

See the full list of error states and what triggers each one in
[office-module.md](office-module.md#error-states).

## Related

- [office-module.md](office-module.md): what each Office tool does, its options, and the security
  model.
- [deployment.md](deployment.md): running doctool and LibreOffice in Docker.
- [SPEC.md](SPEC.md): product specification.

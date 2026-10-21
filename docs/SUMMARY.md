# doctool: summary

**What it is:** your own iLovePDF, running on your PC. No uploads, no limits, and it **remembers**: every file you process goes into a library with its full history.

## First MVP (PDF only), in priority order
**Essential (v0.1)**
1. Merge PDFs (drag to reorder)
2. Split: by ranges, every N pages, by size; extract or remove pages
3. Visual page organizer: reorder, rotate, delete, duplicate, insert blank pages
4. Compress (3 levels)
5. Protect with password / unlock
6. Images -> PDF and PDF -> images
7. Watermark and page numbers
8. Read/edit metadata
9. **Library + version history**: find old files, see what was done to each, go back
10. Preview, ZIP download, chain "use result as input for another tool"

**Next (v0.2):** OCR, Word/Excel/PowerPoint/HTML -> PDF, PDF -> Word, repair, PDF/A, compare, saved recipes (chains), search inside the library, CLI.

**Later:** edit text, forms, redaction, signatures, image tools (convert/resize/crop/compress), Word/Excel editing, local AI (summarize/translate), watched "inbox" folder, desktop app.

## How it is built (short)
Python (FastAPI) engine on your machine + React web UI. Tools: pikepdf/qpdf, PDFium, Ghostscript, Tesseract, LibreOffice. Everything binds to localhost; input PDFs are treated as hostile.

## What I need from you
D1 license (recommend Apache-2.0), D2 local server vs pure-browser (recommend local server), D3 workflow (recommend ODD per milestone). Details in `docs/SPEC.md` section 12. Evidence and sources: `docs/RESEARCH.md`.

"""Surgical edits and facts on OOXML packages (docx/xlsx/pptx) without a round trip through a
high-level library: only the XML parts we touch are rewritten, everything else (charts, images,
custom XML) is copied byte for byte. Inputs have already passed officecore.guard_package."""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass

from lxml import etree

from doctool.tools.base import ToolError

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
OOXML_EXT = frozenset({"docx", "xlsx", "pptx"})
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
_OLE_MACRO_MARKERS = ("_VBA_PROJECT", "VBA", "Macros")


def _xml(data: bytes) -> etree._Element:
    return etree.fromstring(data, _PARSER)


def _dump(root: etree._Element) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def rewrite(data: bytes, edit: Callable[[str, bytes], bytes | None]) -> bytes:
    """Copy a zip package, replacing a part when `edit(name, content)` returns new bytes."""
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            content = src.read(info)
            new = edit(info.filename, content)
            dst.writestr(info, content if new is None else new, compress_type=info.compress_type)
    return out.getvalue()


def _read(data: bytes, name: str) -> bytes | None:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        try:
            return z.read(name)
        except KeyError:
            return None


# ---------- external references ----------
def neutralize_external(data: bytes) -> tuple[bytes, int]:
    """Point every fetchable external relationship (images, OLE links, templates, frames) at an
    empty target so LibreOffice cannot load it. Hyperlinks stay: they are only links in the PDF."""
    blocked = 0

    def edit(name: str, content: bytes) -> bytes | None:
        nonlocal blocked
        if not name.endswith(".rels") or b'TargetMode="External"' not in content:
            return None
        root = _xml(content)
        changed = False
        for rel in root.iter(f"{{{NS_PKG_REL}}}Relationship"):
            if rel.get("TargetMode") != "External" or rel.get("Type", "").endswith("/hyperlink"):
                continue
            rel.set("Target", "")
            blocked += 1
            changed = True
        return _dump(root) if changed else None

    return rewrite(data, edit), blocked


# ---------- spreadsheets ----------
@dataclass
class SheetSetup:
    visible: int
    hidden_skipped: int


_AFTER_PAGE_SETUP = (
    "headerFooter",
    "rowBreaks",
    "colBreaks",
    "customProperties",
    "cellWatches",
    "ignoredErrors",
    "smartTags",
    "drawing",
    "legacyDrawing",
    "legacyDrawingHF",
    "drawingHF",
    "picture",
    "oleObjects",
    "controls",
    "webPublishItems",
    "tableParts",
    "extLst",
)
_WIDE_COLUMNS = 10  # "auto" orientation: more used columns than this -> landscape


def _col_count(ref: str | None) -> int:
    """Columns spanned by a dimension ref like "A1:Y39" (0 when unknown)."""
    if not ref:
        return 0
    cols = re.findall(r"([A-Z]+)\d*", ref.upper())

    def num(s: str) -> int:
        n = 0
        for ch in s:
            n = n * 26 + ord(ch) - 64
        return n

    return num(cols[-1]) - num(cols[0]) + 1 if cols else 0


def _q(tag: str) -> str:
    return f"{{{NS_MAIN}}}{tag}"


def _setup_sheet(xml: bytes, orientation: str, fit_width: bool, fit_sheet: bool) -> bytes:
    root = _xml(xml)
    if orientation == "auto":
        dim = root.find(_q("dimension"))
        orientation = (
            "landscape"
            if _col_count(dim.get("ref") if dim is not None else None) > _WIDE_COLUMNS
            else "portrait"
        )
    setup = root.find(_q("pageSetup"))
    if setup is None:
        setup = etree.Element(_q("pageSetup"))
        anchor = next(
            (root.find(_q(t)) for t in _AFTER_PAGE_SETUP if root.find(_q(t)) is not None), None
        )
        if anchor is not None:
            anchor.addprevious(setup)
        else:
            root.append(setup)
    setup.set("orientation", orientation)
    if fit_width or fit_sheet:
        setup.set("fitToWidth", "1")
        setup.set("fitToHeight", "1" if fit_sheet else "0")
        pr = root.find(_q("sheetPr"))
        if pr is None:
            pr = etree.Element(_q("sheetPr"))
            root.insert(0, pr)
        psp = pr.find(_q("pageSetUpPr"))
        if psp is None:
            psp = etree.SubElement(pr, _q("pageSetUpPr"))
        psp.set("fitToPage", "1")
    return _dump(root)


def _matches(sel: str, index: int, name: str) -> bool:
    sel = sel.strip()
    return (sel.isdigit() and int(sel) == index) or sel.casefold() == name.casefold()


def xlsx_page_setup(
    data: bytes, *, sheets: list[str] | None, orientation: str, fit_width: bool, fit_sheet: bool
) -> tuple[bytes, SheetSetup]:
    """Apply print settings to an xlsx and hide the sheets that were not selected.

    Sheet numbers count the sheets as shown (1 = first tab). Hidden sheets are never printed."""
    wb_xml = _read(data, "xl/workbook.xml")
    rels_xml = _read(data, "xl/_rels/workbook.xml.rels")
    if wb_xml is None or rels_xml is None:
        raise ToolError("damaged", "the spreadsheet has no workbook part")
    wb = _xml(wb_xml)
    targets = {
        r.get("Id"): r.get("Target", "")
        for r in _xml(rels_xml).iter(f"{{{NS_PKG_REL}}}Relationship")
    }
    entries = wb.find(_q("sheets"))
    sheet_list = list(entries) if entries is not None else []
    wanted = [s for s in (sheets or []) if s.strip()]
    hidden_before = 0
    visible: list[etree._Element] = []
    for i, sh in enumerate(sheet_list, start=1):
        if sh.get("state") in ("hidden", "veryHidden"):
            hidden_before += 1
            continue
        if wanted and not any(_matches(s, i, sh.get("name", "")) for s in wanted):
            sh.set("state", "hidden")
            continue
        visible.append(sh)
    if not visible:
        raise ToolError(
            "out_of_range", "none of the selected sheets exist (hidden sheets cannot be chosen)"
        )
    parts = {}
    for sh in visible:
        target = targets.get(sh.get(f"{{{NS_REL}}}id"), "")
        path = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
        parts[path] = True
    # A workbook-level "active tab" pointing at a now-hidden sheet confuses LibreOffice.
    view = wb.find(f"{_q('bookViews')}/{_q('workbookView')}")
    if view is not None:
        view.set("activeTab", str(sheet_list.index(visible[0])))
        view.attrib.pop("firstSheet", None)
    new_wb = _dump(wb)

    def edit(name: str, content: bytes) -> bytes | None:
        if name == "xl/workbook.xml":
            return new_wb
        if name in parts:
            return _setup_sheet(content, orientation, fit_width, fit_sheet)
        return None

    return rewrite(data, edit), SheetSetup(visible=len(visible), hidden_skipped=hidden_before)


# ---------- presentations ----------
def pptx_hidden_slides(data: bytes) -> int:
    count = 0
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            if re.fullmatch(r"ppt/slides/slide\d+\.xml", name):
                root = _xml(z.read(name))
                count += root.get("show") == "0"
    return count


# ---------- fonts and legacy macros ----------
def _w(tag: str) -> str:
    return f"{{{NS_W}}}{tag}"


def _rfonts(el: etree._Element | None) -> set[str]:
    found: set[str] = set()
    if el is None:
        return found
    for rf in el.iter(_w("rFonts")):
        for attr in ("ascii", "hAnsi"):
            if v := rf.get(_w(attr)):
                found.add(v)
    return found


def _docx_fonts(z: zipfile.ZipFile) -> set[str]:
    """Fonts of the runs, of the styles actually used (with their basedOn chain) and of the
    document defaults. Styles that the template defines but nothing uses are ignored."""
    doc = _xml(z.read("word/document.xml"))
    fonts = _rfonts(doc.find(_w("body")))
    try:
        styles = _xml(z.read("word/styles.xml"))
    except KeyError:
        return fonts
    by_id = {s.get(_w("styleId")): s for s in styles.iter(_w("style"))}
    used = {
        el.get(_w("val")) for tag in ("pStyle", "rStyle", "tblStyle") for el in doc.iter(_w(tag))
    }
    used |= {
        sid
        for sid, s in by_id.items()
        if s.get(_w("default")) in ("1", "true") and s.get(_w("type")) == "paragraph"
    }
    seen: set[str] = set()
    while used:
        sid = used.pop()
        if sid in seen or sid not in by_id:
            continue
        seen.add(sid)
        style = by_id[sid]
        fonts |= _rfonts(style.find(_w("rPr")))
        based = style.find(_w("basedOn"))
        if based is not None:
            used.add(based.get(_w("val")))
    fonts |= _rfonts(styles.find(_w("docDefaults")))
    return fonts


def document_fonts(data: bytes, ext: str) -> set[str]:
    """Font family names the document's content asks for (theme placeholders excluded)."""
    fonts: set[str] = set()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if ext == "docx":
            return _docx_fonts(z)
        for name in z.namelist():
            if not name.endswith(".xml"):
                continue
            if ext == "pptx" and re.fullmatch(r"ppt/slides/slide\d+\.xml", name):
                for el in _xml(z.read(name)).iter(f"{{{NS_A}}}latin"):
                    if (v := el.get("typeface")) and not v.startswith("+"):
                        fonts.add(v)
            elif ext == "xlsx" and name == "xl/styles.xml":
                for el in _xml(z.read(name)).iter(_q("name")):
                    if v := el.get("val"):
                        fonts.add(v)
    return fonts


def ole_has_macros(data: bytes) -> bool:
    """Legacy .doc/.xls/.ppt with a VBA project. Macros never run (profile locks them)."""
    head = data[:4_000_000]
    return any(m.encode("utf-16-le") in head for m in _OLE_MACRO_MARKERS)

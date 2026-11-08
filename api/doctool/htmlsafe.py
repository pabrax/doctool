"""Make an uploaded HTML file safe to render: nothing runs, nothing is fetched (no network, no
local files), and the page size is set with CSS @page (LibreOffice honours it)."""

from __future__ import annotations

import re

from lxml import etree, html

_DROP_TAGS = (
    "script",
    "noscript",
    "iframe",
    "frame",
    "frameset",
    "object",
    "embed",
    "applet",
    "base",
    "link",
    "portal",
    "template",
)
_URL_ATTRS = (
    "src",
    "srcset",
    "data",
    "poster",
    "background",
    "lowsrc",
    "dynsrc",
    "action",
    "formaction",
    "xlink:href",
    "codebase",
    "longdesc",
    "ping",
)
_SAFE_URL = re.compile(r"^\s*(data:image/|#)", re.I)
_CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.I | re.S)
_CSS_IMPORT = re.compile(r"@import[^;]*;?", re.I)
_PAGE_MM = {"a4": (210, 297), "letter": (215.9, 279.4)}
_CSS_EXPR = re.compile(r"expression\s*\(|behavior\s*:|-moz-binding", re.I)


def _clean_css(css: str) -> tuple[str, int]:
    blocked = len(_CSS_IMPORT.findall(css)) + len(_CSS_EXPR.findall(css))
    css = _CSS_EXPR.sub("", _CSS_IMPORT.sub("", css))

    def repl(m: re.Match) -> str:
        nonlocal blocked
        if _SAFE_URL.match(m.group(2)):
            return m.group(0)
        blocked += 1
        return "none"

    return _CSS_URL.sub(repl, css), blocked


def sanitize(
    data: bytes, *, page_size: str, orientation: str, backgrounds: bool
) -> tuple[bytes, int]:
    """Return (safe html bytes, number of external/active references removed)."""
    doc = html.document_fromstring(
        data, parser=html.HTMLParser(no_network=True, remove_comments=True)
    )
    blocked = 0
    for el in list(doc.iter(*_DROP_TAGS)):
        blocked += 1
        el.drop_tree()
    for el in list(doc.iter("meta")):
        if (el.get("http-equiv") or "").lower() in (
            "refresh",
            "set-cookie",
            "content-security-policy",
        ):
            el.drop_tree()
            blocked += 1
    for el in doc.iter():
        if not isinstance(el.tag, str):
            continue
        for attr in list(el.attrib):
            low = attr.lower()
            if low.startswith("on"):
                del el.attrib[attr]
                blocked += 1
            elif low == "srcset" or (low in _URL_ATTRS and not _SAFE_URL.match(el.get(attr, ""))):
                # srcset lists several URLs: never kept (src is enough)
                del el.attrib[attr]
                blocked += 1
            elif low == "href" and el.tag != "a":
                del el.attrib[attr]
                blocked += 1
            elif low == "href" and re.match(
                r"^\s*(javascript|vbscript|file):", el.get(attr, ""), re.I
            ):
                del el.attrib[attr]
                blocked += 1
            elif low == "style":
                css, n = _clean_css(el.get(attr, ""))
                el.set(attr, css)
                blocked += n
    for style in doc.iter("style"):
        css, n = _clean_css(style.text or "")
        style.text = css
        blocked += n
    head = doc.find("head")
    if head is None:
        head = etree.Element("head")
        doc.insert(0, head)
    # LibreOffice understands explicit lengths but not every CSS size keyword (e.g. "letter").
    short, long_ = _PAGE_MM[page_size]
    w, h = (long_, short) if orientation == "landscape" else (short, long_)
    size = etree.Element("style")
    size.text = f"@page {{ size: {w}mm {h}mm; }}"
    if orientation == "auto":
        head.insert(0, size)  # first: a page that sets its own @page size keeps it
    else:
        head.append(size)  # last: an explicit choice wins over the document's own @page
    # The user's margin and background choices always win, so they go last.
    rules = "@page { margin: 15mm; }"
    if not backgrounds:
        rules += " * { background: none !important; background-color: transparent !important; }"
    choices = etree.Element("style")
    choices.text = rules
    head.append(choices)
    meta = etree.Element("meta", charset="utf-8")
    head.insert(0, meta)
    return html.tostring(doc, encoding="utf-8", method="html", doctype="<!DOCTYPE html>"), blocked

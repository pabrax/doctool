import re
from urllib.parse import quote


def content_disposition(filename: str, inline: bool = False) -> str:
    """RFC 6266/5987 header that survives any Unicode name and cannot inject headers."""
    kind = "inline" if inline else "attachment"
    fallback = re.sub(r"[^\x20-\x7e]|[\"\\]", "", filename) or "download"
    return f"{kind}; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"

import re
from pathlib import PurePath

from doctool.tools.base import ToolError

_TOKEN = re.compile(r"^(\d+)(?:-(\d+))?$")


def parse_ranges(spec: str, total: int) -> list[list[int]]:
    """Parse '1-3,5,8-10' into 0-based index groups. Strict: any bad token is an error."""
    if not spec or not spec.strip():
        raise ToolError("out_of_range", "page range is empty")
    ranges: list[list[int]] = []
    for raw in spec.split(","):
        m = _TOKEN.match(raw.strip())
        if not m:
            raise ToolError("out_of_range", f"invalid page range '{raw.strip()}'")
        start = int(m.group(1))
        end = int(m.group(2) or start)
        if start < 1 or end < start or end > total:
            raise ToolError(
                "out_of_range", f"range '{raw.strip()}' is outside 1-{total} or reversed"
            )
        ranges.append(list(range(start - 1, end)))
    return ranges


def parse_pages(spec: str, total: int) -> list[int]:
    """'all' or a range spec -> flat sorted unique 0-based page indexes."""
    if spec.strip().lower() == "all":
        return list(range(total))
    return sorted({i for r in parse_ranges(spec, total) for i in r})


def stem(filename: str) -> str:
    return PurePath(filename).stem or "document"

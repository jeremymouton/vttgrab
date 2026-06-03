"""Turn an input URL into an enumerable list of subtitle-segment URLs.

Two input shapes are supported:

* a single segment URL  (``.../segment13.vtt?fastly_token=...``) — we template
  the numeric index and walk the range,
* an HLS media playlist (``.../subtitles.m3u8?...``) — we parse the listed
  segment URIs.

A signed query string (the Fastly token) is preserved on every derived URL,
because the token authorizes the whole directory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple
from urllib.parse import urljoin, urlsplit, urlunsplit

# Matches the LAST run of digits in a segment filename, e.g. "segment13" -> "13".
_INDEX_RE = re.compile(r"^(?P<prefix>.*?)(?P<num>\d+)(?P<suffix>\D*)$")


@dataclass(frozen=True)
class SegmentTemplate:
    """A printf-style description of a numbered segment URL.

    ``url_for(n)`` rebuilds the full URL (query/token included) for index ``n``.
    """

    scheme: str
    netloc: str
    dir_path: str  # path up to and including the trailing slash
    prefix: str  # filename text before the number, e.g. "segment"
    suffix: str  # filename text after the number, e.g. ".vtt"
    query: str  # raw query string (token), without leading '?'
    seed_index: int  # the index present in the user-supplied URL
    pad: int  # zero-pad width (0 = no padding) inferred from the seed filename

    def url_for(self, n: int) -> str:
        num = str(n).zfill(self.pad) if self.pad else str(n)
        path = f"{self.dir_path}{self.prefix}{num}{self.suffix}"
        return urlunsplit((self.scheme, self.netloc, path, self.query, ""))


def is_m3u8(url: str) -> bool:
    """True if the URL path points at an HLS playlist."""
    path = urlsplit(url).path.lower()
    return path.endswith(".m3u8")


def parse_segment_url(url: str) -> SegmentTemplate:
    """Decompose a numbered segment URL into a :class:`SegmentTemplate`.

    Raises ``ValueError`` if the filename has no numeric component to iterate.
    """
    parts = urlsplit(url)
    path = parts.path
    slash = path.rfind("/")
    dir_path = path[: slash + 1]
    filename = path[slash + 1 :]

    m = _INDEX_RE.match(filename)
    if not m:
        raise ValueError(
            f"could not find a numeric segment index in filename {filename!r}; "
            "pass an .m3u8 playlist URL or a URL like '.../segment13.vtt'"
        )
    num = m.group("num")
    return SegmentTemplate(
        scheme=parts.scheme,
        netloc=parts.netloc,
        dir_path=dir_path,
        prefix=m.group("prefix"),
        suffix=m.group("suffix"),
        query=parts.query,
        seed_index=int(num),
        # Preserve zero-padding ("007" -> pad 3); a plain "7"/"13" implies none.
        pad=len(num) if (len(num) > 1 and num[0] == "0") else 0,
    )


def parse_m3u8(text: str, base_url: str) -> List[str]:
    """Parse a media playlist, returning absolute segment URLs in order.

    Relative URIs are resolved against ``base_url``. If a resolved segment URL
    carries no query of its own but the playlist URL did, the playlist's query
    (token) is inherited.
    """
    base_query = urlsplit(base_url).query
    urls: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue  # tags and comments
        resolved = urljoin(base_url, line)
        if base_query and not urlsplit(resolved).query:
            p = urlsplit(resolved)
            resolved = urlunsplit((p.scheme, p.netloc, p.path, base_query, p.fragment))
        urls.append(resolved)
    return urls


def discover_range(
    seed_index: int,
    is_valid: Callable[[int], bool],
    *,
    min_index: int = 0,
    max_index: int = 100_000,
) -> Tuple[int, int]:
    """Find the contiguous valid ``[lo, hi]`` index range around ``seed_index``.

    ``is_valid(n)`` reports whether segment ``n`` exists (HTTP 200 + VTT body).
    Walks down to the first index and up to the last. If the seed itself is
    invalid, scans downward toward ``min_index`` to relocate a valid anchor.
    Raises ``ValueError`` if no valid segment can be found.
    """
    anchor: Optional[int] = None
    if is_valid(seed_index):
        anchor = seed_index
    else:
        # Seed points past the end (or at a hole) — find the nearest valid index
        # at or below it. This keeps a stray "segment9999" URL from giving up.
        probe = seed_index - 1
        while probe >= min_index:
            if is_valid(probe):
                anchor = probe
                break
            probe -= 1
    if anchor is None:
        raise ValueError(f"no valid segment found at or below index {seed_index}")

    lo = anchor
    while lo - 1 >= min_index and is_valid(lo - 1):
        lo -= 1
    hi = anchor
    while hi + 1 <= max_index and is_valid(hi + 1):
        hi += 1
    return lo, hi

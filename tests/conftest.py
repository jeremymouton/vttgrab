"""Shared test fixtures: an in-memory fake of a segmented-VTT HLS server."""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional, Tuple

from vttgrab.fetch import FetchResult

_IDX_RE = re.compile(r"segment(\d+)\.vtt")


def vtt(*cue_blocks: str, timestamp_map: Optional[str] = "MPEGTS:0") -> str:
    """Build a small WEBVTT document body from raw cue blocks.

    Cue blocks are separated by blank lines, as the WebVTT format requires.
    """
    head = "WEBVTT\n"
    if timestamp_map is not None:
        head += f"X-TIMESTAMP-MAP=LOCAL:00:00:00.000,{timestamp_map}\n"
    head += "\n"
    body = "\n\n".join(block.rstrip("\n") for block in cue_blocks)
    return head + (body + "\n" if body else "")


class FakeFetcher:
    """Records calls and returns canned FetchResults via a responder callable."""

    def __init__(self, responder: Callable[[str], Tuple[int, str, str]]):
        self.responder = responder
        self.calls: List[str] = []

    def get(self, url: str) -> FetchResult:
        self.calls.append(url)
        status, ctype, body = self.responder(url)
        return FetchResult(url=url, status=status, content_type=ctype, body=body)


def segment_server(bodies: Dict[int, str]) -> Callable[[str], Tuple[int, str, str]]:
    """A responder that serves ``segmentN.vtt`` from ``bodies`` and returns the
    real server's 500 'invalid segment' sentinel for anything else.
    """

    def responder(url: str) -> Tuple[int, str, str]:
        m = _IDX_RE.search(url)
        if m:
            idx = int(m.group(1))
            if idx in bodies:
                return (200, "text/vtt", bodies[idx])
        return (500, "text/plain; charset=utf-8", "Error 400: 'invalid segment'")

    return responder

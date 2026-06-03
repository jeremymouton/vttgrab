"""Parsing of WebVTT segment text and serialization to .vtt / .srt."""

from __future__ import annotations

import re
from typing import List

from .cue import Cue, format_timestamp, parse_timestamp

# A cue timing line:  <start> --> <end> [settings]
# The arrow may be surrounded by one or more spaces per the spec.
_TIMING_RE = re.compile(
    r"^\s*(?P<start>[0-9:.,]+)\s+-->\s+(?P<end>[0-9:.,]+)(?P<settings>.*)$"
)

# X-TIMESTAMP-MAP=LOCAL:00:00:00.000,MPEGTS:900000
_TSMAP_RE = re.compile(r"X-TIMESTAMP-MAP\s*=\s*(?P<body>.+)", re.IGNORECASE)

# MPEG-2 transport stream clock runs at 90 kHz.
_MPEGTS_HZ = 90_000


def _parse_timestamp_map(line: str) -> int:
    """Return the offset (ms) to add to every cue, from an X-TIMESTAMP-MAP line.

    Per the HLS WebVTT spec, presentation time = cue_local_time - LOCAL + MPEGTS/90000.
    So the constant offset is ``MPEGTS/90000 - LOCAL``. Returns 0 when the map is
    absent or unparseable (the common ``LOCAL:0,MPEGTS:0`` case yields 0 too).
    """
    m = _TSMAP_RE.search(line)
    if not m:
        return 0
    local_ms = 0
    mpegts_ms = 0
    for part in m.group("body").split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        name, _, value = part.partition(":")
        name = name.strip().upper()
        value = value.strip()
        if name == "LOCAL":
            try:
                local_ms = parse_timestamp(value)
            except ValueError:
                local_ms = 0
        elif name == "MPEGTS":
            try:
                # MPEGTS is an integer count of 90 kHz ticks.
                mpegts_ms = round(int(value) * 1000 / _MPEGTS_HZ)
            except ValueError:
                mpegts_ms = 0
    return mpegts_ms - local_ms


def parse_webvtt(text: str) -> List[Cue]:
    """Parse one WebVTT document (a single segment) into a list of cues.

    Applies any X-TIMESTAMP-MAP offset found in the header so the returned cues
    are on the program's absolute timeline, ready to be merged with other
    segments. Malformed cue blocks are skipped rather than raising.
    """
    # Normalize newlines; a BOM sometimes leads segment payloads.
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    offset_ms = 0
    cues: List[Cue] = []

    i = 0
    n = len(lines)
    # The header runs until the first blank line; scan it for the timestamp map.
    while i < n and lines[i].strip() != "":
        if "X-TIMESTAMP-MAP" in lines[i].upper():
            offset_ms = _parse_timestamp_map(lines[i])
        i += 1

    while i < n:
        # Skip blank separators.
        if lines[i].strip() == "":
            i += 1
            continue

        identifier = ""
        # A cue may begin with an identifier line (no '-->') before the timing.
        if "-->" not in lines[i]:
            identifier = lines[i].strip()
            i += 1
            if i >= n:
                break

        timing = _TIMING_RE.match(lines[i])
        if not timing:
            # Not a real cue (stray NOTE/STYLE/REGION block or junk) — skip to
            # the next blank line so we don't misread its body as cues.
            while i < n and lines[i].strip() != "":
                i += 1
            continue
        i += 1

        try:
            start = parse_timestamp(timing.group("start"))
            end = parse_timestamp(timing.group("end"))
        except ValueError:
            continue

        body_lines: List[str] = []
        while i < n and lines[i].strip() != "":
            body_lines.append(lines[i])
            i += 1

        cue = Cue(
            start_ms=start,
            end_ms=end,
            text="\n".join(body_lines),
            settings=timing.group("settings").strip(),
            identifier=identifier,
        )
        cues.append(cue.shifted(offset_ms))

    return cues


def serialize_vtt(cues: List[Cue]) -> str:
    """Serialize cues to a WebVTT document string (trailing newline included)."""
    out = ["WEBVTT", ""]
    for cue in cues:
        timing = (
            f"{format_timestamp(cue.start_ms)} --> {format_timestamp(cue.end_ms)}"
        )
        if cue.settings:
            timing += f" {cue.settings}"
        out.append(timing)
        if cue.text:
            out.append(cue.text)
        out.append("")
    return "\n".join(out) + "\n"


# SRT does not understand WebVTT cue settings; drop them. Inline tags like <i>
# are kept since most players accept them in SRT.
def serialize_srt(cues: List[Cue]) -> str:
    """Serialize cues to a SubRip (.srt) document string."""
    out: List[str] = []
    for idx, cue in enumerate(cues, start=1):
        out.append(str(idx))
        out.append(
            f"{format_timestamp(cue.start_ms, srt=True)} --> "
            f"{format_timestamp(cue.end_ms, srt=True)}"
        )
        out.append(cue.text)
        out.append("")
    return "\n".join(out) + "\n"

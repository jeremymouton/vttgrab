"""Stitch cues from many segments into one ordered, de-duplicated track."""

from __future__ import annotations

from typing import Iterable, List

from .cue import Cue


def merge_cues(segments: Iterable[Iterable[Cue]]) -> List[Cue]:
    """Combine per-segment cue lists into a single sorted, de-duplicated list.

    A cue that straddles a segment boundary is emitted by the server in *both*
    adjacent segments with identical timing and text; we keep only the first
    occurrence. Cues are returned sorted by (start, end) with original relative
    order preserved for ties (stable).
    """
    seen = set()
    flat: List[Cue] = []
    for seg in segments:
        for cue in seg:
            k = cue.key
            if k in seen:
                continue
            seen.add(k)
            flat.append(cue)

    # Stable sort by start then end keeps same-start cues in arrival order.
    flat.sort(key=lambda c: (c.start_ms, c.end_ms))
    return flat

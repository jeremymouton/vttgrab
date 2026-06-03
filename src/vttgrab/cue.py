"""The Cue value object and WebVTT/SRT timestamp parsing & formatting.

Times are carried internally as integer milliseconds to avoid floating-point
drift when we add the X-TIMESTAMP-MAP offset and round-trip through formats.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# WebVTT/SRT timestamps look like  [HH:]MM:SS.mmm  (WebVTT) or  HH:MM:SS,mmm (SRT).
# Hours are optional in WebVTT; the fractional separator may be '.' or ','.
_TIMESTAMP_RE = re.compile(
    r"""
    (?:(?P<h>\d+):)?      # optional hours
    (?P<m>\d{1,2}):       # minutes
    (?P<s>\d{1,2})        # seconds
    [.,](?P<ms>\d{1,3})   # millis, '.' or ','
    """,
    re.VERBOSE,
)


def parse_timestamp(text: str) -> int:
    """Parse a WebVTT/SRT timestamp into integer milliseconds.

    Accepts ``HH:MM:SS.mmm``, ``MM:SS.mmm`` and the SRT comma variant.
    Raises ``ValueError`` if the text is not a well-formed timestamp.
    """
    m = _TIMESTAMP_RE.fullmatch(text.strip())
    if not m:
        raise ValueError(f"not a valid timestamp: {text!r}")
    h = int(m.group("h") or 0)
    minutes = int(m.group("m"))
    seconds = int(m.group("s"))
    # Right-pad the fractional part so "5" -> 500ms, "05" -> 50ms, "050" -> 50ms.
    ms = int(m.group("ms").ljust(3, "0"))
    return ((h * 60 + minutes) * 60 + seconds) * 1000 + ms


def format_timestamp(ms: int, *, srt: bool = False) -> str:
    """Format integer milliseconds as a subtitle timestamp.

    WebVTT -> ``HH:MM:SS.mmm`` ; SRT -> ``HH:MM:SS,mmm``. Negative values clamp
    to zero (a cue can never legitimately start before the program origin).
    """
    if ms < 0:
        ms = 0
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    sep = "," if srt else "."
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{sep}{millis:03d}"


@dataclass
class Cue:
    """A single subtitle cue.

    ``settings`` holds WebVTT cue settings (e.g. ``align:start position:10%``)
    which are preserved for .vtt output and dropped for .srt output.
    """

    start_ms: int
    end_ms: int
    text: str
    settings: str = ""
    identifier: str = field(default="", compare=False)

    @property
    def key(self) -> tuple:
        """Identity used to de-duplicate cues that repeat across segment seams."""
        return (self.start_ms, self.end_ms, self.settings, self.text)

    def shifted(self, offset_ms: int) -> "Cue":
        """Return a copy moved by ``offset_ms`` (used to apply X-TIMESTAMP-MAP)."""
        if offset_ms == 0:
            return self
        return Cue(
            start_ms=self.start_ms + offset_ms,
            end_ms=self.end_ms + offset_ms,
            text=self.text,
            settings=self.settings,
            identifier=self.identifier,
        )

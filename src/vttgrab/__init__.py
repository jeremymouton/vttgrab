"""vttgrab — download and stitch segmented WebVTT/SRT subtitles from HLS streams."""

from .cue import Cue
from .webvtt import parse_webvtt, serialize_vtt, serialize_srt

__version__ = "0.1.0"

__all__ = ["Cue", "parse_webvtt", "serialize_vtt", "serialize_srt", "__version__"]

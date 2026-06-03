import pytest

from vttgrab.source import (
    discover_range,
    is_m3u8,
    parse_m3u8,
    parse_segment_url,
)

SEG_URL = (
    "https://cdn.example.com/media/v1/hls/v7/clear/abc/def/ghi/"
    "segment13.vtt?fastly_token=TOKEN%3D%3D"
)


def test_parse_segment_url_templates_index_and_preserves_query():
    t = parse_segment_url(SEG_URL)
    assert t.seed_index == 13
    assert t.prefix == "segment"
    assert t.suffix == ".vtt"
    assert t.pad == 0
    u0 = t.url_for(0)
    assert u0.endswith("segment0.vtt?fastly_token=TOKEN%3D%3D")
    assert t.url_for(207).endswith("segment207.vtt?fastly_token=TOKEN%3D%3D")
    # directory is preserved
    assert "/ghi/segment0.vtt" in u0


def test_parse_segment_url_zero_padding_preserved():
    t = parse_segment_url("https://h/p/seg_007.vtt?q=1")
    assert t.seed_index == 7
    assert t.pad == 3
    assert t.url_for(8).endswith("seg_008.vtt?q=1")
    assert t.url_for(123).endswith("seg_123.vtt?q=1")


def test_parse_segment_url_without_number_raises():
    with pytest.raises(ValueError):
        parse_segment_url("https://h/p/subtitles.vtt?q=1")


def test_is_m3u8():
    assert is_m3u8("https://h/p/playlist.m3u8?token=x")
    assert not is_m3u8(SEG_URL)


def test_parse_m3u8_relative_and_token_inheritance():
    playlist = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:30
#EXTINF:30.000,
segment0.vtt
#EXTINF:30.000,
segment1.vtt
#EXT-X-ENDLIST
"""
    base = "https://cdn.example.com/a/b/sub.m3u8?fastly_token=TOK"
    urls = parse_m3u8(playlist, base)
    assert urls == [
        "https://cdn.example.com/a/b/segment0.vtt?fastly_token=TOK",
        "https://cdn.example.com/a/b/segment1.vtt?fastly_token=TOK",
    ]


def test_parse_m3u8_absolute_uri_with_own_query_kept():
    playlist = "#EXTM3U\nhttps://other.cdn/x/seg0.vtt?own=1\n"
    urls = parse_m3u8(playlist, "https://cdn/a/sub.m3u8?tok=2")
    assert urls == ["https://other.cdn/x/seg0.vtt?own=1"]


def test_discover_range_walks_both_directions():
    valid = set(range(0, 213))  # segments 0..212 exist

    def is_valid(n):
        return n in valid

    lo, hi = discover_range(13, is_valid)
    assert (lo, hi) == (0, 212)


def test_discover_range_relocates_when_seed_past_end():
    valid = set(range(0, 50))

    def is_valid(n):
        return n in valid

    lo, hi = discover_range(9999, is_valid, max_index=10000)
    assert (lo, hi) == (0, 49)


def test_discover_range_raises_when_nothing_valid():
    with pytest.raises(ValueError):
        discover_range(5, lambda n: False)

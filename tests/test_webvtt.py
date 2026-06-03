from vttgrab.webvtt import parse_webvtt, serialize_srt, serialize_vtt
from vttgrab.cue import Cue


SEGMENT = """WEBVTT
X-TIMESTAMP-MAP=LOCAL:00:00:00.000,MPEGTS:0

06:30.000 --> 06:31.178
not a soymilk shop.

06:31.178 --> 06:33.514
<i>Little Hsin-Hsin Restaurant.</i>
"""


def test_parse_basic_segment():
    cues = parse_webvtt(SEGMENT)
    assert len(cues) == 2
    assert cues[0].start_ms == 6 * 60_000 + 30_000
    assert cues[0].end_ms == 6 * 60_000 + 31_178
    assert cues[0].text == "not a soymilk shop."
    assert cues[1].text == "<i>Little Hsin-Hsin Restaurant.</i>"


def test_header_only_segment_yields_no_cues():
    assert parse_webvtt("WEBVTT\nX-TIMESTAMP-MAP=LOCAL:00:00:00.000,MPEGTS:0\n\n") == []


def test_timestamp_map_offset_applied():
    # MPEGTS 900000 ticks / 90000 = 10s offset; LOCAL 0 -> add 10s.
    body = "WEBVTT\nX-TIMESTAMP-MAP=LOCAL:00:00:00.000,MPEGTS:900000\n\n00:00:01.000 --> 00:00:02.000\nhi\n"
    cues = parse_webvtt(body)
    assert cues[0].start_ms == 11_000
    assert cues[0].end_ms == 12_000


def test_timestamp_map_with_local_offset():
    # presentation = local - LOCAL + MPEGTS/90000 = 5 - 2 + 0 = 3s
    body = "WEBVTT\nX-TIMESTAMP-MAP=LOCAL:00:00:02.000,MPEGTS:0\n\n00:00:05.000 --> 00:00:06.000\nhi\n"
    cues = parse_webvtt(body)
    assert cues[0].start_ms == 3_000


def test_multiline_cue_and_settings():
    body = (
        "WEBVTT\n\n00:00:01.000 --> 00:00:02.000 align:start position:10%\n"
        "line one\nline two\n"
    )
    cues = parse_webvtt(body)
    assert cues[0].text == "line one\nline two"
    assert cues[0].settings == "align:start position:10%"


def test_cue_identifier_is_skipped_in_timing():
    body = "WEBVTT\n\ncue-7\n00:00:01.000 --> 00:00:02.000\nhello\n"
    cues = parse_webvtt(body)
    assert len(cues) == 1
    assert cues[0].identifier == "cue-7"
    assert cues[0].text == "hello"


def test_note_block_is_ignored():
    body = "WEBVTT\n\nNOTE this is a comment\nspanning lines\n\n00:00:01.000 --> 00:00:02.000\nhi\n"
    cues = parse_webvtt(body)
    assert len(cues) == 1
    assert cues[0].text == "hi"


def test_crlf_and_bom_tolerated():
    body = "﻿WEBVTT\r\n\r\n00:00:01.000 --> 00:00:02.000\r\nhi\r\n"
    cues = parse_webvtt(body)
    assert len(cues) == 1
    assert cues[0].text == "hi"


def test_serialize_vtt_round_trip():
    cues = [
        Cue(390_000, 391_178, "not a soymilk shop."),
        Cue(391_178, 393_514, "<i>Little Hsin-Hsin Restaurant.</i>"),
    ]
    out = serialize_vtt(cues)
    assert out.startswith("WEBVTT\n")
    assert "00:06:30.000 --> 00:06:31.178" in out
    reparsed = parse_webvtt(out)
    assert [c.text for c in reparsed] == [c.text for c in cues]
    assert [c.start_ms for c in reparsed] == [c.start_ms for c in cues]


def test_serialize_srt_numbers_and_comma():
    cues = [Cue(1000, 2000, "a"), Cue(3000, 4000, "b\nc")]
    out = serialize_srt(cues)
    lines = out.splitlines()
    assert lines[0] == "1"
    assert lines[1] == "00:00:01,000 --> 00:00:02,000"
    assert lines[2] == "a"
    assert "2" in lines
    assert "00:00:03,000 --> 00:00:04,000" in out


def test_serialize_vtt_preserves_settings():
    out = serialize_vtt([Cue(1000, 2000, "x", settings="align:start")])
    assert "00:00:01.000 --> 00:00:02.000 align:start" in out

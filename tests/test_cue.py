import pytest

from vttgrab.cue import Cue, format_timestamp, parse_timestamp


@pytest.mark.parametrize(
    "text,ms",
    [
        ("00:00:00.000", 0),
        ("06:30.000", 6 * 60_000 + 30_000),  # MM:SS.mmm short form
        ("01:40:49.331", (1 * 3600 + 40 * 60 + 49) * 1000 + 331),
        ("00:00:01,500", 1500),  # SRT comma separator
        ("1:02:03.004", (3600 + 2 * 60 + 3) * 1000 + 4),
        ("00:00:00.5", 500),  # short millis right-pad
        ("00:00:00.05", 50),
    ],
)
def test_parse_timestamp(text, ms):
    assert parse_timestamp(text) == ms


def test_parse_timestamp_rejects_garbage():
    with pytest.raises(ValueError):
        parse_timestamp("not a time")
    with pytest.raises(ValueError):
        parse_timestamp("12:34")  # no seconds/millis


def test_format_timestamp_vtt_and_srt():
    ms = (1 * 3600 + 2 * 60 + 3) * 1000 + 4
    assert format_timestamp(ms) == "01:02:03.004"
    assert format_timestamp(ms, srt=True) == "01:02:03,004"


def test_format_timestamp_clamps_negative():
    assert format_timestamp(-50) == "00:00:00.000"


def test_timestamp_round_trip():
    for text in ["00:06:30.000", "01:40:49.331", "00:00:00.000"]:
        assert format_timestamp(parse_timestamp(text)) == text


def test_cue_key_and_shift():
    c = Cue(1000, 2000, "hi", settings="align:start")
    assert c.key == (1000, 2000, "align:start", "hi")
    s = c.shifted(500)
    assert (s.start_ms, s.end_ms) == (1500, 2500)
    assert c.shifted(0) is c  # no-op returns same object

from vttgrab.downloader import download_subtitles
from vttgrab.fetch import FetchResult

from conftest import FakeFetcher, segment_server, vtt


def _movie_bodies():
    # 3 content segments + 1 trailing empty segment (like the real stream's tail).
    return {
        0: vtt("00:00:01.000 --> 00:00:02.000\nhello"),
        1: vtt(
            "00:00:02.000 --> 00:00:03.000\nworld",
            # boundary cue duplicated into the next segment:
            "00:00:03.000 --> 00:00:04.000\nseam",
        ),
        2: vtt(
            "00:00:03.000 --> 00:00:04.000\nseam",
            "00:00:04.000 --> 00:00:05.000\nend",
        ),
        3: vtt(),  # valid but empty
    }


def test_download_discovers_range_and_merges():
    fetcher = FakeFetcher(segment_server(_movie_bodies()))
    # Seed URL points at segment1; discovery should find 0..3.
    url = "https://cdn/x/y/segment1.vtt?fastly_token=TOK"
    result = download_subtitles(url, fetcher=fetcher, concurrency=4)

    assert [c.text for c in result.cues] == ["hello", "world", "seam", "end"]
    assert result.segment_count == 4
    assert result.empty_segments == 1


def test_download_respects_explicit_start_end():
    fetcher = FakeFetcher(segment_server(_movie_bodies()))
    url = "https://cdn/x/y/segment0.vtt?fastly_token=TOK"
    result = download_subtitles(url, fetcher=fetcher, start=0, end=1)
    assert [c.text for c in result.cues] == ["hello", "world", "seam"]
    assert result.segment_count == 2


def test_download_progress_callback_invoked():
    fetcher = FakeFetcher(segment_server(_movie_bodies()))
    seen = []
    download_subtitles(
        "https://cdn/x/y/segment0.vtt?tok=1",
        fetcher=fetcher,
        on_progress=lambda d, t: seen.append((d, t)),
    )
    assert seen[-1][0] == seen[-1][1]  # ends at done==total
    assert seen[-1][1] == 4


def test_download_m3u8_playlist():
    bodies = _movie_bodies()
    playlist = "#EXTM3U\n" + "".join(
        f"#EXTINF:1.0,\nsegment{i}.vtt\n" for i in range(4)
    )

    def responder(url):
        if ".m3u8" in url:
            return (200, "application/x-mpegURL", playlist)
        return segment_server(bodies)(url)

    fetcher = FakeFetcher(responder)
    result = download_subtitles(
        "https://cdn/x/y/subs.m3u8?fastly_token=TOK", fetcher=fetcher
    )
    assert [c.text for c in result.cues] == ["hello", "world", "seam", "end"]


def test_download_single_valid_segment_only():
    fetcher = FakeFetcher(segment_server({5: vtt("00:00:01.000 --> 00:00:02.000\nonly")}))
    result = download_subtitles("https://cdn/x/y/segment5.vtt?t=1", fetcher=fetcher)
    assert [c.text for c in result.cues] == ["only"]
    assert result.segment_count == 1

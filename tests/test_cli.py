import os

import pytest

from vttgrab import cli

from conftest import FakeFetcher, segment_server, vtt


def _bodies():
    return {
        0: vtt("00:00:01.000 --> 00:00:02.000\nhello"),
        1: vtt("00:00:02.000 --> 00:00:03.000\nworld"),
    }


@pytest.fixture
def patched_fetcher(monkeypatch):
    """Replace HttpFetcher in the CLI with one backed by the fake server."""
    responder = segment_server(_bodies())

    def factory(**kwargs):
        return FakeFetcher(responder)

    monkeypatch.setattr(cli, "HttpFetcher", factory)
    return responder


def test_cli_writes_vtt(patched_fetcher, tmp_path):
    out = tmp_path / "movie.vtt"
    rc = cli.main(["https://cdn/x/y/segment0.vtt?tok=1", "-o", str(out)])
    assert rc == 0
    text = out.read_text()
    assert text.startswith("WEBVTT")
    assert "hello" in text and "world" in text
    assert "00:00:01.000 --> 00:00:02.000" in text


def test_cli_auto_format_srt_from_extension(patched_fetcher, tmp_path):
    out = tmp_path / "movie.srt"
    rc = cli.main(["https://cdn/x/y/segment0.vtt?tok=1", "-o", str(out)])
    assert rc == 0
    text = out.read_text()
    assert text.splitlines()[0] == "1"
    assert "00:00:01,000 --> 00:00:02,000" in text  # comma => SRT


def test_cli_explicit_srt_format(patched_fetcher, tmp_path):
    out = tmp_path / "subs.txt"
    rc = cli.main(
        ["https://cdn/x/y/segment0.vtt?tok=1", "-o", str(out), "-f", "srt"]
    )
    assert rc == 0
    assert "-->" in out.read_text() and "," in out.read_text()


def test_cli_stdout(patched_fetcher, capsys):
    rc = cli.main(["https://cdn/x/y/segment0.vtt?tok=1", "-o", "-", "-q"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("WEBVTT")


def test_cli_refuses_overwrite(patched_fetcher, tmp_path):
    out = tmp_path / "exists.vtt"
    out.write_text("old")
    rc = cli.main(["https://cdn/x/y/segment0.vtt?tok=1", "-o", str(out)])
    assert rc == 1
    assert out.read_text() == "old"  # untouched


def test_cli_overwrite_flag(patched_fetcher, tmp_path):
    out = tmp_path / "exists.vtt"
    out.write_text("old")
    rc = cli.main(
        ["https://cdn/x/y/segment0.vtt?tok=1", "-o", str(out), "--overwrite"]
    )
    assert rc == 0
    assert "hello" in out.read_text()


def test_cli_start_end(patched_fetcher, tmp_path):
    out = tmp_path / "m.vtt"
    rc = cli.main(
        ["https://cdn/x/y/segment0.vtt?tok=1", "-o", str(out), "--start", "0", "--end", "0"]
    )
    assert rc == 0
    text = out.read_text()
    assert "hello" in text and "world" not in text


def test_cli_bad_header_errors(patched_fetcher, capsys):
    with pytest.raises(SystemExit):
        cli.main(["https://cdn/x/y/segment0.vtt?tok=1", "-H", "no-colon-here"])


def test_cli_no_cues_returns_error(monkeypatch, tmp_path):
    # A server where the seed exists but has no cues anywhere.
    monkeypatch.setattr(
        cli, "HttpFetcher", lambda **k: FakeFetcher(segment_server({0: vtt()}))
    )
    rc = cli.main(["https://cdn/x/y/segment0.vtt?tok=1", "-o", str(tmp_path / "e.vtt")])
    assert rc == 1


def test_default_output_name_for_m3u8():
    assert cli._default_output("https://h/p/subs.m3u8?t=1", "vtt") == "subs.vtt"
    assert cli._default_output("https://h/p/segment0.vtt?t=1", "srt") == "subtitles.srt"

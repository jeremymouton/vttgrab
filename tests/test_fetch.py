import urllib.error

import pytest

from vttgrab.fetch import FetchError, FetchResult, HttpFetcher


def test_fetchresult_helpers():
    r = FetchResult("u", 200, "text/vtt", "WEBVTT\n\n")
    assert r.ok and r.looks_like_vtt
    e = FetchResult("u", 500, "text/plain", "Error 400: 'invalid segment'")
    assert not e.ok and not e.looks_like_vtt
    bom = FetchResult("u", 200, "", "﻿WEBVTT\n")
    assert bom.looks_like_vtt


class _Resp:
    def __init__(self, body):
        self._body = body.encode()
        self.status = 200

        class _H:
            def get_content_charset(self_inner):
                return "utf-8"

            def get(self_inner, k, default=""):
                return "text/vtt" if k == "Content-Type" else default

        self.headers = _H()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_http_error_is_returned_not_raised(monkeypatch):
    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 500, "err", hdrs=None, fp=None)

    monkeypatch.setattr("vttgrab.fetch.urllib.request.urlopen", fake_urlopen)
    f = HttpFetcher(retries=0, sleep=lambda s: None)
    r = f.get("https://h/segment999.vtt")
    assert r.status == 500
    assert not r.ok


def test_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.URLError("temporary")
        return _Resp("WEBVTT\n\n")

    monkeypatch.setattr("vttgrab.fetch.urllib.request.urlopen", fake_urlopen)
    f = HttpFetcher(retries=3, sleep=lambda s: None)
    r = f.get("https://h/segment0.vtt")
    assert r.ok and r.looks_like_vtt
    assert calls["n"] == 3


def test_retries_exhausted_raises(monkeypatch):
    def fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("down")

    monkeypatch.setattr("vttgrab.fetch.urllib.request.urlopen", fake_urlopen)
    f = HttpFetcher(retries=2, sleep=lambda s: None)
    with pytest.raises(FetchError):
        f.get("https://h/segment0.vtt")


def test_custom_headers_and_user_agent():
    f = HttpFetcher(user_agent="UA/1", headers={"Referer": "https://site"})
    assert f.headers["User-Agent"] == "UA/1"
    assert f.headers["Referer"] == "https://site"

"""A small, dependency-free HTTP GET wrapper with retries.

Returns a :class:`FetchResult` for *every* HTTP response — including 4xx/5xx —
so callers can treat a server's ``500 'invalid segment'`` as an ordinary "stop"
signal rather than an exception. Only genuine transport failures (DNS, reset,
timeout) are retried and ultimately raised.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, Optional

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass
class FetchResult:
    url: str
    status: int
    content_type: str
    body: str

    @property
    def ok(self) -> bool:
        return self.status == 200

    @property
    def looks_like_vtt(self) -> bool:
        return self.body.lstrip("﻿ \t\r\n").upper().startswith("WEBVTT")


class FetchError(RuntimeError):
    """Raised when a URL cannot be retrieved after all retries (transport-level)."""


class HttpFetcher:
    """Fetches URLs over HTTP(S). Thread-safe: each call opens its own request."""

    def __init__(
        self,
        *,
        headers: Optional[Dict[str, str]] = None,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 30.0,
        retries: int = 3,
        backoff: float = 0.5,
        sleep=time.sleep,
    ):
        self.timeout = timeout
        self.retries = max(0, retries)
        self.backoff = backoff
        self._sleep = sleep
        self.headers = {"User-Agent": user_agent}
        if headers:
            self.headers.update(headers)

    def get(self, url: str) -> FetchResult:
        last_exc: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            try:
                req = urllib.request.Request(url, headers=self.headers, method="GET")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read()
                    charset = resp.headers.get_content_charset() or "utf-8"
                    return FetchResult(
                        url=url,
                        status=getattr(resp, "status", 200) or 200,
                        content_type=resp.headers.get("Content-Type", ""),
                        body=raw.decode(charset, errors="replace"),
                    )
            except urllib.error.HTTPError as e:
                # The server answered — surface it (e.g. the 500 'invalid segment'
                # sentinel) instead of retrying or raising.
                raw = b""
                try:
                    raw = e.read()
                except Exception:
                    pass
                return FetchResult(
                    url=url,
                    status=e.code,
                    content_type=e.headers.get("Content-Type", "") if e.headers else "",
                    body=raw.decode("utf-8", errors="replace"),
                )
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_exc = e
                if attempt < self.retries:
                    self._sleep(self.backoff * (2 ** attempt))
                    continue
        raise FetchError(f"failed to fetch {url}: {last_exc}")

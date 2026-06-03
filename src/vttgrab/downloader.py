"""High-level orchestration: input URL -> merged list of cues.

Ties together :mod:`source` (what to fetch), :mod:`fetch` (getting bytes),
:mod:`webvtt` (parsing) and :mod:`merge` (stitching).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .cue import Cue
from .fetch import FetchError, FetchResult, HttpFetcher
from .merge import merge_cues
from .source import (
    SegmentTemplate,
    discover_range,
    is_m3u8,
    parse_m3u8,
    parse_segment_url,
)
from .webvtt import parse_webvtt

ProgressCb = Callable[[int, int], None]


@dataclass
class DownloadResult:
    cues: List[Cue]
    segment_urls: List[str] = field(default_factory=list)
    empty_segments: int = 0

    @property
    def segment_count(self) -> int:
        return len(self.segment_urls)


def _fetch_many(
    fetcher,
    urls: List[str],
    *,
    concurrency: int,
    on_progress: Optional[ProgressCb],
    prefilled: Optional[Dict[str, FetchResult]] = None,
) -> List[FetchResult]:
    """Fetch ``urls`` (concurrently) preserving input order. Reuses any results
    already present in ``prefilled`` (the discovery probes) to avoid re-fetching.
    """
    results: List[Optional[FetchResult]] = [None] * len(urls)
    prefilled = prefilled or {}
    todo = []
    done = 0
    total = len(urls)
    for i, url in enumerate(urls):
        if url in prefilled:
            results[i] = prefilled[url]
            done += 1
            if on_progress:
                on_progress(done, total)
        else:
            todo.append(i)

    if todo:
        workers = max(1, min(concurrency, len(todo)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_to_i = {pool.submit(fetcher.get, urls[i]): i for i in todo}
            for fut in future_to_i:
                pass  # submitted
            for fut, i in list(future_to_i.items()):
                results[i] = fut.result()
                done += 1
                if on_progress:
                    on_progress(done, total)

    return [r for r in results if r is not None]


def download_subtitles(
    url: str,
    *,
    fetcher=None,
    start: Optional[int] = None,
    end: Optional[int] = None,
    concurrency: int = 8,
    on_progress: Optional[ProgressCb] = None,
    max_index: int = 100_000,
) -> DownloadResult:
    """Download every subtitle segment reachable from ``url`` and merge them.

    ``start``/``end`` (inclusive) override automatic range discovery for the
    numbered-segment case. For an .m3u8 input the playlist defines the segments.
    """
    fetcher = fetcher or HttpFetcher()

    if is_m3u8(url):
        playlist = fetcher.get(url)
        if not playlist.ok:
            raise FetchError(
                f"playlist returned HTTP {playlist.status}: {url}"
            )
        seg_urls = parse_m3u8(playlist.body, url)
        if not seg_urls:
            raise ValueError("playlist contained no segment URIs")
        results = _fetch_many(
            fetcher, seg_urls, concurrency=concurrency, on_progress=on_progress
        )
        return _assemble(seg_urls, results)

    template = parse_segment_url(url)

    # Cache every probe so discovery and the final pass share one fetch per URL.
    cache: Dict[str, FetchResult] = {}

    def fetch_idx(n: int) -> FetchResult:
        u = template.url_for(n)
        if u not in cache:
            cache[u] = fetcher.get(u)
        return cache[u]

    def is_valid(n: int) -> bool:
        r = fetch_idx(n)
        return r.ok and r.looks_like_vtt

    if start is not None and end is not None:
        lo, hi = start, end
    else:
        dlo, dhi = discover_range(
            template.seed_index, is_valid, min_index=0, max_index=max_index
        )
        lo = start if start is not None else dlo
        hi = end if end is not None else dhi

    if hi < lo:
        raise ValueError(f"empty segment range: start={lo} > end={hi}")

    seg_urls = [template.url_for(n) for n in range(lo, hi + 1)]
    results = _fetch_many(
        fetcher,
        seg_urls,
        concurrency=concurrency,
        on_progress=on_progress,
        prefilled=cache,
    )
    return _assemble(seg_urls, results)


def _assemble(seg_urls: List[str], results: List[FetchResult]) -> DownloadResult:
    """Parse fetched segments and merge their cues, skipping non-VTT responses."""
    per_segment: List[List[Cue]] = []
    empty = 0
    for r in results:
        if not (r.ok and r.looks_like_vtt):
            continue
        cues = parse_webvtt(r.body)
        if not cues:
            empty += 1
        per_segment.append(cues)
    merged = merge_cues(per_segment)
    return DownloadResult(cues=merged, segment_urls=seg_urls, empty_segments=empty)

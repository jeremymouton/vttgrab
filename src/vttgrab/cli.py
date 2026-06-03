"""Command-line interface for vttgrab."""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional
from urllib.parse import urlsplit

from . import __version__
from .downloader import download_subtitles
from .fetch import DEFAULT_USER_AGENT, FetchError, HttpFetcher
from .source import is_m3u8
from .webvtt import serialize_srt, serialize_vtt


def _parse_header(values: Optional[List[str]]) -> dict:
    headers = {}
    for item in values or []:
        if ":" not in item:
            raise argparse.ArgumentTypeError(
                f"--header must be 'Name: value', got {item!r}"
            )
        name, _, value = item.partition(":")
        headers[name.strip()] = value.strip()
    return headers


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vttgrab",
        description=(
            "Download and stitch segmented WebVTT subtitles from an HLS stream "
            "into a single .vtt or .srt file."
        ),
    )
    p.add_argument(
        "url",
        help="A subtitle segment URL (.../segment13.vtt?token=...) or an .m3u8 playlist URL.",
    )
    p.add_argument(
        "-o",
        "--output",
        help="Output file. Use '-' for stdout. Default: subtitles.<ext>.",
    )
    p.add_argument(
        "-f",
        "--format",
        choices=["auto", "vtt", "srt"],
        default="auto",
        help="Output format. 'auto' infers from -o extension (default vtt).",
    )
    p.add_argument("--start", type=int, help="First segment index (inclusive).")
    p.add_argument("--end", type=int, help="Last segment index (inclusive).")
    p.add_argument(
        "-c",
        "--concurrency",
        type=int,
        default=8,
        help="Parallel download workers (default 8).",
    )
    p.add_argument(
        "--retries", type=int, default=3, help="Network retries per request (default 3)."
    )
    p.add_argument(
        "--timeout", type=float, default=30.0, help="Per-request timeout seconds (default 30)."
    )
    p.add_argument(
        "-H",
        "--header",
        action="append",
        metavar="'Name: value'",
        help="Extra request header (repeatable), e.g. -H 'Referer: https://site'.",
    )
    p.add_argument("--user-agent", help="Override the User-Agent header.")
    p.add_argument(
        "--overwrite", action="store_true", help="Overwrite the output file if it exists."
    )
    p.add_argument("-q", "--quiet", action="store_true", help="Suppress progress output.")
    p.add_argument(
        "-v", "--verbose", action="store_true", help="Print extra diagnostics to stderr."
    )
    p.add_argument("--version", action="version", version=f"vttgrab {__version__}")
    return p


def _resolve_format(fmt: str, output: Optional[str]) -> str:
    if fmt != "auto":
        return fmt
    if output and output != "-":
        lower = output.lower()
        if lower.endswith(".srt"):
            return "srt"
        if lower.endswith(".vtt"):
            return "vtt"
    return "vtt"


def _default_output(url: str, ext: str) -> str:
    # Name the file after the playlist/segment's directory when we can, else generic.
    path = urlsplit(url).path
    stem = "subtitles"
    if is_m3u8(url):
        base = os.path.basename(path)
        if base.lower().endswith(".m3u8"):
            stem = base[:-5] or stem
    return f"{stem}.{ext}"


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    def log(msg: str) -> None:
        if not args.quiet:
            print(msg, file=sys.stderr)

    try:
        headers = _parse_header(args.header)
    except argparse.ArgumentTypeError as e:
        parser.error(str(e))

    if args.concurrency < 1:
        parser.error("--concurrency must be >= 1")

    fmt = _resolve_format(args.format, args.output)
    output = args.output or _default_output(args.url, fmt)

    if output != "-" and os.path.exists(output) and not args.overwrite:
        print(
            f"error: {output} already exists (use --overwrite to replace it)",
            file=sys.stderr,
        )
        return 1

    fetcher = HttpFetcher(
        headers=headers,
        user_agent=args.user_agent or DEFAULT_USER_AGENT,
        timeout=args.timeout,
        retries=args.retries,
    )

    last_pct = [-1]

    def on_progress(done: int, total: int) -> None:
        if args.quiet:
            return
        pct = int(done * 100 / total) if total else 100
        if pct != last_pct[0]:
            last_pct[0] = pct
            print(f"\r  fetching segments… {done}/{total} ({pct}%)", end="", file=sys.stderr)
            if done == total:
                print("", file=sys.stderr)

    log(f"vttgrab {__version__} — source: {args.url}")
    try:
        result = download_subtitles(
            args.url,
            fetcher=fetcher,
            start=args.start,
            end=args.end,
            concurrency=args.concurrency,
            on_progress=on_progress,
        )
    except (FetchError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130

    if not result.cues:
        print("error: no subtitle cues were found", file=sys.stderr)
        return 1

    text = serialize_srt(result.cues) if fmt == "srt" else serialize_vtt(result.cues)

    if output == "-":
        sys.stdout.write(text)
    else:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(text)

    log(
        f"  {len(result.cues)} cues from {result.segment_count} segments "
        f"({result.empty_segments} empty) -> {output if output != '-' else 'stdout'} [{fmt}]"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

# vttgrab

Download and stitch segmented **WebVTT** subtitles from an HLS stream into a
single `.vtt` or `.srt` file.

Built for streams (Brightcove / Fastly and similar) that serve subtitles as
hundreds of tiny numbered segments — `segment0.vtt`, `segment1.vtt`, … — each a
self-contained WebVTT file. `vttgrab` discovers the whole range from a single
segment URL, downloads every segment (in parallel, with the signed token
preserved), and merges the cues into one continuous, de-duplicated track.

## Why it's needed

A player loads subtitles one segment at a time. There's no single file to
"save as". Each segment:

- carries an `X-TIMESTAMP-MAP` header that anchors its cues on the program
  timeline,
- repeats any cue that straddles a segment boundary in **both** neighbouring
  segments,
- may be empty (gaps with no dialogue) — so "first empty segment" is *not* the
  end of the stream.

`vttgrab` handles all three: it applies the timestamp map, de-duplicates seam
cues, and keeps going until the server actually reports the segment is out of
range.

## Install

Runtime is **stdlib-only** — no third-party dependencies.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
```

This puts a `vttgrab` command on your PATH.

## Usage

Paste **any one** subtitle segment URL — including its `?fastly_token=…` query.
The token signs the whole directory, so `vttgrab` reuses it for every segment:

```bash
# Auto-discover the full range from one segment, write WebVTT
vttgrab 'https://…/segment13.vtt?fastly_token=…' -o movie.vtt

# Convert to SubRip on the way out (format inferred from the .srt extension)
vttgrab 'https://…/segment13.vtt?fastly_token=…' -o movie.srt

# An .m3u8 subtitle playlist works too
vttgrab 'https://…/subtitles.m3u8?fastly_token=…' -o movie.vtt

# Print to stdout
vttgrab 'https://…/segment0.vtt?token=…' -o - -q > movie.vtt
```

> Tip: quote the URL — the signed token contains `&`/`=`/`%` characters that
> your shell would otherwise mangle.

### Options

| Flag | Meaning |
|------|---------|
| `-o, --output` | Output file. `-` for stdout. Default `subtitles.<ext>`. |
| `-f, --format {auto,vtt,srt}` | Output format. `auto` infers from `-o` (default `vtt`). |
| `--start N` / `--end N` | Force the segment index range instead of auto-discovering. |
| `-c, --concurrency K` | Parallel download workers (default 8). |
| `--retries R` | Network retries per request (default 3). |
| `--timeout T` | Per-request timeout, seconds (default 30). |
| `-H, --header 'Name: value'` | Extra request header (repeatable), e.g. a `Referer`. |
| `--user-agent UA` | Override the User-Agent. |
| `--overwrite` | Replace the output file if it already exists. |
| `-q, --quiet` | Suppress all progress/summary output on stderr. |
| `-v, --verbose` | Print extra diagnostics on stderr (resolved config, user-agent, extra headers, segment range, and the cue time span). |
| `--version` | Print the version and exit. |

## How it works

```
input URL ─► source.py    decompose into a segment template (+ token) or parse the m3u8
          ─► fetch.py      HTTP GET with retries; a 500 'invalid segment' is a stop signal
          ─► discover      walk the index down to 0 and up until the server says stop
          ─► webvtt.py     parse each segment, applying its X-TIMESTAMP-MAP offset
          ─► merge.py      concatenate, drop boundary-duplicate cues, sort by time
          ─► serialize     write .vtt or .srt
```

## Development

```bash
pip install -e '.[dev]'
pytest                 # 59 unit tests, no network
```

The HTTP layer is injected, so the entire pipeline is tested against an
in-memory fake of the segmented server (`tests/conftest.py`) — no network
needed for the suite. (A `live` pytest marker is registered for opt-in
network tests, but none ship today.)

## Notes & limits

- **Token expiry.** Signed tokens expire. If you get HTTP 403/410, grab a fresh
  segment URL from the player and re-run.
- **Use responsibly.** Only download subtitles from content you're authorized to
  access.

# Editor — autonomous shorts-editing agent

Claude Code IS reasoning engine. No third-party LLM API call, anywhere. Tool
access only: bash, ffmpeg, whisper (local), yt-dlp, filesystem.

Output: vertical shorts, 9:16, 1080x1920.

## Layout

```
agent/
  planner.md          story/pacing rule set (P1-P13)
  caption_rules.md     word-overlay style/timing rule set (C1-C12)
  music_rules.md        song/BPM/mood matching rule set (M1-M10)
  pipeline.py           9-stage runner: intake, plan, fetch, retrieve,
                         assemble, caption, score, render, qa
.venv/                  local venv, openai-whisper + Pillow installed here
knowledge_base/
  memes/{hindi,kannada,instagram_viral,movie_viral,african}/*.json
  templates/templates.json
  music/index.json
  schema.md              asset schema + legal source_type contract
downloads/               scratch space, gitignored
output/                   final renders + qa_flags, gitignored
```

## Status

- [x] Folder scaffold, `schema.md`, `planner.md`, `caption_rules.md`,
      `music_rules.md` — rule sets written
- [x] `pipeline.py` — all 9 stages implemented and smoke-tested end to end
      against a real public clip (yt-dlp fetch → plan → whisper transcribe
      → word-level caption burn-in → 9:16 crop/scale → ffmpeg render → qa)
- [x] Local whisper installed in `.venv` (`openai-whisper`, no third-party
      API). `transcribe()` shells out to `.venv/bin/whisper`.
- [x] Caption burn-in uses Pillow-rendered PNG overlays + ffmpeg `overlay`
      filter — **not** `drawtext`/`ass`, because the installed Homebrew
      ffmpeg (8.1, minimal bottle) has no freetype/libass compiled in
      (`ffmpeg -filters` shows neither). PNG-overlay path needs nothing
      beyond what's already installed. If a fuller ffmpeg build is ever
      installed, `ass`-based subtitles would be simpler for very long
      caption counts (current approach adds one ffmpeg input per word
      chunk — fine for shorts-length runtimes, gets input-limit-heavy well
      past a few hundred words).
- [x] `retrieve`/`assemble` respect the legal gate (Rule P11): assets stay
      `usable_in_public_render: false` until `source_type` is
      `licensed_local`/`user_provided` with a real `source_path`.
- [x] **Music unblocked** — 16 real tracks in `knowledge_base/music/`,
      sourced from incompetech.com (Kevin MacLeod, CC BY 4.0, no login
      needed — Pixabay was tried first but blocks downloads without an
      account, which is off-limits for me to create). BPM spread 84-178,
      mood-tagged, `source_type: licensed_local`, real `duration_sec` via
      ffprobe. **Attribution required on publish**: "Music by Kevin MacLeod
      (incompetech.com), Licensed under Creative Commons: By Attribution
      4.0" — this is a CC-BY condition, not optional.
- [x] Rule M7 mixing replaced: real two-pass `loudnorm` (measure pass →
      apply pass with `measured_*` values) targeting -14 LUFS integrated,
      then a static -6dB duck, mixed *under* the original dialogue via
      `amix` — **not** per-word sidechain ducking (that needs the dialogue
      track's own loudness profile; static cushion only, flagged as a
      known gap, not something this pass claims to have solved).
      Caught + fixed a real bug in the same pass: the old filter graph
      mapped `[bg]` as the only output audio, silently dropping the
      original dialogue track entirely. Verified fixed via `ffprobe` +
      `loudnorm` measurement on a real render (audio stream present,
      output -13.9 LUFS integrated, ~2 LUFS of headroom left).
- [ ] **Meme/movie clips still metadata-only** — 25 entries (5 per hindi/
      kannada/instagram_viral/movie_viral/african), all
      `reference_link_only`, no video files. Unchanged from your earlier
      explicit call: I don't scrape copyrighted movie/meme content, you
      supply real clip files. **Spec for handing me files fast:
      [`knowledge_base/memes/HOWTO_ADD_CLIP.md`](knowledge_base/memes/HOWTO_ADD_CLIP.md)**
      — 3 clips (one per bucket) is enough to unblock testing, don't need
      all 25 at once.
- [x] **BPM-target QA false-positive fixed** — `music_rules.md` Rule M2
      now tries beat subdivisions k ∈ {0.5, 1, 2, 4} (cut every half/1/2/4
      beats) instead of only k=1, and only flags when the *best* (k, track)
      pair is still >25% off its own target — not whenever the literal k=1
      target has no match. Re-ran the 3 Phase 2 scenarios: all 3
      false-positive flags gone, mood-matching still picks sensible tracks.
      Verified the flag still fires on a genuine mismatch (constructed an
      extreme 20-cuts/sec cut rate on purpose — correctly flagged, closest
      catalog track 422 BPM off).
- [x] **Stress tests — 4 run, 2 real bugs found and fixed**:
  - *Silent clip*: whisper hallucinated a word on pure silence (known
    whisper behavior) at confidence 0.026. The grouping rule (C1-C3) was
    supposed to drop isolated low-confidence words but only handled the
    case where a merge partner existed — a **trailing singleton slipped
    through and would've displayed**. Fixed: isolated low-confidence words
    with no neighbor are now dropped, not merged-or-shown.
  - *Non-English/non-Latin audio*: generated real Hindi speech via macOS
    `say` (Lekha voice) — no copyright risk, fully synthetic. Whisper
    transcribed real Devanagari text correctly. Confirmed the caption font
    (Arial Bold) has no Devanagari/Kannada glyphs — would've rendered tofu
    boxes. Fixed: `_font_for_text()` routes by Unicode block to
    `Devanagari Sangam MN.ttc` / `Kannada Sangam MN.ttc` / `Arial Unicode.ttf`
    (Arabic, CJK) before falling back to Arial Bold. Verified by pulling an
    actual frame from a real render — correct glyphs, not tofu.
  - *Source shorter than target runtime*: an 8x-too-short synthetic clip
    against a 20s plan under-delivered (12s instead of 20s) — the wraparound
    logic clamped the tail cut instead of looping. Fixed: `render()` now
    uses `ffmpeg -stream_loop -1` whenever a beat needs more footage than
    remains in the source past the wrapped cursor, so the planned duration
    is always delivered in full. Verified: 20.08s actual against a 20s plan.
  - *Bad/dead yt-dlp link*: was already failing loudly (`subprocess`
    `check=True`), but the error was a generic `CalledProcessError`.
    Tightened into a `FetchError` with the URL and yt-dlp's stderr attached,
    plus explicit checks for empty stdout and a missing/empty output file —
    no path where a bad fetch silently passes an empty file downstream.
      Verified with a real dead video id.
- [x] **Usability**: `pipeline.py __main__` and any `summarize(ctx)` call
      now print a one-screen run summary — goal/mood, actual render
      duration, cut counts, caption chunk count, selected track + measured
      LUFS, and every QA flag — instead of needing a log dig.
- [x] **Batch mode** — `run_batch(items)` runs a `list[BatchItem]`
      sequentially (no concurrency — not needed yet, sequential is simpler
      and correct; parallelize the render stage later only if this turns
      out too slow in practice). One bad item doesn't kill the queue: caught
      per-item, recorded as `failed` with the real error, batch continues.
      `summarize_batch(results)` prints per-item summaries plus an
      N/total tally. Verified with a 2-item batch (1 real fetch+render,
      1 deliberately dead link) — the good item rendered clean, the bad
      one failed with a clear `FetchError`, no crash, no orphaned files.
- [x] **Scratch-space hygiene**:
  - `run()` now defaults `reel_id` to a slug of the instruction (was a
    hardcoded `"reel"` for every call) — two different runs no longer
    collide on the same temp/output filenames.
  - `render()` wraps its trims/concat/caption-PNG temp files in a
    try/finally via `_cleanup_reel_temp()`, called *before* a render
    starts too (clearing any leftovers from a previous crashed run with
    the same `reel_id`) — a failed render never leaves half-written
    intermediates for a later run to pick up. Verified by watching
    `output/` after the deliberately-failed batch item above: nothing
    named after that reel_id was left behind.
  - `downloads/` (raw fetched clips + whisper transcripts) is wiped after
    every *successful* render via `clear_downloads()` — source footage is
    always re-fetchable from the original URL, nothing there is worth
    keeping. `output/` (final renders + `*_qa_flags.md`) is never
    auto-deleted by anything in this pipeline.

## Current real limitations (read before assuming more coverage exists)

- **Meme KB is still almost entirely stubs.** 25 metadata entries, 0 real
  clip files as of this writing. `assemble()`'s meme-insert path (Rule
  P9/P10/P12) is validated on logic and legal-gate behavior, but not on
  real footage yet — that only happens once real files land per
  `knowledge_base/memes/HOWTO_ADD_CLIP.md`.
- **Music index is 16 tracks**, all from one source (incompetech.com,
  Kevin MacLeod). Covers the mood/BPM spread exercised in testing so far;
  a goal/mood combo that comes up empty in real use is the trigger to add
  more, not a fixed target count.
- **No concurrency.** `run_batch()` is strictly sequential — fine for the
  batch sizes tested (2 items), unproven at real scale.
- **Ducking is static, not dynamic.** Music sits at a flat -6dB under
  dialogue for the whole reel, not sidechain-ducked per word (Rule M7's
  fuller intent). Needs the dialogue track's own loudness profile to do
  properly — not attempted yet.
- **ffmpeg build has no freetype/libass** — captions are Pillow-rendered
  PNG overlays composited via the `overlay` filter, one ffmpeg input per
  word chunk. Fine at shorts length; would need revisiting (or a fuller
  ffmpeg build) well past a few hundred words per render.

## Platform dependency (macOS only, currently)

Caption fonts are hardcoded to macOS system paths
(`/System/Library/Fonts/Supplemental/...` — Arial Bold, Arial Unicode,
Devanagari Sangam MN, Kannada Sangam MN — see `_SCRIPT_FONTS` in
`agent/pipeline.py`). A Linux CI runner or another dev's machine won't have
these at those paths and caption rendering will fail loudly (`OSError`
from Pillow) rather than silently produce blank captions. Not yet made
cross-platform — swap in bundled font files (e.g. Noto Sans + Noto Sans
Devanagari/Kannada shipped in-repo) if this needs to run somewhere other
than macOS.

## Dependencies

- Python 3.14 (developed against; not pinned lower)
- `yt-dlp` — system install (not in requirements.txt, expected on PATH)
- `ffmpeg` + `ffprobe` — system install, expected on PATH. This
  environment's Homebrew build has no freetype/libass compiled in, which is
  *why* captions are Pillow PNG overlays instead of `drawtext`/`ass` — see
  the caption note above. A build with freetype/libass works fine too, the
  pipeline just doesn't require it.
- Everything else is pinned in `requirements.txt` (`openai-whisper`,
  `Pillow`, and their transitive deps — `torch` included, whisper's model
  download happens on first `transcribe()` call, not at install time)

## Setup

```bash
cd editor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# yt-dlp and ffmpeg are separate system installs, e.g.:
#   brew install yt-dlp ffmpeg
```

## Try it

```bash
cd editor && source .venv/bin/activate
python3 agent/pipeline.py "funny reaction reel to this clip" "<youtube-url>"
```

Batch mode (Python, not CLI-wired yet):

```python
import sys; sys.path.insert(0, "agent")
import pipeline as p

items = [
    p.BatchItem(instruction="...", links=["<url>"]),
    p.BatchItem(instruction="...", links=["<url>"]),
]
print(p.summarize_batch(p.run_batch(items)))
```

## Legal

Everything under `knowledge_base/memes/` is metadata/references only right
now. No copyrighted movie/meme video files are stored in this repo. Before
any asset ships in a public render its `source_type` must be
`licensed_local` or `user_provided` with a real `source_path` — see
`schema.md` and `planner.md` P11/P12.

`knowledge_base/music/` **does** bundle real audio files (16 tracks,
CC BY 4.0, Kevin MacLeod/incompetech.com) — attribution is a license
condition on any public render that uses one. See [`NOTICE.md`](NOTICE.md)
for the required credit line and [`LICENSE`](LICENSE) for the MIT terms
covering this repo's code (code and bundled assets are under different
licenses — read both before publishing anything made with this).

## Repo readiness

This repo has been prepared for a GitHub push (LICENSE, NOTICE.md,
requirements.txt, .gitignore audited) but **no git commands have been run
here** — no `git init`, no commit, no push. That's intentionally left for
you to do yourself.

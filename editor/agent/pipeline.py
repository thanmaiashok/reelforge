"""
Stage runner for the Editor agent: intake -> plan -> fetch -> retrieve ->
assemble -> caption -> score -> render -> qa.

Each stage is a plain function taking/returning a dict-based Context so
Claude (driving this via Claude Code) can inspect and override state
between stages instead of it being a black box.

No third-party LLM calls anywhere in this file. Reasoning happens via
deterministic rule application (agent/planner.md, caption_rules.md,
music_rules.md) or by shelling out to yt-dlp/ffmpeg/whisper.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "knowledge_base"
DOWNLOADS_DIR = ROOT / "downloads"
OUTPUT_DIR = ROOT / "output"
VENV_WHISPER = ROOT / ".venv" / "bin" / "whisper"

GOALS = ("comedy_reel", "story_reel", "info_reel", "meme_mashup")

# Rule P6: cut-rate target band (seconds per cut) by goal, (build, punchline)
CUT_RATE_SEC = {
    "comedy_reel": {"build": (1.0, 2.0), "punchline": (0.6, 1.2)},
    "story_reel": {"build": (2.5, 4.0), "punchline": (2.5, 4.0)},
    "info_reel": {"build": (1.5, 2.5), "punchline": (1.5, 2.5)},
    "meme_mashup": {"build": (0.8, 1.5), "punchline": (0.8, 1.5)},
}

# Rule C7: mood -> accent color hex
MOOD_ACCENT = {
    "comedic": "#FFD400",
    "sarcastic": "#FFD400",
    "hype": "#FF5A1F",
    "wholesome": "#FFE8C2",
    "nostalgic": "#FFE8C2",
    "dramatic": "#FFFFFF",
    "informative": "#3FD0FF",
}


@dataclass
class Context:
    """Shared state threaded through every pipeline stage."""

    instruction: str
    links: list[str] = field(default_factory=list)
    goal: str | None = None
    plan: dict[str, Any] = field(default_factory=dict)
    fetched_clips: list[Path] = field(default_factory=list)
    retrieved_assets: list[dict[str, Any]] = field(default_factory=list)
    cut_list: list[dict[str, Any]] = field(default_factory=list)
    transcript_words: list[dict[str, Any]] = field(default_factory=list)
    caption_chunks: list[dict[str, Any]] = field(default_factory=list)
    selected_track: dict[str, Any] | None = None
    render_path: Path | None = None
    qa_flags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 1. Intake
# ---------------------------------------------------------------------------
def intake(instruction: str, links: list[str] | None = None) -> Context:
    return Context(instruction=instruction, links=links or [])


# ---------------------------------------------------------------------------
# 2. Plan  (agent/planner.md Rules P1-P9)
# ---------------------------------------------------------------------------
_NARRATIVE_HINTS = ("tell the story of", "what happened when", "the story of")
_REACT_HINTS = ("react to", "funniest", "make fun of")
_MASHUP_HINTS = ("mashup", "compilation")

_MOOD_KEYWORDS = {
    "comedic": ("funny", "comedy", "joke", "hilarious", "meme"),
    "sarcastic": ("sarcastic", "roast", "savage"),
    "wholesome": ("wholesome", "heartwarming", "feel good"),
    "hype": ("hype", "epic", "insane", "crazy"),
    "dramatic": ("dramatic", "shocking", "twist"),
    "informative": ("explain", "how to", "guide", "facts", "did you know"),
    "nostalgic": ("nostalgia", "throwback", "remember when"),
}


def classify_goal(instruction: str, links: list[str]) -> str:
    text = instruction.lower()
    # Rule P3
    if any(h in text for h in _MASHUP_HINTS):
        return "meme_mashup"
    # Rule P2
    if links and any(h in text for h in _REACT_HINTS):
        return "comedy_reel"
    # Rule P1
    if any(h in text for h in _NARRATIVE_HINTS):
        return "story_reel"
    return "info_reel"


def derive_mood_tags(instruction: str, goal: str) -> list[str]:
    text = instruction.lower()
    tags = [m for m, kws in _MOOD_KEYWORDS.items() if any(k in text for k in kws)]
    if not tags:
        # sensible default per goal so retrieval never runs empty
        tags = {
            "comedy_reel": ["comedic"],
            "story_reel": ["dramatic"],
            "info_reel": ["informative"],
            "meme_mashup": ["hype", "comedic"],
        }[goal]
    return tags


def build_beats(goal: str, target_runtime_sec: float) -> list[dict[str, Any]]:
    """Rule P4/P5: 4-beat structure, meme_mashup skips CTA and build."""
    if goal == "meme_mashup":
        return [
            {"name": "hook", "start": 0.0, "end": 1.5},
            {"name": "punchline_chain", "start": 1.5, "end": target_runtime_sec},
        ]
    build_end = target_runtime_sec * 0.65
    punchline_end = target_runtime_sec * 0.85
    return [
        {"name": "hook", "start": 0.0, "end": 1.5},
        {"name": "build", "start": 1.5, "end": build_end},
        {"name": "punchline", "start": build_end, "end": punchline_end},
        {"name": "cta", "start": punchline_end, "end": target_runtime_sec},
    ]


def plan(ctx: Context, target_runtime_sec: float = 30.0) -> Context:
    ctx.goal = classify_goal(ctx.instruction, ctx.links)
    mood_tags = derive_mood_tags(ctx.instruction, ctx.goal)
    ctx.plan = {
        "goal": ctx.goal,
        "mood_tags": mood_tags,
        "beats": build_beats(ctx.goal, target_runtime_sec),
        "cut_rate_sec": CUT_RATE_SEC[ctx.goal],
        "target_runtime_sec": target_runtime_sec,
    }
    return ctx


# ---------------------------------------------------------------------------
# 3. Fetch
# ---------------------------------------------------------------------------
class FetchError(RuntimeError):
    """yt-dlp failed to fetch a source clip — never pass through silently."""


def fetch_clip(url: str, dest_dir: Path = DOWNLOADS_DIR) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_template = str(dest_dir / "%(id)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f", "bv*[height<=1920]+ba/b",
        "--no-playlist",
        "-o", out_template,
        "--print", "after_move:filepath",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise FetchError(
            f"yt-dlp failed for {url!r} (exit {result.returncode}):\n"
            f"{result.stderr.strip()[-800:]}"
        )
    lines = [l for l in result.stdout.strip().splitlines() if l]
    if not lines:
        raise FetchError(f"yt-dlp reported success for {url!r} but printed no filepath")
    filepath = Path(lines[-1])
    if not filepath.exists() or filepath.stat().st_size == 0:
        raise FetchError(f"yt-dlp reported {filepath} for {url!r} but it's missing/empty")
    return filepath


def fetch(ctx: Context) -> Context:
    for url in ctx.links:
        ctx.fetched_clips.append(fetch_clip(url))
    return ctx


# ---------------------------------------------------------------------------
# 4. Retrieve  (schema.md retrieval contract)
# ---------------------------------------------------------------------------
def load_kb_assets(category_dirs: list[str] | None = None) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    memes_dir = KB_DIR / "memes"
    search_dirs = (
        [memes_dir / d for d in category_dirs] if category_dirs else list(memes_dir.glob("*"))
    )
    for d in search_dirs:
        if not d.is_dir():
            continue
        for meta_file in d.glob("*.json"):
            with open(meta_file) as f:
                data = json.load(f)
                assets.extend(data if isinstance(data, list) else [data])
    return assets


def _score_asset(asset: dict[str, Any], mood_tags: list[str], language: str | None) -> float:
    if language and asset.get("language") not in (language, "multi"):
        return -1.0  # exact language match required
    mood_overlap = len(set(asset.get("mood", [])) & set(mood_tags))
    return float(mood_overlap)


def retrieve(ctx: Context, language: str | None = None, top_n: int = 10) -> Context:
    mood_tags = ctx.plan.get("mood_tags", [])
    scored = []
    for asset in load_kb_assets():
        s = _score_asset(asset, mood_tags, language)
        if s < 0:
            continue
        asset = dict(asset)
        # Rule P11: legal gate — reference_link_only never usable in public render
        asset["usable_in_public_render"] = asset.get("source_type") in (
            "licensed_local",
            "user_provided",
        )
        scored.append((s, asset))
    scored.sort(key=lambda t: t[0], reverse=True)
    ctx.retrieved_assets = [a for _, a in scored[:top_n]]
    return ctx


# ---------------------------------------------------------------------------
# 5. Assemble  (planner.md P9-P12)
# ---------------------------------------------------------------------------
def assemble(ctx: Context, min_gap_between_cutaways_sec: float = 4.0) -> Context:
    """Build a cut list from fetched source clips + usable retrieved assets.

    cut_list entries: {source, kind, start, end, insert_type, rule_id, asset_id}
    Source clips fill build/hook/cta beats; usable meme assets are inserted
    at punchline / end-of-build boundaries only (Rule P9), respecting
    density (Rule P10) and movie-clip trim (Rule P12).
    """
    cut_list: list[dict[str, Any]] = []
    beats = ctx.plan.get("beats", [])
    usable_assets = [a for a in ctx.retrieved_assets if a["usable_in_public_render"]]
    if not usable_assets and ctx.retrieved_assets:
        ctx.qa_flags.append(
            "No usable meme/template assets (all retrieved candidates are "
            "reference_link_only) — punchline/build beats fall back to source "
            "footage only. Provide licensed_local clips to enable inserts."
        )

    last_cutaway_end = -min_gap_between_cutaways_sec
    asset_i = 0
    src_i = 0

    for beat in beats:
        beat_name = beat["name"]
        beat_start, beat_end = beat["start"], beat["end"]

        wants_cutaway = beat_name in ("punchline", "punchline_chain") and usable_assets
        if wants_cutaway and (beat_start - last_cutaway_end) >= min_gap_between_cutaways_sec:
            asset = usable_assets[asset_i % len(usable_assets)]
            asset_i += 1
            dur = asset["duration_hint_sec"]
            # Rule P12: movie_viral clips capped at <=3s regardless of hint
            if asset.get("category") == "movie_viral":
                dur = min(dur, 3.0)
            dur = min(dur, beat_end - beat_start)
            cut_list.append({
                "kind": "meme_insert",
                "source": asset.get("source_path"),
                "asset_id": asset["id"],
                "start": beat_start,
                "end": beat_start + dur,
                "rule_id": "P9/P10" + ("/P12" if asset.get("category") == "movie_viral" else ""),
            })
            last_cutaway_end = beat_start + dur
            beat_start += dur
            if beat_start >= beat_end:
                continue

        if ctx.fetched_clips:
            clip = ctx.fetched_clips[src_i % len(ctx.fetched_clips)]
            src_i += 1
            cut_list.append({
                "kind": "source",
                "source": str(clip),
                "start": beat_start,
                "end": beat_end,
                "rule_id": f"beat:{beat_name}",
            })

    ctx.cut_list = cut_list
    return ctx


# ---------------------------------------------------------------------------
# 6. Caption  (caption_rules.md C1-C12)
# ---------------------------------------------------------------------------
def transcribe(clip_path: Path, model: str = "base") -> list[dict[str, Any]]:
    """Run local whisper on a clip, return word-level timestamps."""
    whisper_bin = str(VENV_WHISPER) if VENV_WHISPER.exists() else "whisper"
    out_dir = DOWNLOADS_DIR / "_transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        whisper_bin, str(clip_path),
        "--model", model,
        "--word_timestamps", "True",
        "--output_format", "json",
        "--output_dir", str(out_dir),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    json_path = out_dir / (clip_path.stem + ".json")
    with open(json_path) as f:
        data = json.load(f)
    words: list[dict[str, Any]] = []
    for seg in data.get("segments", []):
        for w in seg.get("words", []):
            words.append({
                "word": w["word"].strip(),
                "start": w["start"],
                "end": w["end"],
                "confidence": w.get("probability", 1.0),
            })
    return words


def _group_words(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Rule C1-C3: 1 word per chunk, merge short/low-confidence neighbors.

    A low-confidence word with no neighbor to merge into (e.g. a lone
    whisper hallucination on a silent/near-silent clip) is dropped rather
    than shown isolated — Rule C3's intent is "never display a likely-wrong
    word alone", which a trailing singleton would otherwise violate.
    """
    chunks: list[list[dict[str, Any]]] = []
    i = 0
    while i < len(words):
        w = words[i]
        dur = w["end"] - w["start"]
        low_conf = w["confidence"] < 0.55
        has_next = i + 1 < len(words)
        merge_next = has_next and (
            (dur < 0.15 and (words[i + 1]["end"] - words[i + 1]["start"]) < 0.15)
            or low_conf
        )
        if merge_next:
            chunks.append([w, words[i + 1]])
            i += 2
        elif low_conf and not has_next:
            i += 1  # drop: isolated low-confidence word, nothing to merge into
        else:
            chunks.append([w])
            i += 1
    return chunks


def caption(ctx: Context) -> Context:
    mood_tags = ctx.plan.get("mood_tags", [])
    accent = next((MOOD_ACCENT[m] for m in mood_tags if m in MOOD_ACCENT), "#FFD400")

    chunks = []
    for group in _group_words(ctx.transcript_words):
        start = group[0]["start"]
        end = group[-1]["end"]
        text = " ".join(w["word"] for w in group)
        max_rms_word = max(group, key=lambda w: w.get("confidence", 0))
        # Rule C8: crude emphasis proxy — real RMS needs audio analysis;
        # fall back to ALL-CAPS / numeric heuristic which is decidable from text alone.
        emphasize = text.isupper() or any(c.isdigit() for c in text)
        chunks.append({
            "text": text,
            "start": start,
            "end": end,
            "emphasize": emphasize,
            "accent_color": accent if emphasize else "#FFFFFF",
        })
    # Rule C12: clamp last chunk to not run past video end (caller sets true end)
    ctx.caption_chunks = chunks
    return ctx


# ---------------------------------------------------------------------------
# 7. Score  (music_rules.md M1-M6)
# ---------------------------------------------------------------------------
def load_music_index() -> list[dict[str, Any]]:
    index_path = KB_DIR / "music" / "index.json"
    if not index_path.exists():
        return []
    with open(index_path) as f:
        return json.load(f)


# Rule M2: target_bpm ~= cuts_per_second * 60 * k. k=1 is cut-on-every-beat;
# real editors don't always cut on every single beat, especially at slow
# cut rates, so also try cutting every 2nd/4th beat (k=2, k=4) and half-beat
# (k=0.5) and keep whichever k lands closest to an actual catalog track.
# This is what "nearest-BPM-within-tolerance" means in practice: we're not
# chasing one literal target, we're finding the most plausible beat
# subdivision a real track could satisfy.
_BPM_K_OPTIONS = (0.5, 1, 2, 4)
_BPM_TOLERANCE_FRAC = 0.25


def score(ctx: Context) -> Context:
    mood_tags = set(ctx.plan.get("mood_tags", []))
    cut_rate = ctx.plan.get("cut_rate_sec", {}).get("build", (1.5, 2.5))
    avg_cut_sec = sum(cut_rate) / 2
    cuts_per_sec = 1.0 / avg_cut_sec if avg_cut_sec else 0.5

    candidates = [
        t for t in load_music_index()
        if t.get("source_type") in ("licensed_local", "royalty_free")  # Rule M3
        and set(t.get("mood", [])) & mood_tags
    ]
    if not candidates:
        ctx.qa_flags.append(
            "No licensed_local/royalty_free track in knowledge_base/music/index.json "
            "matches mood tags — render will ship without scored music until one is added."
        )
        ctx.selected_track = None
        return ctx

    best_track, best_k, best_target, best_diff = None, None, None, float("inf")
    for k in _BPM_K_OPTIONS:
        target = cuts_per_sec * 60 * k
        for t in candidates:
            diff = abs(t.get("bpm", target) - target)
            if diff < best_diff:
                best_track, best_k, best_target, best_diff = t, k, target, diff

    tolerance = best_target * _BPM_TOLERANCE_FRAC
    if best_diff > tolerance:
        ctx.qa_flags.append(
            f"No track within ±{_BPM_TOLERANCE_FRAC:.0%} of any plausible beat-subdivision "
            f"target (closest: {best_target:.0f} BPM at k={best_k}, catalog closest "
            f"{best_track.get('bpm')} BPM, off by {best_diff:.0f}) — Rule M2 pacing "
            "mismatch, used anyway."
        )
    ctx.selected_track = best_track
    return ctx


# ---------------------------------------------------------------------------
# 8. Render
# ---------------------------------------------------------------------------
_FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
_CAPTION_PNG_SIZE = (1080, 260)  # wide strip, positioned at ~62% frame height

# Arial Bold has no glyphs outside Latin/Cyrillic/Greek — whisper transcribes
# non-English audio in its native script, so a caption in Devanagari/Kannada/
# etc. would render as tofu boxes with the Latin font. Pick a script-matched
# system font by Unicode block instead. These aren't bold-weight fonts (macOS
# ships them regular-only), so stroke_width compensates a bit more for those.
_SCRIPT_FONTS = [
    (range(0x0900, 0x0980), "/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc"),
    (range(0x0C80, 0x0D00), "/System/Library/Fonts/Supplemental/Kannada Sangam MN.ttc"),
    (range(0x0600, 0x0700), "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),  # Arabic/Urdu
    (range(0x4E00, 0xA000), "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),  # CJK
]


def _font_for_text(text: str) -> str:
    for ch in text:
        cp = ord(ch)
        for block, font_path in _SCRIPT_FONTS:
            if cp in block:
                return font_path
    return _FONT_PATH


def _render_caption_png(text: str, color_hex: str, out_path: Path) -> Path:
    """Rule C4: bold white/accent fill, black stroke outline, centered."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", _CAPTION_PNG_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font_path = _font_for_text(text)
    font = ImageFont.truetype(font_path, size=110)
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=6)
    x = (_CAPTION_PNG_SIZE[0] - (bbox[2] - bbox[0])) / 2 - bbox[0]
    y = (_CAPTION_PNG_SIZE[1] - (bbox[3] - bbox[1])) / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=color_hex, stroke_width=6, stroke_fill="black")
    img.save(out_path)
    return out_path


def _build_caption_overlays(chunks: list[dict[str, Any]], out_dir: Path) -> list[dict[str, Any]]:
    """Render each caption chunk to a PNG. Returns [{path, start, end}]."""
    out_dir.mkdir(parents=True, exist_ok=True)
    overlays = []
    for i, c in enumerate(chunks):
        png_path = out_dir / f"cap_{i:04d}.png"
        color = c["accent_color"] if c["emphasize"] else "#FFFFFF"
        _render_caption_png(c["text"], color, png_path)
        overlays.append({"path": png_path, "start": c["start"], "end": c["end"]})
    return overlays


def _loudnorm_measure(audio_path: str, target_i: float = -14.0) -> dict[str, str]:
    """Two-pass loudnorm, pass 1: measure. Returns ffmpeg's measured_* JSON."""
    cmd = [
        "ffmpeg", "-i", audio_path,
        "-af", f"loudnorm=I={target_i}:TP=-1.5:LRA=11:print_format=json",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    stderr = result.stderr
    start, end = stderr.rindex("{"), stderr.rindex("}") + 1
    return json.loads(stderr[start:end])


def _loudnorm_apply_filter(measured: dict[str, str], target_i: float = -14.0) -> str:
    """Two-pass loudnorm, pass 2: apply using pass-1 measured_* values."""
    return (
        f"loudnorm=I={target_i}:TP=-1.5:LRA=11:"
        f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}:linear=true"
    )


def _probe_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def _cleanup_reel_temp(reel_id: str) -> None:
    """Remove every intermediate this reel_id could have left behind.

    Called both before a render starts (in case a previous run with the
    same reel_id crashed mid-way and left partial files) and after, in a
    finally block, so a failed run never leaves something a later run
    with the same id could accidentally pick up.
    """
    for d in (OUTPUT_DIR / f"{reel_id}_trims", OUTPUT_DIR / f"{reel_id}_captions"):
        shutil.rmtree(d, ignore_errors=True)
    for f in (OUTPUT_DIR / f"{reel_id}_concat.txt", OUTPUT_DIR / f"{reel_id}_concat.mp4"):
        f.unlink(missing_ok=True)


def render(ctx: Context, reel_id: str = "reel") -> Context:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not ctx.cut_list:
        raise ValueError("cut_list is empty — run assemble() first")

    _cleanup_reel_temp(reel_id)  # clear any stale leftovers from a prior crash
    try:
        return _render_inner(ctx, reel_id)
    finally:
        _cleanup_reel_temp(reel_id)  # never leave trims/concat/caption temp files behind


def _render_inner(ctx: Context, reel_id: str) -> Context:
    # Trim each cut to its planned duration before concatenating. `source`
    # cuts advance a per-file cursor so repeated beats sample fresh footage
    # instead of replaying the same seconds; `meme_insert` cuts always play
    # from the start of their own short clip. If a source clip is shorter
    # than the cumulative beat time asked of it (e.g. a 3s clip covering a
    # 12s plan), the cursor wraps modulo clip length AND the ffmpeg trim
    # uses `-stream_loop -1` so the requested duration is always delivered
    # in full — never a shrunk tail cut, never an -ss past end-of-file.
    trims_dir = OUTPUT_DIR / f"{reel_id}_trims"
    trims_dir.mkdir(parents=True, exist_ok=True)
    source_cursor: dict[str, float] = {}
    source_duration: dict[str, float] = {}
    trim_paths: list[Path] = []
    for i, cut in enumerate(ctx.cut_list):
        if not cut["source"]:
            continue
        duration = cut["end"] - cut["start"]
        if duration <= 0:
            continue
        src = str(Path(cut["source"]).resolve())
        needs_loop = False
        if cut["kind"] == "source":
            if src not in source_duration:
                source_duration[src] = _probe_duration(src)
            clip_len = source_duration[src]
            offset = source_cursor.get(src, 0.0)
            if clip_len > 0:
                offset = offset % clip_len
                needs_loop = (clip_len - offset) < duration
            source_cursor[src] = offset + duration
        else:
            offset = 0.0
        trim_path = trims_dir / f"trim_{i:04d}.mp4"
        cmd = ["ffmpeg", "-y"]
        if needs_loop:
            cmd += ["-stream_loop", "-1"]
        cmd += ["-ss", f"{offset:.3f}", "-i", src, "-t", f"{duration:.3f}",
                "-c:v", "libx264", "-c:a", "aac", str(trim_path)]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        trim_paths.append(trim_path)

    concat_list_path = OUTPUT_DIR / f"{reel_id}_concat.txt"
    with open(concat_list_path, "w") as f:
        for trim_path in trim_paths:
            # ffmpeg concat demuxer quoting: escape ' as '\'' inside single quotes
            escaped = str(trim_path.resolve()).replace("'", r"'\''")
            f.write(f"file '{escaped}'\n")

    concat_out = OUTPUT_DIR / f"{reel_id}_concat.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list_path),
         "-c", "copy", str(concat_out)],
        check=True, capture_output=True, text=True,
    )

    scale_crop = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"

    final_out = OUTPUT_DIR / f"{reel_id}.mp4"
    cmd = ["ffmpeg", "-y", "-i", str(concat_out)]
    next_input_idx = 1

    overlays = []
    if ctx.caption_chunks:
        overlays = _build_caption_overlays(ctx.caption_chunks, OUTPUT_DIR / f"{reel_id}_captions")
        for ov in overlays:
            cmd += ["-i", str(ov["path"])]

    audio_input_idx = None
    if ctx.selected_track and ctx.selected_track.get("file_path"):
        cmd += ["-i", ctx.selected_track["file_path"]]
        audio_input_idx = next_input_idx + len(overlays)

    filter_parts = [f"[0:v]{scale_crop}[base0]"]
    label = "base0"
    for i, ov in enumerate(overlays):
        in_idx = 1 + i
        out_label = f"base{i + 1}"
        # Rule C4/C5: single caption strip at ~62% frame height, one on screen at a time
        filter_parts.append(
            f"[{label}][{in_idx}:v]overlay=x=0:y=1190:"
            f"enable='between(t,{ov['start']:.3f},{ov['end']:.3f})'[{out_label}]"
        )
        label = out_label
    filter_complex = ";".join(filter_parts)

    map_args = ["-map", f"[{label}]"]
    if audio_input_idx is not None:
        # Rule M7 target -14 LUFS: real two-pass loudnorm (measure, then
        # apply with the measured_* values) rather than a flat volume trim,
        # then mixed *under* the original dialogue track (not replacing it).
        # Duck under dialogue is still a static -6dB cushion, not per-word
        # sidechain ducking — that needs the dialogue track's own loudness
        # profile, a follow-up beyond this pass.
        measured = _loudnorm_measure(ctx.selected_track["file_path"])
        norm_filter = _loudnorm_apply_filter(measured)
        filter_complex += (
            f";[{audio_input_idx}:a]{norm_filter},volume=-6dB[bg]"
            f";[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
        map_args += ["-map", "[aout]"]
    else:
        map_args += ["-map", "0:a?"]

    cmd += ["-filter_complex", filter_complex, *map_args,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(final_out)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    ctx.render_path = final_out
    return ctx


# ---------------------------------------------------------------------------
# 9. QA  (planner.md Rule P13)
# ---------------------------------------------------------------------------
def qa(ctx: Context, reel_id: str = "reel") -> Context:
    flags = list(ctx.qa_flags)

    beats = ctx.plan.get("beats", [])
    if beats and beats[0]["name"] == "hook" and not ctx.fetched_clips and not ctx.cut_list:
        flags.append("Hook check (P4) skipped — no source footage to inspect first frames.")

    if ctx.goal != "meme_mashup" and not any(b["name"] == "cta" for b in beats):
        flags.append("CTA beat missing (P13) for a non-mashup goal.")

    leaked = [c for c in ctx.cut_list if c["kind"] == "meme_insert"
              and not any(a["id"] == c["asset_id"] and a["usable_in_public_render"]
                          for a in ctx.retrieved_assets)]
    if leaked:
        flags.append(f"P11 violation: {len(leaked)} meme insert(s) not marked usable_in_public_render.")

    if ctx.caption_chunks:
        for c in ctx.caption_chunks:
            if c["end"] < c["start"]:
                flags.append(f"Caption chunk end<start: {c}")
                break

    ctx.qa_flags = flags
    if flags:
        flag_path = OUTPUT_DIR / f"{reel_id}_qa_flags.md"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        flag_path.write_text("# QA flags\n\n" + "\n".join(f"- {f}" for f in flags) + "\n")
    return ctx


# ---------------------------------------------------------------------------
# Summary  (usability add — one-screen readout instead of a log dig)
# ---------------------------------------------------------------------------
def summarize(ctx: Context, label: str | None = None) -> str:
    lines = ["=" * 60, f"EDITOR RUN SUMMARY{f' — {label}' if label else ''}", "=" * 60]
    lines.append(f"goal: {ctx.goal}   mood: {', '.join(ctx.plan.get('mood_tags', []))}")
    lines.append(f"planned runtime: {ctx.plan.get('target_runtime_sec')}s")

    if ctx.render_path and ctx.render_path.exists():
        actual_dur = _probe_duration(str(ctx.render_path))
        lines.append(f"render: {ctx.render_path}  ({actual_dur:.2f}s actual)")
    else:
        lines.append("render: (none)")

    src_cuts = [c for c in ctx.cut_list if c["kind"] == "source"]
    meme_cuts = [c for c in ctx.cut_list if c["kind"] == "meme_insert"]
    lines.append(f"cuts: {len(src_cuts)} source, {len(meme_cuts)} meme insert "
                 f"({[c['asset_id'] for c in meme_cuts]})")
    lines.append(f"captions: {len(ctx.caption_chunks)} chunks")

    if ctx.selected_track:
        lines.append(f"music: {ctx.selected_track['title']} "
                     f"({ctx.selected_track.get('bpm')} BPM)")
        if ctx.render_path and ctx.render_path.exists():
            try:
                measured = _loudnorm_measure(str(ctx.render_path))
                lines.append(f"  final mix loudness: {measured['input_i']} LUFS integrated")
            except Exception:
                pass
    else:
        lines.append("music: (none)")

    if ctx.qa_flags:
        lines.append(f"QA flags ({len(ctx.qa_flags)}):")
        lines.extend(f"  - {f}" for f in ctx.qa_flags)
    else:
        lines.append("QA flags: none")
    lines.append("=" * 60)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scratch-space retention
# ---------------------------------------------------------------------------
def _slugify(text: str, max_len: int = 40) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in text]
    slug = "".join(keep).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:max_len] or "reel"


def clear_downloads() -> None:
    """Wipe downloads/ (raw fetched clips + whisper transcripts).

    Source footage is always re-fetchable from the original URL via
    yt-dlp, so nothing here is worth keeping once a render has succeeded.
    output/ is never touched by this — final renders and qa_flags files
    are the actual deliverable and are left alone.
    """
    for child in DOWNLOADS_DIR.iterdir():
        if child.name == ".gitkeep":
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run(
    instruction: str,
    links: list[str] | None = None,
    reel_id: str | None = None,
    cleanup_downloads: bool = True,
) -> Context:
    """Run one instruction end to end. reel_id defaults to a slug of the
    instruction so two different runs never collide on the same temp/output
    filenames (the earlier hardcoded default of "reel" could).
    """
    reel_id = reel_id or _slugify(instruction)
    ctx = intake(instruction, links)
    ctx = plan(ctx)
    ctx = fetch(ctx)
    ctx = retrieve(ctx)
    ctx = assemble(ctx)
    if ctx.fetched_clips:
        ctx.transcript_words = transcribe(ctx.fetched_clips[0])
    ctx = caption(ctx)
    ctx = score(ctx)
    ctx = render(ctx, reel_id=reel_id)
    ctx = qa(ctx, reel_id=reel_id)
    if cleanup_downloads and ctx.render_path and ctx.render_path.exists():
        clear_downloads()
    return ctx


@dataclass
class BatchItem:
    instruction: str
    links: list[str] = field(default_factory=list)
    reel_id: str | None = None


@dataclass
class BatchResult:
    reel_id: str
    status: str  # "ok" | "failed"
    ctx: Context | None = None
    error: str | None = None


def run_batch(items: list[BatchItem], cleanup_downloads: bool = True) -> list[BatchResult]:
    """Run a queue of items sequentially — simplest-correct, no concurrency.

    One bad item (bad link, whisper crash, etc.) doesn't kill the queue:
    caught, recorded as failed, temp files for that reel_id cleaned up via
    render()'s own finally block, and the batch moves on.
    """
    results: list[BatchResult] = []
    for i, item in enumerate(items):
        reel_id = item.reel_id or f"batch{i:03d}_{_slugify(item.instruction)}"
        try:
            ctx = run(item.instruction, item.links, reel_id=reel_id,
                      cleanup_downloads=cleanup_downloads)
            results.append(BatchResult(reel_id=reel_id, status="ok", ctx=ctx))
        except Exception as e:
            results.append(BatchResult(reel_id=reel_id, status="failed", error=str(e)))
    return results


def summarize_batch(results: list[BatchResult]) -> str:
    lines = ["#" * 60, f"BATCH SUMMARY — {len(results)} item(s)", "#" * 60]
    for r in results:
        if r.status == "ok" and r.ctx is not None:
            lines.append(summarize(r.ctx, label=r.reel_id))
        else:
            lines.append(f"[{r.reel_id}] FAILED: {r.error}")
    ok = sum(1 for r in results if r.status == "ok")
    lines.append(f"#  {ok}/{len(results)} succeeded")
    lines.append("#" * 60)
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: pipeline.py '<instruction>' [url ...]")
        raise SystemExit(1)
    result = run(sys.argv[1], sys.argv[2:])
    print(summarize(result))

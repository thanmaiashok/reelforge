# Knowledge Base Schema

## Meme / Template Asset (`knowledge_base/memes/**/metadata.json`, one file per asset OR array file per folder)

```json
{
  "id": "kn_0001",
  "language": "kannada",
  "category": "movie_viral",
  "mood": ["comedic", "sarcastic"],
  "format": "reaction_cutaway",
  "duration_hint_sec": 2.5,
  "usage_notes": "best as punchline cutaway, not opener",
  "source_type": "licensed_local | user_provided | reference_link_only",
  "source_path": "knowledge_base/memes/kannada/kn_0001.mp4 | null",
  "reference_url": "https://... | null",
  "tags": ["timing:punchline", "energy:high"]
}
```

Rule: `source_type` decides what agent may do.
- `licensed_local` / `user_provided` — clip on disk (`source_path` set). Safe to composite into public render.
- `reference_link_only` — no local file. Agent must NOT auto-download and hard-cut it into a public render. Flag to user first (see `agent/planner.md` legal gate).

## Template Asset (`knowledge_base/templates/*.json`)

```json
{
  "id": "tpl_hook_split_0001",
  "name": "split_screen_reaction",
  "use_stage": "hook | build | punchline | cta",
  "layout": "full_bleed | split_top_bottom | pip_bottom_right",
  "caption_style_ref": "bold_yellow_pop",
  "notes": "pair with high-energy meme clip, 1.5-2.5s hold"
}
```

## Music Index Entry (`knowledge_base/music/index.json`, array of these)

```json
{
  "id": "mu_0001",
  "title": "local_track_name",
  "file_path": "knowledge_base/music/local_track_name.mp3 | null",
  "source_type": "licensed_local | royalty_free | reference_link_only",
  "bpm": 128,
  "mood": ["hype", "comedic"],
  "energy_curve": "flat | build | drop_at_chorus",
  "drop_time_sec": 14.2,
  "tags": ["pacing:fast_cut"]
}
```

## Retrieval contract

`agent/pipeline.py` retrieve stage queries by `language` + `mood` + `format`/`category` tags produced in the plan stage. Match rule: exact `language` match required for meme assets; `mood`/`tags` match is best-effort scored, top-N returned. Assets with `source_type: reference_link_only` are returned but marked `usable_in_public_render: false` unless user explicitly confirms.

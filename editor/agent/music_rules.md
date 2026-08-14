# Music Rules — song/BPM/mood matching & beat alignment

## 1. Selection

Rule M1: candidate tracks pulled from `knowledge_base/music/index.json` filtered by mood-tag overlap with plan-stage mood vector (≥1 tag match required, prefer ≥2).
Rule M2: BPM target derived from cut rate (Rule P6 in `planner.md`): target_bpm ≈ (cuts_per_second) × 60 × k. Try k ∈ {0.5, 1, 2, 4} — cutting on the half-beat, every beat, every 2nd beat, or every 4th beat are all real editing choices, and slower cut rates (story_reel, info_reel) usually mean cutting every 2-4 beats of a normal-tempo track rather than sourcing an unnaturally slow track. Evaluate every (k, candidate track) pair and keep whichever is closest. Only log a QA flag (pacing mismatch) if that closest match is still outside ±25% of its own target — not whenever the single literal k=1 target has no match. This avoids false-positive flags on every slow-paced goal while still catching genuine no-good-match cases.
Rule M3: `source_type: reference_link_only` tracks are excluded from Score stage by default (same legal gate as `planner.md` P11) — licensed_local/royalty_free only for actual render audio.

## 2. Alignment

Rule M4: track's `drop_time_sec` (if present) aligned to the punchline beat's first frame. Offset track start (trim intro) so drop lands exactly on punchline cut, not before/after.
Rule M5: if no `drop_time_sec` metadata, fall back to aligning nearest strong-beat estimate (from local BPM grid: beat_n = track_start + n × 60/bpm) to hook start (t=0) and to punchline start — two anchor points, stretch/compress permitted only within ±3% tempo (avoid audible pitch artifacts); beyond that, log QA flag instead of stretching further.
Rule M6: every hard cut in Assemble stage should land on-beat (±60ms) where the beat grid allows; if a narratively-required cut can't land on-beat, prefer nudging the cut ±1 frame toward the nearest beat rather than leaving it arbitrary, but never shift a cut enough to break caption sync tolerance (`caption_rules.md` C11).

## 3. Mixing

Rule M7: default music bed level -18 to -14 LUFS relative to dialogue/voiceover, ducked further (-6dB additional) under any spoken word, restored within 200ms after word ends (fast duck, avoid pumping).
Rule M8: at the punchline/drop moment, allow music to peak up to -3dB relative duck reduction for impact (brief foreground moment), then return to standard duck level in Build/CTA.

## 4. Mood energy curve matching

Rule M9: track `energy_curve` should match beat structure —
- `build` curve tracks paired with `comedy_reel`/`story_reel` (tension into punchline)
- `flat` curve tracks paired with `info_reel` (don't want music fighting fact density)
- `drop_at_chorus` reserved for `meme_mashup`/high-hype `comedic` content, drop must land on punchline per M4

## 5. Legal/licensing

Rule M10: only `licensed_local` or `royalty_free` tracks ship in a public-facing render. `user_provided` allowed only if user explicitly supplied the file themselves in this session. Any ambiguity → same flag-to-user behavior as `planner.md` P11, never silent.

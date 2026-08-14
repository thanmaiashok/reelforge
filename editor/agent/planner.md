# Planner Rules — story & pacing decisions

Every decision below must be traceable: pipeline logs which rule ID fired for each cut/insert/overlay/music choice. No improvised edits.

## 1. Goal classification (Intake stage)

Input instruction/link classified into one of:
- `comedy_reel` — meme mashup, reaction cutaways, punchline-driven
- `story_reel` — narrative arc, single throughline, voiceover or dialogue-led
- `info_reel` — explainer/listicle, text-forward, fact density high
- `meme_mashup` — rapid-fire clip stitching, no single narrative, montage energy

Rule P1: If instruction contains a topic + no source link → `info_reel` or `story_reel` default, pick `story_reel` if instruction has narrative verbs ("tell the story of", "what happened when"), else `info_reel`.
Rule P2: If instruction contains one or more links and says "react to" / "funniest" / "make fun of" → `comedy_reel`.
Rule P3: If instruction explicitly says "mashup" / "compilation" → `meme_mashup`.

## 2. Structure (Plan stage)

All reels use 4-beat structure unless goal is `meme_mashup`:

| Beat | Time budget | Purpose |
|---|---|---|
| Hook | 0.0–1.5s | Earn scroll-stop. Visual or audio surprise, question, or bold claim. NEVER a slow establishing shot. |
| Build | 1.5s–60–70% of runtime | Escalate stakes/info, 1 idea per 3–5s block |
| Punchline | 60–70%–85% | Payoff: joke landing, twist, key fact, emotional peak |
| CTA | last 2–4s | Follow/comment/share prompt, or a loop-back to hook frame |

Rule P4 (hook): first frame must contain motion or a face within 3 frames — never open on a static title card. If source footage's first 1.5s is dead air, agent must trim it before the hook, no exceptions.
Rule P5 (meme_mashup structure): no CTA beat required; hook rule P4 still applies; body is punchline-chain (every clip is itself a mini-payoff, no build beat).

## 3. Pacing (cuts-per-second target)

Rule P6: target cut rate by goal —
- `comedy_reel`: 1 cut per 1.0–2.0s during build, 1 cut per 0.6–1.2s during punchline chain
- `story_reel`: 1 cut per 2.5–4.0s (let dialogue/voiceover breathe)
- `info_reel`: 1 cut per 1.5–2.5s, synced to fact boundaries not arbitrary time
- `meme_mashup`: 1 cut per 0.8–1.5s throughout

Rule P7: never exceed 1 cut per 0.5s except for a single deliberate "rapid flash" moment (max 3 flashes, ≤0.2s each) used at most once per reel, only in `comedy_reel`/`meme_mashup`, and only immediately before the punchline.

## 4. Mood targeting

Rule P8: mood vector derived from goal + instruction keywords, expressed as tags matching `knowledge_base` mood taxonomy (`comedic`, `sarcastic`, `wholesome`, `hype`, `dramatic`, `informative`, `nostalgic`). Plan stage must emit an explicit mood tag list — retrieval stage will not run without it.

## 5. Meme/template insertion points

Rule P9: comedic cutaway inserts only allowed at: end of a build sub-beat (as escalation), or as the punchline itself. Never mid-sentence of source dialogue/voiceover — always insert on a natural clause boundary detected from whisper word timestamps.
Rule P10: max meme insert density — no more than 1 meme cutaway per 4 seconds of runtime, and no two consecutive cutaways without at least 1 source clip shot between them (avoid "meme soup").

## 6. Legal gate (applies at Retrieve + Assemble)

Rule P11: any asset with `source_type: reference_link_only` is excluded from Assemble by default. Agent must surface it to the user as "wanted to use X, rights unclear, skipping / need confirmation" rather than silently downloading and hard-cutting it in.
Rule P12: `movie_viral` category assets get an extra check — even `licensed_local`/`user_provided` movie clips longer than the `duration_hint_sec` are trimmed down at Assemble; agent never uses a movie clip as more than a quick-cut reaction (≤3s), never as sustained footage.

## 7. QA pass checklist (Stage 9)

Rule P13: after render, agent must verify against this file:
- Hook obeys P4 (motion/face in first 3 frames)
- Cut rate within P6 band ±20% for the goal
- No P7 violation (rapid-flash overused)
- Every meme/template insert cites a rule ID + asset id in the edit log
- No `reference_link_only` asset made it into final render (P11)
- Movie clip durations respect P12
- CTA beat present (unless `meme_mashup`)

If any check fails: do not silently ship. Write failure to `output/<reel_id>_qa_flags.md` and report to user before marking done.

# Caption Rules — word-overlay style & timing

Source of truth for word-level caption sync is local whisper output: per-word `{word, start, end, confidence}`. Sentence-level subtitles are never acceptable as final output — always render word-by-word or small-group (2-3 word) chunks per rules below.

## 1. Grouping (chunk size)

Rule C1: default chunk = 1 word per on-screen change (karaoke/hormozi style), advancing exactly on whisper's per-word `start` timestamp.
Rule C2: exception — if two adjacent words each have duration < 150ms (fast speech), merge into one 2-word chunk to avoid flicker. Never merge more than 2 words.
Rule C3: if whisper confidence for a word < 0.55, do not display that word in isolation — merge it silently into the neighboring chunk rather than flashing a likely-wrong word alone.

## 2. Style

Rule C4 default style token `bold_yellow_pop`:
- Font: bold sans (e.g. Montserrat ExtraBold / system bold fallback), size ~9-11% of frame height
- Fill: white, 3-4px black stroke outline for contrast on any background
- Active/emphasized word: yellow fill (or mood-driven accent, see C7), slight scale pop (1.0 → 1.12 → 1.0 over 120ms) on entry
- Position: lower-middle third, ~62-72% frame height, centered horizontally, never covering face bounding box if detected

Rule C5: max 1 line on screen at a time in default mode. 2-line stacking only permitted for `info_reel` fact-card moments, and only for whole-phrase emphasis (not per-word karaoke).

Rule C6: punctuation is not rendered as characters — convey it via timing gaps (>400ms silence = implicit pause, hold last chunk slightly longer, +80ms) instead of "." or "," on screen.

## 3. Mood-driven accent color

Rule C7: accent color keyed to plan-stage mood tag:
- `comedic`/`sarcastic` → yellow (#FFD400)
- `hype` → red-orange (#FF5A1F)
- `wholesome`/`nostalgic` → warm cream (#FFE8C2)
- `dramatic` → white-on-white with red underline instead of fill swap
- `informative` → cyan (#3FD0FF)

## 4. Emphasis logic

Rule C8: a word gets emphasis (accent color + pop) if: it is capitalized/ALL-CAPS in source transcript, OR whisper marks it as the loudest word in its sentence (top decile RMS in word window), OR it's a number/stat in `info_reel` mode.
Rule C9: max emphasis density 1 per 4-6 words — if the loudness heuristic would emphasize more, keep only the single highest-RMS word per clause.

## 5. Meme/template caption interaction

Rule C10: during a meme cutaway insert, source-video captions pause; if the cutaway itself has dialogue, caption it in a distinct style (italic, smaller, top-third) so viewer never confuses cutaway speech with the main narrator.

## 6. Sync tolerance & QA

Rule C11: caption chunk on-screen start must be within ±80ms of whisper word `start`. Anything outside tolerance is a QA-stage failure per `planner.md` Rule P13 and blocks ship.
Rule C12: captions must never run past the final frame — last chunk's `end` clamped to `video_duration - 0.1s`.

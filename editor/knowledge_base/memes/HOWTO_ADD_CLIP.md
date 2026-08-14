# Adding a real meme/movie clip to the KB

Minimum to unblock testing: **3 clips, one per language/category bucket**
(not all 25 stub entries). Send each as:

1. **File** — mp4, ≤15s, vertical or easily croppable to 9:16.
2. **Category** — one of `hindi` / `kannada` / `instagram_viral` /
   `movie_viral` / `african` (matches the folder it lives in).
3. **Which stub `id` it replaces** (e.g. `hi_0001`) — or say "new" and I'll
   mint the next free id in that category's file.
4. **Mood tag(s)** — from the existing vocabulary only, don't invent new
   ones: `comedic`, `sarcastic`, `wholesome`, `hype`, `dramatic`,
   `informative`, `nostalgic`. One or two is enough.

## What I do with it

1. Copy/move the file into `knowledge_base/memes/<category>/`.
2. In that category's `*.json`, find the matching entry (by id) and flip:
   - `source_type`: `"reference_link_only"` → `"licensed_local"` or
     `"user_provided"` (your call — `user_provided` if it's yours/a friend's
     footage, `licensed_local` if it's from a licensed stock source)
   - `source_path`: `"knowledge_base/memes/<category>/<filename>"`
   - `mood`: your tag(s), if different from the stub's guess
3. Re-run `retrieve()` + `assemble()` for that category and confirm the
   "no usable meme/template assets" QA flag stops firing for it.

## Why this exists

`planner.md` Rule P11 (legal gate) means `assemble()` refuses to hard-cut
any asset into a render unless `source_type` is `licensed_local` or
`user_provided` with a real `source_path` on disk. Stub entries stay
`reference_link_only` forever until someone with actual rights to the clip
supplies the file — that's a deliberate block, not a bug.

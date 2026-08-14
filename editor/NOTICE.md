# Third-party asset notices

The MIT license in [`LICENSE`](LICENSE) covers this repo's code only. Assets
below carry their own license terms which travel with them — required
reading before you publish a render made with them.

## knowledge_base/music/*.mp3 (16 tracks)

Music by Kevin MacLeod (incompetech.com), licensed under
**Creative Commons: By Attribution 4.0** (CC BY 4.0) —
https://creativecommons.org/licenses/by/4.0/

**Attribution is a condition of the license, not optional.** Any public
render that uses one of these tracks must credit it, e.g.:

> Music: "<Track Title>" by Kevin MacLeod (incompetech.com)
> Licensed under Creative Commons: By Attribution 4.0
> https://creativecommons.org/licenses/by/4.0/

Per-track titles and metadata are in `knowledge_base/music/index.json`
(`license` field on every entry).

## knowledge_base/memes/**/*.json

Metadata-only right now — no video files are bundled in this repo. Every
entry's `source_type` is `reference_link_only` until a real clip is
supplied with actual usage rights (see
`knowledge_base/memes/HOWTO_ADD_CLIP.md`). Once real files land, this
NOTICE file should grow a matching section listing their source and
license/rights basis — don't ship clips without one.

## Fonts

Caption rendering uses fonts already present on macOS
(`/System/Library/Fonts/...` — Arial Bold, Arial Unicode, Devanagari Sangam
MN, Kannada Sangam MN). These are not bundled in this repo; they're a
runtime dependency of the machine running the pipeline. See the
"Platform dependency" note in README.md — this is currently macOS-only for
that reason.

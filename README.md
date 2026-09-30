<p align="center"><img src="docs/flow-3.svg" alt="Animated ReelForge pipeline: Intake → Plan → Fetch → Retrieve → Assemble → Caption → Score → Render → QA" width="100%"/></p>

<p align="center"><sub>10-second tour: Intake → Plan → Fetch → Retrieve → Assemble → Caption → Score → Render → QA</sub></p>

<p align="center"><img src="docs/px3/intro.svg" width="100%" alt="Autonomous shorts-editing agent. Claude Code is the reasoning engine: no third-party LLM API calls anywhere. Tool access only: bash, ffmpeg, local Whisper, yt-dlp and the filesystem."/></p>

<p align="center"><img src="docs/px3/features.svg" width="100%" alt="Key features"/></p>

<p align="center"><img src="docs/px3/divider.svg" width="100%" alt=""/></p>

<a id="what-it-does"></a>
<h2><img src="docs/px3/h2-what-it-does.svg" width="100%" alt="What it does"/></h2>

<p align="center"><img src="docs/px3/t-01.svg" width="100%" alt="Give it a source clip and a brief. It plans the story and pacing, fetches the footage, transcribes it locally, burns in word-level captions, picks music that matches the mood and tempo, and renders a vertical 9:16 short (1080x1920), then runs a QA pass."/></p>

<p align="center"><img src="docs/px3/divider.svg" width="100%" alt=""/></p>

<a id="pipeline"></a>
<h2><img src="docs/px3/h2-pipeline.svg" width="100%" alt="Pipeline"/></h2>

<p align="center"><img src="docs/px3/t-02.svg" width="100%" alt="Nine stages, run by editor/agent/pipeline.py: intake -&gt; plan -&gt; fetch -&gt; retrieve -&gt; assemble -&gt; caption -&gt; score -&gt; render -&gt; qa Behaviour is driven by three written rule sets rather than hidden prompts: File | Covers editor/agent/planner.md | Story and pacing rules (P1-P13) editor/agent/caption_rules.md | Word overlay style and timing (C1-C12) editor/agent/music_rules.md | Song, BPM and mood matching (M1-M10)"/></p>

<p align="center"><img src="docs/px3/divider.svg" width="100%" alt=""/></p>

<a id="knowledge-base"></a>
<h2><img src="docs/px3/h2-knowledge-base.svg" width="100%" alt="Knowledge base"/></h2>

<p align="center"><img src="docs/px3/t-03.svg" width="100%" alt="Memes: Hindi, Kannada, Instagram-viral, movie-viral and African clip metadata Music: 16 tracks with an index (CC BY 4.0, attribution required, see editor/NOTICE.md) Templates: reusable edit templates A legal gate keeps assets out of public renders until their source and license are confirmed"/></p>

<p align="center"><img src="docs/px3/divider.svg" width="100%" alt=""/></p>

<a id="local-by-design"></a>
<h2><img src="docs/px3/h2-local-by-design.svg" width="100%" alt="Local by design"/></h2>

<p align="center"><img src="docs/px3/t-04.svg" width="100%" alt="Whisper runs locally, footage comes through yt-dlp, and captions are rendered as Pillow PNG overlays composited with ffmpeg, so it works with a minimal ffmpeg build."/></p>

<p align="center"><img src="docs/px3/divider.svg" width="100%" alt=""/></p>

<a id="getting-started"></a>
<h2><img src="docs/px3/h2-getting-started.svg" width="100%" alt="Getting started"/></h2>

<p align="center"><img src="docs/px3/t-05.svg" width="100%" alt="Everything lives in editor/. See editor/README.md for the full layout, status and usage, and editor/NOTICE.md for third-party asset licenses before publishing any render."/></p>

<p align="center"><a href="editor/"><img src="docs/px3/link-01.svg" height="34" alt="editor/"/></a> <a href="editor/README.md"><img src="docs/px3/link-02.svg" height="34" alt="editor/README.md"/></a> <a href="editor/NOTICE.md"><img src="docs/px3/link-03.svg" height="34" alt="editor/NOTICE.md"/></a></p>

<p align="center"><img src="docs/px3/divider.svg" width="100%" alt=""/></p>

<a id="license"></a>
<h2><img src="docs/px3/h2-license.svg" width="100%" alt="License"/></h2>

<p align="center"><img src="docs/px3/t-06.svg" width="100%" alt="MIT for the code (see editor/LICENSE). Bundled music and other assets carry their own terms."/></p>

<p align="center"><a href="editor/LICENSE"><img src="docs/px3/link-04.svg" height="34" alt="editor/LICENSE"/></a></p>

<p align="center"><img src="docs/px3/divider.svg" width="100%" alt=""/></p>

<p align="center"><a href="https://github.com/thanmaiashok"><img src="docs/px3/footer.svg" width="100%" alt="Built by Thanmai A, founder of FoxynAI"/></a></p>

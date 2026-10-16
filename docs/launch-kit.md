# SessionLens launch kit

These are publication drafts, not posts that have already been sent. Adapt them to the destination and check its current community rules. All media uses the bundled synthetic session; no private history is included.

## Positioning

Find repeated mistakes in your Codex and Claude Code sessions—locally.

For developers who already have session logs but do not want to export them or set up a full evaluation platform. SessionLens automatically discovers local transcripts and highlights tool failures, identical retries after failures, possible user corrections, and large tool outputs.

Local analysis needs no account or API key. Optional model review is a separate opt-in feature. Scores describe observable process signals; they are not measures of task success. Suggestions are unverified until tested.

## Assets

- [Report preview](assets/report-preview.png): actual HTML report rendered from the synthetic fixture.
- [25-second video](assets/demo.mp4): synthetic CLI output followed by the HTML evidence and suggestion.
- [Animated walkthrough](assets/demo.gif): the same sequence for inline sharing.

The walkthrough uses staged navigation and reading pauses. It is not a performance benchmark or proof of a successful repair.

## X draft

```text
Does your coding agent repeat the same failed tool call?

I built SessionLens to inspect local Codex/Claude Code sessions and show evidence-linked diagnostics and suggestions.

No API key for local analysis. Open source.

https://github.com/wangjinjie722/sessionlens
```

Attach the synthetic demo video. In a follow-up, share the demo command and explain that the score measures observed process signals, not task success.

## Show HN draft

Title:

```text
Show HN: SessionLens – Local diagnostics for Codex and Claude Code sessions
```

URL:

```text
https://github.com/wangjinjie722/sessionlens
```

Author comment:

```text
I built SessionLens because agent failures often leave useful evidence in session logs, but manually reviewing those logs is tedious.

It discovers local Codex and Claude Code transcripts, pairs tool calls with their results, and produces a terminal, JSON, or offline HTML report. Findings include unchanged retries after failures, explicit tool errors, possible user corrections, and large outputs. Each finding includes source line references and a suggested next step.

Local analysis has no runtime third-party dependencies and makes no network requests. There is no signup or API key requirement for the default mode. A bundled synthetic demo lets you try it without reading your history.

The current version uses transparent heuristics. Its score is not a task-success metric, and expected failing tests can count as failures. It does not automatically rewrite your harness or prove that a suggestion works. Optional model review sends selected excerpts to an endpoint you explicitly configure.

I would especially appreciate feedback on missing session formats, false positives, and whether any suggestion changed what you did next. Please do not share private transcripts; a short description or synthetic example is enough.
```

## Community post draft

Title:

```text
I made a local tool to inspect failed retries in Codex and Claude Code sessions
```

Body:

```text
SessionLens is a small open-source CLI that reads local session logs and turns them into evidence-linked diagnostics. You do not need to export your history.

The attached synthetic example shows an agent repeating a tool call after a missing-parameter error. The report points to the original steps and suggests checking the required input before retrying.

It supports Codex and Claude Code logs, local text/JSON/HTML reports, and a foreground watch mode. The default analysis stays on your machine and does not need an API key.

This is an early heuristic-based tool. A high score does not establish task success, and advice is not automatically tested or applied.

Repository and install instructions: https://github.com/wangjinjie722/sessionlens

If you try it, I would like to know whether it found your sessions and whether a finding was useful or misleading. Please keep private logs out of public replies.
```

## First-user outreach draft

```text
I built a local CLI for diagnosing Codex and Claude Code sessions. Would you be willing to try it on a few recent sessions?

There is a synthetic demo first, and default analysis does not upload your logs. I am looking for three pieces of feedback: did discovery work, was any finding useful or wrong, and did you change anything after reading the advice?

No need to send me your logs. A short description is enough.

https://github.com/wangjinjie722/sessionlens
```

## Suggested first-week experiment

1. Ask 5–10 developers to try the synthetic demo and then their own sessions.
2. Fix installation/discovery failures and the most frequent false positives.
3. Share the demonstration with a relevant developer audience and respond to concrete feedback.
4. Submit a Show HN when the installation path and example report are easy to follow.

Track voluntary feedback: successful setup, useful finding, false positive, advice adopted, and later reuse. Repository stars and visits are secondary. No usage telemetry is added by this launch kit.

## Reproducing the demo assets

Requires the project installed locally, Node.js, Playwright with a Chromium browser, and FFmpeg. These are media-generation dependencies, not CLI runtime requirements.

```sh
python scripts/prepare_demo.py
npm install --no-save --package-lock=false playwright
npx playwright install chromium
node scripts/capture_demo.cjs
ffmpeg -y -f concat -safe 0 -i reports/demo-frames.txt -t 25 -r 10 -an -c:v libx264 -pix_fmt yuv420p -movflags +faststart docs/assets/demo.mp4
ffmpeg -y -i docs/assets/demo.mp4 -filter_complex "[0:v]fps=5,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer" -loop 0 docs/assets/demo.gif
```

Set `SESSIONLENS_BROWSER_EXECUTABLE` if using an existing Chromium browser. The script launches an isolated browser context and accesses only generated local demo pages. The public report path is a synthetic fixture label, not a user's home directory.

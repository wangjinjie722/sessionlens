# SessionLens

**自动读取真实 Agent 会话，诊断问题、评分，并给出带证据的优化建议。**

Local-first diagnostics for Codex and Claude Code sessions. Install once, run from your terminal, and inspect where your agent gets stuck—without exporting or uploading history.

- **自动发现**：读取本机 Codex / Claude Code JSONL session，无需手动导入。
- **有证据的诊断**：每条发现附原文件行号、事件片段、原因假设和建议。
- **透明评分**：工具可靠性、失败重试、上下文输出体积；不把过程分冒充任务成功率。
- **持续观察**：`watch` 自动分析新增或变化的会话，更新报告。
- **可选深度诊断**：通过明确开启的模型调用提供针对当前任务的建议；支持兼容 Chat Completions 的本地或远程服务。
- **本地优先**：默认零网络请求、零运行时第三方依赖；不会修改 agent 配置或执行日志中的命令。

## Install

Requires **Python 3.10+**. Works in macOS/Linux terminals and Windows CMD/PowerShell. The GitHub release includes a wheel and source archive; the package is not published to PyPI.

Recommended, with [uv](https://docs.astral.sh/uv/):

```sh
uv tool install git+https://github.com/wangjinjie722/sessionlens.git
sessionlens
```

With pipx:

```sh
pipx install git+https://github.com/wangjinjie722/sessionlens.git
sessionlens
```

Or clone and install with Python:

```sh
git clone https://github.com/wangjinjie722/sessionlens.git
cd sessionlens
python -m pip install .
sessionlens
```

If your shell cannot find the executable, run `python -m sessionlens` with the Python where you installed it, or run `uv tool update-shell` / `pipx ensurepath` and reopen your terminal. On managed Python installations, use uv, pipx, or a virtual environment rather than system pip. Downloading and installing a release wheel does not require Git.

## Quick start

```sh
# Default: local diagnosis of the 10 most recently modified sessions
sessionlens

# Check sources and installation, without showing credentials
sessionlens doctor

# Preview a synthetic example without reading personal sessions
sessionlens demo

# Inspect just one source / project
sessionlens scan --source claude --limit 5
sessionlens scan --project .

# Standalone, offline HTML report (open the resulting file in your browser)
sessionlens scan --format html --output reports/sessions.html

# Machine-readable output
sessionlens scan --format json --output reports/sessions.json

# Keep watching; only changed snapshots produce output. Ctrl+C stops.
sessionlens watch --interval 10 --format html --output reports/live.html

# Optional explicit path, useful for custom installs and archived transcripts
sessionlens scan --path /path/to/session.jsonl
```

`watch` runs in the foreground; it does not install a startup daemon. HTML reports are static snapshots: refresh the browser after an update. Model calls are intentionally unavailable in watch mode to prevent unbounded background spend.

## What you get

The bundled synthetic demo includes an unchanged retry after a missing-parameter error and a user correction:

```text
[codex] 52/100 · 修复订单查询接口。先检查现有实现，不要修改支付模块。
  Coverage: limited | Task success: unknown | Tools: 3
  [HIGH] Unchanged retry after failure / 失败后原样重试 ×1
    L4 exec_command: Process exited with code 2 ... Missing required parameter
    L5 exec_command: {"cmd": "python lookup_order.py --order 123"}
  [MEDIUM] Tool execution failures / 工具执行失败 ×2
  [MEDIUM] Possible user corrections / 疑似用户纠正 ×1
```

Each report separates **observations**, **root-cause hypotheses**, **suggestions**, and **candidate instructions**. Candidate instructions are suggestions to review and test, not automatically applied patches. Cross-session aggregation currently groups rule categories, not semantic root causes.

## Deep diagnosis (optional)

Local rules require no API key and generate rule-specific advice. For contextual analysis, use a model endpoint. You explicitly choose the model; no paid model is selected for you.

macOS/Linux:

```sh
export SESSIONLENS_BASE_URL="https://api.openai.com/v1"
export SESSIONLENS_MODEL="YOUR_MODEL_ID"
export SESSIONLENS_API_KEY="YOUR_API_KEY"
sessionlens scan --limit 3 --preview-deep --output reports/context-preview.json
sessionlens scan --limit 3 --deep --format html --output reports/deep.html
```

Windows CMD:

```bat
set SESSIONLENS_BASE_URL=https://api.openai.com/v1
set SESSIONLENS_MODEL=YOUR_MODEL_ID
set SESSIONLENS_API_KEY=YOUR_API_KEY
sessionlens scan --limit 3 --preview-deep
sessionlens scan --limit 3 --deep
```

PowerShell uses `$env:SESSIONLENS_MODEL="YOUR_MODEL_ID"` and the same syntax for the other variables.

A local compatible service can use `SESSIONLENS_BASE_URL=http://localhost:11434/v1` and an installed model supporting JSON output. `OPENAI_API_KEY` is accepted only for `api.openai.com`; custom services require their own `SESSIONLENS_API_KEY` (localhost may omit it). Remote endpoints require HTTPS. Redirects are refused so credentials cannot silently follow a different endpoint.

`--deep` sends **selected, best-effort redacted excerpts** to that endpoint, up to three sessions by default (`--deep-limit`). The model gets the initial task, recent events, and finding neighborhoods within a 24,000-character event budget. It does not get complete session history, files, credentials from agent config, hidden reasoning, or tool execution access. Returned citations must refer to supplied lines. The model may still misinterpret valid evidence; its suggestions are marked unverified. Deep analysis does not alter the deterministic score.

Use `--language en` for English model advice (default: Chinese). Use `--preview-deep` before sending sensitive sessions. Secret masking is not exhaustive; business content and personal information may remain. The fixed system prompt and payload construction are in [llm.py](src/sessionlens/llm.py).

## Session sources

| Source | Default location | Environment override |
| --- | --- | --- |
| Codex | `~/.codex/sessions/**/*.jsonl` | `CODEX_HOME` (parent of `sessions`) |
| Claude Code | `~/.claude/projects/**/*.jsonl` | `CLAUDE_CONFIG_DIR` (parent of `projects`) |

The adapters read local, observed transcript formats. They are not official SDK integrations. New application versions can change the schema. Cloud-only sessions and other agents require additional adapters. `list` shows paths without opening transcript content. Normal scanning reads the most recent matching sessions, up to `--limit`; project filtering may inspect more files to find matches.

Files are read-only. Symlinked files/directories are skipped. Hidden reasoning, images, system instructions and authentication stores are not collected. Malformed or partially written records are skipped and reported. Limits: 64 MiB/file, 4 MiB/line, 40,000-event soft cap checked between records; truncated reports disclose their limited coverage.

## What the score means

**Observed process quality, not task success.** A score of 100 means no measured penalty in the observed events, not that the output is correct. Sessions without tool results receive `N/A`.

| Dimension | Formula | Weight |
| --- | --- | --- |
| Tool reliability | `100 × (1 − explicit failures / tool results)` | 0.5 |
| Retry discipline | `100 × max(0, 1 − identical failed retries / failures)` | 0.3 |
| Context economy | `100 × (1 − outputs over 12,000 characters / tool results)` | 0.2 |

Each dimension is rounded, then the available dimensions are combined using normalized weights. Retry discipline applies only when calls and failures are present. User-correction matches do **not** affect the score because new requirements or quotations can look like corrections.

Expected failing tests can lower reliability; large outputs may be necessary. `rg`/`grep` with exit code 1 and a simple command is treated as no matches rather than failure. Unknown failure formats may go undetected. See [scoring and limitations](docs/scoring.md).

## Development

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python -m pip install build
python -m build
```

Tests use synthetic fixtures and mocked model transport. CI runs on Linux, macOS and Windows with Python 3.10, 3.12 and 3.14. Actual provider calls are optional and are not performed by CI. No private sessions belong in fixtures, issues, or commits.

See [architecture](docs/architecture.md), [privacy](docs/privacy.md), and [release instructions](docs/releasing.md).

## Scope of v0.1

Implemented: automatic discovery, local diagnostics, transparent scores, evidence lines, optimization advice, recurring rule patterns, optional model review, watch mode, HTML/JSON/text reports.

Not implemented: arbitrary agent SDK ingestion, causal root-cause proof, automatic harness edits, sandbox task replay, A/B validation, GEPA integration, business-task success scoring. These require task-specific evaluators and replay adapters; historical logs alone do not establish that a suggested fix works.

MIT licensed.

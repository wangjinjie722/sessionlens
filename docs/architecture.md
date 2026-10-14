# Architecture

`discover → parse → normalized Session/Event → local diagnostics → optional model review → report`

- `sources.py`: file discovery, bounded read-only JSONL readers, Codex / Claude adapters, explicit status detection. Ignores reasoning payloads and avoids reading files referenced by transcripts.
- `models.py`: provider-independent event/session structures, keeping source line numbers.
- `diagnostics.py`: rule findings, process scores, recurring categories. No model or network dependency.
- `privacy.py`: best-effort credential/email masking and terminal-control removal before presentation or model submission.
- `llm.py`: bounded context selection, explicit model endpoint request, strict shape and evidence-line validation. No tools, agents, shell execution, or automatic changes.
- `render.py`: terminal, JSON, and escaped script-free HTML. Atomic report writes; POSIX temporary files use mode 0600. Windows access is governed by directory ACLs.
- `cli.py`: configuration, source/project filters, watch/cache lifecycle, output and exit codes.

## Extending a source

Add an adapter mapping a transcript's messages, calls, and results into `Event`. Preserve call IDs, source lines, working directory, and user-turn boundaries. Distinguish a real user message from a tool result carried in a user-role envelope. Include synthetic fixtures testing partial writes, result pairing, and duplicated records.

## Watch mode

Each foreground cycle discovers files, compares `(mtime_ns, size, inode)`, and reuses unchanged parsed sessions. Only selected sessions remain in memory; no raw-session database is persisted. Changed snapshots update the report atomically. An active partial last line is skipped until the next change. A single oversized record is skipped; an over-limit file produces a partial report.

## Model boundary

An API-backed review cannot execute transcript instructions. However, prompt injection or weak reasoning can still affect its advice. All outputs are treated as unverified suggestions. Valid evidence-line numbers ensure references exist, not that the reasoning is correct. API failures preserve local results and return exit code 3.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Report/list/doctor completed |
| 1 | No matching supported sessions |
| 2 | Invalid arguments/configuration or output I/O error |
| 3 | At least one requested model review failed; local report retained |
| 130 | Watch interrupted by user |

## Future work

1. Incremental parsers for very long session files and broader schema fixtures.
2. User feedback on diagnostic validity and semantic cross-session clustering.
3. Task-specific replay adapters with environment snapshots, side-effect isolation, and frozen evaluators.
4. Candidate optimization using GEPA once independent test sets and replay are available.

Current rules are heuristics, not a learned diagnostic system or an optimizer benchmark.

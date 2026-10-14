# Scoring v1

The score describes **observed process signals**. It is intentionally separate from model advice, task success, and prompt quality.

## Definitions

- Tool failure: explicit `isError` / `is_error`, nonzero numeric exit status, supported execution wrapper status, or a recognized tool failure prefix. The word `error` inside a file is not enough.
- Identical failed retry: same normalized tool name and arguments after a failed result in the same user turn. A succeeding result clears the pending failure. Normal repeated polling is not penalized without a preceding failure. Transient failures can justify such retries, so the diagnosis calls for review.
- Large output: more than 12,000 text characters in a result. This is not a tokenizer or model context-window estimate.
- Possible correction: a small set of Chinese/English correction phrases in a subsequent user message. This is a hypothesis and carries no score penalty.

Formula and weights are in the README and machine-readable report dimensions. Missing dimensions have no assigned score; remaining weights are normalized. No tool results means no score. Repeated failure events and unchanged retry events can affect separate dimensions: reliability measures tool outcomes, while retry discipline measures recovery behavior.

## Known limitations

- Logs are observations, not causal experiments. A failure might come from environment permissions, deliberate negative tests, or external services.
- Unknown result formats may hide failures. A 100 score means only that configured rules observed no penalties.
- Codex desktop can batch several inner commands in one outer tool event. A failing inner execution makes the outer event a failure; denominators count outer events, not every inner command. Exact retry detection compares the complete outer arguments.
- Sessions may be active, partially written, or truncated. Missing tool results are not assumed to be failures.
- Scores across unrelated tasks, different provider logging schemas, or coverage levels are not directly comparable.
- Long output can be necessary. Small output can still be harmful. No token cost or dollar spend is inferred.
- Corrections inside quotations and examples can be false positives. Cross-session patterns currently aggregate categories, not shared causes.
- Proposed instructions have not been replayed or tested. The tool never labels them as proven improvements.

The product's useful output is the cited evidence and a specific next investigation, not a universal ranking of agents.

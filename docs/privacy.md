# Privacy and data handling

Default commands (`scan`, `watch`, `list`, `doctor`, `demo`) do not make network requests. The tool reads only discovered JSONL transcripts, not authentication files or files mentioned by a transcript. It does not execute logged commands or alter agent settings.

Reports include selected excerpts, session identifiers, and source paths (the current home directory is replaced by `~`). Known token formats, common credential assignments, emails, private-key blocks, and terminal control characters are masked. This is best-effort masking, not a guarantee that all confidential or personal information is removed. JSON embedded in strings and unusual secret formats may evade masking.

`--deep` is an explicit instruction to send selected redacted events to the configured provider. `--preview-deep` shows those events without a request. You are responsible for choosing a provider suitable for the data. The tool makes no promises about a provider's retention policy. API keys are read from environment variables and are not written to reports. HTTP error bodies are not echoed.

There is no telemetry, session upload service, persistent session database, or background startup service. `watch` keeps selected parsed sessions in process memory until stopped. Report files are written only when you supply `--output`. Reports remain on disk until you delete them. POSIX report files are created with owner-only permissions; Windows uses the destination directory's ACLs.

HTML reports contain no remote assets or JavaScript. Session content is escaped and the report includes a restrictive content security policy. Review a report before sharing it. Never include real session excerpts or credentials in public bug reports.

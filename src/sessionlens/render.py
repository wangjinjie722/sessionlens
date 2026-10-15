import html
import json
import os
import tempfile
from pathlib import Path


def terminal(data: dict) -> str:
    rows = ["SESSIONLENS · Session diagnostics", "", data["score_notice"], ""]
    for item in data["sessions"]:
        score = "N/A" if item["score"] is None else f"{item['score']}/100"
        rows += [f"[{item['source']}] {score} · {item['title']}", f"  {item['path']}", f"  Coverage: {item['coverage']} | Task success: unknown | Tools: {item['stats']['tool_calls']}"]
        for finding in item["findings"]:
            rows += [f"  [{finding['severity'].upper()}] {finding['title']} ×{finding['count']}", f"    Suggestion: {finding['suggestion']}"]
            for proof in finding["evidence"][:2]:
                rows.append(f"    L{proof['line']} {proof['tool']}: {proof['excerpt'].replace(chr(10), ' ')[:220]}")
        if not item["findings"]:
            rows.append("  No configured rule fired. Task outcome has not been evaluated.")
        for warning in item["warnings"]:
            rows.append(f"  Note: {warning}")
        if item.get("deep_review"):
            rows.append("  Model review (unverified): " + item["deep_review"]["summary"])
            for finding in item["deep_review"]["findings"]:
                rows.extend([f"    {finding['title']} · lines {finding['evidence_lines']}", f"    Observation: {finding['observation']}", f"    Hypothesis: {finding['hypothesis']}", f"    Suggestion: {finding['suggestion']}", f"    Candidate instruction: {finding['candidate_instruction']}", f"    Validation plan: {finding['validation_plan']}"])
        rows.append("")
    if data["recurring_patterns"]:
        rows.append("RECURRING")
        rows.extend(f"  {p['title']}: {p['sessions']} sessions" for p in data["recurring_patterns"])
    rows.extend("Note: " + w for w in data.get("warnings", []))
    return "\n".join(rows) + "\n"


def html_report(data: dict) -> str:
    esc = lambda x: html.escape(str(x), quote=True)
    cards = []
    for s in data["sessions"]:
        score = "—" if s["score"] is None else s["score"]
        findings = []
        for f in s["findings"]:
            evidence = "".join(f'<div class="proof"><b>L{e["line"]} · {esc(e["tool"] or e["kind"])}</b><pre>{esc(e["excerpt"])}</pre></div>' for e in f["evidence"])
            findings.append(f'''<details><summary><span class="badge {esc(f['severity'])}">{esc(f['severity'])}</span> {esc(f['title'])} <span class="muted">×{f['count']}</span></summary>
<p><b>Observed</b></p>{evidence}<p><b>Hypothesis</b><br>{esc(f['hypothesis'])}</p>
<p><b>Suggestion</b><br>{esc(f['suggestion'])}</p>
<p><b>Candidate instruction</b></p><pre>{esc(f['candidate_instruction'])}</pre><small>Unverified. Review applicability before adopting.</small></details>''')
        dimensions = "".join(f'<span class="metric">{esc(k)} <b>{d["score"]}</b></span>' for k, d in s["dimensions"].items())
        warnings = "".join(f"<li>{esc(w)}</li>" for w in s["warnings"])
        deep = ""
        if s.get("deep_review"):
            review = s["deep_review"]
            deep = '<h3>Model review · unverified</h3><p>' + esc(review["summary"]) + '</p>'
            for f in review["findings"]:
                deep += f'<details><summary>{esc(f["title"])}</summary>'
                for key in ("evidence_lines", "observation", "hypothesis", "suggestion", "candidate_instruction", "validation_plan"):
                    deep += f'<p><b>{esc(key)}</b></p><pre>{esc(f[key])}</pre>'
                deep += '</details>'
        cards.append(f'''<article><div class="session-head"><div><div class="eyebrow">{esc(s['source'])} / {esc(s['coverage'])}</div><h2>{esc(s['title'])}</h2></div><div class="score">{score}<small>/ 100</small></div></div>
<p class="path">{esc(s['path'])}</p><div class="metrics">{dimensions}</div>
<p class="muted">{s['stats']['tool_calls']} tool calls · {s['stats']['user_messages']} user messages · Task success: unknown</p>
{''.join(findings) or '<p>No configured rule fired. This does not establish task success.</p>'}{deep}<ul class="notes">{warnings}</ul></article>''')
    patterns = "".join(f'<li>{esc(p["title"])} <b>{p["sessions"]} sessions</b></li>' for p in data["recurring_patterns"])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>SessionLens · Session diagnostics</title><style>
:root{{color-scheme:dark;--bg:#0c1118;--panel:#141d28;--line:#2a3848;--muted:#9eafc2;--accent:#72e1bd}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:#eaf0f7;font:15px/1.65 system-ui,sans-serif}}main{{max-width:1080px;margin:auto;padding:54px 24px}}header{{margin-bottom:34px}}.eyebrow{{letter-spacing:.13em;text-transform:uppercase;color:var(--accent);font-size:12px}}h1{{font-size:clamp(32px,5vw,54px);line-height:1.12;margin:15px 0}}h2{{font-size:19px;margin:8px 0;overflow-wrap:anywhere}}.lead{{font-size:18px;color:var(--muted);max-width:760px}}.notice{{border-left:3px solid var(--accent);padding:12px 18px;background:var(--panel);color:var(--muted)}}article{{border:1px solid var(--line);border-radius:16px;padding:25px;margin:22px 0;background:var(--panel)}}.session-head{{display:flex;justify-content:space-between;gap:20px}}.score{{font-size:40px;color:var(--accent);line-height:1.2;white-space:nowrap}}.score small{{font-size:12px;display:block;text-align:right;color:var(--muted)}}.path, .muted, small,.notes{{color:var(--muted)}}.path{{overflow-wrap:anywhere;font-size:12px}}.metrics{{display:flex;flex-wrap:wrap;gap:8px}}.metric{{font-size:12px;border:1px solid var(--line);border-radius:5px;padding:4px 9px}}.metric b{{color:var(--accent);margin-left:5px}}details{{border-top:1px solid var(--line);padding:14px 0}}summary{{cursor:pointer;font-weight:600}}.badge{{font-size:10px;text-transform:uppercase;display:inline-block;border-radius:4px;padding:2px 7px;margin-right:6px;background:#344254}}.high{{color:#ffadad;background:#442b34}}.medium{{color:#ffdc99;background:#433a2a}}.low{{color:#a3c9ff;background:#26384b}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#0d141d;padding:14px;border-radius:8px;font:12px/1.7 ui-monospace,monospace}}.proof b{{font-size:12px;color:var(--muted)}}footer{{color:var(--muted);font-size:12px;margin-top:35px}}li{{margin:7px 0}}@media(max-width:600px){{main{{padding:25px 14px}}article{{padding:17px}}.score{{font-size:30px}}}}</style></head>
<body><main><header><div class="eyebrow">SessionLens / Local session diagnostics</div><h1>Find the friction.<br>See the evidence.</h1><p class="lead">{len(data['sessions'])} sessions analyzed. Evidence-linked findings and practical changes for your next run.</p></header>
<div class="notice">{esc(data['score_notice'])}</div>{'<h3>Recurring patterns</h3><ul>'+patterns+'</ul>' if patterns else ''}
{''.join(cards)}<ul class="notes">{''.join('<li>'+esc(w)+'</li>' for w in data.get('warnings', []))}</ul>
<footer>{esc(data['privacy'])}<br>Generated {esc(data['generated_at'])} · SessionLens 0.1.1</footer></main></body></html>'''


def serialize(data: dict, format: str) -> str:
    if format == "json":
        return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if format == "html":
        return html_report(data)
    return terminal(data)


def write_private(path: Path, content: str) -> None:
    """Atomic replacement. Never truncate a source file via a symlink."""
    path = path.expanduser()
    if path.is_symlink():
        raise ValueError("Refusing to overwrite a symlink.")
    if path.suffix.lower() == ".jsonl":
        raise ValueError("Reports cannot overwrite .jsonl transcript files.")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".sessionlens-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

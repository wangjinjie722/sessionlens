"""Prepare public demo pages using only the bundled synthetic fixture."""
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sessionlens.diagnostics import report
from sessionlens.render import html_report, terminal
from sessionlens.sources import parse

session = parse(ROOT / "src/sessionlens/demo.jsonl")
session.path = "demo/synthetic-session.jsonl"
data = report([session])
output = ROOT / "reports"
output.mkdir(exist_ok=True)
(output / "public-demo.html").write_text(html_report(data), encoding="utf-8")
console = html.escape(terminal(data))
(output / "public-terminal.html").write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8">
<title>SessionLens synthetic CLI demo</title><style>
body{{margin:0;background:#0c1118;color:#eaf0f7;font:16px/1.6 system-ui,sans-serif;padding:42px 50px}}
.label{{color:#72e1bd;letter-spacing:.13em;font-size:12px}}h1{{font-size:36px;margin:14px 0}}p{{color:#9eafc2}}
.window{{background:#141d28;border:1px solid #2a3848;border-radius:12px;padding:24px;margin-top:25px}}
.command{{color:#72e1bd;font:18px ui-monospace,monospace;margin-bottom:18px}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.65 ui-monospace,monospace;margin:0}}
</style><body><div class="label">SESSIONLENS / SYNTHETIC DEMO</div><h1>Start with one command.</h1>
<p>No account. No API key for local analysis. No session uploads.</p>
<div class="window"><div class="command">$ sessionlens demo</div><pre>{console}</pre></div></body></html>''', encoding="utf-8")
print("Prepared synthetic public demo pages in reports/.")

"""Build rider-log/index.html from template.html + data_min.json.
PAGE_URL is the published artifact link used inside the Google Calendar reminder.
Run:  python build.py
"""
from pathlib import Path
here = Path(__file__).parent
PAGE_URL = "https://claude.ai/artifact/U3CcTFg2vXWFFCgPpGUH7a"
tpl = (here / "template.html").read_text(encoding="utf-8")
data = (here / "data_min.json").read_text(encoding="utf-8")
out = tpl.replace("__DATA__", data).replace("__PAGE_URL__", PAGE_URL)
(here / "index.html").write_text(out, encoding="utf-8")
print("built rider-log/index.html", len(out), "bytes")

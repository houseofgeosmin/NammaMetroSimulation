"""Build simulator/index.html from sim_template.html + data.json.
Run:  python build.py
"""
from pathlib import Path
here = Path(__file__).parent
tpl = (here / "sim_template.html").read_text(encoding="utf-8")
data = (here / "data.json").read_text(encoding="utf-8")
assert tpl.count("__DATA__") == 1
(here / "index.html").write_text(tpl.replace("__DATA__", data), encoding="utf-8")
print("built simulator/index.html", len(tpl) + len(data), "bytes")

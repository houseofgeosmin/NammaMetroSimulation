"""Build ride-logger/index.html from template.html + data_min.json. Run: python build.py"""
from pathlib import Path
here = Path(__file__).parent
tpl = (here / "template.html").read_text(encoding="utf-8")
data = (here / "data_min.json").read_text(encoding="utf-8")
(here / "index.html").write_text(tpl.replace("__DATA__", data), encoding="utf-8")
print("built ride-logger/index.html")

"""Build both pages and copy them into site/ for static hosting (Vercel serves site/, see vercel.json).
site/index.html            = simulator
site/rider-log/index.html  = rider log
Run:  python build_site.py   (then commit site/ too, Vercel does not run Python)
"""
import shutil, subprocess, sys
from pathlib import Path
root = Path(__file__).parent
for b in ("simulator/build.py", "rider-log/build.py"):
    subprocess.run([sys.executable, str(root / b)], check=True)
site = root / "site"
(site / "rider-log").mkdir(parents=True, exist_ok=True)
shutil.copyfile(root / "simulator" / "index.html", site / "index.html")
shutil.copyfile(root / "rider-log" / "index.html", site / "rider-log" / "index.html")
print("site/ ready")

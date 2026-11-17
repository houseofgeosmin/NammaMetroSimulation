"""Build every page into site/ for Vercel (it serves site/ as is, see vercel.json; functions live in api/).
site/index.html            simulator, wrapped in a proper document (doctype + mobile viewport) with the Vercel feature flags
site/rider-log/index.html  old trip logger (claude.ai database, cannot save on Vercel)
site/ride-log/             Timely Ride Log, offline-first app: index.html, queue.js, manifest, fonts, icons
site/ride-log-sw.js        its service worker (at the root so its scope can be /ride-log), versioned by a content hash
Run:  python build_site.py   (then commit site/ too, Vercel does not run Python)
"""
import hashlib, json, shutil, subprocess, sys
from pathlib import Path
root = Path(__file__).parent
site = root / "site"
for b in ("simulator/build.py", "rider-log/build.py"):
    subprocess.run([sys.executable, str(root / b)], check=True)

# simulator: the template is a page body for claude.ai; on Vercel give it a doctype, a phone viewport and the flags
SITE_FLAGS = {"build": "vercel", "riderReports": False, "rideLog": "/ride-log/"}
head = ('<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
        f'<script>window.SITE={json.dumps(SITE_FLAGS)}</script>\n')
(site / "rider-log").mkdir(parents=True, exist_ok=True)
(site / "index.html").write_text(head + (root / "simulator" / "index.html").read_text(encoding="utf-8"), encoding="utf-8")
shutil.copyfile(root / "rider-log" / "index.html", site / "rider-log" / "index.html")

# Timely Ride Log
src, dst = root / "ride-log", site / "ride-log"
if dst.exists(): shutil.rmtree(dst)
(dst / "fonts").mkdir(parents=True); (dst / "icons").mkdir()
page = (src / "template.html").read_text(encoding="utf-8")
assert page.count("__DATA__") == 1
(dst / "index.html").write_text(page.replace("__DATA__", (src / "data_min.json").read_text(encoding="utf-8").strip()), encoding="utf-8")
for f in ["queue.js", "manifest.webmanifest"] + [f"fonts/{p.name}" for p in (src / "fonts").iterdir()] + [f"icons/{p.name}" for p in (src / "icons").iterdir()]:
    shutil.copyfile(src / f, dst / f)
# everything the service worker precaches; the cache version is a hash of their contents, so any change updates phones
assets = ["/ride-log/", "/ride-log/queue.js", "/ride-log/manifest.webmanifest"] + \
         [f"/ride-log/fonts/{p.name}" for p in sorted((dst / "fonts").glob("*.woff2"))] + \
         [f"/ride-log/icons/{p.name}" for p in sorted((dst / "icons").glob("*.png"))]
h = hashlib.sha256()
for a in assets:
    h.update((dst / (a[len("/ride-log/"):] or "index.html")).read_bytes())
sw = (src / "sw.js").read_text(encoding="utf-8")
h.update(sw.encode())
sw = sw.replace("'__VERSION__'", repr(h.hexdigest()[:12])).replace("__ASSETS__", json.dumps(assets))
(site / "ride-log-sw.js").write_text(sw, encoding="utf-8")
print(f"site/ ready (ride log cache {h.hexdigest()[:12]}, {len(assets)} files)")

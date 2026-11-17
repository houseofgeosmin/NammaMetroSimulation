# Namma Metro Live Simulation: project context for Claude Code

Goal: a live-stream-style, interactive map of Bengaluru's Namma Metro trains for a public fun app, and later for
station displays (with BMRCL, later). BMRCL has NO public real-time feed, so everything is a **schedule-based
simulation**, always labelled "Scheduled simulation, not live GPS". It is built so a live feed can be plugged in later.

## Layout
- `simulator/sim_template.html`  master source (single HTML file, Canvas 2D). Contains `__DATA__` placeholder.
- `simulator/data.json`          compact data (stations, shapes, patterns, profiles, runs, hol, feed).
- `simulator/build.py`           builds `simulator/index.html` (template + data). Run `python simulator/build.py`.
- `rider-log/template.html`      friends' trip logger (one big button flow). `rider-log/build.py` builds index.html.
- `data/bmrcl_full_timetable.csv`  full timetable already delivered to the user.
- `data/gtfs-core/`              core GTFS files from the unofficial community feed (Vonter/bmrcl-gtfs, valid 17 Aug 2026 to 17 Aug 2027).
- `tests/`                       Playwright smoke tests (stubbed `claude.use('db')`).
- `build_site.py`                builds both pages into `site/` (simulator at `/`, rider log at `/rider-log/`). Vercel serves `site/` as is (`vercel.json`), so commit `site/` too.
- `data/rider-data/`             rider measurements as CSV, one row per station (`README.md` explains columns; `TEMPLATE_rider_stops.csv`, `station_names.csv`).
- `tools/make_corrections.py`    CSVs -> `simulator/corrections.json` (median halt, run time, arrival delay per station/direction/peak). `--check`, `--stations`, `--in`, `--out`.
- `CLAUDE.md`                    this file: project context and rules.
- `PROGRESS.md`                  dated log of every change, what is waiting and what is next (newest first).
- `HANDOFF.md`                   full status, decisions, data schemas and the step-by-step plan.

## Always
- **After every change to project files, update `PROGRESS.md`** (what changed, in which files, what is waiting), and update this file when the layout, rules or conventions change.
- **Every commit includes `CLAUDE.md` and `PROGRESS.md`** in their current state. Run `python build_site.py` before committing page changes so `site/` matches the templates.
- Hosting: private GitHub repo houseofgeosmin/NammaMetroSimulation, `main` auto-deploys to https://live-nammametro-simulation.vercel.app/. No database off claude.ai yet.

## Rules and conventions
- Times are IST (UTC+5.5). Simulated clock has speed and jump. Position = interpolation along stop_times, located on the shape polyline (`posAt`).
- Direction colours: Green/Purple direction_id 0 = dark (towards Silk Institute / Challaghatta), 1 = light; Yellow direction_id 1 = dark (towards Bommasandra), 0 = light. Two tracks per colour.
- Projection: equirectangular km, LAT0=12.98, LON0=77.6, oblique pitch 0.6. Trains are drawn as 6-car prisms (`NCARS`), 1.2x the old 4-car length; width/height follow the old 4-car size.
- `dist` marks the middle of the train, so a halted train is centred on its platform. `stateOf(...).halt` flags a halt. `posX` extends a shape straight past its ends so terminal halts stay centred too.
- Simulator page order: header, time controls, map, line cards + planned lines, departures, rider reports, notes, footer (House of Geosmin style, hidden in station-screen mode). The rider log has the same footer.
- Station names are placed after all M badges, at the first free spot (right, left, above, below, diagonals) avoiding badges, names and the HUD overlays (`HUDBOX`). Ordinary stations whose badge would overlap another become small dots.
- Tests: `python tests/test_sim_crowd_panel.py`, `tests/test_rider_log.py`, `tests/test_ride_mode.py` (run from a scratch folder; they write PNGs to the current folder). Python 3.12 is at `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`.
- Do not claim accuracy beyond the data: crowd reports are rider-reported and unchecked.
- Keep the page one self-contained HTML file; external scripts only from cdnjs/jsdelivr/unpkg and Google Fonts if it is hosted as a claude.ai artifact.

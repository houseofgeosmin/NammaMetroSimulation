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
- `ride-logger/`                 personal ride logger for claude.ai (four buttons per station, saves to the artifact database). Left as is.
- `ride-log/`                    **Timely Ride Log**, the Vercel port of `ride-logger/`: `template.html` (page, `__DATA__`), `queue.js` (IndexedDB + upload queue, shared with the service worker), `sw.js` (service worker template), `manifest.webmanifest`, `fonts/` (self-hosted Inter + Space Grotesk, OFL), `icons/` (from `tools/make_ride_log_icons.py`), `data_min.json`.
- `api/`                         Vercel functions: `ride-log.js` (POST uploads), `keepalive.js` (daily cron), `_ride-log-core.js` (logic; `_` = not a route). No npm dependencies; `package.json` only sets ESM.
- `supabase/schema.sql`          tables `rides`, `ride_events`, `ride_log_rate`, RLS on with no policies, functions `ride_log_submit` / `ride_log_rate_hit` / `ride_log_ping` (service role only).
- `scripts/`                     `export_rides.py` (Supabase -> CSV, incl. `rider_stops.csv` for make_corrections), `hash_code.py` (access code + hash).
- `build_site.py`                builds everything into `site/`: simulator at `/` (wrapped with doctype + phone viewport + `window.SITE` flags), rider log at `/rider-log/`, ride log at `/ride-log/` plus `/ride-log-sw.js` (cache version = content hash). Vercel serves `site/` as is (`vercel.json`: also crons, headers), so commit `site/` too.
- `data/rider-data/`             rider measurements as CSV, one row per station (`README.md` explains columns; `TEMPLATE_rider_stops.csv`, `station_names.csv`).
- `tools/make_corrections.py`    CSVs -> `simulator/corrections.json` (median halt, run time, arrival delay per station/direction/peak). `--check`, `--stations`, `--in`, `--out`.
- `CLAUDE.md`                    this file: project context and rules.
- `PROGRESS.md`                  dated log of every change, what is waiting and what is next (newest first).
- `HANDOFF.md`                   full status, decisions, data schemas and the step-by-step plan.

## Always
- **After every change to project files, update `PROGRESS.md`** (what changed, in which files, what is waiting), and update this file when the layout, rules or conventions change.
- **Every commit includes `CLAUDE.md` and `PROGRESS.md`** in their current state. Run `python build_site.py` before committing page changes so `site/` matches the templates.
- Hosting: private GitHub repo houseofgeosmin/NammaMetroSimulation, `main` auto-deploys to https://live-nammametro-simulation.vercel.app/; other branches get preview URLs. Database: Supabase via Vercel Storage, reached only through `/api/ride-log`.
- **Ask the user before anything involving hosting, domains, secrets, accounts or deleting files.** Secrets only in Vercel env vars (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_SECRET_KEY`, `RIDE_LOG_CODE_SHA256`) and a git-ignored local `.env`; never in the repo. `exports/` (riders' names) is git-ignored.

## Rules and conventions
- Times are IST (UTC+5.5). Simulated clock has speed and jump. Position = interpolation along stop_times, located on the shape polyline (`posAt`).
- Direction colours: Green/Purple direction_id 0 = dark (towards Silk Institute / Challaghatta), 1 = light; Yellow direction_id 1 = dark (towards Bommasandra), 0 = light. Two tracks per colour.
- Projection: equirectangular km, LAT0=12.98, LON0=77.6, oblique pitch 0.6. Trains are drawn as 6-car prisms (`NCARS`), 1.2x the old 4-car length; width/height follow the old 4-car size.
- `dist` marks the middle of the train, so a halted train is centred on its platform. `stateOf(...).halt` flags a halt. `posX` extends a shape straight past its ends so terminal halts stay centred too.
- Simulator page order: header, time controls, map, line cards + planned lines, departures, rider reports, notes, footer (House of Geosmin style, hidden in station-screen mode). The rider log has the same footer.
- Station names are placed after all M badges, at the first free spot (right, left, above, below, diagonals) avoiding badges, names and the HUD overlays (`HUDBOX`). Ordinary stations whose badge would overlap another become small dots.
- Tests: `python tests/test_sim_crowd_panel.py`, `tests/test_rider_log.py`, `tests/test_ride_mode.py`, `tests/test_ride_logger.py`, `tests/test_timely_ride_log.py` (needs `python build_site.py` first; uses `tests/ride_log_server.py`, a local stand-in for the API with the same rules as the SQL) and `node tests/test_api_core.mjs`. Run Python tests from a scratch folder; they write PNGs to the current folder. Python 3.12 is at `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`, Node at `C:\Program Files\nodejs`.
- Timely Ride Log rules: times come from the phone clock at the tap (IST, 0.1 s); users type nothing but an optional first name. Every tap goes to IndexedDB first (plus a localStorage mirror of the ride in progress), then uploads; rides and events have client UUIDs so retries are idempotent; Undo sets `undone` instead of deleting. The status line says "Saved online" only after the server confirmed every tap, else "No signal. Saved on this phone ..." with the unsent count within 3 s. A new service worker waits until no ride is in progress.
- Simulator on Vercel: `window.SITE = {build:'vercel', riderReports:false, rideLog:'/ride-log/'}` from `build_site.py`. The "Timely Ride Log" button (`#rlRow` on phones, `#rlDesk` on desktop) and the hidden Rider reports panel depend on it; the claude.ai build has no button.
- Do not claim accuracy beyond the data: crowd reports are rider-reported and unchecked.
- Keep the page one self-contained HTML file; external scripts only from cdnjs/jsdelivr/unpkg and Google Fonts if it is hosted as a claude.ai artifact.

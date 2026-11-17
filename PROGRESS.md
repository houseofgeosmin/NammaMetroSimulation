# Progress log: Namma Metro Live Simulation

Newest first. Updated after every change to project files, and committed with every commit (see CLAUDE.md).
Live site: https://live-nammametro-simulation.vercel.app/ · Repo: https://github.com/houseofgeosmin/NammaMetroSimulation (private)

## Now
- **Waiting on you:** Supabase setup through Vercel + run `supabase/schema.sql` + set `RIDE_LOG_CODE_SHA256`
  (HANDOFF.md section 8), then the airplane-mode test on a real phone using the preview URL of branch `ride-log`.
- **Then:** merge `ride-log` into `main`, share the link with friends; rider data -> `scripts/export_rides.py` ->
  `tools/make_corrections.py` -> the simulator reads `simulator/corrections.json` (next build step).
- **Later:** move the simulator's Rider reports panel to the same database, own domain, Pink Line, Figma fixes, BMRCL letter.

## 2026-11-17
### Timely Ride Log on Vercel (Claude Code, branch `ride-log`)
- `ride-log/`: port of `ride-logger/template.html` with the same four-button flow, as an installable offline-first app:
  service worker (`sw.js` -> `site/ride-log-sw.js`) precaches page, script, manifest, self-hosted fonts and icons; every
  tap to IndexedDB (`queue.js`) + localStorage mirror; background upload with backoff, `online`/visibility triggers and
  Background Sync; honest status line with unsent count; resume unfinished ride; Backup/Copy CSV; install prompt.
- `api/_ride-log-core.js`, `api/ride-log.js`, `api/keepalive.js`: access code (SHA-256 env), rate limits, validation,
  idempotent upsert via `ride_log_submit`; daily keep-alive cron (`vercel.json`) so the free Supabase never pauses.
- `supabase/schema.sql`, `scripts/export_rides.py`, `scripts/hash_code.py`, `tools/make_ride_log_icons.py`, `package.json`.
- Simulator: "Timely Ride Log" button (phone: own row top right, 44 px, safe areas; desktop: by the clock), only on the
  Vercel build. `build_site.py` now gives the simulator a doctype and phone viewport (real phones were getting the
  desktop layout scaled down) and `window.SITE` flags; Rider reports panel hidden by flag `riderReports:false`.
- Tests: `tests/test_timely_ride_log.py` (49 checks: full ride, offline + reload from the service worker, close/reopen with
  the server down, exactly-once upload, button at 390 px), `tests/ride_log_server.py`, `tests/test_api_core.mjs` (25 checks).
- `.gitignore`: keep app icons, ignore `exports/`. HANDOFF.md: merged the older copy you restored (kept your ride-logger
  row and schema) with the current facts, and added section 8 (setup, deploy, share). Node.js LTS installed for tests.

### Rider data and layout
### Layout, footer, rider data pipeline (Claude Code)
- `simulator/sim_template.html`: order is now header, time controls (speed, jump, timetable), map, line cards and
  planned lines, next departures, rider reports, notes, footer. Footer after houseofgeosmin.com (logo mark, quote,
  © House of Geosmin · HSR Layout · Bengaluru · Instagram) plus "Scheduled simulation, not live GPS · Not a BMRCL
  service". Footer hidden in station-screen mode.
- `rider-log/template.html`: same footer (light and dark). New card *Your data on this phone*: every trip and ride is
  kept on the phone (`localStorage.history`) and can be downloaded or copied as CSV, one row per station.
  Buttons look disabled when there is nothing to export. `tests/test_ride_mode.py` checks the history and CSV.
- `data/rider-data/`: `README.md` (how to record, columns, tips), `TEMPLATE_rider_stops.csv`, `station_names.csv`.
- `tools/make_corrections.py`: reads the CSVs, matches each ride to the nearest scheduled train, writes medians of
  halt, running time and arrival delay per station, direction and peak/off-peak to `simulator/corrections.json`
  (only n >= 3). Tested with fake rides built from the timetable: it recovered the offsets put in.
- `PROGRESS.md` (this file) created; `CLAUDE.md` file list and rules updated.

### Hosting (Claude Code)
- GitHub repo created and pushed; Vercel deploys `site/` on every push to `main`. `build_site.py`, `vercel.json`.
- Off claude.ai the simulator hides the rider-reports panel and the rider log shows a "cannot share yet" notice.

### Simulator and rider log fixes (Claude Code)
- Six-car trains, centred on their platform (terminals too, via `posX`).
- Station names no longer overlap at full view (placed after badges, avoid HUD); STOP tags only from closer zoom;
  station-screen clock no longer clipped.
- Rider log Ride mode: doors open / doors close per station, station advances by itself, skip, undo, end ride.
  Saved as one `trips` document with `kind: "ride"` and a `stops` array.
- Tests: `tests/test_ride_mode.py` added.

## Before 2026-11-17 (Claude chat)
- Simulator, rider log, crowd panel, data-collection spreadsheet, Figma file, full timetable CSV. See HANDOFF.md.

# Progress log: Namma Metro Live Simulation

Newest first. Updated after every change to project files, and committed with every commit (see CLAUDE.md).
Live site: https://live-nammametro-simulation.vercel.app/ · Repo: https://github.com/houseofgeosmin/NammaMetroSimulation (private)

## Now
- **Waiting on:** your rider data (CSV files in `data/rider-data/`). Then: `python tools/make_corrections.py`, and
  the simulator reads `simulator/corrections.json` (code for that is the next build step).
- **Later:** database for the public rider log (Supabase), own domain, Pink Line, Figma fixes, BMRCL letter.

## 2026-11-17
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

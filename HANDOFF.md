# Handoff: Namma Metro Live Simulation (from Claude chat to Claude Code)

Prepared Tue 17 Nov 2026. Owner: Rohit.

## 1. Where things stand

| Piece | State | Link or file |
|---|---|---|
| Project plan doc | Done | https://claude.ai/artifact/78Vhi3r7sGEti9bWwCi9mj |
| Simulator (Green, Purple, Yellow) | Done and published, owner-only. Autostart at 10x, 3D look, underground/elevated stations, tunnel tint and portals, train stops with "STOP" tag, station display mode, planned-lines overlay | https://claude.ai/artifact/T4qxrn7FDqTpKQEdYQovPN, source `simulator/` |
| Crowd timing panel in the simulator | Done. Station + direction + "Train arrived just now" button. Saves to the artifact database (`reports`) | same artifact |
| Rider log (friends' trip logger) | Done and published, owner-only until shared. One big button: arrived, doors closing, reached my stop. Times taken automatically. Optional Google Calendar reminder | https://claude.ai/artifact/U3CcTFg2vXWFFCgPpGUH7a, source `rider-log/` |
| Public site (Vercel, from GitHub) | Live since 17 Nov 2026. Simulator at `/` (with a "Timely Ride Log" button), old trip logger at `/rider-log` (cannot save there), **Timely Ride Log at `/ride-log/`** (offline-first app with its own database). Every push to `main` redeploys; other branches get preview URLs | https://live-nammametro-simulation.vercel.app/, repo https://github.com/houseofgeosmin/NammaMetroSimulation (private) |
| **Timely Ride Log** (Vercel version of the ride logger, 17 Nov 2026) | Built and tested locally (Playwright + Node). Same four-button flow as `ride-logger/`. Installable app with a service worker: opens, reloads and logs with no signal; every tap goes to IndexedDB first, then uploads with retry; status says "Saved online" only after the server confirms. Database: Supabase via Vercel, behind `/api/ride-log` with a shared access code. **Waiting on: Supabase setup + env vars (section 8), then the phone test in airplane mode** | source `ride-log/`, `api/`, `supabase/schema.sql`, `scripts/` |
| Personal ride logger (full-ride mode, added after the first handoff) | Done and published, owner-only. Four buttons per station: train stopped, doors opened, doors closed, train moving. Auto-advances stations; saves to `rides` in the artifact database; Copy CSV | https://claude.ai/artifact/DLAgseV7955KhYsh8EH9pZ, source `ride-logger/` |
| Data collection plan (spreadsheet) | Done | https://claude.ai/artifact/23cwHNr5xf2NKqZgp1HkDu |
| Figma design file | Partly done, some fixes pending | https://www.figma.com/design/QaJeHBNT2uGI6VX2KtlhdC |
| Full timetable CSV | Delivered | `data/bmrcl_full_timetable.csv` |

Important: the two artifacts above live on claude.ai. Claude Code cannot edit them directly. Edit the local files, rebuild,
then either re-publish through Claude chat (paste or attach the built `index.html`) or host the files yourself (section 5).

## 2. Key facts and decisions
- BMRCL publishes terminal times only; times at stations in between are modelled. There is no public live feed (checked by web search). Other GitHub projects also simulate from the timetable.
- The user chose to hold off contacting BMRCL and finish everything possible independently first (a data-request letter is optional and deferred).
- Data source: unofficial community GTFS (Vonter/bmrcl-gtfs). Pink Line is not in the feed yet.
- Real trains are 6 cars; the simulator draws 6 since 17 Nov 2026 (longer than true scale so they stay visible).
- Hosting (decided 17 Nov 2026): private GitHub repo + Vercel. Vercel serves the committed `site/` folder (no build there) and the functions in `api/`. Database for the public ride log: Supabase, created through Vercel's Storage tab so keys arrive as environment variables. Secrets live only in Vercel env vars and a git-ignored `.env` on your PC.
- Crowd data is rider-reported and unchecked. Median over many reports is the way to use it.

## 3. Data schemas (artifact database)
`reports/{autoId}` (simulator panel): station (index), stationName, line (G/P/Y), dir, towards, svc, actualSec (IST seconds of day), schedSec, delaySec (actual minus scheduled, null if no scheduled train within 20 min), ts (ms), uid, simSpeed.

`trips/{autoId}` (rider log): kind "trip", uid, nick, date (YYYY-MM-DD), svc, fromId, fromName, toId, toName, line, dir, arrSec, depSec, destSec, dwellSec (depSec minus arrSec), runSec, runIncludesDwell, schedArrSec, delayArrSec, schedDwellSec, schedRunSec, ts.
A trip is created on the first tap and updated on the next taps, so partial trips exist.

`rides/{autoId}` (ride logger): kind "ride", uid, nick, date, dow, svc, opt, from, fromName, line, dir, towards, pat (pattern index), startTs, endTs, done, matched {prof, start} (the scheduled run it was matched to at the first stop), events[] of {k: board|stop|open|close|move|skip|alight, st (station index), sec (IST seconds since midnight, 0.1 s), ts (ms)}. Whole document is rewritten on each tap.

`trips/{autoId}` with kind "ride" (rider log, Ride mode, added 17 Nov 2026 in Claude Code): uid, nick, date, svc, line, dir, towards, fromId, fromName, toId, toName, nStops, done, matched, ts, updatedTs, stops: [{id, name, arrSec, depSec, dwellSec, schedArrSec, schedDepSec, schedDwellSec, delayArrSec}].

Reading these from claude.ai chat: the Claude chat can query them (db_query on the artifact slug). Claude Code cannot, unless you
add your own backend (section 5) or export from chat.

### Timely Ride Log database (Supabase, `supabase/schema.sql`) — same shape as `rides/{id}` above, split into two tables
`rides`: id (uuid, made on the phone), device_id (random uuid per phone), created_at, updated_at, nick, date, weekday, service, line, dir, towards, option_index, pattern_index, from_station, from_name, matched_profile, matched_start, start_ts, end_ts, done.
`ride_events`: id (uuid, made on the phone per tap), ride_id, kind (board|stop|open|close|move|skip|alight), station_index, sec_ist (IST seconds since midnight, 0.1 s), client_ts (phone ms), undone (Undo sets this instead of deleting), received_at.
`ride_log_rate`: hashed rate-limit counters only (no IP addresses).
Rules: browsers can read and write nothing (RLS on, no policies, grants revoked). `/api/ride-log` checks the access code (SHA-256 in env `RIDE_LOG_CODE_SHA256`), rate-limits (300 req / 10 min per IP hash, 200 per phone, 20 wrong codes / hour), validates every field and calls `ride_log_submit()`, which inserts a ride or updates one only from the same device, and stores each event id once. Retries can never duplicate.
Export: `python scripts/export_rides.py` -> `exports/<date>/rides.csv`, `ride_events.csv`, `rider_stops.csv` (the last is the `data/rider-data` format for `tools/make_corrections.py`). Needs `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` in the environment or a git-ignored `.env`.
Full backup: run the export weekly and keep the folder; for a complete database copy use `pg_dump "<POSTGRES_URL_NON_POOLING from Vercel>" > backup.sql` (needs PostgreSQL client tools). The free Supabase plan has no downloadable automatic backups.

## 4. Known issues and pending work
1. ~~Simulator: trains to six cars~~ Done 17 Nov 2026 (Claude Code), live on Vercel.
2. ~~Simulator: station labels overlap at the full-network view~~ Done 17 Nov 2026, live on Vercel.
3. Figma: mobile tab bar and truncated rows, station display header overlap, truncated "Whitefield" text, empty lower-left panel / interchange strip. (Figma Starter plan call limit was hit; do the fixes tomorrow or on another plan.)
4. Ride logger is built (`ride-logger/`, claude.ai) and ported to Vercel as the Timely Ride Log (`ride-log/`). Remaining: Supabase setup and phone test (section 8), analyse the first rides. The simulator's "Rider reports" panel is hidden on Vercel (feature flag `riderReports:false` in `build_site.py`) until it is moved to the same database.
5. Pink Line timetable (deferred), platform-board photo timing tuning (deferred).
6. Apply crowd corrections to the simulator: per line and direction, peak and off-peak tables, straight-line fade between measured stations and terminals; show a "corrected with rider data on <date>" label.
7. Optional: BMRCL data-request letter; live-feed adapter once any feed exists.

## 5. How to finish (step by step)
1. **Set up Claude Code in this folder.** Open a terminal in `R:\GEOSMIN'S PROJECTS\Claude Projects\Metro Rail Live Simulation` and run `claude`. Paste the handoff prompt (section 6). Check that Python 3 is installed (`python --version`).
2. **Confirm the build works.** `python simulator/build.py` and `python rider-log/build.py`, then open both `index.html` files in a browser. The simulator should start running at 10x.
3. **Fix the small things first.** Label overlap, then six-car trains (draw each car as one prism with a short gap; keep the halted train centred on its platform).
4. **Collect data (do this in parallel, it takes days).** Share the rider log from its artifact page on claude.ai with friends as Contributors. Ask for 5 to 10 trips each over a week. Do the 18-hour plan in the spreadsheet yourself (3 days, one per line).
5. **Analyse in Claude chat.** After a few days, ask Claude in chat: "read the trips and reports and give me the median halt and timetable error per station". Save the result as `simulator/corrections.json`.
6. **Apply corrections in Claude Code.** Add a correction step to `stateOf`/timetable setup using `corrections.json`, rebuild, test.
7. **Decide on hosting.** Option A: keep publishing through Claude chat as an artifact (private or shared, simplest, database works). Option B: host the static files on GitHub Pages, Netlify or Cloudflare Pages; then the rider log needs its own backend (Supabase or Firebase) because the artifact database only works inside claude.ai. Choose B when you want a public app.
   **Decided 17 Nov 2026:** B on Vercel + Supabase. To update the site: edit a template, run `python build_site.py`, commit including `site/`, push.
8. **Station displays and BMRCL.** Once the app is stable, send the optional data-request letter and use station display mode (`#display-<station>`) as the demo.
9. **Back up to GitHub later** (as you planned): `git init`, commit, push. Large files: `data/bmrcl_full_timetable.csv` is 7.7 MB, fine for GitHub.

## 6. Handoff prompt (paste this into Claude Code)

> You are taking over the "Namma Metro Live Simulation" project from a Claude chat. Read `CLAUDE.md` and `HANDOFF.md` in this folder first.
>
> Summary: a single-file, canvas-based 3D-style simulation of Bengaluru Namma Metro trains (Green, Purple, Yellow lines) driven by the community GTFS timetable, plus a rider-log page that lets friends log real arrival, halt and ride times, to calibrate the simulation. There is no public live feed, so the app must always say it is a scheduled simulation.
>
> Do these in order, and ask me before anything that changes hosting or deletes files:
> 1. Run `python simulator/build.py` and `python rider-log/build.py`, open both pages with Playwright (headless Chromium) and confirm they work. Run the smoke tests in `tests/` (they stub `claude.use('db')`).
> 2. Switch simulated trains from 4 cars to 6 cars, keeping a halted train centred on its platform and checking the drawing at full-network and station zoom.
> 3. Fix station-label overlap at the full-network view.
> 4. Add "Ride mode" to the rider log: after choosing a line and direction, one button taps "doors open" and "doors close" at each station and the station name advances automatically. Save a ride as one document with an array of per-station arrival and departure seconds.
> 5. When I give you `corrections.json` (median halt and timetable error per station and direction, peak and off-peak), apply it in the simulator, show a "corrected with rider data on <date>" label, and keep the original timetable as fallback.
> 6. Then help me choose hosting (static host plus Supabase or Firebase) for a public version.
>
> Rules: times are IST; keep everything in single self-contained HTML files; never claim live accuracy; do not remove the "Scheduled simulation, not live GPS" label; keep changes small and test with Playwright screenshots before saying something is done. The generator that produced `simulator/data.json` from the GTFS files was not saved; if data needs regenerating, rebuild it from `data/gtfs-core/` and verify it against the existing file.

## 7. What was not saved
- The script that converted GTFS into `simulator/data.json` (the output is saved; the generator can be rebuilt from `data/gtfs-core/`).
- The artifacts' database contents (they stay on claude.ai).
- The Figma file stays in Figma.

## 8. Timely Ride Log: setup, deploy, share (Vercel + Supabase)

**One-time setup (you; about 10 minutes).** Nothing here is in the repo; secrets stay in Vercel.
1. **Database.** Vercel -> your project -> **Storage** -> **Create Database** -> **Supabase** -> free plan, region Mumbai (ap-south-1) if offered -> connect it to this project for Production and Preview. Vercel then adds `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and friends as environment variables by itself.
2. **Tables.** Open the new Supabase project (Vercel -> Storage -> the database -> Open in Supabase) -> **SQL Editor** -> New query -> paste all of `supabase/schema.sql` -> **Run**. It is safe to run again.
3. **Access code.** On your PC: `python scripts/hash_code.py` (or `python scripts/hash_code.py your-own-code`). In Vercel -> Settings -> **Environment Variables** add `RIDE_LOG_CODE_SHA256` = the printed hash, for Production and Preview. Keep the code itself somewhere private (it goes in the link you share).
4. **Redeploy** (Vercel -> Deployments -> the latest -> Redeploy) so the function sees the new variables.
5. **Check:** open `/ride-log/#code=<code>`, start a ride, tap once with signal: the status line must turn to "Saved online".

**Deploy changes:** edit `ride-log/template.html` (or `queue.js`, `sw.js`), run `python build_site.py`, commit including `site/`, push. A branch other than `main` gives a preview URL; `main` updates the live site. Phones pick up the new version on their next visit once no ride is in progress (the service worker cache is versioned by a content hash).

**Phone test in airplane mode** (on the preview URL first, then live): open the link with signal once (this stores the code and caches the app), Add to Home Screen, turn on airplane mode, open it from the home screen, start a ride, tap through a few stations, close the app, reopen it (still offline: the ride must be there), then turn airplane mode off and watch the status go from "No signal ... N unsent taps" to "Saved online".

**Share with friends:** send `https://live-nammametro-simulation.vercel.app/ride-log/#code=<code>` in a private chat. Each friend opens it once with signal, then adds it to the home screen. If the code leaks, make a new one (step 3 + redeploy) and share a new link; taps already on phones are kept and upload after they open the new link.

**Export:** `python scripts/export_rides.py` (needs `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` copied from Vercel into a `.env` file in the project folder; `.env` is git-ignored).

**Tests:** `python build_site.py`, then from a scratch folder `python tests/test_timely_ride_log.py` (full ride, offline + reload, close and reopen with the server down, button at 390 px) and `node tests/test_api_core.mjs` (the server function: code, limits, validation, idempotency).

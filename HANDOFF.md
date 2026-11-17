# Handoff: Namma Metro Live Simulation (from Claude chat to Claude Code)

Prepared Tue 17 Nov 2026. Owner: Rohit.

## 1. Where things stand

| Piece | State | Link or file |
|---|---|---|
| Project plan doc | Done | https://claude.ai/artifact/78Vhi3r7sGEti9bWwCi9mj |
| Simulator (Green, Purple, Yellow) | Done and published, owner-only. Autostart at 10x, 3D look, underground/elevated stations, tunnel tint and portals, train stops with "STOP" tag, station display mode, planned-lines overlay | https://claude.ai/artifact/T4qxrn7FDqTpKQEdYQovPN, source `simulator/` |
| Crowd timing panel in the simulator | Done. Station + direction + "Train arrived just now" button. Saves to the artifact database (`reports`) | same artifact |
| Public site (Vercel, from GitHub) | Live since 17 Nov 2026. Simulator at `/`, rider log at `/rider-log` (cannot save there: no database off claude.ai, so the crowd panel is hidden and the rider log shows a notice). Every push to `main` redeploys | https://live-nammametro-simulation.vercel.app/, repo https://github.com/houseofgeosmin/NammaMetroSimulation (private) |
| Rider log (friends' trip logger) | Done and published, owner-only until shared. One big button: arrived, doors closing, reached my stop. Times taken automatically. Optional Google Calendar reminder | https://claude.ai/artifact/U3CcTFg2vXWFFCgPpGUH7a, source `rider-log/` |
| Data collection plan (spreadsheet) | Done | https://claude.ai/artifact/23cwHNr5xf2NKqZgp1HkDu |
| Figma design file | Partly done, some fixes pending | https://www.figma.com/design/QaJeHBNT2uGI6VX2KtlhdC |
| Full timetable CSV | Delivered | `data/bmrcl_full_timetable.csv` |

Important: the two artifacts above live on claude.ai. Claude Code cannot edit them directly. Edit the local files, rebuild,
then either re-publish through Claude chat (paste or attach the built `index.html`) or host the files yourself (section 5).

## 2. Key facts and decisions
- BMRCL publishes terminal times only; times at stations in between are modelled. There is no public live feed (checked by web search). Other GitHub projects also simulate from the timetable.
- The user chose to hold off contacting BMRCL and finish everything possible independently first (a data-request letter is optional and deferred).
- Data source: unofficial community GTFS (Vonter/bmrcl-gtfs). Pink Line is not in the feed yet.
- Real trains are 6 cars; the simulator draws 4 for clarity. Switching to 6 is deferred.
- Crowd data is rider-reported and unchecked. Median over many reports is the way to use it.

## 3. Data schemas (artifact database)
`reports/{autoId}` (simulator panel): station (index), stationName, line (G/P/Y), dir, towards, svc, actualSec (IST seconds of day), schedSec, delaySec (actual minus scheduled, null if no scheduled train within 20 min), ts (ms), uid, simSpeed.

`trips/{autoId}` (rider log): kind "trip", uid, nick, date (YYYY-MM-DD), svc, fromId, fromName, toId, toName, line, dir, arrSec, depSec, destSec, dwellSec (depSec minus arrSec), runSec, runIncludesDwell, schedArrSec, delayArrSec, schedDwellSec, schedRunSec, ts.
A trip is created on the first tap and updated on the next taps, so partial trips exist.

`trips/{autoId}` with kind "ride" (rider log, Ride mode, added 17 Nov 2026 in Claude Code): uid, nick, date, svc, line, dir, towards, fromId, fromName, toId, toName, nStops, done, matched (a timetable run was found within 20 min of the first tap), ts (first tap), updatedTs, stops: [{id, name, arrSec, depSec, dwellSec, schedArrSec, schedDepSec, schedDwellSec, delayArrSec}]. A skipped tap is null. Created on the first tap, updated on every tap.

Reading these from claude.ai chat: the Claude chat can query them (db_query on the artifact slug). Claude Code cannot, unless you
add your own backend (section 5) or export from chat.

## 4. Known issues and pending work
1. ~~Simulator: trains to six cars~~ Done 17 Nov 2026 (Claude Code), local files only, not yet re-published.
2. ~~Simulator: station labels overlap at the full-network view~~ Done 17 Nov 2026, local files only.
3. Figma: mobile tab bar and truncated rows, station display header overlap, truncated "Whitefield" text, empty lower-left panel / interchange strip. (Figma Starter plan call limit was hit; do the fixes tomorrow or on another plan.)
4. ~~Rider log: add "Ride mode"~~ Done 17 Nov 2026, local files only, not yet re-published.
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
   **Decided 17 Nov 2026:** B on Vercel, simulator first. The repo is private; Vercel serves the committed `site/` folder (see `vercel.json`, no build on Vercel). To update: edit a template, run `python build_site.py`, commit including `site/`, push. Friends keep logging on the claude.ai rider log until a database (Supabase) is added.
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

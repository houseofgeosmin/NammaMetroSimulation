# Claude Code prompt: add a "Timely Ride Log" button and offline-first ride log to the Vercel site

Paste everything below the line into Claude Code, started in this project folder.

---

Read `CLAUDE.md` and `HANDOFF.md` first. The simulator is deployed on Vercel at https://live-nammametro-simulation.vercel.app/ (source: `simulator/`). `ride-logger/template.html` is a working ride logger that currently saves to a claude.ai artifact database, which does not work on Vercel. Build the ride logger into the Vercel site as an offline-first web app with its own database. Do not change the simulator's look except for the button below.

## 1. The button
- Add a "Timely Ride Log" button in the **top right of the mobile page** of the simulator. It links to `/ride-log/` on the same site (same tab). It must not cover the existing top bar content, must respect `env(safe-area-inset-*)`, and must have a tap target of at least 44px.
- On desktop it can sit in the top bar next to the existing controls.

## 2. The ride logger page `/ride-log/`
Port `ride-logger/template.html` (keep its behaviour exactly): start a ride (line and direction, station), then per station four buttons: Train stopped, Doors opened, Doors closed, Train moving; auto-advance; "I got on the train", Undo last tap, Missed this station, Finish ride; per-station table with halt and timetable difference; Copy CSV. Times are IST taken from the phone clock at the moment of the tap; users never type times. Keep `data_min.json` embedded or fetched as a static file.

## 3. Must work underground with no signal (top requirement)
- Make it an installable PWA: web app manifest, icons, and a service worker that precaches the page, scripts, fonts (self-host Inter and Space Grotesk, do not rely on Google Fonts), and `data_min.json`, so the page opens and reloads fully offline. Use a versioned cache and update it safely.
- Every tap is first written to IndexedDB (not only localStorage), synchronously with the tap, then queued for upload. A refresh, a killed tab or a phone restart must never lose a ride. On load, resume any unfinished ride.
- Upload queue: send events in the background with retry and exponential backoff; use Background Sync where supported and also retry on the `online` event and on the next tap. Uploads must be idempotent (each ride has a client-generated UUID, each event has a client-generated id) so retries never create duplicates.
- The status line must be honest: "Saving..." then "Saved online" only after the server confirmed, or "No signal. Saved on this phone, will upload when online" if not confirmed within 3 seconds. Show the number of unsent taps.
- Add a "Backup" action that downloads or copies the whole ride as CSV.

## 4. Database and API
- Use Supabase (Postgres) on the free tier unless you find a clearly better fit for this Vercel setup; ask me before creating any account or paid resource. Tables: `rides` (id uuid pk, created_at, device_id, nick, date, weekday, service, line, dir, towards, pattern_index, from_station, matched_profile, matched_start, done) and `ride_events` (id uuid pk, ride_id fk, kind: board|stop|open|close|move|skip|alight, station_index, sec_ist numeric(8,1), client_ts bigint). Keep the schema aligned with the `rides/{id}` document described in `HANDOFF.md`.
- Row-level security: anonymous users can only INSERT (and update their own ride by device_id); nobody can read other people's rows from the browser. Add a simple shared access code (stored hashed server-side, checked in a Vercel serverless function that does the inserts) to stop junk. Rate-limit the function.
- Store only a first name or nickname, stations and times. No other personal data. Add a one-line privacy note on the page.
- Provide `scripts/export_rides.py` that exports all rides and events to CSV so I can analyse them, and document how to take a full backup.

## 5. The old Rider reports panel
The simulator has a "Rider reports" panel that depends on the claude.ai database and shows "Sign in to the artifact" on Vercel. Hide it on the Vercel build (feature flag or build step) until it is ported to the same Supabase backend; mention what you did.

## 6. Quality and testing
- Playwright tests in `tests/`: (a) full ride online; (b) go offline mid-ride (`context.set_offline(true)`), tap through several stations, reload while offline, confirm the ride is intact and the page still loads from the service worker, go back online and confirm all events arrive exactly once; (c) kill and reopen the page with unsent taps; (d) the top-right button on a 390px-wide mobile viewport, screenshot it.
- Test on a real phone using Vercel preview deployments, including airplane mode.
- Keep each change small, show me screenshots, and ask before anything that touches hosting, domains, secrets or deletes files. Put secrets only in Vercel environment variables, never in the repo.
- Do not claim live accuracy anywhere; keep the "Scheduled simulation, not live GPS" label.

## 7. When done
Update `HANDOFF.md` and `CLAUDE.md` (new folders, schema, how to export data, how to deploy) and tell me the exact steps to share the ride log link and access code with friends.

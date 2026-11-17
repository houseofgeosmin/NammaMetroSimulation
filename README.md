# Namma Metro Live Simulation

Open `simulator/index.html` in a browser to see the simulation (no server needed).
Open `rider-log/index.html` for the rider logger (saving to the shared database only works when published as a claude.ai artifact).

Live: https://live-nammametro-simulation.vercel.app/ (simulator), /ride-log/ (Timely Ride Log: offline-first ride logger
with its own database, see HANDOFF.md section 8) and /rider-log (old trip logger, cannot save off claude.ai).

Rebuild after editing a template, then commit `site/` too (Vercel serves it as is):
    python build_site.py

See `HANDOFF.md` for status and next steps.

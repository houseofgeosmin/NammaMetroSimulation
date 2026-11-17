# Namma Metro Live Simulation

Open `simulator/index.html` in a browser to see the simulation (no server needed).
Open `rider-log/index.html` for the rider logger (saving to the shared database only works when published as a claude.ai artifact).

Live: https://live-nammametro-simulation.vercel.app/ (simulator) and /rider-log (rider log, cannot save off claude.ai).

Rebuild after editing a template, then commit `site/` too (Vercel serves it as is):
    python build_site.py

See `HANDOFF.md` for status and next steps.

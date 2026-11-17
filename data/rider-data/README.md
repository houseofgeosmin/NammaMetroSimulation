# Rider data: how to record it

This folder holds what you measure on real trains. `tools/make_corrections.py` turns it into
`simulator/corrections.json`, which the simulator uses to correct the timetable (see "What happens to it" below).

## Two ways to record

1. **Rider log app, Ride mode (easiest).** Open https://live-nammametro-simulation.vercel.app/rider-log on your phone,
   switch to *Ride mode*, pick line, direction and starting station, and tap at every station:
   *Doors open* when the doors open, *Doors closing* when they start to close. At the end, in
   *Your data on this phone*, tap **Download as CSV** and put the file in this folder (any name, not `TEMPLATE_...`).
   Taps are kept on the phone even without signing in.
2. **By hand (spreadsheet).** Copy `TEMPLATE_rider_stops.csv`, open it in Excel or Google Sheets, delete the 3 example
   rows and fill in one row per station. Save as CSV (UTF-8) into this folder.

Both give the same columns, so you can mix them.

## Columns (one row per station the train stopped at)

| Column | Needed? | What to write | Example |
|---|---|---|---|
| `session_id` | yes | Same value for every row of one ride. Anything unique: date + start time works | `R20261118-0905` |
| `date` | yes | Date of the ride, `YYYY-MM-DD` | `2026-11-18` |
| `line` | yes | `Green`, `Purple` or `Yellow` | `Green` |
| `towards` | yes | Last station of the line in your direction (the board on the train): Silk Institute / Madavara, Challaghatta / Whitefield (Kadugodi), Bommasandra / RV Road | `Silk Institute` |
| `station` | yes | Station name as in `station_names.csv` (the script tells you the file and line of any name it cannot match) | `Chickpete` |
| `doors_open` | yes* | Time the doors opened, IST, `HH:MM:SS` | `09:07:40` |
| `doors_close` | yes* | Time the doors started closing | `09:08:05` |
| `platform_at` | optional | Time you reached the platform (first station only): measures how long riders wait | `09:01:30` |
| `display_min` | optional | What the platform screen said for this train when you arrived ("next train in 3 min" = `3`) | `3` |
| `crowd` | optional | 1 empty seats, 2 all seats taken, 3 standing comfortably, 4 packed, 5 could not board | `4` |
| `source` | optional | `manual`, `app-ride` or `app-trip` | `manual` |
| `notes` | optional | Anything unusual: held at a signal, train ended early, short train, skipped a station | `held 2 min at signal` |

\* Leave a time empty if you missed it. A row with only `doors_open` still gives arrival time; a missed
station simply means that gap is not used for running time.

**Tips for good data**
- Use your phone clock (it is network time). Seconds matter: a halt is often 20 to 60 s.
- Log every station of a ride, not only some: running time is measured between *adjacent* stations.
- Note the time the doors *start* closing, not when the train starts moving.
- Spread rides over different times: morning peak (08:00 to 11:00), evening peak (17:00 to 20:30), off-peak, and
  weekends. The corrections are split into peak and off-peak.
- At least **3 rides per station and direction and period** before a number is used. 5 to 10 is better.

## What each number measures

From the rows the script works out, per station, direction and peak/off-peak:

- **Halt** = `doors_close - doors_open` (how long the train stands at the platform). Timetable value for comparison.
- **Running time** = next station's `doors_open` - this station's `doors_close`.
- **Arrival vs timetable** = `doors_open` - scheduled arrival of the nearest scheduled train (within 20 min of your
  first station). Positive = late.
- **Total ride time** follows from the first and last row.
- `platform_at`, `display_min` and `crowd` are kept for later (wait times, checking the platform screens, crowding);
  they do not change the map yet.

## Making the corrections file

```
python tools/make_corrections.py --check   # read the files, print what was found and any problems, write nothing
python tools/make_corrections.py           # write simulator/corrections.json
```

Medians are used (one odd ride cannot move the result), and anything with fewer than 3 observations is printed but
not written.

## What happens to it

`simulator/corrections.json` has three lists: `halts`, `runs` and `delays`. The simulator will use them to change
where trains are drawn: measured halts replace the modelled ones, running times between stations are scaled to what
riders measured, and stations without data blend between the nearest measured ones and the terminals. The page then
says "corrected with rider data on <date>", and the plain timetable stays the fallback wherever there is no data.

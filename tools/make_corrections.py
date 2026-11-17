"""Turn rider data (CSV, one row per station) into simulator/corrections.json.

  python tools/make_corrections.py              read data/rider-data/*.csv, write simulator/corrections.json, print a report
  python tools/make_corrections.py --check      only check the files and print the report, write nothing
  python tools/make_corrections.py --stations   (re)write data/rider-data/station_names.csv

Input columns (see data/rider-data/README.md): session_id, date, line, towards, station, doors_open, doors_close,
platform_at, display_min, crowd, source, notes. Times are IST, HH:MM or HH:MM:SS.

Output (all seconds; medians over rider observations; peak/offpeak split):
  halts : how long trains stand at a station        {st, name, l, dr, period, haltSec, schedSec, n}
  runs  : running time between two adjacent stops     {from, to, l, dr, period, runSec, schedSec, n}
  delays: arrival vs timetable at a station           {st, name, l, dr, period, delaySec, n}
Rows with fewer than MIN_N observations are reported but not written, so one odd ride cannot move the map.
"""
import csv, json, re, statistics, sys
from datetime import date as Date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / 'simulator' / 'data.json').read_text(encoding='utf-8'))
_arg = lambda flag, default: Path(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default
IN_DIR = _arg('--in', ROOT / 'data' / 'rider-data')          # --in DIR   read CSVs from another folder (tests)
OUT = _arg('--out', ROOT / 'simulator' / 'corrections.json')  # --out FILE write somewhere else (tests)
PEAK = [('08:00', '11:00'), ('17:00', '20:30')]   # IST, edit if your data says otherwise
MIN_N = 3
MATCH_WINDOW = 1200                               # a session must start within 20 min of a scheduled train
LINES = {'g': 'G', 'green': 'G', 'p': 'P', 'purple': 'P', 'y': 'Y', 'yellow': 'Y'}
LNAME = {'G': 'Green', 'P': 'Purple', 'Y': 'Yellow'}

ST, PAT, PROF, RUNS, HOL = DATA['stations'], DATA['patterns'], DATA['profiles'], DATA['runs'], set(DATA['hol'])

def short(i):
    return (ST[i]['n'].replace('Nadaprabhu Kempegowda Station, Majestic', 'Majestic')
            .replace('Delta Electronics Bommasandra', 'Bommasandra').replace('Rashtreeya Vidyalaya Road', 'RV Road'))
norm = lambda s: re.sub(r'[^a-z0-9]', '', (s or '').lower())
ALIAS = {}
for i, s in enumerate(ST):
    for a in (s['n'], short(i), s['n'].split(',')[0], s['n'].split('(')[0]):
        ALIAS.setdefault(norm(a), i)

def station_id(name):
    k = norm(name)
    if k in ALIAS: return ALIAS[k]
    hits = {i for a, i in ALIAS.items() if k and (a.startswith(k) or k.startswith(a))}
    return hits.pop() if len(hits) == 1 else None

ROUTE = {}   # (l, dr) -> longest pattern = the whole line in that direction
for p in PAT:
    if (p['l'], p['dr']) not in ROUTE or len(p['s']) > len(ROUTE[(p['l'], p['dr'])]['s']):
        ROUTE[(p['l'], p['dr'])] = p

def direction(l, towards):
    k = norm(towards)
    for dr in (0, 1):
        r = ROUTE.get((l, dr))
        if r and k and (k in norm(short(r['s'][-1])) or norm(short(r['s'][-1])) in k): return dr
    return None

def secs(t):
    t = (t or '').strip()
    if not t: return None
    m = re.fullmatch(r'(\d{1,2}):(\d{2})(?::(\d{2}))?', t)
    if not m: raise ValueError(f'bad time {t!r}, use HH:MM:SS')
    return int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3] or 0)

def day_type(d):
    if d.strftime('%Y%m%d') in HOL: return 'holiday'
    return {6: 'sunday', 0: 'monday'}.get(d.weekday(), 'weekday')

def period(sec):
    hm = f'{sec // 3600 % 24:02d}:{sec // 60 % 60:02d}'
    return 'peak' if any(a <= hm < b for a, b in PEAK) else 'offpeak'

def match_run(svc, l, dr, first_st, first_arr):
    """Nearest scheduled train of this line and direction at the first logged station (same rule as the rider log)."""
    best = None
    for add in (0, 86400, -86400):
        for pi, start in RUNS[svc]:
            pr = PROF[pi]; p = PAT[pr['p']]
            if p['l'] != l or p['dr'] != dr or first_st not in p['s']: continue
            k = p['s'].index(first_st)
            if k == len(p['s']) - 1: continue
            d = first_arr - (start + add + pr['a'][k])
            if best is None or abs(d) < abs(best[0]): best = (d, pr, start + add)
    return best if best and abs(best[0]) <= MATCH_WINDOW else None

def write_station_list():
    out = IN_DIR / 'station_names.csv'
    with out.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['line', 'towards', 'order', 'station'])
        for (l, dr), r in sorted(ROUTE.items()):
            for k, si in enumerate(r['s']): w.writerow([LNAME[l], short(r['s'][-1]), k + 1, short(si)])
    print('wrote', out.relative_to(ROOT))

def main():
    if '--stations' in sys.argv: return write_station_list()
    files = sorted(f for f in IN_DIR.glob('*.csv') if not f.name.upper().startswith(('TEMPLATE', 'STATION_NAMES')))
    if not files: print('No data yet: put CSV files in data/rider-data/ (not TEMPLATE_*.csv).'); return
    problems, sessions = [], {}
    for f in files:
        with f.open(encoding='utf-8-sig', newline='') as fh:
            for n, row in enumerate(csv.DictReader(fh), start=2):
                where = f'{f.name} line {n}'
                row = {k.strip().lower(): (v or '').strip() for k, v in row.items() if k}
                if not any(row.values()): continue
                try:
                    l = LINES.get(row.get('line', '').lower()); si = station_id(row.get('station'))
                    if not l: raise ValueError(f"line {row.get('line')!r}: use Green, Purple or Yellow")
                    if si is None: raise ValueError(f"station {row.get('station')!r} not recognised, see station_names.csv")
                    dr = direction(l, row.get('towards'))
                    if dr is None: raise ValueError(f"towards {row.get('towards')!r}: use the last station of the line")
                    if si not in ROUTE[(l, dr)]['s']: raise ValueError(f'{short(si)} is not on the {LNAME[l]} line')
                    d = Date.fromisoformat(row.get('date', ''))
                    sid = f.name + ':' + (row.get('session_id') or row.get('date'))
                    sessions.setdefault(sid, {'l': l, 'dr': dr, 'date': d, 'rows': []})['rows'].append(
                        {'st': si, 'open': secs(row.get('doors_open')), 'close': secs(row.get('doors_close'))})
                except ValueError as e:
                    problems.append(f'{where}: {e}')
    halts, runs, delays, used, unmatched = {}, {}, {}, 0, 0
    for sid, s in sessions.items():
        route = ROUTE[(s['l'], s['dr'])]['s']
        rows = sorted(s['rows'], key=lambda r: route.index(r['st']))
        svc = day_type(s['date'])
        first = next((r for r in rows if r['open'] is not None), None)
        m = match_run(svc, s['l'], s['dr'], first['st'], first['open']) if first else None
        if not m: unmatched += 1
        prof, start = (m[1], m[2]) if m else (None, None)
        sched = lambda st, key: (start + prof[key][PAT[prof['p']]['s'].index(st)]) if prof and st in PAT[prof['p']]['s'] else None
        used += 1
        for i, r in enumerate(rows):
            t = r['open'] if r['open'] is not None else r['close']
            if t is None: continue
            key = (r['st'], s['l'], s['dr'], period(t))
            if r['open'] is not None and r['close'] is not None and 0 < r['close'] - r['open'] < 900:
                sa, sd = sched(r['st'], 'a'), sched(r['st'], 'd')
                halts.setdefault(key, ([], []))[0].append(r['close'] - r['open'])
                if sa is not None: halts[key][1].append(sd - sa)
            if r['open'] is not None and sched(r['st'], 'a') is not None:
                dl = r['open'] - sched(r['st'], 'a')
                if abs(dl) < 3600: delays.setdefault(key, []).append(dl)
            if i + 1 < len(rows):
                nx = rows[i + 1]
                if route.index(nx['st']) == route.index(r['st']) + 1 and r['close'] is not None and nx['open'] is not None and 0 < nx['open'] - r['close'] < 1800:
                    rk = (r['st'], nx['st'], s['l'], s['dr'], period(r['close']))
                    sr = (sched(nx['st'], 'a') - sched(r['st'], 'd')) if sched(nx['st'], 'a') is not None and sched(r['st'], 'd') is not None else None
                    runs.setdefault(rk, ([], []))[0].append(nx['open'] - r['close'])
                    if sr is not None: runs[rk][1].append(sr)
    med = lambda a: round(statistics.median(a)) if a else None
    H = [{'st': k[0], 'name': short(k[0]), 'l': k[1], 'dr': k[2], 'period': k[3], 'haltSec': med(v[0]), 'schedSec': med(v[1]), 'n': len(v[0])} for k, v in halts.items()]
    R = [{'from': k[0], 'to': k[1], 'name': short(k[0]) + ' > ' + short(k[1]), 'l': k[2], 'dr': k[3], 'period': k[4], 'runSec': med(v[0]), 'schedSec': med(v[1]), 'n': len(v[0])} for k, v in runs.items()]
    Dl = [{'st': k[0], 'name': short(k[0]), 'l': k[1], 'dr': k[2], 'period': k[3], 'delaySec': med(v), 'n': len(v)} for k, v in delays.items()]
    dates = sorted(s['date'].isoformat() for s in sessions.values())
    print(f'{len(files)} file(s), {used} sessions, {sum(len(s["rows"]) for s in sessions.values())} station rows, {unmatched} sessions with no timetable train within 20 min')
    for p in problems: print('  SKIPPED', p)
    for title, rows, val in (('Halts', H, 'haltSec'), ('Runs', R, 'runSec'), ('Arrival vs timetable', Dl, 'delaySec')):
        print(f'\n{title} (written when n >= {MIN_N}):')
        for x in sorted(rows, key=lambda x: (x['l'], x['dr'], x['name'], x['period'])):
            print(f"  {'ok ' if x['n'] >= MIN_N else '   '}{LNAME[x['l']]:6} dr{x['dr']} {x['period']:7} {x['name'][:44]:44} {x[val]:>5} s" + (f"  (timetable {x['schedSec']} s)" if x.get('schedSec') is not None else '') + f"  n={x['n']}")
    if '--check' in sys.argv: return
    keepn = lambda a: [x for x in a if x['n'] >= MIN_N]
    out = {'version': 1, 'date': Date.today().isoformat(), 'source': {'sessions': used, 'dates': [dates[0], dates[-1]] if dates else []},
           'peak': [list(p) for p in PEAK], 'minN': MIN_N, 'halts': keepn(H), 'runs': keepn(R), 'delays': keepn(Dl)}
    OUT.write_text(json.dumps(out, indent=1), encoding='utf-8')
    print(f'\nwrote {OUT}:{len(out["halts"])} halts, {len(out["runs"])} runs, {len(out["delays"])} delays')

if __name__ == '__main__':
    main()

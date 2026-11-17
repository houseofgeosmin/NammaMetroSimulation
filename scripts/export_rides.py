"""Export every Timely Ride Log ride and tap from Supabase to CSV.

  python scripts/export_rides.py                  write exports/<today>/{rides,ride_events,rider_stops}.csv
  python scripts/export_rides.py --since 2026-11-20
  python scripts/export_rides.py --out somewhere/

Needs two values from Vercel (Project -> Settings -> Environment Variables), given as environment variables or in a
local file `.env` (git-ignored) in the project folder:
  SUPABASE_URL=https://xxxx.supabase.co
  SUPABASE_SERVICE_ROLE_KEY=...        (or SUPABASE_SECRET_KEY=sb_secret_...)
The service key can read everything: keep it on your PC only, never commit or share it.

Files:
  rides.csv        one row per ride (first name, line, direction, start station, matched timetable train, times)
  ride_events.csv  one row per tap (kind, station, IST time, phone timestamp, undone flag)
  rider_stops.csv  one row per station in the data/rider-data format, so tools/make_corrections.py can read it
                   (copy it into data/rider-data/ to use it). Undone taps are left out.
"""
import csv, json, os, sys, urllib.request, urllib.parse
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = json.loads((ROOT / 'ride-log' / 'data_min.json').read_text(encoding='utf-8')) if (ROOT / 'ride-log' / 'data_min.json').exists() \
    else json.loads((ROOT / 'ride-logger' / 'data_min.json').read_text(encoding='utf-8'))
LINE = {'G': 'Green', 'P': 'Purple', 'Y': 'Yellow'}

def short(i):
    try: n = D['stations'][int(i)]['n']
    except (IndexError, ValueError, TypeError): return str(i)
    return n.replace('Nadaprabhu Kempegowda Station, Majestic', 'Majestic').replace('Delta Electronics Bommasandra', 'Bommasandra').replace('Rashtreeya Vidyalaya Road', 'RV Road')
def hms(s):
    s = int(float(s)) % 86400; return f'{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}'

def env():
    e = dict(os.environ)
    f = ROOT / '.env'
    if f.exists():
        for line in f.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                k, v = line.split('=', 1); e.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    url = (e.get('SUPABASE_URL') or e.get('NEXT_PUBLIC_SUPABASE_URL') or '').rstrip('/')
    key = e.get('SUPABASE_SERVICE_ROLE_KEY') or e.get('SUPABASE_SECRET_KEY') or ''
    if not url or not key: sys.exit('Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (environment or .env). See the top of this file.')
    return url, key

def fetch_all(url, key, table, query):
    headers = {'apikey': key, 'Accept': 'application/json'}
    if not key.startswith('sb_'): headers['Authorization'] = 'Bearer ' + key
    rows, step = [], 1000
    while True:
        q = urllib.parse.urlencode({**query, 'limit': step, 'offset': len(rows)})
        with urllib.request.urlopen(urllib.request.Request(f'{url}/rest/v1/{table}?{q}', headers=headers), timeout=60) as r:
            page = json.load(r)
        rows += page
        if len(page) < step: return rows

def write(path, rows, cols):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore'); w.writeheader(); w.writerows(rows)
    print(f'  {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}  ({len(rows)} rows)')

def main():
    url, key = env()
    since = sys.argv[sys.argv.index('--since') + 1] if '--since' in sys.argv else None
    out = Path(sys.argv[sys.argv.index('--out') + 1]) if '--out' in sys.argv else ROOT / 'exports' / date.today().isoformat()
    out.mkdir(parents=True, exist_ok=True)
    rq = {'select': '*', 'order': 'created_at.asc,id.asc'}
    if since: rq['date'] = 'gte.' + since
    rides = fetch_all(url, key, 'rides', rq)
    ids = {r['id'] for r in rides}
    events = [e for e in fetch_all(url, key, 'ride_events', {'select': '*', 'order': 'ride_id.asc,client_ts.asc,id.asc'}) if e['ride_id'] in ids]
    for e in events: e['station_name'] = short(e['station_index']); e['time_ist'] = hms(e['sec_ist'])
    for r in rides: r['line_name'] = LINE.get(r['line'], r['line'])
    print(f'{len(rides)} rides, {len(events)} taps ->')
    write(out / 'rides.csv', rides, ['id', 'created_at', 'updated_at', 'nick', 'date', 'weekday', 'service', 'line', 'line_name', 'dir', 'towards', 'from_station', 'from_name',
                                     'option_index', 'pattern_index', 'matched_profile', 'matched_start', 'start_ts', 'end_ts', 'done', 'device_id'])
    write(out / 'ride_events.csv', events, ['id', 'ride_id', 'kind', 'station_index', 'station_name', 'sec_ist', 'time_ist', 'client_ts', 'undone', 'received_at'])
    # rider_stops: doors open / doors close per station, same columns as data/rider-data/TEMPLATE_rider_stops.csv
    by = {r['id']: r for r in rides}; stops = {}
    for e in events:
        if e['undone'] or e['kind'] not in ('open', 'close', 'stop', 'move'): continue
        r = by[e['ride_id']]; k = (e['ride_id'], e['station_index'])
        s = stops.setdefault(k, {'session_id': 'TRL-' + e['ride_id'][:8], 'date': r['date'], 'line': LINE.get(r['line'], r['line']), 'towards': r['towards'],
                                 'station': e['station_name'], 'doors_open': '', 'doors_close': '', 'platform_at': '', 'display_min': '', 'crowd': '',
                                 'source': 'timely-ride-log', 'notes': '', '_ts': e['client_ts']})
        if e['kind'] == 'open' and not s['doors_open']: s['doors_open'] = e['time_ist']
        if e['kind'] == 'close': s['doors_close'] = e['time_ist']
        if e['kind'] == 'stop' and not s['notes']: s['notes'] = 'stopped ' + e['time_ist']
        if e['kind'] == 'move': s['notes'] = (s['notes'] + '; moving ' + e['time_ist']).lstrip('; ')
    write(out / 'rider_stops.csv', sorted(stops.values(), key=lambda s: (s['session_id'], s['_ts'])),
          ['session_id', 'date', 'line', 'towards', 'station', 'doors_open', 'doors_close', 'platform_at', 'display_min', 'crowd', 'source', 'notes'])

if __name__ == '__main__':
    main()

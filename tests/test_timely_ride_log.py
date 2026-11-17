"""Playwright tests for the Timely Ride Log (offline-first) and the simulator's "Timely Ride Log" button.
Run from a scratch folder after `python build_site.py`:   python tests/test_timely_ride_log.py
Screenshots written to the current folder: ride_log_button_390.png, ride_log_live_390.png, ride_log_offline_390.png

  A  full ride online: every tap reaches the server exactly once; "Saved online" only after the server answered
  B  offline mid-ride: taps while offline, reload with no network (page from the service worker), back online,
     every event arrives exactly once (including an Undo)
  C  close the browser with unsent taps, reopen it with the server completely down, then upload
  D  simulator button at 390 px: visible, >= 44 px, inside the safe area, not covering the header; hidden on the
     claude.ai build; rider reports panel hidden on the Vercel build
"""
import json, socket, sys, tempfile, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ride_log_server

ROOT = Path(__file__).resolve().parent.parent
fails = []
def check(cond, what):
    print(('ok   ' if cond else 'FAIL ') + what)
    if not cond: fails.append(what)

def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p
def ist_now():
    n = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30); return n.hour * 3600 + n.minute * 60 + n.second

MOBILE = dict(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
def ctx_for(p, profile):
    c = p.chromium.launch_persistent_context(str(profile), **MOBILE)
    c.errors = []
    return c
def watch(pg, ctx):
    pg.on('pageerror', lambda e: ctx.errors.append(str(e)))
    pg.on('console', lambda m: m.type == 'error' and 'net::ERR' not in m.text and 'Failed to load resource' not in m.text and ctx.errors.append(m.text))
    return pg
def open_log(ctx, base, hash_=''):
    pg = watch(ctx.pages[0] if ctx.pages else ctx.new_page(), ctx)
    resp = pg.goto(base + '/ride-log/' + hash_)
    pg.wait_for_function('navigator.serviceWorker && navigator.serviceWorker.controller !== null', timeout=15000)
    return pg, resp
def start_ride(pg, line='Green line towards Silk Institute', station='Majestic'):
    v = [o for o in pg.eval_on_selector_all('#lineDir option', 'o=>o.map(x=>[x.value,x.text])') if o[1] == line][0][0]
    pg.select_option('#lineDir', v)
    s = [o for o in pg.eval_on_selector_all('#stSel option', 'o=>o.map(x=>[x.value,x.text])') if o[1] == station][0][0]
    pg.select_option('#stSel', s); pg.fill('#nick', 'Tester'); pg.click('#go')
def tap(pg, k):
    pg.click(f'.act[data-k={k}]' if k in ('stop', 'open', 'close', 'move') else '#' + k); pg.wait_for_timeout(120)
status = lambda pg: (pg.get_attribute('#status', 'data-s'), pg.inner_text('#statusTxt'))
def wait_status(pg, s, timeout=20000):
    pg.wait_for_function(f"document.getElementById('status').dataset.s === '{s}'", timeout=timeout)
def local_events(pg):
    return json.loads(pg.evaluate("""async()=>{const rs=await RideLogQueue.allRides();let out=[];for(const r of rs){out=out.concat(await RideLogQueue.eventsOf(r.id))}return JSON.stringify(out)}"""))

def server_matches_phone(srv, pg, label):
    loc = {e['id']: e for e in local_events(pg)}
    sv = srv.state['events']
    check(set(loc) == set(sv), f'{label}: server has exactly the phone\'s {len(loc)} events (server {len(sv)})')
    check(srv.state['inserts'] == len(loc), f'{label}: each event inserted once ({srv.state["inserts"]} inserts, {srv.state["repeats"]} harmless repeats)')
    check(all(sv[i]['undone'] == loc[i]['undone'] and abs(sv[i]['sec_ist'] - loc[i]['sec']) < 0.01 for i in loc if i in sv), f'{label}: times and undone flags match')

with sync_playwright() as p:
    # ---------------- A: full ride online ----------------
    srv = ride_log_server.start(free_port()); base = srv.url
    ctx = ctx_for(p, tempfile.mkdtemp(prefix='trl-a-'))
    pg, _ = open_log(ctx, base, '#code=' + ride_log_server.CODE)
    check('#code' not in pg.url, 'access code removed from the address bar')
    check(pg.evaluate("RideLogQueue.kvGet('code')") == ride_log_server.CODE, 'access code kept on the phone')
    check(pg.inner_text('#offlinePill') == 'Works offline', 'page says it works offline')
    start_ride(pg); tap(pg, 'board')
    srv.cfg['delay'] = 1.5; t0 = time.time(); tap(pg, 'stop')
    s_now = status(pg)
    check(s_now[0] in ('saving', 'phone') and 'Saved online' not in s_now[1], f'right after a tap it does not claim "Saved online" ({s_now[1]})')
    wait_status(pg, 'online', 8000)
    check(time.time() - t0 >= 1.4, '"Saved online" appeared only after the (slow) server answered')
    srv.cfg['delay'] = 0
    for st in range(3):
        for k in (['open', 'close', 'move'] if st == 0 else ['stop', 'open', 'close', 'move']): tap(pg, k)
    pg.screenshot(path='ride_log_live_390.png', full_page=True)
    wait_status(pg, 'online')
    with pg.expect_download() as d: pg.click('#backup')
    csv_lines = Path(d.value.path()).read_text(encoding='utf-8').strip().split('\n')
    check(len(csv_lines) == 1 + 13, f'backup CSV has every tap ({len(csv_lines) - 1} of 13: board, stop, 3 + 2 x 4)')
    tap(pg, 'finish'); wait_status(pg, 'online')
    st = srv.state; ride = list(st['rides'].values())
    check(len(ride) == 1 and ride[0]['done'] and ride[0]['nick'] == 'Tester' and ride[0]['line'] == 'G', 'one finished ride on the server, with first name and line')
    kinds = [e['kind'] for e in sorted(st['events'].values(), key=lambda e: e['client_ts'])]
    check(kinds[0] == 'board' and kinds[-1] == 'alight' and len(kinds) == 14, f'14 events in tap order, board first, alight last ({len(kinds)})')
    secs = [e['sec_ist'] for e in st['events'].values()]
    check(all(abs(s - ist_now()) < 300 or abs(s - ist_now()) > 86100 for s in secs), 'event times are the phone clock in IST')
    server_matches_phone(srv, pg, 'A')
    check('on the server' in pg.inner_text('#rides'), 'finished ride listed as "on the server"')
    check(not ctx.errors, f'A: no page errors {ctx.errors}')
    ctx.close(); srv.stop()

    # ---------------- B: offline mid-ride, reload offline, back online ----------------
    srv = ride_log_server.start(free_port()); base = srv.url
    ctx = ctx_for(p, tempfile.mkdtemp(prefix='trl-b-'))
    pg, _ = open_log(ctx, base, '#code=' + ride_log_server.CODE)
    start_ride(pg, 'Purple line towards Whitefield (Kadugodi)', 'Majestic'); tap(pg, 'stop'); tap(pg, 'open'); wait_status(pg, 'online')
    online_before = srv.state['inserts']
    ctx.set_offline(True); srv.cfg['drop'] = True   # even if a request slips past the browser's offline mode, it gets no answer
    t0 = time.time(); tap(pg, 'close')
    wait_status(pg, 'offline', 4500)
    check(time.time() - t0 <= 4.0, f'"No signal" shown within about 3 s ({time.time() - t0:.1f} s)')
    for k in ['move', 'stop', 'open', 'close', 'move', 'stop']: tap(pg, k)
    tap(pg, 'undo')
    s_off = status(pg)
    check('No signal' in s_off[1] and 'unsent' in s_off[1], f'offline status is honest: {s_off[1]}')
    pg.screenshot(path='ride_log_offline_390.png', full_page=True)
    n_before = len(local_events(pg))
    resp = pg.reload()
    pg.wait_for_selector('#live:not([hidden])', timeout=10000)
    check(resp is not None and resp.from_service_worker, 'reload with no network: page came from the service worker')
    check('resumed' in pg.inner_text('#msg'), 'unfinished ride resumed after the reload')
    check(len(local_events(pg)) == n_before, f'all {n_before} events still on the phone after the reload')
    check(pg.evaluate("document.fonts.ready.then(()=>document.fonts.check('16px Inter') && document.fonts.check('700 16px \"Space Grotesk\"'))"), 'fonts load from the phone with no network')
    check(pg.inner_text('#now') != '-', f'still at the right station: {pg.inner_text("#now")}')
    tap(pg, 'stop'); tap(pg, 'open')
    check(srv.state['inserts'] == online_before, 'nothing reached the server while offline')
    ctx.set_offline(False); srv.cfg['drop'] = False
    wait_status(pg, 'online', 90000)
    server_matches_phone(srv, pg, 'B')
    undone = [e for e in srv.state['events'].values() if e['undone']]
    check(len(undone) == 1 and undone[0]['kind'] == 'stop', 'the undone tap is marked undone on the server, not deleted or duplicated')
    check(not ctx.errors, f'B: no page errors {ctx.errors}')
    ctx.close(); srv.stop()

    # ---------------- C: close the app with unsent taps, reopen with the server down ----------------
    port = free_port(); srv = ride_log_server.start(port); base = srv.url
    prof = tempfile.mkdtemp(prefix='trl-c-')
    ctx = ctx_for(p, prof)
    pg, _ = open_log(ctx, base, '#code=' + ride_log_server.CODE)
    pg.wait_for_timeout(500)
    ctx.set_offline(True); srv.cfg['drop'] = True
    start_ride(pg, 'Yellow line towards Bommasandra', 'RV Road')
    for k in ['board', 'stop', 'open', 'close', 'move']: tap(pg, k)
    n_taps = len(local_events(pg))
    ctx.close()                      # app killed with unsent taps
    srv.stop()                       # and no network at all: the server is gone
    ctx = ctx_for(p, prof); ctx.set_offline(True)
    pg = watch(ctx.pages[0] if ctx.pages else ctx.new_page(), ctx)
    resp = pg.goto(base + '/ride-log/')
    pg.wait_for_selector('#live:not([hidden])', timeout=10000)
    check(resp is not None and resp.from_service_worker, 'reopened with the server down: page came from the service worker')
    check(len(local_events(pg)) == n_taps, f'all {n_taps} unsent taps still there after closing the app')
    check(pg.inner_text('#now') == 'Ragigudda', 'ride resumed at the next station after RV Road: ' + pg.inner_text('#now'))
    srv = ride_log_server.start(port)  # signal is back
    ctx.set_offline(False)
    wait_status(pg, 'online', 90000)
    server_matches_phone(srv, pg, 'C')
    check(not ctx.errors, f'C: no page errors {ctx.errors}')
    ctx.close(); srv.stop()

    # ---------------- D: the button on the simulator ----------------
    srv = ride_log_server.start(free_port()); base = srv.url
    b = p.chromium.launch()
    pg = b.new_page(**MOBILE); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(base + '/'); pg.wait_for_timeout(1200)
    a = pg.locator('#rlRow a.rlbtn')
    check(a.is_visible(), 'mobile: "Timely Ride Log" button visible')
    bb = a.bounding_box(); brand = pg.locator('.brand').bounding_box(); when = pg.locator('.when').bounding_box()
    inter = lambda r, q: not (r['x'] + r['width'] <= q['x'] or q['x'] + q['width'] <= r['x'] or r['y'] + r['height'] <= q['y'] or q['y'] + q['height'] <= r['y'])
    check(bb['height'] >= 44 and bb['width'] >= 44, f'tap target {bb["width"]:.0f} x {bb["height"]:.0f} px')
    check(bb['x'] + bb['width'] <= 390 - 16 + 0.5 and bb['y'] >= 0, f'inside the page gutter, top right (right edge {bb["x"] + bb["width"]:.0f})')
    check(bb['x'] > 195, 'sits on the right half')
    check(not inter(bb, brand) and not inter(bb, when), 'does not cover the header')
    check(pg.get_attribute('#rlRow a', 'href') == '/ride-log/', 'links to /ride-log/')
    check(not pg.is_visible('#rlDesk'), 'desktop copy hidden on the phone')
    check(not pg.is_visible('#crowd'), 'rider reports panel hidden on the Vercel build')
    check(pg.is_visible('text=Scheduled simulation, not live GPS'), '"Scheduled simulation, not live GPS" label kept')
    check(pg.evaluate("document.compatMode") == 'CSS1Compat' and pg.evaluate("innerWidth") == 390, 'standards mode with a phone viewport')
    pg.screenshot(path='ride_log_button_390.png', clip={'x': 0, 'y': 0, 'width': 390, 'height': 260})
    pg.click('#rlRow a'); pg.wait_for_url('**/ride-log/'); check('Timely Ride Log' in pg.title(), 'button opens the ride log')
    d = b.new_page(viewport={'width': 1200, 'height': 900}); d.goto(base + '/'); d.wait_for_timeout(800)
    check(d.is_visible('#rlDesk') and not d.is_visible('#rlRow'), 'desktop: button next to the clock pill')
    db = d.locator('#rlDesk').bounding_box(); check(db['height'] >= 44, 'desktop tap target >= 44 px')
    c = b.new_page(**MOBILE); c.add_init_script("window.claude={use:async()=>{throw 0}}")
    c.goto((ROOT / 'simulator' / 'index.html').as_uri()); c.wait_for_timeout(800)
    check(not c.is_visible('.rlbtn'), 'claude.ai build: no button, look unchanged')
    check(not errs, f'D: no page errors {errs}')
    b.close(); srv.stop()

print('FAILED: ' + '; '.join(fails) if fails else 'ALL PASSED')
sys.exit(1 if fails else 0)

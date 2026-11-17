"""Smoke test for rider-log Ride mode. Run: python tests/test_ride_mode.py  (writes ride.png in the current folder)
Stubs claude.use('db') with an in-memory store that honours doc ids, and moves Date.now forward instead of waiting."""
import json, pathlib
from playwright.sync_api import sync_playwright
URL = (pathlib.Path(__file__).resolve().parent.parent / 'rider-log' / 'index.html').as_uri()
stub = """(()=>{const ss=sessionStorage,_n=Date.now;window.__off=+(ss.getItem('off')||0);Date.now=()=>_n()+window.__off;
setInterval(()=>ss.setItem('off',window.__off),50);
const rows=JSON.parse(ss.getItem('rows')||'{}');window.__rows=rows;let c=+(ss.getItem('c')||0);
const emit=()=>{ss.setItem('rows',JSON.stringify(rows));ss.setItem('c',c);window.__cb&&window.__cb({docs:Object.values(rows).sort((a,b)=>b.ts-a.ts).map(r=>({data:()=>r}))})};
const docRef=id=>({id,set:async r=>{rows[id]=JSON.parse(JSON.stringify(r));emit()},update:async r=>{if(!rows[id])throw{code:'not-found'};Object.assign(rows[id],JSON.parse(JSON.stringify(r)));emit()}});
const q={orderBy:()=>q,limit:()=>q,onSnapshot:cb=>{window.__cb=cb;emit()},doc:id=>docRef(id||('d'+(++c)))};
window.claude={use:async n=>{if(n==='user')return{id:async()=>'u1'};if(n==='db')return{collection:()=>q,doc:()=>({set:async()=>{},get:async()=>({exists:false})})}}};})()"""
fails = []
def check(cond, what):
    print(('ok   ' if cond else 'FAIL ') + what)
    if not cond: fails.append(what)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 400, 'height': 900}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: m.type == 'error' and errs.append(m.text))
    pg.add_init_script(stub); pg.goto(URL); pg.wait_for_timeout(800)
    adv = lambda s: pg.evaluate(f'window.__off+={s*1000}')
    tap = lambda: (pg.click('#rMain'), pg.wait_for_timeout(150))
    rows = lambda: json.loads(pg.evaluate('JSON.stringify(Object.values(window.__rows).filter(r=>r.kind==="ride"))'))
    pg.click('#mRide'); pg.wait_for_timeout(100)
    check(pg.is_visible('#ride') and not pg.is_visible('#today'), 'ride card shown, trip card hidden')
    pg.select_option('#rLine', 'G'); pg.select_option('#rDir', '0')
    maj = [o for o in pg.eval_on_selector_all('#rFrom option', 'o=>o.map(x=>[x.value,x.text])') if o[1].startswith('Majestic')][0][0]
    pg.select_option('#rFrom', maj)
    check(pg.inner_text('#rMain') == 'Doors open at Majestic', 'button: ' + pg.inner_text('#rMain'))
    tap(); r = rows()
    check(len(r) == 1 and len(r[0]['stops']) == 1 and r[0]['line'] == 'G' and r[0]['dir'] == 0, 'ride doc created on first tap')
    check(pg.inner_text('#rMain') == 'Doors closing at Majestic', 'button: ' + pg.inner_text('#rMain'))
    check('Chickpete' in pg.inner_text('#rNext'), 'next: ' + pg.inner_text('#rNext'))
    adv(40); tap()
    check(rows()[0]['stops'][0]['dwellSec'] in (40, 41), 'halt 40 s saved (41 if the real clock ticked between taps)')
    check(pg.inner_text('#rMain') == 'Doors open at Chickpete', 'station advanced: ' + pg.inner_text('#rMain'))
    adv(1); tap()
    check('ignored' in pg.inner_text('#rMsg') and len(rows()[0]['stops']) == 1, 'double tap ignored')
    adv(110); tap(); adv(25); tap()
    check(pg.inner_text('#rMain').startswith('Doors open at Krishna'), 'after Chickpete: ' + pg.inner_text('#rMain'))
    pg.click('#rUndo'); pg.wait_for_timeout(150)
    check(pg.inner_text('#rMain') == 'Doors closing at Chickpete' and rows()[0]['stops'][1]['depSec'] is None, 'undo restores doors-closing at Chickpete')
    pg.click('#rSkip'); pg.wait_for_timeout(150)
    check(pg.inner_text('#rMain').startswith('Doors open at Krishna'), 'skip close moves on')
    pg.click('#rSkip'); pg.wait_for_timeout(150)
    check(rows()[0]['stops'][2]['arrSec'] is None and pg.inner_text('#rMain') == 'Doors open at National College', 'skip station records empty stop')
    pg.screenshot(path='ride.png', full_page=True)
    pg.reload(); pg.wait_for_timeout(800)
    check(pg.is_visible('#ride') and pg.inner_text('#rMain') == 'Doors open at National College', 'ride survives reload')
    adv(100); tap()
    check(len(rows()) == 1 and len(rows()[0]['stops']) == 4, 'after reload the same doc is updated')
    pg.click('#rEnd'); pg.wait_for_timeout(150); r = rows()[0]
    check(r['done'] and pg.inner_text('#rMain') == 'Start a new ride', 'end ride here')
    print(json.dumps(r['stops'])[:500])
    check('Majestic' in pg.inner_text('#dwellTbl'), 'ride halts appear in the group halt table')
    # second ride: start one before the terminal, the ride ends by itself
    tap(); pg.select_option('#rLine', 'Y'); pg.select_option('#rDir', '1')
    opts = pg.eval_on_selector_all('#rFrom option', 'o=>o.map(x=>[x.value,x.text])'); pg.select_option('#rFrom', opts[-1][0])
    tap(); adv(30); tap(); adv(90); tap()
    r2 = [x for x in rows() if x['line'] == 'Y'][0]
    check(r2['done'] and len(r2['stops']) == 2 and r2['toName'] == 'Bommasandra', 'auto end at terminal: ' + r2['toName'])
    pg.click('#mTrip'); pg.wait_for_timeout(100)
    check(pg.is_visible('#today') and not pg.is_visible('#ride'), 'back to single-trip mode')
    print('errors', errs)
    if errs: fails.append('page errors')
print('FAILED: ' + '; '.join(fails) if fails else 'ALL PASSED')

import pathlib
URL=(pathlib.Path(__file__).resolve().parent.parent/'rider-log'/'index.html').as_uri()
from playwright.sync_api import sync_playwright
stub="""window.claude={use:async n=>{if(n==='user')return{id:async()=>'u1'};if(n==='db'){const rows={};const emit=()=>window.__cb&&window.__cb({docs:Object.values(rows).sort((a,b)=>b.ts-a.ts).map(r=>({data:()=>r}))});let c=0;const mk=()=>{const q={orderBy:()=>q,limit:()=>q,onSnapshot:cb=>{window.__cb=cb;emit()},doc:()=>{const id='d'+(++c);return{id,set:async r=>{rows[id]=r;window.__rows=rows;emit()},update:async r=>{Object.assign(rows[id],r);emit()}}}};return q};return{collection:()=>mk(),doc:()=>({set:async()=>{},get:async()=>({exists:false})})}}}}"""
with sync_playwright() as p:
    b=p.chromium.launch();pg=b.new_page(viewport={'width':400,'height':900});errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e)));pg.on('console',lambda m:m.type=='error' and errs.append(m.text))
    pg.add_init_script(stub);pg.goto(URL);pg.wait_for_timeout(800)
    print('open?',pg.eval_on_selector('#setupBox','e=>e.open'))
    opts=pg.eval_on_selector_all('#fromSt option','o=>o.map(x=>[x.value,x.text])')
    f=[o for o in opts if o[1].startswith('Majestic')][0][0];t=[o for o in opts if o[1].startswith('Sandal Soap')][0][0]
    pg.select_option('#fromSt',f);pg.select_option('#toSt',t);pg.click('#saveSetup');pg.wait_for_timeout(200)
    print('open after?',pg.eval_on_selector('#setupBox','e=>e.open'),pg.inner_text('#main'))
    pg.click('#main');pg.wait_for_timeout(1200);print(pg.inner_text('#main'),'|',pg.inner_text('#tripMsg'))
    pg.click('#main');pg.wait_for_timeout(1200);print(pg.inner_text('#main'),'|',pg.inner_text('#tripMsg'))
    pg.screenshot(path='m1.png')
    pg.click('#main');pg.wait_for_timeout(800);print(pg.inner_text('#tripMsg'));print(pg.evaluate('JSON.stringify(Object.values(window.__rows))')[:600])
    pg.wait_for_timeout(4200);print(pg.inner_text('#main'))
    pg.click('#swap');pg.wait_for_timeout(300);print(pg.inner_text('#tripLine'))
    pg.reload();pg.wait_for_timeout(800);print('after reload',pg.inner_text('#tripLine'),pg.eval_on_selector('#setupBox','e=>e.open'))
    print(errs)

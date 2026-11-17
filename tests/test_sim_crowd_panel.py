import pathlib
URL=(pathlib.Path(__file__).resolve().parent.parent/'simulator'/'index.html').as_uri()
from playwright.sync_api import sync_playwright
stub="""window.claude={use:async n=>{if(n==='user')return{id:async()=>'u1'};if(n==='db'){const rows=[];const q={orderBy:()=>q,limit:()=>q,onSnapshot:cb=>{window.__cb=cb;cb({docs:rows.map(r=>({data:()=>r}))})}};return{collection:()=>Object.assign(q,{add:async r=>{rows.unshift(r);window.__rows=rows;window.__cb({docs:rows.map(r=>({data:()=>r}))})}})}}}}"""
with sync_playwright() as p:
    b=p.chromium.launch();pg=b.new_page(viewport={'width':1100,'height':900});errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e)));pg.on('console',lambda m:m.type=='error' and errs.append(m.text))
    pg.add_init_script(stub);pg.goto(URL);pg.wait_for_timeout(1500)
    print(pg.inner_text('#cStation'),pg.eval_on_selector('#cDir','e=>e.options.length'),pg.is_disabled('#cGo'))
    pg.click('#cGo');pg.wait_for_timeout(500);print(pg.inner_text('#cMsg'));print(pg.inner_text('#cSum')[:200])
    pg.locator('#crowd').scroll_into_view_if_needed();pg.locator('#crowd').screenshot(path='crowd.png');print(errs)

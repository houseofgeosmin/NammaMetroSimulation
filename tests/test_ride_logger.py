import pathlib
URL=(pathlib.Path(__file__).resolve().parent.parent/'ride-logger'/'index.html').as_uri()
from playwright.sync_api import sync_playwright
stub="""window.claude={use:async n=>{if(n==='user')return{id:async()=>'u1'};if(n==='db'){const rows={};let c=0;return{collection:()=>({doc:(id)=>{id=id||('r'+(++c));return{id,set:async r=>{rows[id]=r;window.__rows=rows}}}})}}}}"""
with sync_playwright() as p:
    b=p.chromium.launch();pg=b.new_page(viewport={'width':400,'height':900});errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e)));pg.on('console',lambda m:m.type=='error' and errs.append(m.text))
    pg.add_init_script(stub);pg.goto(URL);pg.wait_for_timeout(600)
    opts=pg.eval_on_selector_all('#lineDir option','o=>o.map(x=>[x.value,x.text])');print(opts[:4])
    o=[x for x in opts if x[1].startswith('Green') and 'Madavara' in x[1]][0][0];pg.select_option('#lineDir',o)
    st=pg.eval_on_selector_all('#stSel option','o=>o.map(x=>[x.value,x.text])');m=[x for x in st if x[1]=='Majestic'][0][0];pg.select_option('#stSel',m)
    pg.click('#go');pg.click('#board')
    for i in range(2):
        for k in ['stop','open','close','move']:
            pg.click(f'.act[data-k={k}]');pg.wait_for_timeout(150)
        print(pg.inner_text('#msg'))
    pg.click('.act[data-k=stop]');pg.wait_for_timeout(100);pg.click('#undo')
    pg.screenshot(path='r1.png',full_page=True)
    print(pg.inner_text('#now'),'|',pg.inner_text('#progTxt'))
    pg.click('#finish');pg.wait_for_timeout(300)
    import json;rows=pg.evaluate('JSON.stringify(window.__rows)');print(rows[:700])
    print(pg.inner_text('#rides')[:150]);print(errs)

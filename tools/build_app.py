#!/usr/bin/env python3
"""Builds the one Station app (index.html in the public Station repo) from the Station page (history.html in the
private Logs repo). Usage: build_app.py <history.html> <station_link.js> <out index.html> <app version>
Every change is an exact text replacement that must match once, so a changed source page fails loudly."""
import sys

src, link, out, ver = sys.argv[1:5]
h = open(src, encoding="utf-8").read()
js = open(link, encoding="utf-8").read().replace("__APP_V__", ver)

def rep(old, new, count=1):
    global h
    n = h.count(old)
    if n != count:
        sys.exit("expected %d of %r, found %d" % (count, old[:70], n))
    h = h.replace(old, new)

CSS = """<style>
html{background:#0b1017;color-scheme:dark}
body::before{content:"";position:fixed;top:0;left:0;right:0;height:var(--sat,env(safe-area-inset-top));background:#0b1017;z-index:60;pointer-events:none}
#stnbar{position:fixed;top:0;left:0;right:0;z-index:2147482000;display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:4px 10px;
  padding:calc(var(--sat0,env(safe-area-inset-top)) + 22px) 14px 10px;min-height:calc(var(--sat0,env(safe-area-inset-top)) + 22px + 40px);border:0;border-bottom:1px solid rgba(244,185,66,.45);
  background:#21190a;color:#f4b942;font:600 14px/1.25 -apple-system,BlinkMacSystemFont,"SF Pro Text",system-ui,sans-serif;cursor:pointer;text-align:center}
#stnbar[hidden]{display:none}
#stnbar b{font-weight:800;letter-spacing:.2px}
#stnbar span{color:#e9d3a2}
#stnbar span::before{content:"\\00b7";margin-right:10px;color:#a8894a}
#stnbar.none{background:#2a1116;color:#ff8a9b;border-bottom-color:rgba(255,107,139,.5)}
#stnbar.none span{color:#f3c4cc}
.srclink{background:none;border:0;padding:0;color:inherit;font:inherit;text-decoration:underline;text-underline-offset:2px;cursor:pointer}
#stnsrc{position:fixed;inset:0;z-index:2147481000;background:rgba(5,8,12,.78);display:none;align-items:center;justify-content:center;
  padding:calc(var(--sat,env(safe-area-inset-top)) + 16px) 16px calc(env(safe-area-inset-bottom) + 16px)}
#stnsrc.open{display:flex}
#stnsrc .sheet{width:100%;max-width:560px;max-height:100%;overflow-y:auto;-webkit-overflow-scrolling:touch;background:var(--card);border:1px solid var(--line);border-radius:18px;padding:16px 18px}
#stnsrc .fhead{display:flex;align-items:center;justify-content:space-between;gap:12px}
#stnsrc h2{margin:0;font-size:22px}
#stnsrc .panel{background:var(--bg);margin:12px 0 0;padding:12px 14px;display:block;overflow:visible}
.stnp h3{margin:0 0 10px}
#stnsrc .stnp h3{display:none}
.stns{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;align-items:center;padding:10px 12px;border-radius:12px;background:var(--card);border:1px solid var(--line)}
.stns .dot{grid-row:span 2;width:12px;height:12px;border-radius:50%;background:#8aa0bf}
.stns .dot.g{background:#47d6a0}.stns .dot.a{background:#f4b942}.stns .dot.r{background:#ff6b8b}
.stns span:last-child{color:var(--mut);font-size:14px}
.stnt{display:flex;align-items:center;gap:14px;margin:12px 0 4px;cursor:pointer}
.stnt>span{flex:1;min-width:0}.stnt small{display:block;color:var(--mut);font-size:13px;margin-top:2px}
.stnsw{flex:none;position:relative;width:52px;height:31px;border-radius:999px;border:1px solid var(--line);background:#2a3546;cursor:pointer;padding:0;transition:background .15s}
.stnsw i{position:absolute;top:2px;left:2px;width:25px;height:25px;border-radius:50%;background:#fff;transition:transform .15s}
.stnsw.on{background:#f4b942;border-color:#f4b942}.stnsw.on i{transform:translateX(21px)}
.stnf{margin-top:12px}.stnf>label{display:block;font-size:13px;color:var(--mut);margin:0 2px 6px}
.stnf .set input{flex:1;min-width:150px;width:auto;font:15px ui-monospace,SFMono-Regular,Menlo,monospace}
.stnf .set button.alt{background:transparent;color:var(--tx);border:1px solid var(--line)}
.stnf .set button.dng{color:#ff8a9b;border-color:rgba(255,107,139,.5)}
.stnm{min-height:20px;margin-top:10px;font-size:14px}
</style>"""

HEAD = ('<head><meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes">'
        '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"><meta name="apple-mobile-web-app-title" content="Station">'
        '<link rel="apple-touch-icon" href="apple-touch-icon.png"><link rel="icon" type="image/png" href="apple-touch-icon.png">'
        '<link rel="preconnect" href="https://api.github.com" crossorigin>' + CSS + '<script>' + js + '</script>')

rep("<head>", HEAD)
rep("<title>Station History</title>", "<title>Station</title>")
rep('src="/icon.png"', 'src="apple-touch-icon.png"')
# footer: says which source is in use (and opens the Data source window); the connection test link no longer points at "/"
rep('Local History __VERSION__ &middot; home Wi-Fi only &middot; <a href="/" id="ctl">connection test</a>',
    'Local History __VERSION__ &middot; <button type="button" class="srclink" id="srcbtn" data-hint="Data source: live from the Mac mini or the online copy">Checking…</button> &middot; <a href="#health" id="ctl">connection test</a>')
rep("__VERSION__", ver, h.count("__VERSION__"))
# the page's version is now the app's; the server only has to be new enough
rep("const PAGE_V='%s';" % ver, "const PAGE_V='%s';const SRV_NEED=STN.SRV_NEED;const srvOK=v=>STN.vnum(v)>=STN.vnum(SRV_NEED);" % ver)
rep("set(0,j.version===PAGE_V?'g':'a',j.version===PAGE_V?'Reachable · server '+j.version+' · '+ms+' ms':'Reachable · server '+j.version+' · this page is an older copy ('+PAGE_V+') <button type=\"button\" class=\"rlb\" data-hint=\"Reload to get the newest page\" onclick=\"location.reload()\">Reload page</button>');",
    "set(0,srvOK(j.version)?'g':'a',srvOK(j.version)?'Reachable · server '+j.version+' · '+ms+' ms':'Reachable · server '+j.version+' · Station '+PAGE_V+' needs server '+SRV_NEED+' or newer: restart the Mac mini server with the newest file');")
rep("set(4,off<5?'g':off<60?'a':'r',off<5?'Within '+Math.max(1,Math.round(off))+' s':'Off by '+Math.round(off)+' s')}",
    "set(4,off<5?'g':off<60?'a':'r',off<5?'Within '+Math.max(1,Math.round(off))+' s':'Off by '+Math.round(off)+' s');\n"
    "    if(STN.mode==='online'){set(0,'a','Online copy · pushed '+STN.pushedAgo()+' by server '+j.version+' · the Mac mini isn’t being read live');set(4,'a','Not checked on the online copy')}}")
rep("set(2,age<180?'g':age<900?'a':'r',j.last?'Last reading '+dur(age):'No readings yet');",
    "set(2,age<180?'g':age<900?'a':'r',j.last?'Last reading '+dur(age)+(STN.mode==='online'?' before the online copy was made':''):'No readings yet');")
rep("hdotPut(!st.j.last||age>=900?'r':(p.j.version!==PAGE_V||age>=180)?'a':'g')}",
    "hdotPut(!st.j.last||age>=900?'r':(!srvOK(p.j.version)||age>=180)?'a':'g')}")
rep("restart it with the '+PAGE_V+' file", "restart it with the '+SRV_NEED+' file")
# Settings gets the Data source panel at the top (live/online, force-online switch, address and token)
rep("$('fsetbody').innerHTML='<div class=\"panel\"><h3>Weather station</h3>", "$('fsetbody').innerHTML=STN.panelHTML()+'<div class=\"panel\"><h3>Weather station</h3>")
rep("  $('esave').onclick=async()=>{", "  STN.bindPanel($('fsetbody'));\n  $('esave').onclick=async()=>{")
# the notice at the top pushes every page and window down by its height, so nothing sits under it or the status bar
rep("    root.style.setProperty('--sat',v+'px');",
    "    root.style.setProperty('--sat0',v+'px');root.style.setProperty('--sat',(v+STN.barH())+'px');")
rep("  function top(){", "  window.stnSat=sat;\n  function top(){")
# when the source changes (left home, came home, switch flipped) the open page reloads its data straight away
rep("openFromHash();addEventListener('hashchange',openFromHash);",
    "openFromHash();addEventListener('hashchange',openFromHash);\n"
    "addEventListener('stationmode',()=>{load();loadWind();if($('fc').classList.contains('open'))loadForecast();hdotCheck()});")
rep("fsclose:'Close',", "fsclose:'Close',srcbtn:'Data source: live from the Mac mini or the online copy',")
open(out, "w", encoding="utf-8").write(h)
print("built", out, ver, len(h), "bytes")

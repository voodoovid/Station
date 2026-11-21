import asyncio, json, os, re, sys, time
from urllib.parse import urlparse, unquote
from playwright.async_api import async_playwright

APP = "/home/claude/station"
LIVE = "/tmp/live"
ADDR = "192.0.2.10"
ORIGIN = "https://voodoovid.github.io/Station/"
sys.path.insert(0, "/home/claude/logs/station-history")

def snap(url):
    from urllib.parse import parse_qs
    u = urlparse(url)
    qs = "&".join("%s=%s" % (k, v) for k, v in sorted((k, v[0]) for k, v in parse_qs(u.query).items()))
    name = u.path[len("/api/"):].replace("/", "_") + ("@" + qs if qs else "")
    return "api/" + re.sub(r"[^A-Za-z0-9@=&._-]", "_", name) + ".json"

class Net:
    home = True          # Mac mini reachable
    live_hits = []; gh_hits = []; posts = []

async def setup(page, net):
    async def app(route):
        p = urlparse(route.request.url).path.replace("/Station/", "") or "index.html"
        f = os.path.join(APP, p)
        if os.path.isfile(f):
            ct = "text/html" if f.endswith(".html") else "image/png"
            return await route.fulfill(path=f, content_type=ct)
        await route.fulfill(status=404, body="nf")
    async def mac(route):
        r = route.request
        if not net.home:
            return await route.abort("addressunreachable")
        net.live_hits.append(r.url)
        hdr = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Allow-Methods": "GET, POST, OPTIONS"}
        if r.method == "OPTIONS":
            return await route.fulfill(status=204, headers=hdr)
        if r.method == "POST":
            net.posts.append(r.url)
            return await route.fulfill(status=200, headers=hdr, content_type="application/json", body='{"ok":true,"elevation_m":80}')
        path = urlparse(r.url).path
        if path == "/api/pushstatus":
            return await route.fulfill(status=200, headers=hdr, content_type="application/json",
                body=json.dumps({"configured": True, "last_try": time.time()-200, "last_ok": time.time()-200, "err": None, "files": 120, "bytes": 5e6, "secs": 9, "pushes": 3, "every_min": 15, "now": time.time()}))
        n = snap(r.url.split(":8124", 1)[1])
        f = os.path.join(LIVE, n)
        if path == "/api/ping":
            return await route.fulfill(status=200, headers=hdr, content_type="application/json", body=json.dumps({"ok": True, "version": "v1.20", "now": time.time()}))
        if os.path.isfile(f):
            return await route.fulfill(status=200, headers=hdr, content_type="application/json", path=f)
        await route.fulfill(status=404, headers=hdr, content_type="application/json", body='{"error":"not found"}')
    async def gh(route):
        r = route.request
        net.gh_hits.append(r.url)
        hdr = {"Access-Control-Allow-Origin": "*"}
        if r.headers.get("authorization") != "Bearer test_token":
            return await route.fulfill(status=401, headers=hdr, body='{"message":"Bad credentials"}')
        u = urlparse(r.url)
        if "/git/trees/" in u.path:
            tree = []
            for root, _, fs in os.walk(LIVE):
                for x in fs:
                    p = os.path.join(root, x); tree.append({"path": os.path.relpath(p, LIVE), "size": os.path.getsize(p)})
            return await route.fulfill(status=200, headers=hdr, content_type="application/json", body=json.dumps({"tree": tree}))
        rel = unquote(u.path.split("/contents/", 1)[1])
        f = os.path.join(LIVE, rel)
        if os.path.isfile(f):
            return await route.fulfill(status=200, headers=hdr, content_type="application/json", path=f)
        await route.fulfill(status=404, headers=hdr, body='{"message":"Not Found"}')
    await page.route("https://voodoovid.github.io/**", app)
    await page.route("https://%s:8124/**" % ADDR, mac)
    await page.route("https://api.github.com/**", gh)

async def run():
    res = []
    def ok(name, cond, extra=""):
        res.append(("PASS" if cond else "FAIL", name, extra)); print("PASS" if cond else "FAIL", name, extra)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--ignore-certificate-errors"])
        async def newpage(home, store, w=1180, h=820, mobile=False):
            ctx = await b.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile, ignore_https_errors=True)
            page = await ctx.new_page(); net = Net(); net.home = home; net.live_hits = []; net.gh_hits = []; net.posts = []
            errs = []; page.on("pageerror", lambda e: errs.append(str(e)))
            page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
            await setup(page, net)
            await page.add_init_script("(()=>{const s=%s;for(const k in s)localStorage.setItem(k,s[k])})()" % json.dumps(store))
            await page.goto(ORIGIN); return page, net, errs
        both = {"station.macAddr": ADDR, "station.githubToken": "test_token"}

        # 1. at home
        page, net, errs = await newpage(True, both)
        await page.wait_for_function("document.querySelector('#sub') && !/Loading/.test(document.querySelector('#sub').textContent)", timeout=15000)
        mode = await page.evaluate("STN.mode"); hidden = await page.evaluate("document.getElementById('stnbar').hidden")
        ok("home: live", mode == "live" and hidden, f"mode={mode} bar hidden={hidden} sub={await page.text_content('#sub')}")
        ok("home: data from Mac mini", any("/api/history" in u for u in net.live_hits) and not any("history" in u for u in net.gh_hits))
        ok("home: footer", (await page.text_content("#srcbtn")) == "Live from the Mac mini")
        await page.screenshot(path="/tmp/shot_home_ipad.png")
        # forecast page and settings
        await page.click("#fbtn"); await page.wait_for_timeout(1500); await page.click("#fgear"); await page.wait_for_timeout(500)
        ok("settings: data source panel", await page.locator("#fsetbody .stnp").count() == 1)
        await page.screenshot(path="/tmp/shot_settings_live.png")
        # flip force online
        await page.click("#fsetbody .stnsw"); await page.wait_for_timeout(2500)
        mode = await page.evaluate("STN.mode"); bar = await page.text_content("#stnbar")
        ok("force online at home", mode == "online" and "forced" in bar, bar)
        await page.screenshot(path="/tmp/shot_settings_forced.png")
        await page.click("#fsetbody .stnsw"); await page.wait_for_timeout(2500)
        ok("unforce: back to live", await page.evaluate("STN.mode") == "live")
        ok("home: no page errors", not errs, "; ".join(errs[:3]))
        await page.context.close()

        # 2. away (cellular)
        page, net, errs = await newpage(False, both)
        t0 = time.time()
        await page.wait_for_function("document.querySelector('#card-temp')", timeout=20000)
        dt = time.time() - t0
        mode = await page.evaluate("STN.mode"); bar = await page.text_content("#stnbar")
        ok("away: online copy", mode == "online" and "Online copy" in bar, f"{bar} · charts in {dt:.1f}s")
        geo = await page.evaluate("(()=>{const b=document.getElementById('stnbar').getBoundingClientRect(),h=document.querySelector('header').getBoundingClientRect();return {bb:b.bottom,ht:h.top,sat:getComputedStyle(document.documentElement).getPropertyValue('--sat')}})()")
        ok("away: notice doesn't cover the header", geo["bb"] <= geo["ht"], str(geo))
        await page.screenshot(path="/tmp/shot_away_ipad.png")
        # POST is refused politely
        r = await page.evaluate("fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(async r=>[r.status,(await r.json()).error])")
        ok("away: changes refused (read-only)", r[0] == 503 and "read-only" in r[1], str(r))
        # health window
        await page.click("#cbtn"); await page.wait_for_timeout(4000)
        txt = await page.inner_text("#crw")
        ok("away: health shows online copy", "Online copy · pushed" in txt and "Last copy" in txt, txt[:300].replace("\n", " | "))
        await page.screenshot(path="/tmp/shot_away_health.png")
        await page.keyboard.press("Escape")
        # notice opens the Data source window
        await page.click("#px") if await page.locator("#px").is_visible() else None
        await page.mouse.click(5, 5) if False else None
        await page.evaluate("document.getElementById('pop')&&document.getElementById('pop').classList.remove('open')")
        await page.evaluate("STN.openPanel()"); await page.wait_for_timeout(300)
        ok("away: data source pop-up", await page.locator("#stnsrc.open .stnp").count() == 1)
        await page.screenshot(path="/tmp/shot_away_panel.png")
        # remove token asks first (dialog auto-accepted) -> no source
        await page.click("#stnsrc .stnkr"); await page.wait_for_timeout(1500)
        ok("remove token: asks, then no source", await page.evaluate("STN.mode") == "none" and await page.evaluate("!localStorage.getItem('station.githubToken')"))
        ok("away: no page errors", not errs, "; ".join(errs[:3]))
        await page.context.close()

        # 3. leaving home mid-use, then coming back
        page, net, errs = await newpage(True, both)
        await page.wait_for_function("STN.mode==='live' && document.querySelector('#card-temp')", timeout=15000)
        net.home = False
        await page.evaluate("load()"); await page.wait_for_function("STN.mode==='online'", timeout=15000)
        ok("left home: switched to online", True, await page.text_content("#stnbar"))
        net.home = True
        await page.evaluate("dispatchEvent(new Event('online'))"); await page.wait_for_function("STN.mode==='live'", timeout=10000)
        ok("came home: back to live, notice gone", await page.evaluate("document.getElementById('stnbar').hidden"))
        ok("switching: no page errors", not errs, "; ".join(errs[:3]))
        await page.context.close()

        # 4. iPhone portrait, away
        page, net, errs = await newpage(False, both, 440, 956, True)
        await page.wait_for_function("document.querySelector('#card-temp')", timeout=20000); await page.wait_for_timeout(800)
        await page.screenshot(path="/tmp/shot_away_iphone.png")
        await page.click("#fbtn"); await page.wait_for_timeout(1500)
        await page.screenshot(path="/tmp/shot_away_iphone_fc.png")
        fc = await page.evaluate("(()=>{const b=document.getElementById('stnbar').getBoundingClientRect(),h=document.querySelector('#fc .fhead').getBoundingClientRect();return [b.bottom,h.top]})()")
        ok("iPhone: forecast page starts below the notice", fc[0] <= fc[1], str(fc))
        ok("iPhone: no page errors", not errs, "; ".join(errs[:3]))
        await page.context.close()

        # 5. nothing set up
        page, net, errs = await newpage(False, {})
        await page.wait_for_timeout(2500)
        ok("no setup: red notice", await page.evaluate("STN.mode") == "none" and "No data source" in await page.text_content("#stnbar"))
        await page.screenshot(path="/tmp/shot_none.png")
        await page.context.close()
        await b.close()
    print("\n%d passed, %d failed" % (sum(r[0] == "PASS" for r in res), sum(r[0] == "FAIL" for r in res)))

asyncio.run(run())

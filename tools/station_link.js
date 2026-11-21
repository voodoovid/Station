/* Station v1.21: one app, two data sources.
   Live: the Mac mini's secure address (https://<Mac mini>:8124), at home.
   Online: the copy the Mac mini pushes every 15 minutes to the private Logs repo ("live" branch), read with a
   read-only token kept on this device. Every '/api/...' request the page makes goes through here, so the rest of
   the page doesn't need to know which source it is on. Nothing private is in this file: the Mac mini address and
   the token are stored only in this browser. */
(function(){
  'use strict';
  const APP_V='__APP_V__', SRV_NEED='v1.20';
  const API='https://api.github.com/repos/voodoovid/logs', BRANCH='live', PORT=8124;
  const K_ADDR='station.macAddr', K_TOK='station.githubToken', K_OLD='remoteTest.githubToken', K_FORCE='station.forceOnline';
  const PROBE_MS=1800, WATCH_MS=4000, MAN_MS=60000, RECHECK_MS=60000;
  const ls={get(k){try{return localStorage.getItem(k)||''}catch(e){return ''}},
            set(k,v){try{localStorage.setItem(k,v);return true}catch(e){return false}},
            del(k){try{localStorage.removeItem(k)}catch(e){}}};
  if(!ls.get(K_TOK)&&ls.get(K_OLD))ls.set(K_TOK,ls.get(K_OLD));      // a token saved by the Station Test (same site) is reused
  const realFetch=window.fetch.bind(window);
  const onMac=/^(8123|8124)$/.test(location.port);                    // opened from the Mac mini itself: nothing to switch
  const addr=()=>ls.get(K_ADDR).trim(), token=()=>ls.get(K_TOK).trim(), forced=()=>ls.get(K_FORCE)==='1';
  const base=()=>'https://'+addr()+':'+PORT;
  const vnum=v=>{const m=/v(\d+)\.(\d+)/.exec(v||'');return m?+m[1]*1000+ +m[2]:0};
  const S={mode:onMac?'live':'starting',started:false,man:null,manAt:0,manP:null,cache:new Map(),tree:null,lastLive:0};
  const ago=ms=>{const m=Math.round(ms/60000);return m<1?'under a minute ago':m<60?m+' min ago':m<1440?Math.floor(m/60)+' h '+(m%60)+' min ago':Math.floor(m/1440)+' d ago'};
  const pushedAgo=()=>S.man?ago(Date.now()-Date.parse(S.man.pushed_at)):'not read yet';
  const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

  function resp(status,body){
    return new Response(typeof body==='string'?body:JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});
  }
  function abortErr(){try{return new DOMException('Aborted','AbortError')}catch(e){const x=new Error('Aborted');x.name='AbortError';return x}}
  function withSignal(p,sig){
    if(!sig)return p;
    if(sig.aborted)return Promise.reject(abortErr());
    return new Promise((res,rej)=>{sig.addEventListener('abort',()=>rej(abortErr()),{once:true});p.then(res,rej)});
  }
  async function timed(url,opt,ms){
    const c=new AbortController(),t=setTimeout(()=>c.abort(),ms);
    try{return await realFetch(url,Object.assign({cache:'no-store'},opt,{signal:c.signal}))}finally{clearTimeout(t)}
  }

  /* ---- live: the Mac mini ---- */
  async function probeLive(ms){
    if(!addr())return false;
    try{const r=await timed(base()+'/api/ping',{},ms||PROBE_MS);if(!r.ok)return false;const j=await r.json();
      S.liveV=j.version;const ok=vnum(j.version)>=vnum(SRV_NEED);if(ok)S.lastLive=Date.now();return ok}
    catch(e){return false}
  }
  function liveFetch(url,opt){
    return new Promise((resolve,reject)=>{
      let done=false;const fin=(f,v)=>{if(!done){done=true;clearTimeout(t);f(v)}};
      const fallBack=async e=>{                         // the Mac mini stopped answering (left home): carry on from the online copy
        if(done)return;
        if(await probeLive(2000)){if(e)fin(reject,e);return}
        if(done)return;
        if(token()){setMode('online');fin(resolve,onlineFetch(url,opt))}else{setMode('none');if(e)fin(reject,e);else fin(resolve,noSource())}
      };
      realFetch(base()+url,opt).then(r=>{S.lastLive=Date.now();fin(resolve,r)},e=>{
        if(e&&e.name==='AbortError'&&opt&&opt.signal&&opt.signal.aborted)return fin(reject,e);
        fallBack(e)});
      const t=setTimeout(()=>fallBack(null),WATCH_MS);   // slow answer: only switches if the Mac mini really can't be reached
    });
  }

  /* ---- online: the copy in the private Logs repo ---- */
  function snapName(u){                                  // must match snap_name() in tempest_server.py
    const x=new URL(u,'https://station.invalid'),seen={},kv=[];
    for(const [k,v] of x.searchParams){if(v===''||seen[k])continue;seen[k]=1;kv.push([k,v])}
    kv.sort((a,b)=>a[0]<b[0]?-1:a[0]>b[0]?1:a[1]<b[1]?-1:a[1]>b[1]?1:0);
    const qs=kv.map(p=>p[0]+'='+p[1]).join('&');
    const name=x.pathname.slice(5).replace(/\//g,'_')+(qs?'@'+qs:'');
    return 'api/'+name.replace(/[^A-Za-z0-9@=&._-]/g,'_')+'.json';
  }
  function gh(path,ms,accept){
    const p=path.split('/').map(encodeURIComponent).join('/');
    return timed(API+'/'+p+(p.indexOf('?')<0&&path.indexOf('contents/')===0?'?ref='+BRANCH:''),
      {headers:{Authorization:'Bearer '+token(),Accept:accept||'application/vnd.github.raw+json','X-GitHub-Api-Version':'2022-11-28'}},ms||25000);
  }
  function ghErr(r){
    return r.status===401?'GitHub rejected the token (mistyped or expired)':r.status===404?'Not in the online copy yet':'GitHub answered HTTP '+r.status;
  }
  function getManifest(force){
    if(S.manP)return S.manP;
    if(S.man&&!force&&Date.now()-S.manAt<MAN_MS)return Promise.resolve(S.man);
    S.manP=(async()=>{
      const r=await gh('contents/manifest.json',15000);
      if(!r.ok)throw new Error(ghErr(r));
      const m=await r.json(),was=S.man&&S.man.pushed_at;S.man=m;S.manAt=Date.now();
      if(was&&was!==m.pushed_at)refreshViewed();
      bar();return m;
    })().finally(()=>{S.manP=null});
    return S.manP;
  }
  function getFile(name){
    return getManifest().then(m=>{
      const stamp=m.files&&m.files[name];
      if(!stamp)throw new Error('This view isn’t in the online copy');
      const c=S.cache.get(name);
      if(c&&c.stamp===stamp){c.used=Date.now();return c.p}
      const p=gh('contents/'+name).then(r=>{if(!r.ok)throw new Error(ghErr(r));return r.text()});
      const e={stamp,p,used:Date.now()};S.cache.set(name,e);
      p.catch(()=>{if(S.cache.get(name)===e)S.cache.delete(name)});
      return p;
    });
  }
  function refreshViewed(){                              // a new copy arrived: quietly fetch again whatever was looked at lately
    const cut=Date.now()-30*60000;
    for(const [n,c] of S.cache)if(c.used>cut&&S.man.files[n]&&S.man.files[n]!==c.stamp)getFile(n).catch(()=>{});
  }
  async function pushStatus(){                           // stands in for the Mac mini's /api/pushstatus (Health › Online copy)
    const m=await getManifest(),t=Date.parse(m.pushed_at)/1000;
    if(!S.tree||S.tree.at!==m.pushed_at){
      let bytes=null;
      try{const r=await gh('git/trees/'+BRANCH+'?recursive=1',15000,'application/vnd.github+json');
        if(r.ok){const j=await r.json();bytes=(j.tree||[]).reduce((a,x)=>a+(x.size||0),0)}}catch(e){}
      S.tree={at:m.pushed_at,bytes};
    }
    return {configured:true,last_try:t,last_ok:t,err:null,files:Object.keys(m.files||{}).length,bytes:S.tree.bytes||0,
            secs:null,pushes:null,every_min:m.every_min||15,now:Date.now()/1000,source:'online copy'};
  }
  const READ_ONLY='Changes need the Mac mini at home: Station is showing the online copy, which is read-only';
  function noSource(){return resp(503,{error:'No data source yet: open Settings › Data source'})}
  async function onlineFetch(url,opt){
    const method=((opt&&opt.method)||'GET').toUpperCase(),path=url.split('?')[0];
    if(!token())return noSource();
    if(method!=='GET'||path==='/api/backtest/run'||path==='/api/tfcheck')return resp(503,{error:READ_ONLY});
    try{
      if(path==='/api/pushstatus')return resp(200,await withSignal(pushStatus(),opt&&opt.signal));
      return resp(200,await withSignal(getFile(snapName(url)),opt&&opt.signal));
    }catch(e){if(e.name==='AbortError')throw e;return resp(503,{error:e.message})}
  }
  function preload(){                                    // the views every visit opens, fetched before the page asks
    ['/api/ping','/api/stats','/api/wind','/api/forecast','/api/history?hours=24','/api/sun?hours=24','/api/raintest?lite=1',
     '/api/settings','/api/hourly','/api/raincheck','/api/tfcompare?hours=24','/api/history?hours=168','/api/sun?hours=168',
     '/api/records','/api/backtest','/api/raintest']
      .forEach(u=>getFile(snapName(u)).catch(()=>{}));
  }

  /* ---- choosing the source ---- */
  function setMode(m){
    if(S.mode===m)return;
    const was=S.mode;S.mode=m;bar();
    if(m==='online')getManifest().then(preload).catch(()=>{});
    if(was!=='starting')dispatchEvent(new CustomEvent('stationmode',{detail:{mode:m,was}}));
  }
  async function decide(){
    if(token()&&!S.man)getManifest().catch(()=>{});        // start reading the online copy at once, in case it's needed
    if(!forced()&&await probeLive())return setMode('live');
    setMode(token()?'online':'none');
  }
  const ready=onMac?Promise.resolve():decide();
  async function recheck(){                              // on the online copy (not forced): back to live as soon as home is reachable
    if(document.hidden||onMac||forced()||S.mode==='live')return;
    if(await probeLive())setMode('live');
    else if(S.mode==='online')getManifest().catch(()=>{});
  }
  if(!onMac){
    setInterval(recheck,RECHECK_MS);
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)recheck()});
    addEventListener('online',recheck);
  }

  window.fetch=function(input,opt){
    const url=typeof input==='string'?input:(input&&input.url)||'';
    if(onMac||url.indexOf('/api/')!==0)return realFetch(input,opt);
    opt=opt||{};
    return ready.then(()=>S.mode==='live'?liveFetch(url,opt):S.mode==='online'?onlineFetch(url,opt):noSource());
  };

  /* ---- the notice at the top (online copy or no source only) ---- */
  let barEl=null;
  function bar(){
    if(!document.body){document.addEventListener('DOMContentLoaded',bar,{once:true});return}
    if(!barEl){
      barEl=document.createElement('button');barEl.type='button';barEl.id='stnbar';
      barEl.dataset.hint='Data source: live from the Mac mini or the online copy (tap for settings)';
      barEl.onclick=()=>openPanel();document.body.appendChild(barEl);
    }
    const show=S.mode==='online'||S.mode==='none';
    barEl.className=S.mode==='none'?'none':'';barEl.hidden=!show;
    if(S.mode==='online')barEl.innerHTML='<b>Online copy</b><span>updated '+esc(pushedAgo())+'</span><span>'+(forced()?'forced in Settings':'Mac mini not reachable')+'</span><span>read-only</span>';
    else if(S.mode==='none')barEl.innerHTML='<b>No data source</b><span>tap to set up the Mac mini address or the GitHub token</span>';
    document.documentElement.classList.toggle('stn-on',show);
    if(window.stnSat)window.stnSat();
    const sl=document.getElementById('srcbtn');
    if(sl)sl.textContent=S.mode==='live'?(onMac?'Mac mini page':'Live from the Mac mini'):S.mode==='online'?'Online copy':'No data source';
    document.querySelectorAll('.stnp').forEach(fillPanel);
  }
  setInterval(()=>{if(S.mode==='online'&&!document.hidden)bar()},30000);

  /* ---- Data source panel: in Settings, and as its own floating window from the notice ---- */
  function panelHTML(){
    if(onMac)return '<div class="panel stnp"><h3>Data source</h3><div class="note" style="display:block;margin-top:0">This copy of the page is the one served by the Mac mini, so it always reads it live. The one Station app (Home Screen) switches between live and the online copy by itself.</div></div>';
    return '<div class="panel stnp"><h3>Data source</h3>'+
      '<div class="stns"></div>'+
      '<label class="stnt"><span><b>Always use the online copy</b><small>Even at home. The online copy updates every 15 minutes and is read-only.</small></span>'+
        '<button type="button" class="stnsw" role="switch" data-hint="Turn on to use the online copy even when the Mac mini is reachable"><i></i></button></label>'+
      '<div class="stnf"><label>Mac mini address</label><div class="set"><input class="stna" type="text" inputmode="decimal" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="192.168.x.x">'+
        '<button type="button" class="stnas" data-hint="Save the Mac mini address on this device and check it">Save</button></div></div>'+
      '<div class="stnf"><label>GitHub token (read-only, Logs only)</label><div class="set"><input class="stnk" type="password" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="github_pat_…">'+
        '<button type="button" class="stnks" data-hint="Save the token on this device and check it">Save</button>'+
        '<button type="button" class="alt stnkv" data-hint="Show or hide the token">Show</button>'+
        '<button type="button" class="alt stnkc" data-hint="Copy the saved token to the clipboard">Copy token</button>'+
        '<button type="button" class="alt dng stnkr" data-hint="Remove the token from this device (asks first)">Remove token</button></div></div>'+
      '<div class="stnm"></div>'+
      '<div class="note" style="display:block">The address and token are kept only in this browser on this device, never in the app’s code or on GitHub. Station app '+APP_V+' · needs Station server '+SRV_NEED+' or newer.</div></div>';
  }
  function fillPanel(p){
    const st=p.querySelector('.stns');if(!st)return;
    const c=S.mode==='live'?'g':S.mode==='online'?'a':S.mode==='none'?'r':'w';
    st.innerHTML='<span class="dot '+c+'"></span>'+(S.mode==='live'?'<b>Live from the Mac mini</b><span>'+esc(addr())+(S.liveV?' · server '+esc(S.liveV):'')+'</span>':
      S.mode==='online'?'<b>Online copy</b><span>updated '+esc(pushedAgo())+(forced()?' · forced by the switch below':' · the Mac mini isn’t reachable from here')+'</span>':
      S.mode==='none'?'<b>No data source</b><span>Enter the Mac mini address (home) and the GitHub token (anywhere)</span>':'<b>Checking…</b><span></span>');
    const sw=p.querySelector('.stnsw');sw.classList.toggle('on',forced());sw.setAttribute('aria-checked',forced()?'true':'false');
  }
  function bindPanel(root){
    const p=root.querySelector('.stnp');if(!p||onMac)return;
    const a=p.querySelector('.stna'),k=p.querySelector('.stnk'),m=p.querySelector('.stnm'),v=p.querySelector('.stnkv');
    const say=(t,col)=>{m.textContent=t;m.style.color=col||''};
    a.value=addr();k.value=token();fillPanel(p);
    const again=async t=>{say(t+' Checking…');await decide();bar();say(t+' '+(S.mode==='live'?'Now live from the Mac mini.':S.mode==='online'?'Now on the online copy.':'Still no data source.'),S.mode==='none'?'var(--c6)':'var(--c4)')};
    p.querySelector('.stnsw').onclick=()=>{forced()?ls.del(K_FORCE):ls.set(K_FORCE,'1');fillPanel(p);again(forced()?'Online copy forced.':'Back to automatic.')};
    p.querySelector('.stnas').onclick=()=>{
      const x=a.value.trim().replace(/^https?:\/\//,'').replace(/[:/].*$/,'');
      if(x&&!/^[A-Za-z0-9.-]+$/.test(x))return say('That address doesn’t look right (like 192.168.x.x).','var(--c6)');
      if(!(x?ls.set(K_ADDR,x):(ls.del(K_ADDR),true)))return say('This browser blocked saving (private mode?).','var(--c6)');
      a.value=x;again('Address saved.');
    };
    p.querySelector('.stnks').onclick=()=>{
      const t=k.value.trim();if(!t)return say('Paste the token first.','var(--c6)');
      if(!ls.set(K_TOK,t))return say('This browser blocked saving (private mode?).','var(--c6)');
      S.man=null;S.cache.clear();again('Token saved.');
    };
    v.onclick=()=>{const h=k.type==='password';k.type=h?'text':'password';v.textContent=h?'Hide':'Show'};
    p.querySelector('.stnkc').onclick=async()=>{
      const t=token();if(!t)return say('No saved token to copy.','var(--c6)');
      try{await navigator.clipboard.writeText(t);say('Token copied.','var(--c4)')}
      catch(e){k.type='text';k.value=t;k.select();v.textContent='Hide';say('Copy was blocked: the token is selected, copy it by hand.','var(--acc)')}
    };
    p.querySelector('.stnkr').onclick=()=>{
      if(!token())return say('No saved token to remove.','var(--c6)');
      if(!confirm('Remove the GitHub token from this device? Station then can’t show the online copy away from home.'))return;
      ls.del(K_TOK);ls.del(K_OLD);k.value='';S.man=null;S.cache.clear();again('Token removed.');
    };
  }
  let ov=null;
  function openPanel(){
    if(!ov){
      ov=document.createElement('div');ov.id='stnsrc';ov.setAttribute('role','dialog');ov.setAttribute('aria-modal','true');ov.setAttribute('aria-label','Data source');
      ov.innerHTML='<div class="sheet"><div class="fhead"><h2>Data source</h2><button class="xbtn" type="button" data-hint="Close">Done</button></div><div class="stnb"></div></div>';
      ov.addEventListener('click',e=>{if(e.target===ov)ov.classList.remove('open')});
      ov.querySelector('.xbtn').onclick=()=>ov.classList.remove('open');
      document.body.appendChild(ov);
    }
    const fb=document.getElementById('fsetbody');if(fb){const q=fb.querySelector('.stnp');if(q)q.remove()}   // one panel at a time
    ov.querySelector('.stnb').innerHTML=panelHTML();bindPanel(ov);ov.classList.add('open');
  }
  addEventListener('keydown',e=>{if(e.key==='Escape'&&ov)ov.classList.remove('open')});
  document.addEventListener('click',e=>{if(e.target.closest&&e.target.closest('#srcbtn'))openPanel()});

  window.STN={APP_V,SRV_NEED,vnum,ready,get mode(){return S.mode},pushedAgo,panelHTML,
    bindPanel:root=>{if(ov){const q=ov.querySelector('.stnp');if(q){ov.classList.remove('open');q.remove()}}bindPanel(root)},
    openPanel,barH:()=>barEl&&!barEl.hidden?barEl.offsetHeight-(parseFloat(getComputedStyle(barEl).paddingTop)||0):0,snapName};
  bar();
})();

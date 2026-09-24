"""Local dashboard: freshness of every data source, with refresh buttons.

Run with: uv run python -m mcp_boilerplate.dashboard
"""

import asyncio
import hmac
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from .config import env
from .config.settings import settings
from .crawler import Crawler
from .sources import SOURCES
from .status import get_status

# One crawl at a time: they share the SQLite file and the paid API quotas.
_crawl_lock = asyncio.Lock()
LOCAL_HOSTS = ["127.0.0.1", "localhost"]
EXTRA_HOSTS = [h for h in os.environ.get("DASHBOARD_ALLOWED_HOSTS", "").split(",") if h]


def _authorized(request: Request) -> bool:
    """Only accept writes sent by this page's own script.

    A custom header cannot be sent cross-site without a CORS preflight, which this server never
    grants, so other websites open in the browser cannot trigger writes (CSRF).
    """
    token = request.headers.get("x-dashboard-token")
    if token is None:
        return False
    expected = os.environ.get("DASHBOARD_TOKEN")
    return True if not expected else hmac.compare_digest(token, expected)


async def status(request: Request) -> JSONResponse:
    data = get_status()
    data["can_refresh"] = bool(settings.crawlora_api_key and settings.openai_api_key)
    data["keys"] = {
        "CRAWLORA_API_KEY": env.describe(settings.crawlora_api_key),
        "OPENAI_API_KEY": env.describe(settings.openai_api_key),
    }
    data["needs_token"] = bool(os.environ.get("DASHBOARD_TOKEN"))
    return JSONResponse(data)


async def save_settings(request: Request) -> JSONResponse:
    if not _authorized(request):
        return JSONResponse({"error": "Invalid dashboard token"}, status_code=401)
    try:
        body = await request.json()
        updates = {k: v.strip() for k, v in body.items() if isinstance(v, str) and v.strip()}
        if not updates:
            return JSONResponse({"error": "Enter at least one key"}, status_code=400)
        env.save_env(updates)
    except (ValueError, AttributeError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    # Apply now so Refresh works without restarting the dashboard.
    for name, value in updates.items():
        os.environ[name] = value
        setattr(settings, name.lower(), value)
    return JSONResponse({"saved": sorted(updates)})


async def refresh(request: Request) -> JSONResponse:
    if not _authorized(request):
        return JSONResponse({"error": "Invalid dashboard token"}, status_code=401)
    if not (settings.crawlora_api_key and settings.openai_api_key):
        return JSONResponse(
            {"error": "CRAWLORA_API_KEY and OPENAI_API_KEY must be set"}, status_code=400
        )
    level = request.path_params["level"]
    source = request.path_params["source"]
    if level not in SOURCES or (source != "all" and source not in SOURCES[level]):
        return JSONResponse({"error": "Unknown approved source"}, status_code=404)
    if _crawl_lock.locked():
        return JSONResponse({"error": "Another refresh is already running"}, status_code=409)
    async with _crawl_lock:
        try:
            result = await Crawler().crawl(level, source)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=502)
    return JSONResponse(result)


async def index(request: Request) -> HTMLResponse:
    return HTMLResponse(_page("Data sources", "/settings", "Settings", GEAR, MAIN_BODY, MAIN_JS))


async def settings_page(request: Request) -> HTMLResponse:
    return HTMLResponse(_page("Settings", "/", "Back to data sources", HOME, SETTINGS_BODY, SETTINGS_JS))


def _page(title: str, href: str, label: str, icon: str, body: str, script: str) -> str:
    return (
        SHELL.replace("__TITLE__", title).replace("__HREF__", href).replace("__LABEL__", label)
        .replace("__ICON__", icon).replace("__BODY__", body).replace("__SCRIPT__", script)
    )


GEAR = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>'
HOME = '<svg viewBox="0 0 24 24"><path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/></svg>'

SHELL = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>__TITLE__</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--navy:#001155;--sky:#49A6E9;--red:#DD0B1A;--maroon:#440909;
--bg:#f2f6fc;--card:#fff;--fg:#001155;--mut:#4d5a8f;--line:#dbe4f3;--accent:#001155;
--ok:#0a6b45;--okbg:#dcf3e8;--warn:#7a4f00;--warnbg:#fff0cc;--bad:#DD0B1A;--badbg:#fde2e4}
@media(prefers-color-scheme:dark){:root{--bg:#000a33;--card:#001155;--fg:#eaf3ff;--mut:#9db8e0;--line:#1c2f7a;--accent:#49A6E9;
--ok:#6fe3ad;--okbg:#0b3a34;--warn:#ffd27a;--warnbg:#3a2c08;--bad:#ff8087;--badbg:#440909}}
*{box-sizing:border-box}
html{scrollbar-gutter:stable}
body{font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--fg);margin:0}
header{background:var(--card);border-bottom:3px solid var(--sky);padding:12px max(24px,calc((100% - 1200px)/2 + 24px));display:flex;align-items:center;gap:16px}
header .logo{background:#fff;border-radius:10px;padding:4px 10px;display:flex}
header img{height:72px;width:auto;display:block}
h1{font-size:20px;margin:0;font-weight:700}
header .tag{color:var(--mut);font-size:13px}
header .titles{flex:1}
.icon{display:flex;align-items:center;justify-content:center;width:40px;height:40px;border-radius:50%;color:var(--accent);border:1.5px solid var(--line)}
.icon:hover{background:var(--accent);color:var(--card);text-decoration:none}
.icon svg{width:22px;height:22px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.back{display:inline-block;margin-bottom:14px}
main{max-width:1200px;margin:0 auto;padding:20px 24px}
.bar{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;margin-bottom:14px}
.sub{color:var(--mut);font-size:13px}
.pills{display:flex;gap:8px;flex-wrap:wrap}
.pill{border-radius:999px;padding:2px 10px;font-weight:600;font-size:12px}
.pill.fresh{background:var(--okbg);color:var(--ok)}.pill.stale{background:var(--warnbg);color:var(--warn)}
.pill.failed,.pill.missing{background:var(--badbg);color:var(--bad)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut);background:rgba(127,140,200,.08)}
th,td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:0}
a{color:var(--accent);font-weight:600;text-decoration:none}a:hover{text-decoration:underline}
td .sub{margin:0}
.err{color:var(--bad);font-size:12px;max-width:340px;word-break:break-word}
button{font:inherit;font-weight:600;padding:5px 14px;border-radius:999px;border:1.5px solid var(--accent);
background:transparent;color:var(--accent);cursor:pointer}
button:hover:not(:disabled){background:var(--accent);color:var(--card)}
button:disabled{opacity:.45;cursor:not-allowed}
.all button{background:var(--red);border-color:var(--red);color:#fff}.all button:hover:not(:disabled){background:var(--maroon);border-color:var(--maroon);color:#fff}
.settings{padding:16px 20px}
.settings h2{font-size:15px;margin:0 0 2px}
.field{display:grid;grid-template-columns:minmax(180px,1fr) 3fr;gap:6px 16px;align-items:center;margin-top:12px}
.field label{font-weight:600}.field .sub{display:block;font-weight:400}
input{font:inherit;padding:7px 10px;border-radius:8px;border:1.5px solid var(--line);background:var(--bg);color:var(--fg);width:100%}
input:focus{outline:2px solid var(--sky);border-color:var(--sky)}
.help{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;padding:0;margin-left:8px;
border-radius:50%;font-size:12px;line-height:1;vertical-align:middle}
.tip{grid-column:1/-1;background:rgba(127,140,200,.12);border-left:3px solid var(--sky);border-radius:6px;padding:10px 14px;font-size:13px}
.tip[hidden]{display:none}.tip ol{margin:6px 0 0;padding-left:20px}.tip p{margin:0}
.msg{margin-top:10px;font-size:13px}.msg.ok{color:var(--ok)}.msg.bad{color:var(--bad)}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;background:var(--bad)}.dot.on{background:var(--ok)}
@media(max-width:640px){.field{grid-template-columns:1fr}}
@media(max-width:640px){header{padding-left:16px;padding-right:16px}main{padding-left:16px;padding-right:16px}h1{font-size:17px}}
</style></head><body>
<header>
<span class="logo"><img src="/static/logo.png" alt="Swisscom Smurf Team MCP Server"></span>
<div class="titles"><h1>Swisscom Smurf Team - MCP Server</h1><div class="tag">Data sources behind the tools</div></div>
<a class="icon" href="__HREF__" title="__LABEL__" aria-label="__LABEL__">__ICON__</a>
</header>
<main>
__BODY__
</main>
<script>
let token=sessionStorage.getItem('tok')||'';
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const when=t=>t?new Date(t).toLocaleString():'';
function askToken(){if(!token){token=prompt('Dashboard token')||'';sessionStorage.setItem('tok',token);}}
__SCRIPT__
</script></body></html>
"""

MAIN_BODY = """<div class="bar">
<div><div class="pills" id="pills"></div><div class="sub" id="sub">Loading...</div></div>
<div class="all sub">Refresh all: <button data-l="federal">Federal</button>
<button data-l="cantonal">Cantonal</button> <button data-l="municipal">Municipal</button></div>
</div>
<div class="card">
<div class="wrap"><table><thead><tr><th>Level</th><th>Source</th><th>State</th><th>Last refresh</th>
<th>Age</th><th>Passages</th><th>Last failure</th><th></th></tr></thead><tbody id="rows"></tbody></table></div>
</div>"""

MAIN_JS = """let can=false,needsToken=false;
async function load(){
  const d=await (await fetch('/api/status')).json();
  can=d.can_refresh;needsToken=d.needs_token;
  document.getElementById('sub').innerHTML=
    'Updated '+esc(when(d.generated_at))+' - stale after '+d.stale_after_days+' days'+
    (can?'':' - refresh disabled: <a href="/settings">add your API keys in Settings</a>');
  document.querySelectorAll('.all button').forEach(b=>b.disabled=!can);
  const n={};d.sources.forEach(x=>n[x.state]=(n[x.state]||0)+1);
  document.getElementById('pills').innerHTML=['fresh','stale','failed','missing'].filter(k=>n[k]).map(k=>'<span class="pill '+k+'">'+n[k]+' '+k+'</span>').join('');
  document.getElementById('rows').innerHTML=d.sources.map(s=>'<tr>'+
    '<td>'+esc(s.level)+'</td>'+
    '<td>'+(s.url?'<a href="'+esc(s.url)+'" target="_blank" rel="noopener">'+esc(s.source)+'</a>':esc(s.source))+
      '<div class="sub">'+esc(s.authority)+'</div></td>'+
    '<td><span class="pill '+s.state+'">'+s.state+'</span></td>'+
    '<td>'+(when(s.last_refresh)||'never')+'</td>'+
    '<td>'+(s.age_days==null?'-':s.age_days+' d')+'</td><td>'+s.passages+'</td>'+
    '<td>'+when(s.last_failure)+'<div class="err">'+esc(s.error)+'</div></td>'+
    '<td>'+(s.refreshable?'<button data-l="'+esc(s.level)+'" data-s="'+esc(s.source)+'"'+(can?'':' disabled')+'>Refresh</button>':'')+'</td></tr>').join('');
}
async function refresh(btn){
  const l=btn.dataset.l,s=btn.dataset.s||'all';
  if(needsToken)askToken();
  const old=btn.textContent;btn.disabled=true;btn.textContent='Refreshing...';
  try{
    const r=await fetch('/api/refresh/'+l+'/'+s,{method:'POST',headers:{'x-dashboard-token':token}});
    if(!r.ok){alert((await r.json()).error||r.statusText);}
  }finally{btn.textContent=old;btn.disabled=false;await load();}
}
document.addEventListener('click',e=>{const b=e.target.closest('button[data-l]');if(b&&!b.disabled)refresh(b);});
load();"""

SETTINGS_BODY = """<div class="card settings">
<h2>API keys</h2>
<div class="sub">Saved to this project's git-ignored <code>.env</code> and never shown again. Leave a field empty to keep its current value.</div>
<form id="settings" autocomplete="off">
<div class="field"><label for="k1">Crawlora API key<button type="button" class="help" data-tip="t1" aria-expanded="false" aria-label="How to get a Crawlora API key">?</button><span class="sub" id="s1"></span></label>
<input id="k1" type="password" name="CRAWLORA_API_KEY" placeholder="Paste key" autocomplete="off">
<div class="tip" id="t1" hidden>
<p><b>Free.</b> Crawlora fetches the official Swiss pages for the Refresh buttons. Its free plan gives 2,000 credits a month, no card needed.</p>
<ol><li>Go to <a href="https://crawlora.net" target="_blank" rel="noopener">crawlora.net</a> and create a free account.</li>
<li>Open your dashboard and copy your API key.</li>
<li>Paste it here and press Save.</li></ol></div></div>
<div class="field"><label for="k2">OpenAI API key<button type="button" class="help" data-tip="t2" aria-expanded="false" aria-label="How to get an OpenAI API key">?</button><span class="sub" id="s2"></span></label>
<input id="k2" type="password" name="OPENAI_API_KEY" placeholder="Paste key" autocomplete="off">
<div class="tip" id="t2" hidden>
<p><b>Not free, but very cheap.</b> OpenAI has no free API plan; you add a few dollars of prepaid credit. The key powers semantic search (embeddings), which costs a tiny fraction of a cent per query. It is also needed to refresh sources. Without it, search still works with keyword matching.</p>
<ol><li>Sign in at <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">platform.openai.com/api-keys</a>.</li>
<li>Add credit under Billing if your account has none.</li>
<li>Click "Create new secret key", copy it (it is shown only once), paste it here and press Save.</li></ol></div></div>
<div class="field"><span></span><span><button type="submit">Save keys</button></span></div>
<div class="msg" id="smsg"></div>
</form></div>"""

SETTINGS_JS = """let needsToken=false;
async function load(){
  const d=await (await fetch('/api/status')).json();
  needsToken=d.needs_token;
  [['CRAWLORA_API_KEY','s1'],['OPENAI_API_KEY','s2']].forEach(([k,id])=>{
    const v=d.keys[k];
    document.getElementById(id).innerHTML='<span class="dot'+(v.set?' on':'')+'"></span>'+(v.set?'set'+(v.hint?' ('+esc(v.hint)+')':''):'not set');
  });
}
document.addEventListener('click',e=>{
  const b=e.target.closest('.help');if(!b)return;
  const t=document.getElementById(b.dataset.tip),open=t.hidden;
  t.hidden=!open;b.setAttribute('aria-expanded',String(open));
});
document.getElementById('settings').addEventListener('submit',async e=>{
  e.preventDefault();
  const body={},msg=document.getElementById('smsg');
  new FormData(e.target).forEach((v,k)=>{if(v.trim())body[k]=v.trim();});
  if(needsToken)askToken();
  const r=await fetch('/api/settings',{method:'POST',headers:{'content-type':'application/json','x-dashboard-token':token},body:JSON.stringify(body)});
  const d=await r.json();
  msg.className='msg '+(r.ok?'ok':'bad');
  msg.textContent=r.ok?'Saved. Refresh is active now. Restart your harness so the MCP server picks up the new keys.':(d.error||r.statusText);
  if(r.ok){e.target.reset();await load();}
});
load();"""


app = Starlette(
    routes=[
        Route("/", index),
        Route("/settings", settings_page),
        Route("/api/status", status),
        Route("/api/settings", save_settings, methods=["POST"]),
        Route("/api/refresh/{level}/{source}", refresh, methods=["POST"]),
        Mount("/static", StaticFiles(directory=Path(__file__).with_name("static")), name="static"),
    ],
    # Rejects requests whose Host header is not local, which blocks DNS-rebinding attacks.
    middleware=[Middleware(TrustedHostMiddleware, allowed_hosts=LOCAL_HOSTS + EXTRA_HOSTS)],
)


def ensure_running() -> str:
    """Start the dashboard in the background if it is not already listening; return its URL."""
    port = int(os.environ.get("DASHBOARD_PORT", "8765"))
    url = f"http://127.0.0.1:{port}"

    def listening() -> bool:
        with socket.socket() as probe:
            probe.settimeout(0.3)
            return probe.connect_ex(("127.0.0.1", port)) == 0

    if not listening():
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.Popen(
            [sys.executable, "-m", "mcp_boilerplate.dashboard"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags, start_new_session=sys.platform != "win32",
        )
        for _ in range(30):
            if listening():
                break
            time.sleep(0.2)
        else:
            raise RuntimeError(f"Dashboard did not start on port {port}")
    return url


def main() -> None:
    host = os.environ.get("DASHBOARD_HOST", "127.0.0.1")
    if host not in ("127.0.0.1", "localhost") and not os.environ.get("DASHBOARD_TOKEN"):
        raise SystemExit("Set DASHBOARD_TOKEN before binding the dashboard to a non-local host")
    uvicorn.run(app, host=host, port=int(os.environ.get("DASHBOARD_PORT", "8765")))


if __name__ == "__main__":
    main()

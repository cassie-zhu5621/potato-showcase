"""
sidekick_page.py -- the tablet beside the robot, in the sidekick mode.

  http://<laptop>:8000/        open this on the iPad, full screen

What it shows, top to bottom:
  * the robot's face, big -- the same typographic face the CoreS3 wears, so a
    visitor who looks from one to the other sees the same thing twice
  * one line in the robot's voice: what it is doing with you right now
  * its notebook: the things people showed it, and the stories of who took what
    it was guarding, newest first

The tablet is a display. Nothing on it is a button: the robot is touched, not
the screen (docs/SHOWCASE_1108_PLAN.md).

One writer: the conductor calls publish()/add_card() from its loop thread; the
HTTP thread only reads, under a lock.
"""
from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_LOCK = threading.Lock()
_STATE = {"face": "-_-", "caption": "", "phase": "DOZE", "cards": [], "t": 0.0}
_DIR = {"images": "."}
MAX_CARDS = 12

PAGE = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>sidekick</title><style>
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:#141414;color:#f2f0ea;
 font-family:-apple-system,"SF Pro Text",Helvetica,Arial,sans-serif;overflow:hidden;
 user-select:none}
#top{height:42vh;display:flex;flex-direction:column;align-items:center;
 justify-content:center;gap:2vh}
#face{font:700 clamp(64px,14vw,190px) ui-monospace,Menlo,monospace;color:#cfe33a;
 transition:transform .25s}
#face.doze{color:#4a4a44;animation:breathe 4.2s ease-in-out infinite}
@keyframes breathe{0%,100%{opacity:.55}50%{opacity:1}}
#face.pop{transform:scale(1.08)}
#cap{font-size:clamp(20px,3vw,38px);color:#cfcabd;min-height:1.4em;text-align:center;
 padding:0 4vw}
#hint{font-size:clamp(15px,1.8vw,22px);color:#7d796f;text-align:center}
#wall{height:58vh;overflow:hidden;display:grid;grid-template-columns:repeat(3,1fr);
 gap:14px;padding:0 22px 22px}
.card{background:#1e1e1b;border-radius:16px;overflow:hidden;display:flex;
 flex-direction:column;animation:in .5s ease-out}
@keyframes in{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
.card img{width:100%;height:20vh;object-fit:cover;background:#000;display:block}
.card.taken img{object-fit:contain}
.card .t{padding:10px 14px 4px;font-weight:700;font-size:clamp(14px,1.6vw,20px)}
.card .l{padding:0 14px 12px;color:#bdb8aa;font-size:clamp(13px,1.4vw,18px);line-height:1.35}
.card.taken{grid-column:span 3}
.card.taken img{height:24vh}
.tag{display:inline-block;font-size:.75em;padding:2px 8px;border-radius:10px;
 margin-right:8px;background:#cfe33a;color:#141414;font-weight:700}
.taken .tag{background:#ff6b8b}
</style></head><body>
<div id=top><div id=face class=doze>-_-</div><div id=cap></div>
<div id=hint>Show it something &middot; Put it down for it to guard &middot; Touch its head</div></div>
<div id=wall></div>
<script>
let last="", shown="";
function esc(s){return String(s||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
async function poll(){
 try{
  const s=await (await fetch("/state",{cache:"no-store"})).json();
  const f=document.getElementById("face");
  if(f.textContent!==s.face){f.textContent=s.face;f.classList.add("pop");
    setTimeout(()=>f.classList.remove("pop"),250)}
  f.classList.toggle("doze",s.phase==="DOZE");
  document.getElementById("cap").textContent=s.caption||"";
  const key=s.cards.map(c=>c.id+":"+(c.line||"")).join("|");
  if(key!==shown){shown=key;
   document.getElementById("wall").innerHTML=s.cards.map(c=>
    `<div class="card ${c.kind}"><img src="/img/${encodeURIComponent(c.img)}">`+
    `<div class=t><span class=tag>${c.kind==="taken"?"who took it":(c.kind==="guard"?"guarding":"you showed me")}</span>${esc(c.label)}</div>`+
    `<div class=l>${esc(c.line)}</div></div>`).join("")}
 }catch(e){}
 setTimeout(poll,400)}
poll();
</script></body></html>"""


class _H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        if self.path.startswith("/state"):
            with _LOCK:
                body = json.dumps(_STATE).encode()
            return self._send(200, body, "application/json")
        if self.path.startswith("/img/"):
            name = os.path.basename(self.path[5:].split("?")[0])
            from urllib.parse import unquote
            p = os.path.join(_DIR["images"], unquote(name))
            if os.path.isfile(p):
                with open(p, "rb") as fh:
                    return self._send(200, fh.read(), "image/jpeg")
        self._send(404, b"", "text/plain")


def serve(images_dir, port=8000):
    _DIR["images"] = images_dir
    srv = ThreadingHTTPServer(("0.0.0.0", port), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def publish(face, caption, phase):
    with _LOCK:
        _STATE.update(face=face, caption=caption, phase=phase, t=time.time())


def add_card(card_id, kind, label, img, line=""):
    with _LOCK:
        _STATE["cards"].insert(0, dict(id=card_id, kind=kind, label=label,
                                       img=img, line=line))
        del _STATE["cards"][MAX_CARDS:]


def set_line(card_id, line):
    with _LOCK:
        for c in _STATE["cards"]:
            if c["id"] == card_id:
                c["line"] = line


def snapshot():
    with _LOCK:
        return json.loads(json.dumps(_STATE))

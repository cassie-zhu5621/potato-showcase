"""
booth_page.py -- the 11.24 booth's web UI: the operator's screen.

  http://localhost:8000/        on the booth laptop, full screen (or any device
                                on the same network: http://<laptop IP>:8000/)

  ┌──────────────────────────────────────────┬──────────┐
  │  Looking for: a blue water bottle         │          │
  ├──────────────────────────────────────────┤   NEXT   │
  │                                          │          │
  │      live camera, with what it sees      │──────────│
  │                                          │ ToF 0.8 m│
  └──────────────────────────────────────────┴──────────┘

NEXT = the next visitor (asleep, owner and object forgotten). The ToF box sets
how close someone must come, in front of it, for the sleeping robot to stir.

Same publishing API as webui/sidekick_page.py (publish / add_card / set_line /
snapshot), so sidekick_loop.py can use either; plus set_frame() for the live
picture, set_status() for the line above it, and commands for the buttons.
One writer (the loop thread); HTTP threads only read, under a lock, and push
button presses onto `commands`.
"""
from __future__ import annotations

import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_LOCK = threading.Lock()
_STATE = {"face": "-_- zz", "caption": "", "phase": "SLEEP", "cards": [], "t": 0.0,
          "looking_for": "", "tof_m": 0.8, "tof_on": True, "tof_mm": None}
_FRAME = {"jpg": None, "seq": 0}
commands = deque()                 # "next", "tof:+0.1", "tof:-0.1", "tof:on", "tof:off"
MAX_CARDS = 12
LIVE_FPS = 12

PAGE = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>NoticeBot booth</title><style>
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:#141414;color:#f2f0ea;overflow:hidden;
 font-family:-apple-system,"SF Pro Text",Helvetica,Arial,sans-serif;user-select:none}
#wrap{display:grid;grid-template-rows:auto auto 1fr;height:100vh;gap:1.2vh;padding:1.2vh}
#top{display:flex;align-items:baseline;gap:1.2vw;padding:0 .5vw}
#top .k{font-size:2.6vh;color:#8d897f;white-space:nowrap}
#look{font-size:5.4vh;font-weight:800;color:#cfe33a;white-space:nowrap;overflow:hidden;
 text-overflow:ellipsis}
#look.none{color:#5c5a54;font-weight:600}
#state{margin-left:auto;font:600 2.6vh ui-monospace,Menlo,monospace;color:#8d897f;white-space:nowrap}
#bar{display:flex;align-items:center;gap:1.2vw}
#tof{flex:1;display:flex;align-items:center;gap:1vw;background:#1e1e1b;border-radius:1.2vh;
 padding:.8vh 1.2vw;min-width:0}
#tof .k{font-size:2vh;color:#8d897f;white-space:nowrap}
#tof button{height:5vh;min-width:5vh;border:0;border-radius:.8vh;background:#33332e;color:#f2f0ea;
 font:700 3vh -apple-system,Helvetica,Arial,sans-serif;cursor:pointer}
#tof button:active{background:#4a4a44}
#thr{font:800 3.4vh ui-monospace,Menlo,monospace;white-space:nowrap}
#onoff{font-size:1.8vh!important;padding:0 1vw}
#onoff.off{background:#5a2a2a!important}
#now{font-size:2vh;color:#bdb8aa;white-space:nowrap;min-width:9vw}
#meter{flex:1;height:1.2vh;background:#33332e;border-radius:1vh;position:relative;overflow:hidden;min-width:6vw}
#fill{position:absolute;left:0;top:0;bottom:0;background:#7d796f}
#fill.in{background:#cfe33a}
#mark{position:absolute;top:0;bottom:0;width:.4vh;background:#ff6b8b}
#next{height:7vh;padding:0 3vw;border:0;border-radius:1.2vh;background:#cfe33a;color:#141414;
 font:800 3.6vh -apple-system,Helvetica,Arial,sans-serif;cursor:pointer;white-space:nowrap}
#next:active{transform:scale(.97);background:#e4f56a}
#next small{font-size:1.8vh;font-weight:600;opacity:.7;margin-left:.6vw}
#live{background:#000;border-radius:1.2vh;overflow:hidden;display:flex;align-items:center;
 justify-content:center;min-height:0}
#live img{width:100%;height:100%;object-fit:contain}
</style></head><body><div id=wrap>
<div id=top><span class=k>Looking for</span><span id=look class=none>nothing yet</span>
 <span id=state></span></div>
<div id=bar>
 <div id=tof><span class=k>Stir within</span>
  <button onclick="cmd('tof:-0.1')">&minus;</button><span id=thr>0.8 m</span>
  <button onclick="cmd('tof:+0.1')">+</button>
  <button id=onoff onclick="toggle()">on</button>
  <span id=now>now: &ndash;</span>
  <div id=meter><div id=fill></div><div id=mark></div></div>
 </div>
 <button id=next onclick="cmd('next')">NEXT<small>next visitor</small></button>
</div>
<div id=live><img id=img src="/live.mjpg" alt=""></div>
</div>
<script>
let on=true;
async function cmd(c){try{await fetch("/cmd?c="+encodeURIComponent(c),{method:"POST"})}catch(e){}}
function toggle(){cmd(on?"tof:off":"tof:on")}
async function poll(){
 try{
  const s=await (await fetch("/state",{cache:"no-store"})).json();
  const l=document.getElementById("look");
  l.textContent=s.looking_for||"nothing yet"; l.classList.toggle("none",!s.looking_for);
  document.getElementById("state").textContent=s.phase+"  "+s.face;
  document.getElementById("thr").textContent=s.tof_m.toFixed(1)+" m";
  on=s.tof_on; const b=document.getElementById("onoff");
  b.textContent=on?"on":"off"; b.classList.toggle("off",!on);
  const mm=s.tof_mm, max=2500;
  document.getElementById("now").textContent="now: "+(mm==null?"–":(mm/1000).toFixed(2)+" m");
  const f=document.getElementById("fill");
  f.style.width=(mm==null?0:Math.min(100,mm/max*100))+"%";
  f.classList.toggle("in",mm!=null&&mm<=s.tof_m*1000&&on);
  document.getElementById("mark").style.left=Math.min(100,s.tof_m*1000/max*100)+"%";
 }catch(e){}
 setTimeout(poll,300)}
poll();
// the stream can drop (laptop asleep, server restarted): reconnect
document.getElementById("img").onerror=function(){setTimeout(()=>{this.src="/live.mjpg?"+Date.now()},1000)};
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
                body = json.dumps({k: v for k, v in _STATE.items() if k != "cards"}).encode()
            return self._send(200, body, "application/json")
        if self.path.startswith("/live.mjpg"):
            return self._stream()
        self._send(404, b"", "text/plain")

    def do_POST(self):
        if self.path.startswith("/cmd"):
            from urllib.parse import urlparse, parse_qs
            c = parse_qs(urlparse(self.path).query).get("c", [""])[0]
            if c in ("next", "tof:+0.1", "tof:-0.1", "tof:on", "tof:off"):
                commands.append(c)
                return self._send(200, b"ok", "text/plain")
        self._send(400, b"", "text/plain")

    def _stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        # Each part is CLOSED by the next boundary straight away: a browser
        # shows a part only once that boundary arrives, so a picture that
        # stops changing would otherwise never appear. Re-sent every second
        # anyway, so a page opened on a still robot shows something.
        last, sent = -1, 0.0
        try:
            self.wfile.write(b"--frame\r\n")
            while True:
                with _LOCK:
                    jpg, seq = _FRAME["jpg"], _FRAME["seq"]
                now = time.time()
                if jpg is not None and (seq != last or now - sent > 1.0):
                    last, sent = seq, now
                    self.wfile.write(b"Content-Type: image/jpeg\r\n"
                                     + f"Content-Length: {len(jpg)}\r\n\r\n".encode()
                                     + jpg + b"\r\n--frame\r\n")
                    self.wfile.flush()
                time.sleep(1.0 / LIVE_FPS)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return


def serve(images_dir=None, port=8000):
    srv = ThreadingHTTPServer(("0.0.0.0", port), _H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def set_frame(jpg):
    with _LOCK:
        _FRAME["jpg"] = jpg
        _FRAME["seq"] += 1


def set_status(**kw):
    with _LOCK:
        _STATE.update(kw)


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

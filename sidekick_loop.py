#!/usr/bin/env python3
"""
sidekick_loop.py -- the showcase-1108 booth: a robot that attends WITH you.

  python3 sidekick_loop.py --cam 1 --cores3            # the booth
  python3 sidekick_loop.py --cam 1 --cores3 --mute     # testing beside people
  open http://<this laptop>:8000 on the iPad

What a visitor can do (stage 3, the whole booth):
  come close              it wakes and looks at you
  hold something up       it leans in, curious, and follows it while it is
                          named; then nods: "OK! I'll look out for <it>"
  later, the thing turns  it points at it and calls; the tablet shows what it
  up in its view          spotted. Touch its head: "seen it"
  touch its head          it presses up into your hand
  someone new shows       the new thing replaces the old one
  something else

The paper's full delegation cycle is not in this file. For that demo stop this
and run noticebot_loop.py as in docs/SHOWDAY.md -- two modes that never share a
process cannot leak into each other.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from collections import deque

# MediaPipe's own logging ("Failed to send to clearcut") is noise in this
# terminal; set before mediapipe is imported anywhere.
os.environ.setdefault("GLOG_minloglevel", "2")

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from robot.scs import open_bus                         # noqa: E402
from robot.pose import IDS                             # noqa: E402
from robot.clip_player import ClipPlayer               # noqa: E402
from robot import states as ST                         # noqa: E402
from perception.headcam import HeadCam                 # noqa: E402
from perception import sidekick_sense as SS            # noqa: E402
from session.sidekick_brain import Brain, STAGES, clips_for_stage   # noqa: E402
from webui import sidekick_page as PAGE                # noqa: E402

LINE_SCHEMA = {"type": "object", "properties": {"line": {"type": "string"}},
               "required": ["line"], "additionalProperties": False}

VOICE = ("You are a small desk robot with one camera eye, a curious sidekick. "
         "Write ONE short line (at most 14 words) in your own voice, first "
         "person, warm and a little playful, in plain English. Never guess a "
         "person's name, age, gender or ethnicity; describe what they did and "
         "what they wore if it helps. No emoji. ")

FALLBACK = {
    "watch": "Got it -- I'll look out for {label}.",
    "found": "I spotted {label}!",
}

ID_SCHEMA = {"type": "object",
             "properties": {"showing": {"type": "boolean"},
                            "name": {"type": "string"},
                            "term": {"type": "string"}},
             "required": ["showing", "name", "term"],
             "additionalProperties": False}

ID_PROMPT = (
    "You are the camera eye of a small desk robot. A visitor is holding "
    "something up to you to show you what to look out for. What is it?\n"
    "- showing: true if someone is clearly holding up an object to show you\n"
    "- name: how you would say it, short, with an article and one telling "
    "detail (e.g. 'a blue water bottle', 'a set of keys')\n"
    "- term: the everyday noun an object detector would use for it, 1-3 words, "
    "no colour (e.g. 'water bottle', 'keys', 'cell phone')\n"
    "If nothing is clearly being shown, showing=false and name=term=''.")


def identify(jpeg, guess, offline):
    """-> (name, term) for what is being shown, or (None, None). Offline, the
    detector's own guess is used, so the booth still works without a network."""
    if offline or not jpeg:
        return f"the {guess}", guess
    try:
        from planning.provider import call_json
        out, _ = call_json(ID_PROMPT, ID_SCHEMA, images=[jpeg],
                           labels=["what the visitor is holding up"],
                           model=os.environ.get("NOTICEBOT_SIDEKICK_MODEL",
                                                "gemini-3.8-flash"),
                           max_output_tokens=200)
        term = str(out.get("term", "")).strip().lower()
        name = str(out.get("name", "")).strip()
        if not out.get("showing") or not term:
            return None, None
        return (name or f"the {term}"), term
    except Exception as exc:
        print(f"[identify] {str(exc)[:80]} -- using the detector's guess")
        return f"the {guess}", guess


def robot_line(kind, label, jpegs, offline):
    """One line in the robot's voice. The fallback is used when the model is
    off, slow or wrong; a card is never left waiting on it."""
    fb = FALLBACK[kind].format(label=label)
    if offline or not jpegs:
        return fb
    ask = {
        "watch": (f"A visitor just showed you {label} and asked you to look out "
                  f"for it. Promise them, playfully."),
        "found": (f"You were asked to look out for {label}, and you just spotted "
                  f"it -- this is what you see. Call them over, excited."),
    }[kind]
    try:
        from planning.provider import call_json
        # The booth's lines never wait on anything, so they can always use the
        # newest Flash, whatever .env sets for the paper demo (where speed
        # matters more): NOTICEBOT_SIDEKICK_MODEL, default gemini-3.8-flash.
        out, _ = call_json(VOICE + ask, LINE_SCHEMA, images=jpegs,
                           model=os.environ.get("NOTICEBOT_SIDEKICK_MODEL",
                                                "gemini-3.8-flash"),
                           max_output_tokens=200)
        line = str(out.get("line", "")).strip()
        return line[:140] or fb
    except Exception as exc:
        print(f"[voice] {kind}: {str(exc)[:80]} -- using the fallback line")
        return fb


def crop_jpeg(frame, box, pad=0.25):
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = box
    px, py = (x1 - x0) * pad, (y1 - y0) * pad
    x0, y0 = max(0, int(x0 - px)), max(0, int(y0 - py))
    x1, y1 = min(w, int(x1 + px)), min(h, int(y1 + py))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    ok, jpg = cv2.imencode(".jpg", frame[y0:y1, x0:x1], [cv2.IMWRITE_JPEG_QUALITY, 88])
    return jpg.tobytes() if ok else None


def story_strip(event_frames, t0, t1, n=6, height=260):
    """The event as a row of frames, from the camera's 10 Hz ring buffer."""
    picked = [f for f in list(event_frames) if t0 <= f[0] <= t1]
    if not picked:
        return None, []
    idx = np.linspace(0, len(picked) - 1, min(n, len(picked))).round().astype(int)
    jpegs = [picked[i][1] for i in sorted(set(idx))]
    imgs = []
    for j in jpegs:
        im = cv2.imdecode(np.frombuffer(j, np.uint8), cv2.IMREAD_COLOR)
        s = height / im.shape[0]
        imgs.append(cv2.resize(im, (int(im.shape[1] * s), height)))
    ok, strip = cv2.imencode(".jpg", cv2.hconcat(imgs), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return (strip.tobytes() if ok else None), jpegs


class _Tee:
    def __init__(self, a, b):
        self.a, self.b = a, b

    def write(self, s):
        self.a.write(s)
        try:
            self.b.write(time.strftime("%H:%M:%S ") + s if s.strip() else s)
            self.b.flush()
        except Exception:
            pass

    def flush(self):
        self.a.flush()


def _tee(path):
    old = sys.stdout
    sys.stdout = _Tee(old, open(path, "a", buffering=1))
    return old


FIXED_POSE = {"pan": 0.0, "tilt": 0.0, "nod": 0.0}
VIEW = "sidekick -- what it sees   (t touch  p palm  q quit)"
PHASE_COL = {"SLEEP": (90, 90, 90), "DOZE": (120, 120, 120), "LOOK": (60, 200, 255), "SHOW": (80, 220, 120),
             "GUARD": (255, 160, 60), "CALL": (200, 80, 255)}


def draw_view(frame, pc, people, brain, player, stage, saying=""):
    """The debug window: every person and prop the robot found, as it judged
    them, and what it decided. Nothing here feeds back into the decisions."""
    im = annotate(frame, pc, people, brain, saying)
    h, w = im.shape[:2]
    s = 1100.0 / w
    cv2.imshow(VIEW, cv2.resize(im, (int(w * s), int(h * s))))
    return cv2.waitKey(1) & 0xFF


def annotate(frame, pc, people, brain, saying=""):
    """The picture with what it judged drawn on it (the view window, and the
    1124 web UI's live picture)."""
    im = frame.copy()
    h, w = im.shape[:2]
    for p in people:
        for j in (SS.NOSE, SS.L_SH, SS.R_SH, 15, 16):
            if j in p.pts and p.vis.get(j, 0) >= 0.3:
                cv2.circle(im, tuple(int(v) for v in p.pts[j]), 6, (0, 255, 255), -1)
        if SS.L_SH in p.pts and SS.R_SH in p.pts:
            a, b = p.pts[SS.L_SH], p.pts[SS.R_SH]
            cv2.line(im, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), (0, 255, 255), 2)
    for q in pc.people:
        x, y = int(q.head.x), int(q.head.y)
        tag = "NEAR" if q.near else "passer"
        col = (60, 220, 60) if q.near else (180, 180, 180)
        cv2.putText(im, f"{tag}  shoulders {q.sw_frac:.0%}", (x - 80, max(30, y - 30)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, col, 2)
    for q in pc.props:
        x0, y0, x1, y1 = (int(v) for v in q.box)
        col = (60, 220, 60) if q.held else ((0, 0, 255) if q.hand_near else (0, 220, 255))
        cv2.rectangle(im, (x0, y0), (x1, y1), col, 3)
        cv2.putText(im, f"{q.label} {'HELD' if q.held else ''}"
                        f"{' hand' if q.hand_near and not q.held else ''} "
                        f"{q.area:.1%}", (x0, max(25, y0 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
    if pc.waves:
        cv2.putText(im, "hand up", (w - 190, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                    (60, 230, 255), 2)
    # Header: only what state it is in and its face (stage, clip and caption
    # are in the terminal).
    bar = PHASE_COL.get(brain.phase, (255, 255, 255))
    cv2.rectangle(im, (0, 0), (w, 50), (20, 20, 20), -1)
    cv2.putText(im, f"{brain.phase}  {brain.face}",
                (16, 36), cv2.FONT_HERSHEY_SIMPLEX, 1.0, bar, 2)
    if saying:
        # What it is saying right now, as a subtitle: big, at the bottom.
        words, lines, cur = saying.split(), [], ""
        for wd in words:
            if len(cur) + len(wd) + 1 > 42:
                lines.append(cur)
                cur = wd
            else:
                cur = (cur + " " + wd).strip()
        lines.append(cur)
        y0 = h - 30 - 48 * (len(lines) - 1)
        cv2.rectangle(im, (0, y0 - 46), (w, h), (20, 20, 20), -1)
        for k, ln in enumerate(lines):
            tw = cv2.getTextSize(ln, cv2.FONT_HERSHEY_SIMPLEX, 1.3, 3)[0][0]
            cv2.putText(im, ln, ((w - tw) // 2, y0 + 48 * k),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.3, (60, 230, 255), 3)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=0)
    ap.add_argument("--cores3", nargs="?", const="auto")
    ap.add_argument("--port", default=os.environ.get("NOTICEBOT_PORT"))
    ap.add_argument("--clips", default=os.path.join(ROOT, "motion", "clips"))
    ap.add_argument("--stage", type=int, default=3, choices=sorted(STAGES),
                    help="1 touch only | 2 + sleep/doze, glance, look at you | "
                         "3 + show it something to look out for; it calls when "
                         "that turns up. Each stage needs only its own clips.")
    ap.add_argument("--mute", action="store_true")
    ap.add_argument("--speak", action="store_true",
                    help="also SAY the lines out loud (off: they are only shown, "
                         "under its face, on the tablet and in the view -- the "
                         "acknowledgement is the nod and its 'ack' sound)")
    ap.add_argument("--voice", default="Junior",
                    help="macOS `say` voice the robot speaks with "
                         "(`say -v ?` lists them). Needs firmware v21")
    ap.add_argument("--pitch", type=float, default=1.15,
                    help="raise the voice (needs ffmpeg). Junior at 1.15 was "
                         "chosen for the booth: a small robot, still clear")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--cv-hz", type=float, default=4.0)
    ap.add_argument("--props", default=",".join(SS.PROPS),
                    help="the tray's props, as the detector should be asked")
    ap.add_argument("--web-port", type=int, default=8000)
    ap.add_argument("--feed-dir", default=None,
                    help="where cards and stories are written (default: a new "
                         "session_feed/sidekick_<time>)")
    ap.add_argument("--no-robot", action="store_true",
                    help="laptop only: no servos, no CoreS3. Uses --cam as a FIXED "
                         "camera (the laptop's own is fine) and opens the debug "
                         "view; keys t = touch, p = palm, q = quit. For trying the "
                         "detection, the decisions and the tablet without the robot.")
    ap.add_argument("--view", action="store_true",
                    help="debug window: what the camera sees, the people and props "
                         "it found, and what it decided (on by default with "
                         "--no-robot)")
    ap.add_argument("--booth", choices=("1124", "1108"), default="1124",
                    help="1124 (default): the researcher booth -- only a pat wakes "
                         "it, it follows its owner, web UI with NEXT and the ToF "
                         "setting (docs/SHOWCASE_1124_PLAN.md). 1108: the earlier "
                         "sidekick booth")
    ap.add_argument("--forget", action="store_true",
                    help="start with nothing to look out for: delete the saved "
                         "memory of the last thing shown (session_feed/booth_memory.json)")
    ap.add_argument("--offline", action="store_true",
                    help="no model calls: the robot's lines are the fallbacks")
    a = ap.parse_args()
    if a.no_robot:
        a.view = True
        a.cores3 = None
    props = tuple(p.strip() for p in a.props.split(",") if p.strip())

    stamp = time.strftime("%Y%m%d_%H%M%S")
    feed = a.feed_dir or os.path.join(ROOT, "session_feed", f"sidekick_{stamp}")
    os.makedirs(feed, exist_ok=True)
    # EVERYTHING PRINTED IS ALSO KEPT, in the run's folder: the first question
    # after a run is "why didn't it ...", and the terminal is gone by then.
    _stdout = _tee(os.path.join(feed, "run.log"))
    print(f"[run] cards and stories -> {feed}")

    booth = a.booth == "1124"
    if booth:
        from webui import booth_page
        globals()["PAGE"] = booth_page       # same API, plus the live picture
    # 1124: the ToF distance set on the web UI is kept for the next run.
    settings_path = os.path.join(a.feed_dir or os.path.join(ROOT, "session_feed"),
                                 "booth_settings.json")
    settings = {}
    if booth and os.path.exists(settings_path):
        try:
            with open(settings_path) as fh:
                settings = json.load(fh)
        except Exception:
            settings = {}

    def save_settings():
        try:
            with open(settings_path, "w") as fh:
                json.dump(dict(tof_m=brain.tof_m, tof_on=brain.tof_on), fh)
        except Exception as e:
            print(f"[settings] !! could not save: {e}")

    # THE LAST THING SHOWN OUTLIVES THE RUN: kept beside the run folders, not
    # in one, so a restart (or the next day, unless --forget) carries it on.
    mem_dir = a.feed_dir or os.path.join(ROOT, "session_feed")
    mem_path = os.path.join(mem_dir, "booth_memory.json")
    memory = None
    if a.forget and os.path.exists(mem_path):
        os.remove(mem_path)
        print("[memory] forgotten")
    elif os.path.exists(mem_path) and not booth:
        try:
            with open(mem_path) as fh:
                memory = json.load(fh)
            print(f"[memory] will tell the next visitor about {memory.get('name')!r} "
                  f"(shown {memory.get('shown', '?')}); --forget to clear")
        except Exception as e:
            print(f"[memory] !! could not read {mem_path}: {e}")

    if a.no_robot:
        from robot.fakebus import FakeBus
        bus, port = FakeBus(), None
        print("[run] NO ROBOT: servos simulated, camera fixed")
    else:
        bus, port = open_bus(a.port, 1_000_000)
        missing = [n for n, sid in IDS.items() if not bus.ping(sid)[1]]
        if missing:
            sys.exit(f"no reply from {missing} on {port}")

    link = None
    pending = deque()
    if a.cores3:
        from session.cores3_link import CoreS3Link, find_cores3
        if a.cores3 == "auto":
            a.cores3 = find_cores3(exclude=(port,))
            if not a.cores3:
                sys.exit("no CoreS3 found")
        link = CoreS3Link(a.cores3, on_input=lambda line: pending.append(line))
        if booth:
            # The ToF is only READ: the laptop decides what a distance means
            # (BoothBrain.on_distance). The board's own approach gate held its
            # button down for anyone who stood still -- what used to hang
            # exhibitions -- so it stays off.
            link.claim(dist=True, approach=False, volume=0 if a.mute else 100)
        else:
            link.claim(approach="palm", volume=0 if a.mute else 100)
        link.skface("-_-")

    def on_led(v):
        if link:
            link.led(v)

    def on_sfx(name):
        if link and not a.mute:
            link.sfx(name)

    need = clips_for_stage(a.stage)
    print(f"[stage] {a.stage}: {', '.join(STAGES[a.stage])}  (clips: {', '.join(need)})")
    player = ClipPlayer(bus, a.clips, on_led=on_led, on_sfx=on_sfx, sidekick=need)
    # Stage 1 answers a touch and nothing else, so it needs no camera at all:
    # it can be tried with only SK_PURR exported and nothing else set up.
    cam = det = poses = tracker = faces = None
    if a.stage >= 2 or a.view:
        cam = HeadCam(a.cam)
        print("[cv] loading detector + pose ...")
        from perception.perceive import make_detector
        from perception.relations import PoseEstimator, Tracker
        from perception.gaze import HeadPoseEstimator
        # Asked at the TARGET's lower threshold; sense() holds ordinary props
        # to the higher one (sidekick_sense.PROP_CONF / TARGET_CONF).
        det = make_detector("yoloworld", list(props), conf=min(a.conf, SS.TARGET_CONF))
        poses, tracker = PoseEstimator(max_people=4), Tracker()
        faces = HeadPoseEstimator(max_faces=4)
    PAGE.serve(feed, a.web_port)
    print(f"[web] tablet: http://<this laptop>:{a.web_port}/")

    from session.robot_voice import RobotVoice
    # NOT SPOKEN BY DEFAULT (2026-11-07, after trying it): the line is shown,
    # and SK_ACK's own 'ack' sound -- the falling two-note "got it" that goes
    # with the nod -- is the answer you hear. --speak turns the voice back on.
    voice = RobotVoice(link, voice=a.voice, muted=a.mute or not a.speak,
                       pitch=a.pitch)
    say_until = 0.0
    saying = ""
    events = deque()
    answers = deque()               # (name, term) from the model, any thread
    teach_jpg = {"jpg": None}
    def target_vocab(keep):
        """The detector's words: the usual props, minus any overlapping the
        target's words, plus those."""
        from session.sidekick_brain import same_thing
        v = tuple(w for w in SS.PROPS if not any(same_thing(w, k) for k in keep))
        v += tuple(dict.fromkeys(keep))
        if det is not None and hasattr(det, "set_vocab"):
            det.set_vocab(list(v))
        return v

    if booth:
        from session.booth_brain import BoothBrain, TOF_DEFAULT_M
        brain = BoothBrain(player, on_event=lambda k, **kw: events.append((k, kw)),
                           stage=a.stage, tof_m=settings.get("tof_m", TOF_DEFAULT_M),
                           tof_on=settings.get("tof_on", True))
        print(f"[booth] 1124: pat to wake; ToF stir within {brain.tof_m:.1f} m "
              f"({'on' if brain.tof_on else 'off'}); web UI http://localhost:{a.web_port}/")
    else:
        brain = Brain(player, on_event=lambda k, **kw: events.append((k, kw)),
                      stage=a.stage, memory=memory)

    # NEXT VISITOR, by hand: 'n' in the view window, or n + Enter in the
    # terminal. Back to how it starts; the last thing shown is kept.
    commands = deque()
    if sys.stdin is not None and sys.stdin.isatty():
        def read_stdin():
            for line in sys.stdin:
                commands.append(line.strip().lower())
        threading.Thread(target=read_stdin, daemon=True).start()
    if booth:
        print("[run] NEXT on the web UI (or n in the view window / n + Enter here)")
    else:
        print("[run] keys (view window, or type + Enter here): n = next visitor "
              "(tells them the last object, stops looking for it), f = forget it")
    player.start()
    player.request(brain.rest)

    last_state, last_face = None, None
    last_seen, last_phase = None, None
    period = 1.0 / a.cv_hz
    next_cv = 0.0
    next_live = 0.0
    last_pc, last_people = None, []
    frame = None
    n_card = 0

    def card_async(cid, kind, label, jpegs):
        def run():
            PAGE.set_line(cid, robot_line(kind, label, jpegs, a.offline))
        threading.Thread(target=run, daemon=True).start()

    try:
        while True:
            now = time.time()
            # ---- the board: touches and the palm ----
            while commands:
                cmd = commands.popleft()
                if cmd in ("n", "next"):
                    print("[run] next visitor")
                    brain.next_visitor()
                    props = target_vocab([])
                    say_until = 0.0
                    if link:
                        link.sksay("")
                elif cmd in ("f", "forget"):
                    # Nothing to look out for any more, saved memory included.
                    print("[run] forgot the object")
                    brain.forget()
                    for fn in (mem_path, os.path.join(mem_dir, "booth_memory.jpg")):
                        if os.path.exists(fn):
                            os.remove(fn)
                    props = target_vocab([])
                    say_until = 0.0
                    if link:
                        link.sksay("")
            if booth:
                while PAGE.commands:
                    c = PAGE.commands.popleft()
                    if c == "next":
                        commands.append("n")
                    elif c.startswith("tof:"):
                        v = c[4:]
                        if v in ("on", "off"):
                            brain.set_tof(on=(v == "on"))
                        else:
                            brain.set_tof(metres=brain.tof_m + float(v))
                        print(f"[booth] ToF stir within {brain.tof_m:.1f} m "
                              f"({'on' if brain.tof_on else 'off'})")
                        save_settings()
            while pending:
                line = pending.popleft()
                if line.startswith("IN DIST "):
                    try:
                        mm = int(line.split()[2])
                    except (IndexError, ValueError):
                        continue                 # "IN DIST on" / "off": the ack
                    if hasattr(brain, "on_distance"):
                        brain.on_distance(mm, now)
                    continue
                if "BODYTAP" in line:
                    brain.on_tap()
                elif "PTT_DOWN" in line:
                    brain.on_palm()
            # ---- the camera, only from a still head ----
            if (cam is not None and now >= next_cv
                    and player.settled_ms >= ST.AIM_SAMPLE_SETTLED_MS):
                next_cv = now + period
                # Without the robot the camera does not move with the "head",
                # so every angle is taken from a still camera looking level.
                pose = FIXED_POSE if a.no_robot else player.pose_deg()
                frame = cam.latest.copy()
                h, w = frame.shape[:2]
                people = tracker.assign(poses.estimate(frame), (w, h), now)
                dets = det.detect(frame)
                rays = faces.estimate(frame)
                pc = SS.sense(people, dets, (w, h), pose, now, props, faces=rays,
                              target_words=(brain.target or {}).get("words", ()))
                # One line when what it sees CHANGES, so a run can be read back
                # from the terminal: nobody / passer / NEAR, and its decision.
                seen = ("NEAR" if pc.near else ("passer" if pc.people else "nobody"))
                if seen != last_seen:
                    last_seen = seen
                    n = pc.nearest
                    print(f"[sense] {seen}"
                          + (f" (size {n.sw_frac:.0%}, bearing {n.head.pan:+.0f})" if n else ""))
                last_pc, last_people = pc, people
                if a.stage >= 2:
                    brain.on_percept(pc)
                else:
                    brain.tick()
                if a.view:
                    key = draw_view(frame, pc, people, brain, player, a.stage,
                                    saying=saying if now < say_until else "")
                    if key in (ord("n"), ord("f")):
                        commands.append(chr(key))
                    elif key == ord("t"):
                        brain.on_tap()
                    elif key == ord("p"):
                        brain.on_palm()
                    elif key in (ord("q"), 27):
                        raise KeyboardInterrupt
            else:
                brain.tick()
                if a.view and frame is not None:
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord("n"), ord("f")):
                        commands.append(chr(key))
                    elif key == ord("t"):
                        brain.on_tap()
                    elif key == ord("p"):
                        brain.on_palm()
                    elif key in (ord("q"), 27):
                        raise KeyboardInterrupt
            # ---- 1124: the live picture and the line above it ----
            if booth:
                if (cam is not None and now >= next_live):
                    next_live = now + 1.0 / PAGE.LIVE_FPS
                    im = annotate(cam.latest, last_pc or SS.Percept(t=now, pose={}),
                                  last_people, brain,
                                  saying=saying if now < say_until else "")
                    im = cv2.resize(im, (960, int(960 * im.shape[0] / im.shape[1])))
                    ok, jpg = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 72])
                    if ok:
                        PAGE.set_frame(jpg.tobytes())
                PAGE.set_status(looking_for=(brain.target or {}).get("name", ""),
                                tof_m=brain.tof_m, tof_on=brain.tof_on,
                                tof_mm=brain.tof_last_mm)
            # ---- what the brain asked to be written down ----
            while events:
                kind, kw = events.popleft()
                n_card += 1
                cid = f"{kind}_{n_card}"
                if kind == "say":
                    # Written under its face for as long as it takes to read
                    # (and spoken too, with --speak).
                    voice.say(kw["text"])
                    saying = kw["text"]
                    if link:
                        link.sksay(kw["text"])
                    say_until = now + 7.0
                    continue
                if kind == "identify" and frame is not None:
                    jpg = crop_jpeg(frame, kw["box"], pad=0.6)
                    teach_jpg["jpg"] = jpg

                    def ask(jpg=jpg, guess=kw["guess"]):
                        answers.append(identify(jpg, guess, a.offline))
                    threading.Thread(target=ask, daemon=True).start()
                if kind == "taught" and brain.target and not booth:
                    try:
                        with open(mem_path, "w") as fh:
                            json.dump(dict(term=brain.target["term"],
                                           name=brain.target["name"],
                                           words=brain.target["words"],
                                           shown=time.strftime("%Y-%m-%d %H:%M")),
                                      fh, indent=1)
                        if teach_jpg["jpg"]:
                            with open(os.path.join(mem_dir, "booth_memory.jpg"), "wb") as fh:
                                fh.write(teach_jpg["jpg"])
                    except Exception as e:
                        print(f"[memory] !! could not save: {e}")
                if kind == "taught" and teach_jpg["jpg"]:
                    name = f"{cid}.jpg"
                    open(os.path.join(feed, name), "wb").write(teach_jpg["jpg"])
                    PAGE.add_card(cid, "watch", kw["name"], name,
                                  FALLBACK["watch"].format(label=kw["name"]))
                    card_async(cid, "watch", kw["name"], [teach_jpg["jpg"]])
                elif kind == "found" and frame is not None:
                    jpg = crop_jpeg(frame, kw["box"], pad=0.8)
                    if jpg:
                        name = f"{cid}.jpg"
                        open(os.path.join(feed, name), "wb").write(jpg)
                        PAGE.add_card(cid, "found", kw["name"], name,
                                      FALLBACK["found"].format(label=kw["name"]))
                        card_async(cid, "found", kw["name"], [jpg])
                print(f"[brain] {kind} {kw.get('name') or kw.get('guess') or ''}")
            # ---- the model's answer to "what is this?" ----
            while answers:
                name, term = answers.popleft()
                print(f"[identify] {name!r} -> watching for {term!r}")
                if (term and det is not None and term not in props
                        and hasattr(det, "set_vocab")):
                    # The detector is told the new word; the old target's word
                    # is dropped, so it only ever looks out for one thing. Words
                    # that overlap it are dropped too: asked for both 'bottle'
                    # and 'water bottle', the detector can call the target by
                    # the other one.
                    guess = brain._teach.get("guess") if brain._teach else None
                    props = target_vocab([term] + ([guess] if guess else []))
                brain.on_identified(name, term)
            # ---- face, colour, tablet ----
            if player.state != last_state and player.state:
                last_state = player.state
                if link:
                    link.hue(ST.STATES[last_state]["hue"])
            if brain.face != last_face:
                last_face = brain.face
                if link:
                    link.skface(last_face)
            if say_until and now > say_until:
                say_until = 0.0
                if link:
                    link.sksay("")
            if brain.phase != last_phase:
                last_phase = brain.phase
                print(f"[brain] phase {last_phase}")
            PAGE.publish(brain.face, brain.caption, brain.phase)
            if player.error:
                print(f"[player] !! {player.error}")
                break
            time.sleep(0.02)
    except KeyboardInterrupt:
        print("\n[run] stopping")
    finally:
        try:
            player.request(brain.rest)
            time.sleep(1.0)
        except Exception:
            pass
        player.stop()
        if cam:
            cam.close()
        if link:
            link.rest()
            link.close()
        if poses:
            poses.close()
        if faces:
            faces.close()
        if a.view:
            cv2.destroyAllWindows()
        sys.stdout = _stdout


if __name__ == "__main__":
    main()

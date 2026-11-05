#!/usr/bin/env python3
"""
sidekick_loop.py -- the showcase-1108 booth: a robot that attends WITH you.

  python3 sidekick_loop.py --cam 1 --cores3            # the booth
  python3 sidekick_loop.py --cam 1 --cores3 --mute     # testing beside people
  open http://<this laptop>:8000 on the iPad

What a visitor can do, and nothing else is needed (docs/SHOWCASE_1108_PLAN.md):
  come close            it wakes and looks at you
  hold a prop up        it leans in, curious, and follows it as you move it
  hold it still         it nods, and the tablet notes what you showed it
  put it down, let go   it guards it; a hand near it gets an "I see you";
                        taking it makes it call, and the tablet shows who
  touch its head        it presses up into your hand (or, while guarding,
                        "you're back")

The paper's full delegation cycle is not in this file. For that demo stop this
and run noticebot_loop.py as in docs/SHOWDAY.md -- two modes that never share a
process cannot leak into each other.
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from collections import deque

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
    "shown": "A {label}! I'll remember that one.",
    "guard": "Your {label} is safe with me.",
    "taken": "Someone picked up the {label} I was guarding!",
}


def robot_line(kind, label, jpegs, offline):
    """One line in the robot's voice. The fallback is used when the model is
    off, slow or wrong; a card is never left waiting on it."""
    fb = FALLBACK[kind].format(label=label)
    if offline or not jpegs:
        return fb
    ask = {
        "shown": f"A visitor just showed you a {label}. React to it.",
        "guard": f"You are now guarding a visitor's {label}. Reassure them.",
        "taken": (f"You were guarding a {label} and these frames, in order, show "
                  f"someone taking it. Tell its owner what happened."),
    }[kind]
    try:
        from planning.provider import call_json
        out, _ = call_json(VOICE + ask, LINE_SCHEMA, images=jpegs,
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=0)
    ap.add_argument("--cores3", nargs="?", const="auto")
    ap.add_argument("--port", default=os.environ.get("NOTICEBOT_PORT"))
    ap.add_argument("--clips", default=os.path.join(ROOT, "motion", "clips"))
    ap.add_argument("--stage", type=int, default=4, choices=sorted(STAGES),
                    help="1 touch only | 2 + doze, glance, look at you | "
                         "3 + show it something | 4 + guard it. Each stage "
                         "needs only its own clips exported.")
    ap.add_argument("--mute", action="store_true")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--cv-hz", type=float, default=4.0)
    ap.add_argument("--props", default=",".join(SS.PROPS),
                    help="the tray's props, as the detector should be asked")
    ap.add_argument("--web-port", type=int, default=8000)
    ap.add_argument("--feed-dir", default=None,
                    help="where cards and stories are written (default: a new "
                         "session_feed/sidekick_<time>)")
    ap.add_argument("--offline", action="store_true",
                    help="no model calls: the robot's lines are the fallbacks")
    a = ap.parse_args()
    props = tuple(p.strip() for p in a.props.split(",") if p.strip())

    stamp = time.strftime("%Y%m%d_%H%M%S")
    feed = a.feed_dir or os.path.join(ROOT, "session_feed", f"sidekick_{stamp}")
    os.makedirs(feed, exist_ok=True)
    print(f"[run] cards and stories -> {feed}")

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
    cam = det = poses = tracker = None
    if a.stage >= 2:
        cam = HeadCam(a.cam)
        print("[cv] loading detector + pose ...")
        from perception.perceive import make_detector
        from perception.relations import PoseEstimator, Tracker
        det = make_detector("yoloworld", list(props), conf=a.conf)
        poses, tracker = PoseEstimator(max_people=4), Tracker()
    PAGE.serve(feed, a.web_port)
    print(f"[web] tablet: http://<this laptop>:{a.web_port}/")

    events = deque()
    brain = Brain(player, on_event=lambda k, **kw: events.append((k, kw)),
                  stage=a.stage)
    player.start()
    player.request(brain.rest)

    last_state, last_face = None, None
    period = 1.0 / a.cv_hz
    next_cv = 0.0
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
            while pending:
                line = pending.popleft()
                if "BODYTAP" in line:
                    brain.on_tap()
                elif "PTT_DOWN" in line:
                    brain.on_palm()
            # ---- the camera, only from a still head ----
            if (cam is not None and now >= next_cv
                    and player.settled_ms >= ST.AIM_SAMPLE_SETTLED_MS):
                next_cv = now + period
                pose = player.pose_deg()
                frame = cam.latest.copy()
                h, w = frame.shape[:2]
                people = tracker.assign(poses.estimate(frame), (w, h), now)
                dets = det.detect(frame)
                brain.on_percept(SS.sense(people, dets, (w, h), pose, now, props))
            else:
                brain.tick()
            # ---- what the brain asked to be written down ----
            while events:
                kind, kw = events.popleft()
                n_card += 1
                cid = f"{kind}_{n_card}"
                if kind in ("shown", "guard_start") and frame is not None:
                    jpg = crop_jpeg(frame, kw["box"])
                    if jpg:
                        name = f"{cid}.jpg"
                        open(os.path.join(feed, name), "wb").write(jpg)
                        k = "shown" if kind == "shown" else "guard"
                        PAGE.add_card(cid, k, kw["label"], name,
                                      FALLBACK[k].format(label=kw["label"]))
                        card_async(cid, k, kw["label"], [jpg])
                elif kind == "taken":
                    strip, jpegs = story_strip(cam.event_frames if cam else [],
                                               kw["onset"] - 1.5, kw["t"] + 0.5)
                    if strip:
                        name = f"{cid}.jpg"
                        open(os.path.join(feed, name), "wb").write(strip)
                        PAGE.add_card(cid, "taken", kw["label"], name,
                                      FALLBACK["taken"].format(label=kw["label"]))
                        card_async(cid, "taken", kw["label"], jpegs)
                print(f"[brain] {kind} {kw.get('label', '')}")
            # ---- face, colour, tablet ----
            if player.state != last_state and player.state:
                last_state = player.state
                if link:
                    link.hue(ST.STATES[last_state]["hue"])
            if brain.face != last_face:
                last_face = brain.face
                if link:
                    link.skface(last_face)
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


if __name__ == "__main__":
    main()

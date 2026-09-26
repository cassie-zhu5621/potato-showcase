#!/usr/bin/env python3
"""
standing_prompt.py — so nobody has to speak, and it never performs failure.

Runs beside `noticebot_loop.py --serve --approach`. Somebody walks up, the
board's ToF presses the button for them, the head comes up and the microphone
opens. If they say something, the loop handles it and this does nothing. If
they say nothing -- which at a showcase is most people -- this posts the
standing prompt before the speech timeout, so the flow goes on to Acknowledge
and Scan instead of to Error.

  python3 robot/tools/standing_prompt.py
  python3 robot/tools/standing_prompt.py --say "tell me when someone points"
  python3 robot/tools/standing_prompt.py --after 2.5 --watch

ERROR IS THE ONE STATE A SHOWCASE MUST NOT PERFORM. A visitor has no idea what
they were supposed to say, so a robot acting out not having understood reads as
broken rather than as communicative -- and the failure is the one thing the
room will remember. The study needs that state; a demo has nothing to gain
from it, and this exists to make sure it is never reached.

WHY A SEPARATE PROCESS. The loop holds the CoreS3 and the camera, and the
demo is the study build with two things added rather than a fork of it. This
talks to it the way the developer page does -- over HTTP -- so nothing in
session_flow, the planner or the flow's screens had to be touched, and the
study loop with neither --approach nor this running is exactly what it was.

THE PROMPT ITSELF IS THE PART THAT MATTERS, and it is not a technical choice.
Something vague -- "tell me if anything interesting happens" -- gives the
planner nothing to compile into a watch-spec, and what it produces is either
garbage or nothing. Concrete and high-frequency, and about the AUDIENCE, since
the audience is the thing guaranteed to be present and moving:

    "tell me when someone comes close to the table"
    "tell me when someone points at something"
    "tell me when two people look at the same thing"

The payoff is that the report on the laptop is about the person reading it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

DEFAULT = "tell me when someone comes close to the table"
LISTENING = {"S1_ATTEND"}


def get(base, path, timeout=2.0):
    with urllib.request.urlopen(base + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def post(base, path, body, timeout=3.0):
    req = urllib.request.Request(base + path, data=body.encode("utf-8"),
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status


def main():
    # LINE BUFFERED, ALWAYS. Python block-buffers stdout the moment it is not a
    # terminal, so piping this into tee for a log -- which is the one time the
    # log matters -- holds every line back until 4 KB have piled up. During a
    # demo that is the difference between watching it work and finding out
    # afterwards.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass

    ap = argparse.ArgumentParser(description="the standing prompt, for a demo")
    ap.add_argument("--host", default="http://127.0.0.1:8000")
    ap.add_argument("--say", default=DEFAULT, help="the standing prompt")
    ap.add_argument("--after", type=float, default=3.0,
                    help="seconds of listening to nothing before stepping in. "
                         "Must be under the loop's STT timeout, or Error wins")
    ap.add_argument("--watch", action="store_true", help="print every poll")
    a = ap.parse_args()

    # THE ADDRESSES, HERE, because this is the window that stays still. The
    # loop prints them too and then scrolls them away under CV output within
    # seconds -- and the one you need on a tablet is the one you cannot guess.
    try:
        from webui.server import lan_address
        ip = lan_address()
    except Exception:
        ip = None
    port = a.host.rsplit(":", 1)[-1].strip("/")
    print()
    print("  " + "=" * 62)
    print("   FOR THE AUDIENCE   " + (f"http://{ip}:{port}/booth" if ip
                                      else "no LAN address -- see below"))
    print(f"   FOR YOU            http://localhost:{port}/")
    print("  " + "=" * 62)
    if not ip:
        print("   This machine has no address on the LAN, so a tablet or")
        print("   another laptop cannot reach it. Same wi-fi, and http --")
        print("   not https, and not the .local name.")
    print()
    print(f"  standing prompt: {a.say!r}")
    print(f"  stepping in after {a.after}s of silence. Ctrl-C to stop.\n")

    since = None          # when the robot started listening, or None
    served = False        # already answered for this visit
    last = None
    while True:
        try:
            d = get(a.host, "/booth.json")
        except (urllib.error.URLError, OSError, ValueError) as e:
            # The loop may not be up yet, or may be restarting. That is not an
            # error here: this is a companion, and a companion that dies
            # because the thing it accompanies blinked is worse than useless.
            if last != "down":
                print(f"  waiting for {a.host} ... ({e.__class__.__name__})")
                last = "down"
            time.sleep(1.0)
            continue
        last = None

        state = d.get("state") or ""
        heard = (d.get("heard") or "").strip()
        req = (d.get("request") or "").strip()
        now = time.time()

        if a.watch:
            print(f"  {state:16} heard={heard[:24]!r:28} request={req[:28]!r}")

        if state in LISTENING:
            if since is None:
                since, served = now, False
                print(f"  {time.strftime('%H:%M:%S')}  listening...")
            elif heard:
                # They spoke. The loop owns it from here -- including deciding
                # the words were not usable, which is its judgement to make.
                if not served:
                    served = True
                    print(f"  {time.strftime('%H:%M:%S')}  they said "
                          f"{heard[:40]!r} -- standing aside")
            elif not served and now - since >= a.after:
                served = True
                try:
                    post(a.host, "/context", a.say)
                    print(f"  {time.strftime('%H:%M:%S')}  nobody spoke "
                          f"-- posted the standing prompt")
                except (urllib.error.URLError, OSError) as e:
                    print(f"  !! could not post: {e}")
        else:
            since = None

        time.sleep(0.2)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()

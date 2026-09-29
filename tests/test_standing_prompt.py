"""The demo's companion, against a fake loop.

What it has to get right is one thing said two ways: step in when nobody
speaks, and stay out of the way when somebody does. Both are timing, and
neither can be read off the source -- so this runs the real script against an
HTTP server that plays the part of the loop.
"""
from __future__ import annotations

import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "robot", "tools", "standing_prompt.py")
sys.path.insert(0, ROOT)


class FakeLoop:
    """Serves /booth.json and records what is posted to /context."""

    def __init__(self):
        self.state = {"state": "S0_IDLE", "heard": "", "request": ""}
        self.posted = []
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                b = json.dumps(outer.state).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                outer.posted.append(self.rfile.read(n).decode())
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

        self.srv = socketserver.TCPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        self.srv.shutdown()


@pytest.fixture
def loop():
    f = FakeLoop()
    yield f
    f.stop()


def run(loop, script, after=0.4, timeout=6.0):
    """Start the companion, play `script` against it, return what it posted."""
    p = subprocess.Popen(
        [sys.executable, SCRIPT, "--host", loop.url, "--after", str(after)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        script(loop)
    finally:
        p.terminate()
        p.wait(timeout=timeout)
    return loop.posted


# --------------------------------------------------------------------------- #
def test_a_silent_visitor_gets_the_standing_prompt(loop):
    """Most people at a showcase will not speak, and the flow cannot wait for
    them: at the speech timeout it goes to Error, which is the one state a
    demo must never perform."""
    def play(f):
        time.sleep(0.5)
        f.state["state"] = "S1_ATTEND"
        time.sleep(1.4)
    assert len(run(loop, play)) == 1


def test_somebody_who_speaks_is_left_alone(loop):
    """Their sentence is the point. Posting over it would replace what they
    asked for with a default, which is worse than not having the default."""
    def play(f):
        time.sleep(0.5)
        f.state["state"] = "S1_ATTEND"
        time.sleep(0.25)
        f.state["heard"] = "tell me if someone takes my bag"
        time.sleep(1.4)
    assert run(loop, play) == []


def test_one_prompt_per_visit(loop):
    """It keeps polling while the robot listens. Posting on every poll would
    re-plan several times over one arrival."""
    def play(f):
        time.sleep(0.5)
        f.state["state"] = "S1_ATTEND"
        time.sleep(2.2)
    assert len(run(loop, play)) == 1


def test_the_next_visitor_gets_one_too(loop):
    """Armed again by leaving the listening state, not by a timer -- otherwise
    the second person of the day is met in silence."""
    def play(f):
        for _ in range(2):
            f.state["state"] = "S1_ATTEND"
            time.sleep(1.0)
            f.state["state"] = "S0_IDLE"
            time.sleep(0.4)
    assert len(run(loop, play)) == 2


def test_it_survives_the_loop_not_being_there(loop):
    """A companion that dies because the thing it accompanies blinked is worse
    than useless. The loop restarts; this has to still be running."""
    loop.stop()
    def play(f):
        time.sleep(0.8)
    assert run(loop, play) == []


def test_a_value_that_is_given_lands_between_the_menu_and_the_sleep_rule():
    """Squeezed from both sides, and both sides moved.

    BELOW: the tablet now offers four things and takes several, so three
    seconds -- which was right when this was the only way past Attend -- posts
    over the top of somebody mid-choice and re-plans out from under them. Long
    enough to read four lines and pick two.

    ABOVE: the loop's own clock. PTT is held APPR_HOLD (4.5 s) and the
    transcript wait is STT_TIMEOUT_S after that, so anything under their sum
    beats Error. A margin, because both are tuned on the day and neither is
    tuned with this file open.
    """
    import robot.states as ST
    src = open(SCRIPT).read()
    default = float(src.split('"--after", type=float, default=')[1].split(",")[0])
    if not default:
        return          # off is off; the companion is opt-in now
    hold = 4.5          # APPR_HOLD in cores3_sidekick.ino
    assert default >= 8.0, "too short to read a menu and choose"
    assert default <= (hold + ST.STT_TIMEOUT_S) - 5.0, \
        "too close to the flow giving up -- Error would win the race"


def test_it_stands_aside_while_somebody_is_choosing():
    """The companion answers for a visitor who does NOTHING, and a tap is not
    nothing. Without this it posts its own line at 12 s over the top of someone
    picking their second option, and the robot goes off to scan for something
    they did not choose."""
    src = open(SCRIPT).read()
    i = src.index('d.get("choosing")')
    block = src[i:i + 600]
    assert "since = now" in block, "push the clock"
    assert "continue" in block
    # It must PUSH the deadline, not cancel it: one tap then walking away is
    # still a visitor who has to be covered.
    assert "served = True" not in block, \
        "choosing must not mark the visit as dealt with"


def test_choosing_is_a_timestamp_not_a_flag():
    """The page that set it can walk away mid-choice, and nothing would ever
    clear a flag -- the companion would be muted for the rest of the day."""
    from webui.booth import CHOOSING_HOLD_S
    src = open(os.path.join(ROOT, "webui", "booth.py")).read()
    assert "choosing_at" in src and "time.time() -" in src
    assert 0 < CHOOSING_HOLD_S <= 30
    srv = open(os.path.join(ROOT, "webui", "server.py")).read()
    i = srv.index('/booth/choosing')
    assert 'STATE["choosing_at"] = time.time()' in srv[i:i + 900]


def test_the_companion_cannot_silently_pre_empt_the_sleep_rule():
    """TWO CLOCKS THAT MEAN OPPOSITE THINGS about the same silence.

    ATTEND_MAX_S says: fifteen seconds with nobody asking for anything, go back
    to sleep. `--after` says: twelve seconds with nobody asking for anything,
    ask on their behalf. Whichever is shorter wins every time, and the other is
    dead code that reads as live.

    This does not decide which is right -- it refuses to let them be set so the
    conflict is invisible.
    """
    import robot.states as ST
    src = open(SCRIPT).read()
    default = float(src.split('"--after", type=float, default=')[1].split(",")[0])
    if ST.ATTEND_MAX_S and default:
        assert default < ST.ATTEND_MAX_S or default == 0, (
            f"--after={default:g}s never fires: the flow sleeps at "
            f"ATTEND_MAX_S={ST.ATTEND_MAX_S:g}s first. Set one of them to 0 "
            f"and mean it.")


def test_the_companion_is_off_by_default():
    """It was written when a silent visitor had no way out of Attend except
    S7_ERROR. Two things made it redundant: the MENU, so somebody who wants
    something can say so without speaking, and ATTEND_MAX_S, so somebody who
    wants nothing gets a robot that goes back to sleep.

    What is left is a companion that answers on behalf of a person who has just
    spent fifteen seconds demonstrating they are not asking -- and then sends
    the robot off to watch for three minutes on a request nobody made, for
    every passer-by at a busy stand."""
    src = open(SCRIPT).read()
    default = float(src.split('"--after", type=float, default=')[1].split(",")[0])
    assert default == 0.0


def test_it_does_nothing_at_all_when_off():
    """Off has to mean off in the loop, not just in the help text."""
    src = open(SCRIPT).read()
    i = src.index("now - since >= a.after")
    guard = src[max(0, i - 120):i]
    assert "a.after and" in guard, \
        "0 must short-circuit before the comparison -- `now - since >= 0` is " \
        "true on the first poll, so an unchecked 0 posts IMMEDIATELY, which " \
        "is the loudest possible opposite of off"

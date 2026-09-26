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


def test_it_steps_in_well_before_the_flow_gives_up():
    """The default has to be inside the loop's own speech timeout, or Error
    wins the race and the companion is decoration."""
    import robot.states as ST
    src = open(SCRIPT).read()
    default = float(src.split('"--after", type=float, default=')[1].split(",")[0])
    assert default < ST.STT_TIMEOUT_S / 2

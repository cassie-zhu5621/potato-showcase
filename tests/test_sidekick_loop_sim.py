"""The whole booth, in simulation: sidekick_loop.main() with a fake bus, camera,
detector and pose estimator, and a visitor who reacts to what the robot does.

The visitor lives in ROBOT ANGLES (where things are in the room), and the fake
camera turns them into pixels for whatever pose the head is in at that moment.
So the robot only "sees" the banana move down to the table if it actually
follows it there -- the test exercises aiming, not just the decisions.
"""
import math
import os
import sys
import time

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from robot import states as ST                       # noqa: E402
from perception.perceive import Detection            # noqa: E402
from perception.relations import PersonPose          # noqa: E402
from perception import sidekick_sense as SS          # noqa: E402
import test_sidekick_player as TSP                   # noqa: E402  (clip fixture)

W, H = 1280, 720


def to_pixel(pan, gaze, pose):
    """Inverse of sidekick_sense.to_target."""
    th = math.tan(math.radians(ST.CAM_HFOV_DEG / 2))
    tv = math.tan(math.radians(SS.vfov_deg(W, H) / 2))
    dx = (pan - pose["pan"]) * ST.AIM_X_SIGN
    dy = (gaze - (pose["tilt"] + pose["nod"])) * ST.AIM_Y_SIGN
    x = (math.tan(math.radians(dx)) / (2 * th) + 0.5) * W
    y = (0.5 - math.tan(math.radians(dy)) / (2 * tv)) * H
    return x, y


class World:
    """A visitor who does the next thing when the robot has done its part."""

    def __init__(self, sim):
        self.sim = sim
        self.step = "approach"
        self.t0 = time.time()
        self.wiggle = 0

    def scene(self):
        b = self.sim["brain"]
        ev = [k for k, _ in self.sim["events"]]
        face = (15.0, 25.0)                 # pan, gaze of the visitor's face
        banana = None                       # (pan, gaze, held, hand_near)
        if b is None or b.phase == "DOZE":
            pass
        elif b.phase == "LOOK" and "shown" not in ev:
            wig = int((time.time() - self.t0) * 2) % 2     # waved about
            banana = (5.0 + wig * 6, 8.0, True, True)
        elif b.phase == "SHOW" and "shown" not in ev:
            banana = (5.0, 8.0, True, True)            # held still
        elif b.phase == "SHOW":
            banana = (5.0, -30.0, False, False)        # put down on the table
        elif b.phase == "GUARD":
            since = self.sim.setdefault("guard_t", time.time())
            dt = time.time() - since
            if dt < 3.0:
                banana = (5.0, -30.0, False, False)
            elif dt < 3.8:
                banana = (5.0, -30.0, False, True)     # a hand comes near
            else:
                banana = None                          # and takes it
        return face, banana


class FakeCam:
    def __init__(self, index):
        import cv2
        self.latest = np.zeros((H, W, 3), np.uint8)
        self.seq = 0
        ok, j = cv2.imencode(".jpg", self.latest)
        self.event_frames = [(time.time() + i * 0.1, j.tobytes()) for i in range(-50, 400)]

    def close(self):
        pass


def test_a_visitor_shows_guards_and_loses_a_banana(monkeypatch, clips_dir, tmp_path):
    import sidekick_loop as L
    import perception.perceive as P
    import perception.relations as R
    from session import sidekick_brain as B

    sim = {"brain": None, "events": [], "player": None}
    world = World(sim)

    # make the long waits short; the order of things is what is tested
    monkeypatch.setattr(B, "WAKE_S", 0.2)
    monkeypatch.setattr(B, "STILL_S", 0.6)
    monkeypatch.setattr(B, "PLACE_S", 0.4)
    monkeypatch.setattr(B, "GUARD_SETTLE_S", 1.0)

    real_brain = L.Brain

    def brain_spy(player, on_event=None, **kw):
        def ev(kind, **k):
            sim["events"].append((kind, k))
            on_event(kind, **k)
        b = real_brain(player, on_event=ev, **kw)
        sim["brain"], sim["player"] = b, player
        return b

    class Det:
        def detect(self, frame):
            if time.time() - world.t0 > 40:
                sim["timeout"] = True
                raise KeyboardInterrupt
            face, banana = world.scene()
            b, p = sim["brain"], sim["player"]
            if os.environ.get("SIM_DEBUG"):
                print(f"[sim] {time.time() - world.t0:5.1f} {b.phase:5} {str(p.state):14} "
                      f"{banana} pose={ {k: round(v) for k, v in p.pose_deg().items()} }")
            if sim["events"] and sim["events"][-1][0] == "taken":
                if time.time() - sim.setdefault("taken_t", time.time()) > 0.5:
                    raise KeyboardInterrupt
            if banana is None:
                return []
            pose = sim["player"].pose_deg()
            x, y = to_pixel(banana[0], banana[1], pose)
            return [Detection("banana", (x - 60, y - 30, x + 60, y + 30))]

    class Poses:
        def estimate(self, frame):
            pose = sim["player"].pose_deg()
            fx, fy = to_pixel(15.0, 25.0, pose)
            pts = {SS.NOSE: (fx, fy), SS.L_SH: (fx - 220, fy + 150),
                   SS.R_SH: (fx + 220, fy + 150), 23: (fx - 150, fy + 600),
                   24: (fx + 150, fy + 600)}
            _, banana = world.scene()
            if banana and (banana[2] or banana[3]):
                bx, by = to_pixel(banana[0], banana[1], pose)
                pts[15] = (bx, by + (25 if banana[2] else 50))
            vis = {k: 0.9 for k in pts}
            return [PersonPose(pid=-1, pts=pts, vis=vis)]

        def close(self):
            pass

    monkeypatch.setattr(L, "open_bus", lambda port, baud: (TSP.FakeBus(), "fake"))
    monkeypatch.setattr(TSP.FakeBus, "ping", lambda self, sid: (0, True), raising=False)
    monkeypatch.setattr(L, "HeadCam", FakeCam)
    monkeypatch.setattr(L, "Brain", brain_spy)
    monkeypatch.setattr(L.PAGE, "serve", lambda d, p: None)
    monkeypatch.setattr(P, "make_detector", lambda *a, **k: Det())
    monkeypatch.setattr(R, "PoseEstimator", lambda **k: Poses())
    import perception.gaze as GZ

    class NoFaces:
        def estimate(self, frame):
            return []

        def close(self):
            pass
    monkeypatch.setattr(GZ, "HeadPoseEstimator", lambda **k: NoFaces())
    monkeypatch.setattr(sys, "argv", ["sidekick_loop.py", "--clips", clips_dir,
                                      "--offline", "--cv-hz", "8",
                                      "--feed-dir", str(tmp_path)])
    t0 = time.time()
    L.main()
    assert not sim.get("timeout"), [k for k, _ in sim["events"]]
    kinds = [k for k, _ in sim["events"]]
    assert kinds[:3] == ["shown", "guard_start", "alert"], kinds
    assert kinds[-1] == "taken", kinds
    page = L.PAGE.snapshot()
    assert [c["kind"] for c in page["cards"]][:3] == ["taken", "guard", "shown"]
    assert time.time() - t0 < 60


@pytest.fixture(scope="module")
def clips_dir(tmp_path_factory):
    return TSP.clips_dir.__wrapped__(tmp_path_factory)

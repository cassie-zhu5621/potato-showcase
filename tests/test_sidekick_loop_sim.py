"""The whole booth, in simulation: sidekick_loop.main() with a fake bus, camera,
detector and pose estimator, and a visitor who reacts to what the robot does.

The visitor lives in ROBOT ANGLES (where things are in the room), and the fake
camera turns them into pixels for whatever pose the head is in at that moment.
So the robot only sees what its head is actually pointed at -- the test
exercises aiming, not just the decisions.
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
    """A visitor who does the next thing when the robot has done its part:
    comes close, holds up a water bottle, keeps holding it while it is named,
    puts it away, and a little later the bottle turns up on the table."""

    def __init__(self, sim):
        self.sim = sim
        self.t0 = time.time()

    def scene(self):
        b = self.sim["brain"]
        ev = [k for k, _ in self.sim["events"]]
        bottle = None                       # (pan, gaze, held)
        if b is None or b.phase in ("SLEEP", "DOZE"):
            pass
        elif "taught" not in ev:
            bottle = (8.0, 12.0, True)                  # held up to it
        else:
            since = self.sim.setdefault("taught_t", time.time())
            if time.time() - since > 4.5:               # away, then it turns
                bottle = (5.0, 10.0, False)             # up again, in view
        return bottle


class FakeCam:
    def __init__(self, index):
        import cv2
        self.latest = np.zeros((H, W, 3), np.uint8)
        self.seq = 0
        ok, j = cv2.imencode(".jpg", self.latest)
        self.event_frames = [(time.time() + i * 0.1, j.tobytes()) for i in range(-50, 400)]

    def close(self):
        pass


def test_a_visitor_shows_a_bottle_and_it_calls_when_the_bottle_turns_up(
        monkeypatch, clips_dir, tmp_path):
    import sidekick_loop as L
    import perception.perceive as P
    import perception.relations as R
    import perception.gaze as GZ
    from session import sidekick_brain as B

    sim = {"brain": None, "events": [], "player": None}
    world = World(sim)
    monkeypatch.setattr(B, "WAKE_S", 0.2)
    monkeypatch.setattr(B, "TARGET_AWAY_S", 1.5)
    real_brain = L.Brain

    def brain_spy(player, on_event=None, **kw):
        def ev(kind, **k):
            sim["events"].append((kind, k))
            on_event(kind, **k)
        b = real_brain(player, on_event=ev, **kw)
        sim["brain"], sim["player"] = b, player
        return b

    class Det:
        def __init__(self):
            self.vocab = []

        def set_vocab(self, v):
            self.vocab = list(v)

        def detect(self, frame):
            if time.time() - world.t0 > 40:
                sim["timeout"] = True
                raise KeyboardInterrupt
            if sim["events"] and sim["events"][-1][0] == "found":
                raise KeyboardInterrupt
            bottle = world.scene()
            if bottle is None:
                return []
            x, y = to_pixel(bottle[0], bottle[1], sim["player"].pose_deg())
            if not (0 <= x <= W and 0 <= y <= H):
                return []                           # not where it is looking
            return [Detection("water bottle", (x - 70, y - 90, x + 70, y + 90))]

    class Poses:
        def estimate(self, frame):
            pose = sim["player"].pose_deg()
            fx, fy = to_pixel(15.0, 25.0, pose)
            pts = {SS.NOSE: (fx, fy), SS.L_SH: (fx - 220, fy + 150),
                   SS.R_SH: (fx + 220, fy + 150), 23: (fx - 150, fy + 600),
                   24: (fx + 150, fy + 600)}
            bottle = world.scene()
            if bottle and bottle[2]:
                bx, by = to_pixel(bottle[0], bottle[1], pose)
                pts[15] = (bx, by + 60)
            return [PersonPose(pid=-1, pts=pts, vis={k: 0.9 for k in pts})]

        def close(self):
            pass

    class NoFaces:
        def estimate(self, frame):
            return []

        def close(self):
            pass

    monkeypatch.setattr(L, "open_bus", lambda port, baud: (TSP.FakeBus(), "fake"))
    monkeypatch.setattr(TSP.FakeBus, "ping", lambda self, sid: (0, True), raising=False)
    monkeypatch.setattr(L, "HeadCam", FakeCam)
    monkeypatch.setattr(L, "Brain", brain_spy)
    monkeypatch.setattr(L.PAGE, "serve", lambda d, p: None)
    monkeypatch.setattr(P, "make_detector", lambda *a, **k: Det())
    monkeypatch.setattr(R, "PoseEstimator", lambda **k: Poses())
    monkeypatch.setattr(GZ, "HeadPoseEstimator", lambda **k: NoFaces())
    monkeypatch.setattr(sys, "argv", ["sidekick_loop.py", "--clips", clips_dir,
                                      "--stage", "3", "--offline", "--cv-hz", "8",
                                      "--feed-dir", str(tmp_path)])
    L.main()
    kinds = [k for k, _ in sim["events"]]
    assert not sim.get("timeout"), kinds
    assert kinds[:2] == ["identify", "taught"], kinds
    assert kinds[-1] == "found", kinds
    page = L.PAGE.snapshot()
    assert [c["kind"] for c in page["cards"]][:2] == ["found", "watch"]


@pytest.fixture(scope="module")
def clips_dir(tmp_path_factory):
    return TSP.clips_dir.__wrapped__(tmp_path_factory)

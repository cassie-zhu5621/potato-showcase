"""The 11.24 booth end to end, in simulation: a pat wakes it, it takes the
visitor as its owner, the visitor shows a bottle, hides it, and it calls when
the bottle turns up -- and the web UI has the live picture and the object."""
import json
import os
import socket
import sys
import time
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from perception.perceive import Detection            # noqa: E402
from perception.relations import PersonPose          # noqa: E402
from perception import sidekick_sense as SS          # noqa: E402
import test_sidekick_player as TSP                   # noqa: E402
from test_sidekick_loop_sim import to_pixel, FakeCam, W, H   # noqa: E402


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def test_pat_owner_show_hide_and_call_with_the_web_ui(monkeypatch, clips_dir, tmp_path):
    import sidekick_loop as L
    import perception.perceive as P
    import perception.relations as R
    import perception.gaze as GZ
    from session import booth_brain as BB
    from webui import booth_page

    sim = {"brain": None, "events": [], "player": None, "t0": time.time()}
    monkeypatch.setattr(BB.SB, "TARGET_AWAY_S", 1.5)
    real = BB.BoothBrain

    def spy(player, on_event=None, **kw):
        def ev(kind, **k):
            sim["events"].append((kind, k))
            on_event(kind, **k)
        b = real(player, on_event=ev, **kw)
        sim["brain"], sim["player"] = b, player
        return b

    def scene():
        b = sim["brain"]
        ev = [k for k, _ in sim["events"]]
        if b is None or b.phase == "SLEEP" or "owner" not in ev:
            return None
        if "taught" not in ev:
            return (8.0, 12.0, True)
        since = sim.setdefault("taught_t", time.time())
        return (5.0, 10.0, False) if time.time() - since > 4.5 else None

    class Det:
        def set_vocab(self, v):
            pass

        def detect(self, frame):
            b = sim["brain"]
            if time.time() - sim["t0"] > 40:
                sim["timeout"] = True
                raise KeyboardInterrupt
            if any(k == "found" for k, _ in sim["events"]):
                sim["page"] = booth_page.snapshot()
                sim["frame"] = booth_page._FRAME["jpg"]
                raise KeyboardInterrupt
            if b is not None and b.phase == "SLEEP" and not sim.get("patted"):
                sim["patted"] = True
                b.on_tap()                       # the visitor pats its head
            bottle = scene()
            if bottle is None:
                return []
            x, y = to_pixel(bottle[0], bottle[1], sim["player"].pose_deg())
            if not (0 <= x <= W and 0 <= y <= H):
                return []
            return [Detection("water bottle", (x - 130, y - 170, x + 130, y + 170))]

    class Poses:
        def estimate(self, frame):
            pose = sim["player"].pose_deg()
            fx, fy = to_pixel(15.0, 25.0, pose)
            pts = {SS.NOSE: (fx, fy), SS.L_SH: (fx - 220, fy + 150),
                   SS.R_SH: (fx + 220, fy + 150), 23: (fx - 150, fy + 600),
                   24: (fx + 150, fy + 600)}
            bottle = scene()
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
    monkeypatch.setattr(BB, "BoothBrain", spy)
    monkeypatch.setattr(P, "make_detector", lambda *a, **k: Det())
    monkeypatch.setattr(R, "PoseEstimator", lambda **k: Poses())
    monkeypatch.setattr(GZ, "HeadPoseEstimator", lambda **k: NoFaces())
    port = free_port()
    monkeypatch.setattr(sys, "argv", ["sidekick_loop.py", "--clips", clips_dir,
                                      "--stage", "3", "--offline", "--cv-hz", "8",
                                      "--feed-dir", str(tmp_path),
                                      "--web-port", str(port)])
    L.main()
    kinds = [k for k, _ in sim["events"] if k != "say"]
    assert not sim.get("timeout"), kinds
    assert kinds.index("owner") < kinds.index("identify") < kinds.index("taught")
    assert kinds[-1] == "found", kinds
    assert sim["page"]["looking_for"] == "the water bottle"
    assert sim["frame"] and sim["frame"][:2] == b"\xff\xd8"          # a JPEG
    # the web UI answers, and NEXT reaches the loop's queue
    html = urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode()
    assert "NEXT" in html and "/live.mjpg" in html
    st = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/state").read())
    assert st["tof_m"] == pytest.approx(0.8)
    urllib.request.urlopen(urllib.request.Request(
        f"http://127.0.0.1:{port}/cmd?c=next", method="POST")).read()
    assert booth_page.commands.pop() == "next"


@pytest.fixture(scope="module")
def clips_dir(tmp_path_factory):
    return TSP.clips_dir.__wrapped__(tmp_path_factory)

"""The player features the sidekick mode needs (showcase-1108).

The SK_* clips are made in Blender, so these tests make them the same way with a
stand-in for bpy (tests/fake_bpy): every generator is run, which also proves each
one still passes its own floor and ceiling checks.
"""
import csv
import math
import os
import runpy
import shutil
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from robot import states as ST                     # noqa: E402
from robot.pose import JOINTS, IDS, centre_units   # noqa: E402
import robot.clip_player as CP                     # noqa: E402

GENS = {"SK_DOZE": "doze", "SK_GLANCE": "glance", "SK_CURIOUS": "curious",
        "SK_ACK": "ack", "SK_PURR": "purr", "SK_GUARD_ALERT": "guard_alert"}


def _export(name, gen, out_dir):
    """Run one generator against the fake bpy and write the CSV export_clip.py
    would write (linear between keys; the generators key every frame)."""
    sys.path.insert(0, os.path.join(ROOT, "tests", "fake_bpy"))
    # The .blend lives OUTSIDE the repo, as Cassie's do (the design folder):
    # the generators must find everything from their own folder, not from it.
    os.environ["FAKE_BLEND"] = os.path.join("/tmp", "design", "v2.0", name + ".blend")
    script = os.path.join(ROOT, "motion", "sidekick", f"generate_sk_{gen}.py")
    os.environ["FAKE_SCRIPT"] = script
    sys.modules.pop("bpy", None)
    import bpy
    runpy.run_path(script)
    sc = bpy.context.scene
    o = bpy.data.objects
    led = bpy.data.materials["led_mat"].node_tree.nodes[0].inputs["Strength"].keys

    def at(keys, f):
        ks = sorted(keys)
        if f <= ks[0]:
            return keys[ks[0]]
        if f >= ks[-1]:
            return keys[ks[-1]]
        for a, b in zip(ks, ks[1:]):
            if a <= f <= b:
                return keys[a] + (keys[b] - keys[a]) * (f - a) / (b - a)

    def unit(d):
        return max(0, min(1023, round((d + 150) / 300 * 1023)))

    path = os.path.join(out_dir, name + ".csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["t_ms", "pan_deg", "tilt_deg", "nod_deg",
                    "pan_unit", "tilt_unit", "nod_unit", "led"])
        for f in range(sc.frame_start, sc.frame_end + 1):
            p = math.degrees(at(o["pan_pivot"].keys[2], f))
            t = math.degrees(at(o["tilt_pivot"].keys[0], f))
            n = math.degrees(at(o["nod_pivot"].keys[0], f))
            lv = max(0, min(255, round(at(led, f) / 8.0 * 255)))
            w.writerow([round((f - sc.frame_start) * 1000 / 30), round(p, 2),
                        round(t, 2), round(n, 2), unit(p), unit(t), unit(n), lv])
    sys.path.pop(0)


@pytest.fixture(scope="module")
def clips_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("clips")
    for fn in os.listdir(os.path.join(ROOT, "motion", "clips")):
        if fn.endswith(".csv"):
            shutil.copy(os.path.join(ROOT, "motion", "clips", fn), d)
    for name, gen in GENS.items():
        _export(name, gen, str(d))
    return str(d)


class FakeBus:
    def __init__(self):
        self.pos = dict(centre_units())
        self.writes = 0

    def flush_input(self):
        pass

    def read_pos(self, sid):
        j = {v: k for k, v in IDS.items()}[sid]
        return self.pos[j]

    def read_voltage(self, sid):
        return 5.5

    def torque(self, sid, on):
        pass

    def write_pos(self, sid, u, time_ms=0, speed=0):
        j = {v: k for k, v in IDS.items()}[sid]
        self.pos[j] = u
        self.writes += 1

    write_pos_fast = write_pos


def _player(clips_dir):
    p = CP.ClipPlayer(FakeBus(), clips_dir, verbose=False, sidekick=True)
    return p


def _wait(pred, timeout=8.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.02)
    return False


def test_every_generator_passes_its_own_floor_and_ceiling_checks(clips_dir):
    for name in GENS:
        assert os.path.exists(os.path.join(clips_dir, name + ".csv"))


def test_the_paper_flow_does_not_need_the_sidekick_clips():
    real = {f[:-4] for f in os.listdir(os.path.join(ROOT, "motion", "clips"))
            if f.endswith(".csv")}
    assert all(ST.is_sidekick(p.split(":")[0])
               for p in ST.validate(real, sidekick=True))
    assert not [p for p in ST.validate(real) if "SK_" in p]


def test_the_table_validates_with_the_clips(clips_dir):
    have = {f[:-4] for f in os.listdir(clips_dir)}
    assert ST.validate(have, sidekick=True) == []


def test_a_relative_clip_starts_where_the_robot_is(clips_dir):
    p = _player(clips_dir)
    fr = p.clips["SK_PURR"]
    entry = {"pan": 30.0, "tilt": -5.0, "nod": 10.0}
    out = CP.make_relative(fr, entry, verbose=False)
    for j in JOINTS:
        assert abs(CP.unit_to_deg(j, out[0][j]) - entry[j]) < 0.6
    # the shape is unchanged: the excursion survives the translation
    ex_a = max(CP.unit_to_deg("nod", f["nod"]) for f in fr) - CP.unit_to_deg("nod", fr[0]["nod"])
    ex_b = max(CP.unit_to_deg("nod", f["nod"]) for f in out) - CP.unit_to_deg("nod", out[0]["nod"])
    assert abs(ex_a - ex_b) < 0.6


def test_a_glance_lands_on_the_person_either_side(clips_dir):
    p = _player(clips_dir)
    fr = p.clips["SK_GLANCE"]
    for target in (-25.0, 40.0):
        out = CP.make_relative(fr, {"pan": 0.0, "tilt": -8.0, "nod": 0.0},
                               pan_scale=target / ST.GLANCE_TEMPLATE_DEG,
                               verbose=False)
        pans = [CP.unit_to_deg("pan", f["pan"]) for f in out]
        far = max(pans, key=abs)
        assert abs(far - target) < 1.0
        assert abs(pans[-1]) < 0.6          # and comes back


def test_live_aim_saccades_to_the_target_and_holds(clips_dir):
    p = _player(clips_dir).start(home=False)
    try:
        p.set_aim_deg(pan=20.0, nod=10.0)
        p.request("SK_LOOK")
        assert _wait(lambda: abs(p.pose_deg()["pan"] - 20.0) < 1.0)
        assert abs(p.pose_deg()["nod"] - 10.0) < 1.0
        # a target inside the dead band does not move the head
        before = p.bus.writes
        p.set_aim_deg(pan=21.5, nod=10.0)
        time.sleep(0.4)
        assert abs(p.pose_deg()["pan"] - 20.0) < 1.0
    finally:
        p.stop(relax=False)


def test_a_pat_returns_to_what_it_interrupted(clips_dir):
    p = _player(clips_dir)
    p.clips["SK_PURR"] = p.clips["SK_PURR"][:6]     # keep the test short
    p.start(home=False)
    try:
        p.set_aim_deg(pan=0.0, tilt=ST.LOOK_TILT, nod=ST.LOOK_NOD)
        p.request("SK_LOOK")
        assert _wait(lambda: p.state == "SK_LOOK")
        p.request("SK_PURR")
        assert _wait(lambda: p.state == "SK_PURR")
        assert _wait(lambda: p.state == "SK_LOOK")
    finally:
        p.stop(relax=False)


def test_the_alert_keeps_the_eye_on_the_guarded_thing(clips_dir):
    p = _player(clips_dir)
    p.clips["SK_GUARD_ALERT"] = p.clips["SK_GUARD_ALERT"][:10]
    p.start(home=False)
    try:
        p.set_aim_deg(pan=-40.0, tilt=-12.0, nod=-20.0)
        p.request("SK_GUARD")
        assert _wait(lambda: abs(p.pose_deg()["pan"] + 40.0) < 1.0)
        p.request("SK_GUARD_ALERT")
        assert _wait(lambda: p.state == "SK_GUARD_ALERT")
        time.sleep(0.1)
        pose = p.pose_deg()
        assert abs(pose["pan"] + 40.0) < 1.0
        # neck up, head down by the same amount: the gaze has not moved
        assert abs((pose["tilt"] + pose["nod"]) - (-32.0)) < 1.5
        assert _wait(lambda: p.state == "SK_GUARD")
    finally:
        p.stop(relax=False)


def test_a_touch_on_a_sleeping_robot_lifts_all_the_way(clips_dir):
    """as_authored: the purr from S0 reaches the same height as on the bench."""
    p = _player(clips_dir)
    p.start(home=False)
    try:
        p.request("S0_IDLE")
        assert _wait(lambda: p.state == "S0_IDLE")
        top = max(CP.unit_to_deg("nod", f["nod"]) for f in p.clips["SK_PURR"])
        seen = []
        p.request("SK_PURR", resume_to="S0_IDLE", as_authored=True)
        assert _wait(lambda: p.state == "SK_PURR")
        _wait(lambda: (seen.append(p.pose_deg()["nod"]) or p.state != "SK_PURR"), 6)
        assert max(seen) > top - 1.0
        assert _wait(lambda: p.state == "S0_IDLE")
    finally:
        p.stop(relax=False)

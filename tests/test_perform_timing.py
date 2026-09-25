"""The performance clock: the sway's accent, and where a keypress lands.

Both things this tests were wrong when written, in the same way -- the lead was
counted twice -- and neither would have been visible on a robot. A gesture a
fifth of a beat early does not look like a bug, it looks like the robot cannot
keep time, and the instinct is then to change the tempo, which cannot help.
"""
from __future__ import annotations

import importlib.util
import math
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_spec = importlib.util.spec_from_file_location(
    "perform", os.path.join(ROOT, "robot", "tools", "perform.py"))
perform = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(perform)


def perf(bpm=90.0, t0=0.0, shape="nod"):
    p = perform.Perf(player=None)
    p.bpm, p.t0, p.shape = bpm, t0, shape
    return p


def pose_at(p, t):
    """The pose the oscillator COMMANDS at wall-clock t."""
    p.phase = lambda at=None, _t=t: (_t + perform.LEAD_S - p.t0) / p.period
    return p.pose()


# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("shape,joint", [("nod", "nod"), ("lean", "tilt"),
                                         ("dip", "tilt")])
def test_the_accent_arrives_on_the_beat_not_after_it(shape, joint):
    """The extreme of the sway must be commanded LEAD_S BEFORE each beat, so
    that it arrives on it. Evaluating the waveform at `now` instead of at
    `now + lead` is the whole difference between a robot playing along and a
    robot answering."""
    p = perf(shape=shape)
    beat = 4 * p.period                      # some beat, in wall clock
    at_beat = pose_at(p, beat - perform.LEAD_S)[joint]
    sweep = [abs(pose_at(p, beat - perform.LEAD_S + k * p.period / 24)[joint])
             for k in range(24)]
    assert abs(at_beat) == pytest.approx(max(sweep), rel=0.02)


def test_lean_holds_the_gaze_while_the_body_moves():
    """tilt and nod in opposition: the neck dips and the head counter-rotates,
    so the gaze stays level. The musician's version, and the same shape as
    S5A_FOUND's epistemic lean."""
    p = perf(shape="lean")
    q = pose_at(p, 4 * p.period - perform.LEAD_S)
    assert q["tilt"] * q["nod"] < 0, "lean must counter-rotate, not dip"


def test_dip_moves_the_whole_body_together():
    p = perf(shape="dip")
    q = pose_at(p, 4 * p.period - perform.LEAD_S)
    assert q["tilt"] * q["nod"] > 0


# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("clip", sorted(perform.ACCENT_S))
def test_a_gesture_lands_on_a_whole_beat(clip, monkeypatch):
    """Pressed at an arbitrary moment, the clip's ACCENT -- not its first frame
    -- has to land on a beat. The offsets differ by a factor of four across the
    vocabulary, so aligning starts would put half of it visibly off."""
    t_now = 12.37
    monkeypatch.setattr(perform.time, "perf_counter", lambda: t_now)
    p = perf(t0=10.0)
    p.fire(clip)
    fire_at, got, land = p.pending
    assert got == clip
    beats = (land - p.t0) / p.period
    assert beats == pytest.approx(round(beats), abs=1e-6)
    assert fire_at >= t_now, "cannot fire in the past"
    assert land - fire_at == pytest.approx(
        perform.ACCENT_S[clip] + perform.LEAD_S, abs=1e-6)


def test_an_accent_longer_than_a_beat_skips_ahead(monkeypatch):
    """S2_ACKNOWLEDGE's accent is 1.17 s. At 90 BPM a beat is 0.67 s, so it
    cannot make the next one and must take a later beat rather than a beat that
    has already gone."""
    t_now = 12.37
    monkeypatch.setattr(perform.time, "perf_counter", lambda: t_now)
    p = perf(bpm=90.0, t0=10.0)
    p.fire("S2_ACKNOWLEDGE")
    fire_at, _, land = p.pending
    assert fire_at >= t_now
    assert (land - p.t0) / p.period >= 3


def test_tapping_re_anchors_the_downbeat(monkeypatch):
    """Every tap is also a downbeat. Without that there is no way to pull the
    robot back into line against a record without stopping it."""
    t = [100.0]
    monkeypatch.setattr(perform.time, "perf_counter", lambda: t[0])
    p = perf(t0=0.0)
    p.tap()
    assert p.t0 == 100.0


def test_four_taps_set_the_tempo(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(perform.time, "perf_counter", lambda: t[0])
    p = perf()
    for _ in range(4):
        p.tap()
        t[0] += 0.5                      # 120 BPM
    assert p.bpm == pytest.approx(120.0, rel=0.02)


def test_a_wild_tap_does_not_move_the_tempo(monkeypatch):
    """A median, not a mean: one late tap in a steady four is a slip of the
    finger, and a mean would swing the whole piece for it."""
    t = [0.0]
    monkeypatch.setattr(perform.time, "perf_counter", lambda: t[0])
    p = perf()
    for gap in (0.5, 0.5, 1.4, 0.5, 0.5):
        p.tap()
        t[0] += gap
    assert p.bpm == pytest.approx(120.0, rel=0.05)

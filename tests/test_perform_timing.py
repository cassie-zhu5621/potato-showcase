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


# --------------------------------------------------------------------------- #
# tapping while it plays
# --------------------------------------------------------------------------- #
def test_tapping_while_it_runs_does_not_lurch(monkeypatch):
    """Setting t0 = now on every tap snaps the phase to zero from wherever the
    sway had got to, and the neck jumps mid-travel. That made tapping something
    you had to freeze for -- and an instrument you must stop to retune is not
    one."""
    t = [37.4]
    monkeypatch.setattr(perform.time, "perf_counter", lambda: t[0])
    p = perf(bpm=90.0, t0=37.0)
    p.frozen = False
    before = p.phase() % 1.0
    p.tap()
    after = p.phase() % 1.0
    assert abs(after - before) < 0.2, "the phase jumped; it should converge"


def test_tapping_converges_on_the_beat(monkeypatch):
    """A quarter of the error per tap: locked within about four, which is how
    long it takes to give it four taps anyway."""
    t = [100.0]
    monkeypatch.setattr(perform.time, "perf_counter", lambda: t[0])
    p = perf(bpm=120.0, t0=100.0 - 0.21)     # a fifth of a beat out
    p.frozen = False
    errs = []
    for _ in range(6):
        p.tap()
        ph = p.phase()
        errs.append(abs(ph - round(ph)))
        t[0] += p.period
    assert errs[-1] < errs[0] / 3, f"did not converge: {errs}"


def test_frozen_it_snaps(monkeypatch):
    """Nothing is moving, so there is nothing to lurch -- and starting a piece
    should put the downbeat exactly where it was tapped."""
    t = [50.0]
    monkeypatch.setattr(perform.time, "perf_counter", lambda: t[0])
    p = perf(t0=49.13)
    p.frozen = True
    p.tap()
    assert p.t0 == 50.0


def test_a_tempo_change_does_not_move_the_neck(monkeypatch):
    """The period is the denominator of the phase, so changing it without
    re-deriving t0 moves the pose as well and a tempo nudge arrives with a
    jolt."""
    t = [0.0]
    monkeypatch.setattr(perform.time, "perf_counter", lambda: t[0])
    p = perf(bpm=90.0, t0=-0.3)
    p.frozen = False
    for gap in (0.5, 0.5, 0.5):        # tap in a different tempo
        before = p.phase() % 1.0
        p.tap()
        after = p.phase() % 1.0
        assert abs(after - before) < 0.2, "tempo change jolted the phase"
        t[0] += gap


def test_the_turn_is_ramped_not_jumped():
    """pan's limit is the camera loom rather than the servo, so it is the axis
    to be gentle with -- and a 30 degree jump mid-sway is a lurch."""
    p = perf()
    p.pan_want = 60.0
    dt = 1.0 / perform.RATE_HZ
    p.ramp(dt)
    assert 0 < p.pan < 2.0, "one frame of turn must be too small to see"
    t = dt
    while p.pan != p.pan_want and t < 5:
        p.ramp(dt)
        t += dt
    assert p.pan == 60.0 and t < 2.5


def test_a_ramp_snaps_when_it_arrives():
    """Without the snap it oscillates around the target forever, one step
    either side -- a tremble the size of a frame, invisible until something
    counts how long the ramp took. Which is how this was found."""
    p = perf()
    p.pan_want = 0.4                     # smaller than one frame of travel
    p.ramp(1.0 / perform.RATE_HZ)
    assert p.pan == 0.4


def test_the_sway_carries_the_pan():
    """The oscillator never wrote pan at all, which is why it felt like a
    missing axis rather than an unused one."""
    p = perf(shape="lean")
    p.pan = 25.0
    assert p.pose()["pan"] == 25.0


def test_the_amplitude_swells_rather_than_steps():
    """Changing it instantly moves the pose by the difference -- at the bottom
    of a sway, 6 to 15 degrees is a 9 degree jump in one frame, 450 deg/s, and
    it reads as a tick. One frame of ramp has to be small enough to be
    invisible."""
    dt = 1.0 / perform.RATE_HZ
    assert perform.AMP_DPS * dt < 0.5


def test_the_swell_takes_about_a_beat():
    """Short enough to be a gesture, long enough to be a crescendo."""
    p = perf(bpm=90.0)
    p.amp_i = 0
    p._amp = perform.AMPS[0]
    p.amp_i = 3
    dt, t = 1.0 / perform.RATE_HZ, 0.0
    while p._amp != p.amp_target and t < 5:
        p.ramp(dt)                       # the real one, not a copy of it
        t += dt
    assert 0.3 < t / p.period < 2.5, f"{t/p.period:.2f} beats"


def test_the_status_line_shows_what_is_moving_not_what_was_asked():
    """It reports `amp`, the value part way through the ramp, so the number on
    screen is the one in the neck."""
    p = perf(bpm=90.0)
    p.amp_i = 3
    p._amp = 6.0
    assert p.amp == 6.0
    assert p.amp_target != 6.0


def test_the_limiter_is_what_the_bang_reports():
    """At 90 BPM the cap is 12.7 degrees, so asking for 15 is limited -- and
    that has to be visible, because the key pressed and the motion produced are
    then different things."""
    p = perf(bpm=90.0)
    p.amp_i = 3
    assert p.amp_target < perform.AMPS[3] - 0.05
    p2 = perf(bpm=60.0)
    p2.amp_i = 3
    assert p2.amp_target == perform.AMPS[3]


# --------------------------------------------------------------------------- #
# the face on the CoreS3
# --------------------------------------------------------------------------- #
class FakeLink:
    def __init__(self):
        self.beats, self.leds, self.screens = [], [], []

    def beat(self, ms):
        self.beats.append(ms)

    def led(self, v):
        self.leds.append(v)

    def ui(self, name):
        self.screens.append(name)


def test_one_line_per_beat_and_no_more():
    """The board animates and the laptop keeps time. A screen wants 25 fps and
    the link cannot carry that -- so what goes over it is one short line a beat,
    however smooth the face is."""
    p = perf(bpm=120.0, t0=0.0)
    p.link, p.frozen = FakeLink(), False
    for k in range(int(2.0 * perform.RATE_HZ)):
        p._face(k / perform.RATE_HZ)
    assert len(p.link.beats) == 4          # 120 BPM, two seconds
    assert p.link.beats[0] == 500          # and it carries the period


def test_the_face_takes_no_lead():
    """Like the light: a screen has nothing to travel, and a face that bounces
    LEAD_S early is a face that is not on the beat."""
    p = perf(bpm=60.0, t0=0.0)
    p.link, p.frozen = FakeLink(), False
    # a beat falls at t0 + n*period in wall clock; the unshifted phase is what
    # crosses an integer there
    assert p.phase_now(1.0) == pytest.approx(1.0)
    assert p.phase(1.0) != pytest.approx(1.0)


def test_frozen_sends_nothing():
    """Frozen is the end of a phrase. A face still bouncing through it is not
    an ending."""
    p = perf(bpm=120.0, t0=0.0)
    p.link, p.frozen = FakeLink(), True
    for k in range(int(2.0 * perform.RATE_HZ)):
        p._face(k / perform.RATE_HZ)
    assert p.link.beats == []


# --------------------------------------------------------------------------- #
# the status line
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("frozen", [True, False])
@pytest.mark.parametrize("sound", [True, False])
@pytest.mark.parametrize("shape", ["nod", "lean", "dip"])
@pytest.mark.parametrize("pending", [None, (0.0, "S2_ACKNOWLEDGE", 0.0)])
def test_the_status_line_renders_in_every_state(frozen, sound, shape, pending):
    """It was one long format call, edited five times as fields were added, and
    the last edit dropped `pan` from the arguments while leaving its
    placeholder -- so a string landed on {:+4.0f} and the tool died on its first
    frame, after opening the servo bus and homing the neck.

    A format string is the one kind of code that looks right until it runs, so
    this renders it rather than reading it.
    """
    p = perf(bpm=93.7, shape=shape)
    p.frozen, p.sound, p.pending = frozen, sound, pending
    p.amp_i, p.trim, p.pan, p.line = 3, -6.0, -45.0, 3
    out = p.status()
    assert "93.7 BPM" in out
    assert shape in out
    assert ("FROZEN" in out) == frozen
    assert ("snd" in out) == sound
    assert "pan  -45" in out
    assert ("S2_ACKNOWLEDGE" in out) == (pending is not None)


def test_the_status_line_does_not_jump_about():
    """It is rewritten in place ten times a second. A field that changes width
    shuffles everything after it, which is unreadable while playing."""
    widths = set()
    for bpm in (60.0, 93.7, 140.0):
        for trim in (-18.0, 0.0, 27.0):
            for pan in (-60.0, 0.0, 65.0):
                p = perf(bpm=bpm)
                p.trim, p.pan = trim, pan
                p.frozen = False
                widths.add(len(p.status()))
    assert len(widths) == 1, f"the line changes width: {sorted(widths)}"


# --------------------------------------------------------------------------- #
# reading the keyboard
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("data,want", [
    ("\x1b[A", ["\x1b[A"]),               # up
    ("\x1b[B", ["\x1b[B"]),               # down
    ("f", ["f"]),
    ("ff", ["f", "f"]),                   # a key held down
    ("\x1b[A\x1b[A", ["\x1b[A", "\x1b[A"]),
    ("\x1b[Af", ["\x1b[A", "f"]),
    ("f\x1b[C", ["f", "\x1b[C"]),
    ("\x1b", ["\x1b"]),                   # a bare escape, not a sequence
    (" ", [" "]),
])
def test_a_burst_of_input_splits_into_whole_keys(data, want):
    """THE ARROWS WERE DEAD AND NOTHING LOOKED WRONG.

    sys.stdin is a buffered text stream: read(1) pulled the whole ESC [ A into
    Python's buffer, and the select() that followed looked at the file
    descriptor, which was now empty -- so the code concluded there was no
    sequence and returned a lone ESC, matching nothing. Letters worked, arrows
    could not, and the mistake is invisible in the source.

    Reading the fd gets the whole burst, and this splits it.
    """
    assert perform.split_keys(data) == want

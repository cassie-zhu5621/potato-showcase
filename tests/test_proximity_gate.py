"""The approach gate, tested against the ways it fails rather than the way it works.

Every test here is a demo-floor symptom first and a code path second. The happy
path -- someone walks up, it fires once -- is one test. The rest are the
behaviours that make a robot look broken in front of a room, and none of them
would show up in a hand test standing in front of the sensor for a minute.
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from session.proximity import Proximity, parse_dist


def feed(p, samples, t0=0.0, dt=0.05):
    """Run a list of mm readings through at a fixed rate; collect every event.

    THE CLOCK HAS TO BE THREADED between calls. Starting a second `feed` back at
    a round number is a silent time jump, and against a gate whose whole job is
    timing it produces a pass or a fail that is about the test, not the code --
    a two-sample dropout that "took" nine seconds reads as the person leaving,
    correctly. `feed` therefore returns the next timestamp; pass it on.
    """
    got, t = [], t0
    for mm in samples:
        for ev in p.update(t, mm):
            got.append((round(t, 3), ev))
        t += dt
    return got, t


def evs(got):
    return [e for _, e in got]


# --------------------------------------------------------------------------- #
# the one happy path
# --------------------------------------------------------------------------- #
def test_someone_walks_up_and_it_fires_exactly_once():
    p = Proximity()
    got, _ = feed(p, [1500] * 5 + [500] * 40)
    assert evs(got) == ["arrived"]


def test_walking_past_is_not_arriving():
    """The commonest event in a busy room is somebody crossing the beam on their
    way somewhere else. The dwell is the whole difference."""
    p = Proximity(dwell_s=0.4)
    got, _ = feed(p, [1500] * 5 + [500] * 3 + [1500] * 20)   # 0.15 s inside
    assert evs(got) == []


# --------------------------------------------------------------------------- #
# the symptoms
# --------------------------------------------------------------------------- #
def test_standing_on_the_boundary_does_not_make_the_head_bob():
    """THE symptom this module exists for. One threshold plus a person
    breathing at 60 cm = the head rising and falling forever, which reads as
    broken rather than as alive."""
    p = Proximity(enter_mm=600, exit_mm=900)
    got, _ = feed(p, [1500] * 5 + [595, 605, 598, 610, 590, 602] * 12)
    assert evs(got).count("arrived") == 1
    assert "left" not in evs(got), "hysteresis did not hold the person inside"


def test_a_crowd_does_not_retrigger_forever():
    """At a showcase 'somebody is near' is true almost continuously. A gate that
    re-arms on time alone fires every few seconds at whoever is closest."""
    p = Proximity(refractory_s=3.0)
    got, _ = feed(p, [500] * 400)          # 20 s of continuous presence
    assert evs(got).count("arrived") == 1


def test_it_re_arms_once_they_actually_leave():
    p = Proximity(refractory_s=1.0)
    walk_up = [500] * 20
    walk_off = [1500] * 40
    got, _ = feed(p, walk_up + walk_off + walk_up)
    assert evs(got) == ["arrived", "left", "arrived"]


def test_leaving_and_coming_straight_back_does_not_double_fire():
    """Someone steps back to let a friend see, then leans in again. Inside the
    refractory that is one visit, not two."""
    p = Proximity(refractory_s=3.0)
    got, _ = feed(p, [500] * 20 + [1500] * 6 + [500] * 20)
    assert evs(got).count("arrived") == 1


# --------------------------------------------------------------------------- #
# the sensor misbehaving
# --------------------------------------------------------------------------- #
def test_a_single_wild_sample_does_not_trigger_the_flinch():
    """A ToF's bad readings are wild, not noisy. One 40 mm reflection through a
    mean drags it past the near threshold and the robot flinches at nothing."""
    p = Proximity()
    got, _ = feed(p, [500] * 10 + [40] + [500] * 10)
    assert "too_close" not in evs(got)


def test_a_dropped_reading_is_not_a_distance():
    """None must never be read as 0 (a face against the lens) or as infinity
    (the room emptied). Both are wrong and both are dramatic."""
    p = Proximity()
    _, t = feed(p, [500] * 20)
    got, _ = feed(p, [None] * 2, t0=t)          # a brief dropout: 0.1 s
    assert evs(got) == [], "a short dropout must not empty the room"
    assert p.inside


def test_a_long_dropout_does_eventually_mean_gone():
    p = Proximity(lost_s=0.5)
    _, t = feed(p, [500] * 20)
    got, _ = feed(p, [None] * 40, t0=t)         # 2 s of nothing
    assert "left" in evs(got)


def test_out_of_range_arrives_as_none_not_as_minus_one():
    """`IN DIST -1` compared against a threshold is not obviously wrong -- it
    is just a very small number, and it reports a face against the lens."""
    assert parse_dist("IN DIST -1") is None
    assert parse_dist("IN DIST 612") == 612
    assert parse_dist("IN DIST") is None
    assert parse_dist("IN BODYTAP") is None
    assert parse_dist("IN DIST nonsense") is None
    # EVT is the host talking TO the board. A reading arriving that way is a
    # firmware bug, and must not be quietly accepted as if it were a reading.
    assert parse_dist("EVT DIST 612") is None


# --------------------------------------------------------------------------- #
# the two bands are one axis
# --------------------------------------------------------------------------- #
def test_a_hand_is_inside_the_person_band_not_instead_of_it():
    """They are consecutive beats of one story -- it looks up at you, you keep
    coming, it pulls back -- not two competing triggers."""
    p = Proximity()
    got, _ = feed(p, [1500] * 5 + [500] * 20 + [150] * 20)
    assert evs(got) == ["arrived", "too_close"]
    assert p.inside and p.near


def test_the_hand_going_away_does_not_end_the_visit():
    p = Proximity()
    got, _ = feed(p, [1500] * 5 + [500] * 20 + [150] * 10 + [500] * 20)
    assert evs(got) == ["arrived", "too_close", "backed_off"]
    assert p.inside


def test_leaving_from_inside_the_shy_band_reports_both():
    """Snatching a hand away and walking off is one motion. Neither flag may be
    left set, or the next visitor meets a robot that thinks it is being touched."""
    p = Proximity()
    _, t = feed(p, [1500] * 5 + [500] * 20 + [150] * 20)
    got, _ = feed(p, [1500] * 20, t0=t)
    assert set(evs(got)) == {"left", "backed_off"}
    assert not p.inside and not p.near


# --------------------------------------------------------------------------- #
# configuration that is a bug rather than a choice
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("kw", [
    {"enter_mm": 600, "exit_mm": 600},        # equal = the flapping bug
    {"enter_mm": 600, "exit_mm": 400},        # inverted
    {"near_mm": 250, "near_exit_mm": 250},
    {"near_mm": 700, "enter_mm": 600},        # shy band outside the person band
])
def test_thresholds_that_cannot_work_are_refused_at_construction(kw):
    with pytest.raises(ValueError):
        Proximity(**kw)


def test_reset_forgets_everything():
    p = Proximity()
    _, t = feed(p, [500] * 20)
    p.reset()
    assert not p.inside and p.distance is None
    assert evs(feed(p, [500] * 20, t0=t)[0]) == ["arrived"]

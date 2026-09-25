"""The gate, replayed against a recorded session rather than against invented numbers.

`tests/data/walkups.csv` is 139 s from the sensor on its bracket: 2953 samples,
2.3% dropped, one person walking up, holding still, leaning, reaching a hand in,
stepping back, leaving, and finally crossing in front WITHOUT stopping.

THE LAST ONE IS WHY THIS FILE EXISTS. The walk-past spends 1.03 s inside 600 mm
and comes as close as 236 mm on the way through, and the dwell was guessed at
0.4 s -- so before this trace was recorded, somebody walking to the coffee
machine made the robot look up at them and then flinch away. Synthetic samples
did not catch it because the guess that produced the threshold also produced
the test.

So this asserts against the recording, and if the thresholds are ever re-tuned
it is the thing that says whether they still work on a real person.
"""
from __future__ import annotations

import csv
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from session.proximity import Proximity

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TRACE = os.path.join(DATA, "walkups.csv")
TRACE2 = os.path.join(DATA, "take2.csv")

# Read off the trace, not off the script: segment boundaries in seconds.
HOLDING_STILL = (31.4, 54.5)     # stopped in front of it, not moving
HAND_IN = (71.0, 80.0)           # a hand held right up to the sensor
WALK_PAST = (110.0, 115.0)       # crossing in front without stopping
EMPTY_TAIL = (117.5, 139.6)      # nobody in the room


@pytest.fixture(scope="module")
def events():
    rows = []
    with open(TRACE) as f:
        for r in csv.reader(f):
            if not r or r[0] == "t":
                continue
            rows.append((float(r[0]), None if r[1] in ("", "-1") else float(r[1])))
    assert len(rows) > 2000, "the trace is truncated"
    g, out = Proximity(), []
    for t, mm in rows:
        for e in g.update(t, mm):
            out.append((t, e))
    return out


def within(events, span, name):
    a, b = span
    return [t for t, e in events if e == name and a <= t <= b]


# --------------------------------------------------------------------------- #
def test_the_walk_past_is_not_an_arrival(events):
    """1.03 s inside 600 mm, 236 mm at its closest. At the guessed 0.4 s dwell
    this fired `arrived`, and the robot greeted somebody walking to the coffee
    machine."""
    assert within(events, WALK_PAST, "arrived") == []


def test_walking_up_and_stopping_is(events):
    assert len(within(events, (25.0, 40.0), "arrived")) == 1


def test_the_hand_registers_as_too_close(events):
    assert within(events, HAND_IN, "too_close")


def test_the_hand_does_not_end_the_visit(events):
    """Reaching in and taking the hand away is one continuous visit. A `left`
    in the middle of it would send the robot back to idle with the person still
    standing there."""
    assert within(events, HAND_IN, "left") == []


def test_nothing_happens_in_an_empty_room(events):
    """The far wall reads 1844 mm and never once dropped under 1500. If any
    event fires here the thresholds are inside the room's own furniture."""
    assert [e for t, e in events if EMPTY_TAIL[0] <= t <= EMPTY_TAIL[1]] == []


def test_the_whole_session_is_a_readable_story(events):
    """Three approaches, and each one is somebody deliberately coming nearer:
    the walk-up at 33 s, coming back at 59 s after stepping away, and the hand
    put right up to the sensor at 73 s.

    The hand counts now. It did not when a floor sat under arriving at 250 mm,
    which meant the one gesture guaranteed to get no reaction was reaching out
    to the robot -- so the floor went. `too_close` still fires alongside; it is
    what R_SHY will read when R_SHY exists.

    What must NOT happen is firing repeatedly while somebody simply stands
    there: wrong in no single instant, and useless over an hour.
    """
    assert [e for _, e in events].count("arrived") == 3
    # She walked up at 31.4 and stood until 54.5. Exactly one arrival in that
    # stretch -- the window opens at 31 rather than 33 because the arrival
    # moved earlier when the latency was cut, and a bound written around the
    # old timing is a test of the old timing.
    assert len([t for t, e in events if e == "arrived" and 31.0 <= t <= 54.0]) == 1


def test_every_too_close_is_paired_with_a_backed_off(events):
    """An unpaired one leaves the flag set, and the next visitor meets a robot
    that already thinks it is being touched."""
    depth = 0
    for _, e in events:
        if e == "too_close":
            depth += 1
        elif e == "backed_off":
            depth -= 1
        assert depth in (0, 1), "too_close and backed_off got out of step"
    assert depth == 0, "the trace ends with the robot still flinching"


# --------------------------------------------------------------------------- #
# THE HELD-OUT TAKE. walkups.csv fitted the thresholds, so it cannot also test
# them. take2.csv was recorded afterwards, against the tuned gate, and it is the
# one that found something: standing 8 s at 1050 mm went unnoticed, because
# ENTER was 1000. That is the failure a showcase cannot afford -- somebody stops
# a metre away to look and the robot ignores them -- and no amount of replaying
# the fitting trace would have shown it.
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def events2():
    rows = []
    with open(TRACE2) as f:
        for r in csv.reader(f):
            if not r or r[0] == "t":
                continue
            rows.append((float(r[0]), None if r[1] in ("", "-1") else float(r[1])))
    assert len(rows) > 4000, "the held-out trace is truncated"
    g, out = Proximity(), []
    for t, mm in rows:
        for e in g.update(t, mm):
            out.append((t, e))
    return out


def test_held_out_take_has_exactly_three_arrivals(events2):
    """Three, and the third is a correction rather than a regression.

    She stopped at 1109 mm (t=93), then walked right up to 336 mm (t=103), then
    later stopped again at 925 mm (t=188). Those are three separate approaches
    and the robot should attend to each. The threshold-crossing version this
    replaced reported two, because once it was inside it could not see her come
    closer -- it was losing an event, not suppressing a duplicate."""
    assert [e for _, e in events2].count("arrived") == 3


def crowd(path, floor):
    """The trace with somebody ALREADY standing at `floor` mm and never leaving.

    A ToF reports the nearest thing, so another person in front of the sensor
    is exactly a ceiling on every reading. Synthetic, but synthesised from a
    real recording rather than invented: everything she did still happens, on
    top of somebody who was there first.
    """
    rows = []
    with open(path) as f:
        for r in csv.reader(f):
            if not r or r[0] == "t":
                continue
            mm = None if r[1] in ("", "-1") else float(r[1])
            rows.append((float(r[0]), None if mm is None else min(mm, floor)))
    g, out = Proximity(), []
    for t, mm in rows:
        for e in g.update(t, mm):
            out.append((t, e))
    return out


def test_an_approach_is_still_seen_when_somebody_is_already_there():
    """THE SHOWCASE CASE, and the one that broke the first design.

    Re-arming used to require going OUT past exit_mm. In a crowd the nearest
    thing never is, so the first person within range was noticed and nobody
    after them ever was -- replayed with one person at 700 mm, her approach at
    t=33 s disappeared entirely. Arriving is a settle nearer than the last one
    now, which does not care whether the room was empty.
    """
    ev = crowd(TRACE, 700.0)
    assert [t for t, e in ev if e == "arrived" and 30.0 <= t <= 40.0]


def test_the_crowd_limit_is_physical_and_is_written_down():
    """At 400 mm the person already standing is nearer than she ever gets, so
    her arrival is a 37 mm change -- smaller than the 61 mm she leaned by. No
    threshold separates those, and this asserts the limit rather than pretending
    it is not there: the robot is attending to whoever is in front, which is the
    tolerable way to be wrong."""
    ev = crowd(TRACE, 400.0)
    assert [t for t, e in ev if e == "arrived" and t < 10.0]
    assert [t for t, e in ev if e == "arrived" and 30.0 <= t <= 40.0] == []


def test_someone_who_stops_a_metre_away_is_noticed(events2):
    """She stood at 1050 mm for 8 s from t=91. At the fitted ENTER of 1000 this
    produced nothing at all until she stepped closer at t=99 -- the one thing
    the held-out take was recorded to find."""
    assert any(91.0 <= t <= 95.0 for t, e in events2 if e == "arrived")


def test_the_far_passes_are_not_arrivals(events2):
    """Four crossings between t=139 and t=185, none closer than 1018 mm and
    none longer than 1.33 s. Adding a stillness test made these fire until a
    dwell was kept as well: at its closest point a pass stops changing distance,
    so for a few hundred ms it looks exactly like standing."""
    for a, b in ((139.0, 149.0), (176.0, 185.0)):
        assert [t for t, e in events2 if e == "arrived" and a <= t <= b] == []

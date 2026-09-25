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

TRACE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "walkups.csv")

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
    """Two approaches -- she stepped away at 54 s and came back at 60 s -- and
    they are the only two. A gate that fires five times on one visit is not
    wrong in any single instant and is useless over an hour."""
    assert [e for _, e in events].count("arrived") == 2


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

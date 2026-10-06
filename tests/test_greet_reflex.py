"""R_GREET: it answers being looked at.

`truth[3]` -- eye_contact -- has been computed every frame since the relation
engine was written, and was only ever read as a row in somebody's watch-spec.
Catching the robot's eye while it works is the commonest thing a visitor tries
and the robot had no answer to it at all.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import robot.states as ST

SRC = open(os.path.join(ROOT, "noticebot_loop.py")).read()
BLOCK = SRC[SRC.index("# R_GREET"):SRC.index("# R_GREET") + 2200]


def test_it_is_a_reflex_and_never_a_state():
    """`R_*` never enters the state machine's numbering. S0-S7 is a closed set
    of eight and it is drawn in the paper -- the moment a showcase beat becomes
    S8 the figure and the code start diverging again."""
    # THE NUMBERING is the closed set, not the key count: S4 and S5 each split
    # into A/B, so the table has ten entries across eight numbers. A reflex
    # that crept in would show up as an S8, which is the thing
    # docs/STATE_NAMES.md was written to end.
    import re
    assert "R_GREET" not in ST.STATES
    nums = {int(re.match(r"S(\d)", k).group(1)) for k in ST.STATES}
    assert nums == set(range(8)), nums
    code = "\n".join(l for l in BLOCK.split("\n")
                     if not l.strip().startswith("#"))
    assert "player.request(" not in code, "a named state here is a transition"
    assert "drive_deg" not in code, \
        "S4B_WATCH loops a clip and drive_deg is not safe during one"


def test_it_only_answers_while_it_is_watching():
    """Not during a report, not during the scan, not while it is being asked
    something -- those all have the visitor's attention already."""
    assert 'flow.state == "S4B_WATCH"' in BLOCK


def test_one_frame_of_eye_contact_is_not_a_greeting():
    assert ST.GREET_FRAMES >= 2
    assert 'greet["n"] >= ST.GREET_FRAMES' in BLOCK
    assert 'greet["n"] = greet["n"] + 1 if met else 0' in BLOCK, \
        "the streak has to reset, or any two frames ever count"


def test_it_fires_once_per_person_not_once_per_frame():
    assert ST.GREET_REFRACTORY_S >= 3
    assert "now - greet[\"at\"] > ST.GREET_REFRACTORY_S" in BLOCK


def test_the_borrowed_colour_is_given_back():
    """Hue is sent on state CHANGE, so a borrowed one that is not returned
    stays borrowed until the next transition -- and the light is the channel
    that carries `still here`."""
    # BOTH HALVES, because only one of them was guarded and the missing half
    # is the one that matters: borrowing is visible, failing to give back is
    # a light that stays wrong until the next transition.
    assert 'greet["restore"] = now + ST.GREET_FLASH_S' in BLOCK, "borrowed"
    assert 'greet["restore"] = None' in BLOCK, "and released"
    assert "link.hue(" in BLOCK.split('greet["restore"] = None')[1], \
        "releasing without re-sending a hue leaves the borrowed one on"
    assert "ST.STATES.get(flow.state)" in BLOCK, \
        "take it from the state table, not a hard-coded 'cool'"
    assert 0 < ST.GREET_FLASH_S < ST.GREET_REFRACTORY_S


def test_the_missing_nod_is_recorded_as_a_player_limit():
    """It should be a single S2-style accent and is not, because S4B_WATCH is
    `loop: True` and there is no way to interrupt a looping clip and resume it.
    Written down so the next person does not rediscover it by jamming the bus
    the night before a demo."""
    assert ST.STATES["S4B_WATCH"]["loop"] is True
    src = open(os.path.join(ROOT, "robot", "states.py")).read()
    i = src.index("GREET_REFRACTORY_S")
    why = src[max(0, i - 1400):i]
    assert "loop" in why and "drive_deg" in why

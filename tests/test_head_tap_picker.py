"""Choosing by tapping the robot on the head.

A tablet is not an encounter with a robot, and a stranger at a loud stand will
not speak into a laptop microphone either. Touching the thing itself is the one
input that is about the robot, needs no language, and cannot be drowned out.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import robot.states as ST
from webui.booth import PAGE, PRESETS

SRC = open(os.path.join(ROOT, "noticebot_loop.py")).read()


def test_the_tap_is_taken_only_while_it_is_asking():
    """One gesture, two meanings, and they cannot collide: the flow already
    ignores `tap` anywhere but S4B_WATCH, where it means `not that one`. So
    the picker takes it in S1_ATTEND without the flow learning anything."""
    i = SRC.index('elif "BODYTAP" in line and flow.state == "S1_ATTEND":')
    assert SRC.index('elif "BODYTAP" in line:') > i, \
        "the Attend branch must come first or the flow swallows it"
    flow_src = open(os.path.join(ROOT, "session", "session_flow.py")).read()
    j = flow_src.index('if ev == "tap":')
    assert 'self.state == "S4B_WATCH"' in flow_src[j:j + 400], \
        "the flow must still ignore taps outside watching"


def test_nothing_commits_until_something_is_tapped():
    """`at is None` until the first tap, which is what keeps `touched nothing`
    distinguishable from `resting on the first one`. A visitor who touches
    nothing gets ATTEND_MAX_S and the robot sleeps -- the rule that says
    standing there is not asking for anything."""
    assert '"i": 0, "at": None' in SRC
    i = SRC.index('pick["at"] is not None and flow.state == "S1_ATTEND"')
    assert "PICK_COMMIT_S" in SRC[i:i + 200]


def test_a_pause_is_the_confirmation():
    """A confirm button would need teaching, and a second palm is refused by
    the wake's own refractory. Stopping is what somebody does anyway the moment
    they see the one they want."""
    assert 0 < ST.PICK_COMMIT_S <= 5
    assert ST.PICK_COMMIT_S < ST.ATTEND_MAX_S, \
        "it has to commit before the robot gives up and sleeps"


def test_the_taps_cycle_and_wrap():
    """Four presets and no way to go back means wrapping is the only way to
    reach one you have passed."""
    i = SRC.index('pick["i"] = ')
    assert "% n" in SRC[i:i + 120], "wrap, or the fourth tap is a dead end"
    assert "len(PRESETS)" in SRC[i - 200:i]


def test_the_loop_and_the_page_walk_the_same_list():
    """The tablet's highlight and the robot's choice are the same index into
    the same list, imported rather than copied -- two lists would drift and the
    screen would name something the robot did not choose."""
    assert "from webui.booth import PRESETS" in SRC
    assert len(PRESETS) >= 2


def test_the_tablet_stops_pretending_to_be_an_input():
    """A card that looks tappable and is not is worse than one that does not.
    The choice is made on the robot."""
    assert "onpointerdown=\"pick(" not in PAGE
    assert "touch its head to move down the list" in PAGE
    assert "S.pick_i" in PAGE and "S.pick_on" in PAGE


def test_it_works_without_the_web_ui_at_all():
    """--no-serve is how this gets debugged at a bench, and a selector that
    silently does nothing there would be found at the stand."""
    i = SRC.index('print(f"[pick] committed:')
    block = SRC[i:i + 700]
    assert "else:" in block and 'transcripts.append(("typed", chosen))' in block


def test_the_selection_does_not_survive_the_visit():
    """The next person must not inherit a highlight that is one pause away from
    being submitted as theirs."""
    assert 'if flow.state != "S1_ATTEND" and pick["at"] is not None:' in SRC


def test_it_says_touch_rather_than_tap():
    """TAP_SRC is 1: a TTP223 capacitive pad, not the IMU's knock detector. A
    visitor told to tap will hit it, which a capacitive pad reads worse than a
    finger resting for a moment -- and `TAP_G`, the knock threshold, does
    nothing on this path at all."""
    ino = open(os.path.join(ROOT, "robot", "firmware", "cores3_sidekick",
                            "cores3_sidekick.ino")).read()
    assert re.search(r"#define TAP_SRC\s+1\b", ino), \
        "if this becomes 2 the wording below should go back to `tap`"
    body = PAGE[PAGE.index("<body>"):]
    visible = re.sub(r"<[^>]+>", " ", body)
    visible = "\n".join(l for l in visible.split("\n")
                         if not l.strip().startswith("//")).lower()
    assert "touch its head" in visible
    assert "tap its head" not in visible and "tap the robot" not in visible


def test_the_addresses_are_printed_where_they_can_be_read():
    """webui.server prints them when it binds -- before Whisper, the detector
    and Gemini -- so by the time the robot is ready they are a hundred lines up
    and under CV output. standing_prompt.py used to re-print them from the
    second window, and that window is gone."""
    assert SRC.count("def addresses(") == 1
    assert 'addresses("ready")' in SRC
    i = SRC.index('addresses("ready")')
    j = SRC.index('beat = {"t": time.time()')
    assert i < j, "printed last, after everything slow has loaded"
    assert SRC.count("addresses(") >= 3, "and again on the way out"


def test_the_list_shows_where_it_stands_before_anything_is_touched():
    """A screen that looks inert until the first touch cannot teach the gesture
    that is about to be the only way in. And the first touch used to SELECT the
    first line, so it read as `one touch decides` -- the opposite of a thing
    you are invited to keep doing. Now every touch does the same thing."""
    i = SRC.index('pick["i"] = (pick["i"] + 1) % n')
    assert 'pick["at"] is None' not in SRC[i - 300:i + 200], \
        "the first touch must move the highlight like every other one"
    assert "k===i?' on':' dim'" in PAGE, \
        "the highlight is drawn whether or not anything has been touched"


def test_the_window_is_visible_while_it_drains():
    """The missing half. Three seconds is only long enough to notice if
    something on screen says it is running; otherwise the first touch still
    looks like a decision, which is how it read in the hand."""
    assert "pick_left" in PAGE and ".cdown" in PAGE
    from webui.booth import booth_state
    import time as _t
    st = {"flow_state": "S1_ATTEND", "pick_at": _t.time(), "pick_commit_s": 3.0}
    d = booth_state(st, [], None)
    assert 0.5 < d["pick_left"] <= 1.0, "a fresh touch is a full bar"
    st["pick_at"] = _t.time() - 2.9
    assert booth_state(st, [], None)["pick_left"] < 0.2, "and it drains"
    assert booth_state({"flow_state": "S1_ATTEND"}, [], None)["pick_left"] == 0.0


def test_the_touch_feedback_is_not_a_state():
    """IT ASKED FOR S2_ACKNOWLEDGE AS A BIT OF FEEDBACK -- a nod, which is what
    the gesture deserves. S2_ACKNOWLEDGE is a STATE, authored with
    `then="S3_SCAN"`, so the nod finished, the player announced its landing and
    the flow went off to sweep. One touch, straight into the scan, with
    whatever happened to be highlighted.

    The rule was already in the file, four hundred lines down: an EVENT into
    the flow, never player.request(). It holds for feedback too -- the
    acknowledgement of a touch is not a transition, and anything that moves the
    neck through a named state is one."""
    i = SRC.index('elif "BODYTAP" in line and flow.state == "S1_ATTEND":')
    block = SRC[i:SRC.index('elif "BODYTAP" in line:', i)]
    # COMMENTS STRIPPED FIRST. The reasoning for this rule is written inside
    # the block and quotes the call it forbids, so a raw substring search
    # matches the explanation and fails on a correct file -- a test that can
    # only be satisfied by deleting its own reason.
    code = "\n".join(l for l in block.split("\n")
                      if not l.strip().startswith("#"))
    assert "player.request(" not in code, \
        "a named state here is a transition, whatever it was meant as"
    assert "link.sfx(" in code, "it still has to answer the touch"

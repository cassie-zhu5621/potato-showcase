"""Four modes, one board, and nothing optional in the firmware resets itself.

Every switch the firmware has persists until the board is power-cycled. So a
demo run leaves the approach gate armed, a bring-up run leaves the distance
stream flooding whatever reads the port next, and a performance leaves a face
on the screen. Asking each mode to tidy up on the way OUT is the arrangement
that fails the first time one is killed with Ctrl-C -- which is how every
session ends.

So each mode SETS what it wants on the way IN, and these tests hold that: every
tool claims the board, and every claim says all three, including the offs.
"""
from __future__ import annotations

import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from session.cores3_link import FIRMWARE_V, CoreS3Link, _older

# tool -> what it should be claiming
MODES = {
    "robot/tools/perform.py": dict(dist=False, approach=False, face=True),
    "robot/tools/attend_test.py": dict(dist=True, approach=False, face=False),
    "robot/tools/tof_test.py": dict(dist=True, approach=False, face=False),
    "noticebot_loop.py": dict(dist=False, face=False),   # approach is a flag
}


class Recorder:
    """A link that writes down what was asked of the board."""

    def __init__(self):
        self.sent = []

    def event(self, cmd, arg=""):
        self.sent.append((cmd, str(arg)))

    approach = CoreS3Link.approach
    dist = CoreS3Link.dist
    ui = CoreS3Link.ui
    claim = CoreS3Link.claim


@pytest.mark.parametrize("path", sorted(MODES))
def test_every_mode_claims_the_board(path):
    src = open(os.path.join(ROOT, path)).read()
    assert "link.claim(" in src or ".claim(" in src, f"{path} never claims"


def test_a_claim_says_all_three_including_the_offs():
    """A default that is currently right is a default that stops being said,
    and then it stops being right."""
    r = Recorder()
    r.claim()
    cmds = [c for c, _ in r.sent]
    assert "APPROACH" in cmds and "DIST" in cmds and "UI" in cmds


@pytest.mark.parametrize("kw,want", [
    (dict(), {"APPROACH": "0", "DIST": "0", "UI": "idle"}),
    (dict(face=True), {"APPROACH": "0", "DIST": "0", "UI": "perform"}),
    (dict(dist=True), {"APPROACH": "0", "DIST": "1", "UI": "idle"}),
    (dict(approach=True), {"APPROACH": "1", "DIST": "0", "UI": "idle"}),
])
def test_a_claim_sets_exactly_what_was_asked(kw, want):
    r = Recorder()
    r.claim(**kw)
    assert dict(r.sent) == want


def test_the_performance_turns_the_approach_gate_OFF():
    """The one that would actually bite: run the demo, then the performance,
    and without this the board is still pressing its own button through it."""
    r = Recorder()
    r.claim(face=True)
    assert ("APPROACH", "0") in r.sent


# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("board,warn", [
    ("v7", True), ("v8", True), ("v9", False), ("v10", False),
    ("v11", False), (None, True), ("weird", True), ("", True),
])
def test_only_an_OLDER_board_is_worth_a_warning(board, warn):
    """The firmware is shared and grows by addition -- a feature arrives off
    and only the mode that wants it asks -- so a board ahead of this checkout
    understands everything it will be sent.

    Warning about that would cry wolf every time any one mode was reflashed,
    which is the fastest way to teach someone to ignore the warning that
    matters.
    """
    assert _older(board, FIRMWARE_V) is warn


def test_the_firmware_version_matches_the_sketch():
    """They are edited in two files and the check is worthless if they drift."""
    ino = open(os.path.join(ROOT, "robot", "firmware", "cores3_sidekick",
                            "cores3_sidekick.ino")).read()
    vers = set(re.findall(r"cores3_sidekick (v\d+)", ino))
    assert vers == {FIRMWARE_V}, f"sketch says {vers}, link expects {FIRMWARE_V}"

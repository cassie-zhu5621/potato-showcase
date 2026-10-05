"""Four modes, one board, and nothing optional in the firmware resets itself.

Every switch the firmware has persists until the board is power-cycled. So a
demo run leaves the approach gate armed, a bring-up run leaves the distance
stream flooding whatever reads the port next, and a performance leaves a face
on the screen. Asking each mode to tidy up on the way OUT is the arrangement
that fails the first time one is killed with Ctrl-C -- which is how every
session ends.

So each mode SETS what it wants on the way IN, and these tests hold that: every
tool claims the board, and every claim says all FOUR, including the offs.
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

    _WAKE = CoreS3Link._WAKE
    approach = CoreS3Link.approach
    dist = CoreS3Link.dist
    ui = CoreS3Link.ui
    volume = CoreS3Link.volume
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
    for c in ("APPROACH", "DIST", "UI", "VOL"):
        assert c in cmds, c


@pytest.mark.parametrize("kw,want", [
    (dict(), {"APPROACH": "0", "DIST": "0", "UI": "idle", "VOL": "100"}),
    (dict(face=True), {"APPROACH": "0", "DIST": "0", "UI": "perform", "VOL": "100"}),
    (dict(dist=True), {"APPROACH": "0", "DIST": "1", "UI": "idle", "VOL": "100"}),
    (dict(approach=True), {"APPROACH": "1", "DIST": "0", "UI": "idle", "VOL": "100"}),
    # MUTE IS A CLAIM LIKE ANY OTHER, which is the point: a board left at 0 by
    # a --mute run is a robot with no voice and nothing on screen to say so.
    # The next mode says 100 on the way in and it comes back.
    (dict(volume=0), {"APPROACH": "0", "DIST": "0", "UI": "idle", "VOL": "0"}),
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
    ("v7", True), ("v8", True), ("v9", True), ("v10", True), ("v11", True), ("v12", True), ("v13", True), ("v14", False),
    ("v15", False), (None, True), ("weird", True), ("", True),
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


def test_the_demo_warns_when_it_can_never_call():
    """`--feedback console` is the study's right default and the demo's silent
    death: every stage works, the judge confirms, [FEEDBACK] prints, and the
    robot never calls. Warned at startup, not overridden -- a flag that quietly
    means something else in the presence of another flag is a worse trap."""
    src = open("noticebot_loop.py").read()
    i = src.index("[cores3] wake ARMED")
    block = src[i:i + 1400]
    assert 'a.feedback != "robot"' in block
    assert "NEVER CALL" in block


def test_the_runbooks_pass_feedback_robot():
    """The demo command is the STUDY command plus --approach, and the study
    command is the one that has actually run a session. Assembling it from the
    flags that seem necessary is how --feedback robot went missing: every stage
    worked, the judge confirmed, and the robot never called.

    Checked over the whole fenced block, not per line -- the command is written
    across several lines now, and a per-line test passes vacuously on it, which
    is worse than no test.
    """
    import re
    for path in ("docs/SHOWDAY.md", "docs/DEMO_VLM_RUNBOOK.md"):
        blocks = re.findall(r"```bash\n(.*?)```", open(path).read(), re.S)
        demo = [b for b in blocks
                if "noticebot_loop.py" in b and "--approach" in b]
        assert demo, f"{path}: no demo command at all"
        for b in demo:
            for flag in ("--feedback robot", "--detector yoloworld", "--serve"):
                assert flag in b, f"{path} is missing {flag}:\n{b}"


# --------------------------------------------------------------------------- #
# "did not arrive" must READ the voltage, not nominate it.
# --------------------------------------------------------------------------- #
def test_a_low_bus_voltage_is_named_not_nominated():
    """The old line listed three suspects and left the commonest one to a
    multimeter nobody fetches mid-session. The servo knows -- register 62 --
    and the reading is worth most right after the move that failed, because by
    the time it is at rest it has recovered."""
    import inspect
    from robot import clip_player as cp
    src = inspect.getsource(cp.ClipPlayer)
    i = src.index("did not arrive")
    block = src[max(0, i - 1400):i + 200]
    assert "read_voltage" in block, "it must read, not guess"
    assert "THE SUPPLY" in block and "which is fine" in block, \
        "both verdicts, or the line still needs interpreting"
    assert "except Exception" in block, \
        "an unreadable bus must not turn a failed move into a crash"


def test_mute_does_not_outlive_the_run_that_asked_for_it():
    """The switch most likely to be left behind. --mute is for testing beside
    people who are working; a board left at 0 afterwards is a robot that has
    lost its voice with nothing on screen to say why, and the obvious place to
    look -- the mode you are now running -- is not where it was set."""
    muted = Recorder(); muted.claim(volume=0)
    assert ("VOL", "0") in muted.sent
    after = Recorder(); after.claim()
    assert ("VOL", "100") in after.sent, "the next mode must say it out loud"


def test_a_muted_run_does_not_claim_to_have_played_sounds():
    """Counting a sound that was suppressed ends the run with `sounds: 23` and
    sends the next reader of the log looking for a speaker fault."""
    src = open(os.path.join(ROOT, "noticebot_loop.py")).read()
    i = src.index("def on_sfx")
    block = src[i:i + 700]
    assert "a.mute" in block
    assert block.index("a.mute") < block.index('counts["sfx"] += 1'), \
        "the counter must come after the mute check, not before"


def test_a_spoken_line_gives_the_volume_back():
    """SAY set 255 and left it there, so one `V` in a performance re-tuned every
    chirp after it -- and now that --mute exists it could un-mute a session."""
    ino = open(os.path.join(ROOT, "robot", "firmware", "cores3_sidekick",
                            "cores3_sidekick.ino")).read()
    i = ino.index("playWav(VOICE_WAV")
    block = ino[max(0, i - 500):i + 300]
    assert "getVolume()" in block, "it has to know what to give back"
    assert "setVolume(was)" in block, "and give it back"
    assert "was ? 255 : 0" in block, "muted stays muted"


# --------------------------------------------------------------------------- #
# Walking away is not an error, and is not a cancellation either.
# --------------------------------------------------------------------------- #
def test_the_board_says_when_a_visitor_woke_it_and_left():
    """From the flow's side, somebody who left and somebody standing there
    thinking are the same silence -- and that silence ends in S7_ERROR,
    performed to an empty table. Only the sensor can tell them apart."""
    ino = open(os.path.join(ROOT, "robot", "firmware", "cores3_sidekick",
                            "cores3_sidekick.ino")).read()
    i = ino.index("void checkApproach")
    block = ino[i:ino.index("void serviceApproach")]
    assert 'Serial.println("IN LEFT")' in block
    assert "apprWoke" in block, \
        "only a visit that actually pressed the button can have left one"


def test_leaving_is_ignored_once_a_request_exists():
    """The point of this robot is that it watches while you get on with
    something. `I left the room` is the NORMAL case for a delegated task, not a
    cancellation -- so this is gated on the flow state, not on the sensor."""
    src = open(os.path.join(ROOT, "noticebot_loop.py")).read()
    i = src.index('elif "IN LEFT" in line:')
    block = src[i:i + 1600]
    assert 'flow.state == "S1_ATTEND"' in block
    j = block.index('events.append("stop")')
    assert block.index('flow.state == "S1_ATTEND"') < j, \
        "the state check must come first, or leaving discards a live task"


# --------------------------------------------------------------------------- #
# The wake is a MODE, and palm is the showcase's.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("asked,want", [
    (False, "0"), (None, "0"), ("off", "0"),
    (True, "1"), ("approach", "1"),
    ("palm", "2"),
])
def test_the_wake_mode_reaches_the_board_as_a_number(asked, want):
    r = Recorder()
    r.approach(asked)
    assert ("APPROACH", want) in r.sent


def test_an_unknown_wake_mode_is_refused_rather_than_silently_off():
    """`approach("plam")` mapping to 0 would be a demo that never wakes and
    never says why -- the exact shape of the --feedback console evening."""
    r = Recorder()
    with pytest.raises(ValueError):
        r.approach("plam")


def test_palm_is_the_default_and_approach_is_still_reachable():
    src = open(os.path.join(ROOT, "noticebot_loop.py")).read()
    i = src.index('"--wake"')
    block = src[i:i + 600]
    assert '"palm", "approach"' in block and 'default="palm"' in block


def test_the_palm_gate_refuses_a_saturated_zero():
    """A lens with something flat against it, or still wearing its film, reads
    0. A metre from the approach threshold that is harmless noise; at 250 mm it
    is a permanent wake, and the robot greets an empty table all day."""
    ino = open(os.path.join(ROOT, "robot", "firmware", "cores3_sidekick",
                            "cores3_sidekick.ino")).read()
    block = ino[ino.index("void checkApproach"):ino.index("void serviceApproach")]
    assert "palm && mm == 0" in block
    assert "(palm ? 0 : -1)" in block, \
        "and a zero must not refresh the near-clock either, or it never leaves"


def test_palm_uses_a_shorter_dwell_than_a_walking_body():
    """700 ms exists to let a walking body settle. A hand is already where it
    is going; 300 ms rejects a sleeve going past and still feels immediate."""
    ino = open(os.path.join(ROOT, "robot", "firmware", "cores3_sidekick",
                            "cores3_sidekick.ino")).read()
    import re
    palm = int(re.search(r"PALM_DWELL = (\d+)", ino).group(1))
    appr = int(re.search(r"APPR_DWELL = (\d+)", ino).group(1))
    assert palm < appr
    enter = int(re.search(r"PALM_ENTER = (\d+)", ino).group(1))
    exit_ = int(re.search(r"PALM_EXIT = (\d+)", ino).group(1))
    assert enter < exit_, "hysteresis, or it chatters on the boundary"
    assert enter <= 300, "a hand, not a body leaning on the table"

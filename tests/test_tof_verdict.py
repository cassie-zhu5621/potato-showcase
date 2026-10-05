"""The two ToF faults that look like a working sensor.

Both arrive as readings -- the bar moves a little -- so neither reads as broken
on the live screen, and both cost an evening. Diagnosable from the trace alone,
so the tool says which rather than leaving it to be guessed.
"""
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "tof_test", os.path.join(ROOT, "robot", "tools", "tof_test.py"))
tof_test = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tof_test)
verdict = tof_test.pinned_verdict


def test_everything_at_the_lens_names_the_film_and_the_bracket():
    """A hand does not change it, which is the confusing part: the sensor is
    already reporting the obstruction and the hand is behind it."""
    said = verdict([3] * 30)
    assert said and "at the lens" in said
    assert "FILM" in said and "bracket" in said


def test_a_hand_that_barely_moves_the_bar_still_reads_as_pinned():
    """The reported symptom: 0, and 2-3 with a hand in front. Two readings
    that differ is not two readings that mean anything."""
    said = verdict([0] * 20 + [2, 3] * 5)
    assert said and "at the lens" in said


def test_everything_far_is_an_aim_problem_not_a_sensor_one():
    said = verdict([1900] * 30)
    assert said and "aimed past everything" in said


def test_a_room_says_nothing():
    """A real trace has a hand, a wall and some dropouts in it. The verdict
    must stay quiet, or it is noise on every run."""
    assert verdict([250, 1200, 800, 430] * 8) is None
    assert verdict([None] * 10 + [260, 1400] * 12) is None


def test_it_waits_for_enough_samples():
    """Four frames of anything is not a diagnosis."""
    assert verdict([3] * 5) is None


def test_the_boundary_is_not_at_a_plausible_hand_distance():
    """250 mm is where a palm is meant to sit. A verdict that fired there
    would accuse the lens every time the wake worked."""
    assert verdict([250] * 30) is None
    assert verdict([120] * 30) is None


# --------------------------------------------------------------------------- #
# RangeValid is 0, so an all-zeros struct is the most trustworthy reading there
# is. That has to be refused in the firmware, not explained in a comment.
# --------------------------------------------------------------------------- #
def _ino():
    return open(os.path.join(ROOT, "robot", "firmware", "cores3_sidekick",
                             "cores3_sidekick.ino")).read()


def test_the_library_really_does_number_valid_as_zero():
    """The whole bug rests on this, so it is read from the vendored header
    rather than remembered. If a library update renumbers it, the firmware's
    extra conditions become belt-and-braces instead of load-bearing -- and this
    test is where that gets noticed."""
    hdr = os.path.join(ROOT, ".pio", "libdeps", "m5stack-cores3",
                       "VL53L1X", "VL53L1X.h")
    if not os.path.exists(hdr):
        import pytest
        pytest.skip("library not vendored in this checkout")
    import re
    src = open(hdr).read()
    assert re.search(r"RangeValid\s*=\s*0\s*,", src)


def test_a_failed_read_is_not_published_as_a_perfect_zero():
    """An I2C error leaves the struct as it found it: status 0 (RangeValid),
    distance 0 mm. The bar sat pinned at the top of the screen reporting a
    flawless measurement of nothing, and every explanation for that points at
    the lens."""
    ino = _ino()
    block = ino[ino.index("bool ok = ("):ino.index("if (tofStream)")]
    assert "tof.last_status == 0" in block, "the bytes have to have arrived"
    assert "range_mm > 0" in block, \
        "0 mm is not a distance -- the sensor's minimum range is centimetres"
    assert "RangeValid" in block, "and the status still has to be valid"


def test_the_tool_asks_the_board_before_blaming_the_optics():
    """`i2c` is the number that separates `something is stuck to the lens` from
    `the reads are failing`, and the two have opposite fixes."""
    src = open(os.path.join(ROOT, "robot", "tools", "tof_test.py")).read()
    i = src.index("pinned = True")
    block = src[i:i + 900]
    assert "link.tofdiag()" in block
    assert "i2c" in block

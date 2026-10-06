"""A version has to mean one sketch.

On 2026-10-06 it stopped meaning that: PALM_ENTER went 250 to 300 inside v17,
so a board flashed that morning and the repo that evening both answered `v17`
while behaving differently. Everything downstream trusts that number --
`tof_test.py` prints it, `cores3_link` warns on an older one, every runbook
names the one to expect -- and all of it was quietly wrong.

The existing test only checked that the sketch and `cores3_link` agree about
the string. Both can agree and both be stale.
"""
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INO = os.path.join(ROOT, "robot", "firmware", "cores3_sidekick",
                   "cores3_sidekick.ino")
LOCK = os.path.join(ROOT, "robot", "firmware", "cores3_sidekick",
                    "VERSION_LOCK.json")


def test_the_sketch_matches_the_version_it_claims():
    """If this fails you changed the firmware. Bump FIRMWARE_V and the sketch,
    run `python3 robot/tools/lock_firmware.py`, and reflash -- the last part is
    the one the failure is really about."""
    lock = json.load(open(LOCK))
    digest = hashlib.sha256(open(INO, "rb").read()).hexdigest()
    assert digest == lock["sha256"], (
        f"the sketch has changed since it was locked as {lock['version']}.\n"
        "  Bump the version, run robot/tools/lock_firmware.py, and REFLASH.")


def test_the_lock_agrees_with_what_the_code_expects():
    from session.cores3_link import FIRMWARE_V
    assert json.load(open(LOCK))["version"] == FIRMWARE_V

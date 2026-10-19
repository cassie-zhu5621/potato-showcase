"""Will a prompt actually fire? The constraints, read off the code that holds
them rather than off a table written beside it.

A prompt reads fine, compiles fine, and then nothing happens -- which at a
stand is ninety seconds of a robot looking attentive and reporting nothing.
None of the reasons are visible in the sentence.
"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_spec = importlib.util.spec_from_file_location(
    "check_prompt", os.path.join(ROOT, "robot", "tools", "check_prompt.py"))
cp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cp)

def levels(*a, **kw):
    return {lvl for lvl, _ in cp.verdicts(*a, **kw)}


def test_a_required_object_with_no_binding_can_never_pass_the_gate():
    """`hands_on` with no `on` is the quiet one: the relation is true of a hand
    on anything, so it looks live on the panel and the focus gate refuses it
    every single time."""
    assert "stop" in levels([9])
    assert "stop" not in levels([9], "cup")


def test_turn_taking_is_refused_against_its_own_whitelist():
    """The one whitelist in the system, and it is silent: relations.py skips
    any detection whose label is not in ARTIFACT_TYPES, so a handoff of a plant
    never evaluates at all."""
    from perception.relations import ARTIFACT_TYPES
    assert "plant" not in ARTIFACT_TYPES and "cup" in ARTIFACT_TYPES
    assert "stop" in levels([11], "plant")
    assert "stop" not in levels([11], "cup")


def test_pointing_is_reported_as_unreachable_from_the_front():
    """Measured on this rig: the ray is computed in the image plane, so an arm
    aimed at the robot foreshortens to a point. Loosening the extension
    threshold did not fix it, and it is the gesture everybody tries first."""
    assert "stop" in levels([4], "bag")


def test_the_rows_that_need_a_second_person_are_warned_about():
    for i in (2, 5, 6, 11):
        assert "warn" in levels([i], "cup"), i
    assert "warn" not in levels([10])


def test_a_prop_that_is_not_on_the_table_is_refused():
    """The binding the VLM chose has to be a thing the detector will be asked
    for. Checking it against what is actually on the table is offline and
    costs nothing."""
    assert "stop" in levels([9], "cup", props=["bottle", "book"])
    assert "stop" not in levels([9], "cup", props=["cup", "book"])


def test_a_synonym_of_a_prop_still_counts():
    """The planner says `phone`, the table has a `smartphone`, the detector
    canonicalises both. Refusing that pair would send her renaming props."""
    assert "stop" not in levels([9], "phone", props=["smartphone"])


def test_gathering_is_called_out_as_the_reliable_one():
    assert "ok" in levels([10])


def test_an_empty_compile_is_a_stop_not_a_shrug():
    assert "stop" in levels([])


def test_the_constraints_come_from_the_code_not_a_copy():
    """If a relation is added, or ARTIFACT_TYPES grows, this tool must follow
    without being edited -- otherwise it becomes a second opinion that drifts."""
    from planning.planner import _CATALOG
    assert set(cp.ARITY) == {r["id"] for r in _CATALOG["relations"]}
    from planning.spec_utils import OBJECT_DIRECTED
    assert cp.OBJECT_DIRECTED is OBJECT_DIRECTED


# --------------------------------------------------------------------------- #
# A copy-pasteable block with <angle brackets> in it is a command that fails on
# first contact. It did.
# --------------------------------------------------------------------------- #
def test_annotate_frames_refuses_a_placeholder_rather_than_blaming_the_data():
    """`no frames matched` sent somebody looking at their session feed when
    what was wrong was the command they had been handed."""
    import subprocess
    import sys as _s
    r = subprocess.run(
        [_s.executable, os.path.join(ROOT, "robot", "tools", "annotate_frames.py"),
         "--plan", "<runkit>/plan.json", "--frames", "<here>/f_*.jpg",
         "--out", "/tmp/x"],
        capture_output=True, text=True, cwd=ROOT)
    assert r.returncode != 0
    assert "placeholder" in (r.stderr + r.stdout).lower()


def test_the_shipped_command_has_no_placeholders_left_in_it():
    """RUN_THIS.sh is the fix for the docs that caused it; if it grows one
    back, the same evening repeats."""
    import glob as _g
    # COMMENTS STRIPPED. The warning about angle brackets is written in a
    # comment and contains a pair of them, so a whole-file search fails on a
    # correct script -- the same self-matching trap a guard in
    # test_head_tap_picker.py hit, for the same reason.
    for sh in _g.glob(os.path.join(ROOT, "fig", "*", "RUN_THIS.sh")):
        code = [l for l in open(sh).read().split("\n")
                if not l.lstrip().startswith("#")]
        for line in code:
            bare = line.replace("2>", "").replace(">>", "").replace(">&", "")
            assert "<" not in bare and ">" not in bare, f"{sh}: {line}"

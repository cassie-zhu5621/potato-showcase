"""make_decision_strip draws the angle decision with the robot's own numbers.

A figure explaining a decision with numbers that did not produce it would be
worse than no figure -- so the tool recomputes every station with the same
`station_score` the robot used, from the boxes it recorded, and refuses to draw
if the result disagrees with what the robot wrote down that day.
"""
import importlib.util
import json
import os
import subprocess
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "robot", "tools", "make_decision_strip.py")
sys.path.insert(0, ROOT)


def _sweep(tmp, richest_score, richest_pan=-60):
    dets = {-60: [{"label": "plant", "tier": "focus"},
                  {"label": "person", "tier": "focus"}],
            -30: [{"label": "person", "tier": "focus"}],
            0: [], 30: [{"label": "chair", "tier": "context"}], 60: []}
    shots = []
    for pan, d in dets.items():
        fn = f"pan_{pan:+04d}.jpg"
        Image.new("RGB", (64, 36), (200, 200, 200)).save(os.path.join(tmp, fn))
        shots.append({"pan": pan, "file": fn, "dets": d})
    json.dump({"shots": shots, "provider": "gemini",
               "richest_score": richest_score, "richest_pan": richest_pan,
               "watch_spec": {"watch": [{"all": [9], "on": "plant"}]}},
              open(os.path.join(tmp, "plan.json"), "w"))
    return tmp


def _run(sweep, out):
    return subprocess.run([sys.executable, TOOL, sweep, out],
                          capture_output=True, text=True, cwd=ROOT)


def test_the_named_object_outranks_any_number_of_people(tmp_path):
    """100 for being the named object, plus 3 for the plant box itself being
    focus, plus 3 for the person beside it -- 106, against 3 for a station
    holding only a person. The rule's whole argument: a person will walk to the
    plant; the plant will never walk to the person.

    (This test first expected 103, forgetting that the anchor box is also a
    focus box. The tool refused to draw it. That is the refusal working.)"""
    s = _sweep(str(tmp_path), richest_score=106)
    r = _run(s, str(tmp_path / "out.jpg"))
    assert r.returncode == 0, r.stderr
    assert "chose -60 with 106" in r.stdout
    assert os.path.exists(tmp_path / "out.jpg")


def test_it_refuses_numbers_that_did_not_make_the_decision(tmp_path):
    s = _sweep(str(tmp_path), richest_score=6)     # not what the rule gives
    r = _run(s, str(tmp_path / "out.jpg"))
    assert r.returncode != 0
    assert "Refusing" in (r.stdout + r.stderr)
    assert not os.path.exists(tmp_path / "out.jpg")


def test_it_uses_the_robots_own_scoring_function():
    """A second copy of the rule beside the first is how a figure comes to
    explain a decision the robot did not make."""
    src = open(TOOL).read()
    assert "from planning.station_score import" in src
    assert "station_score(" in src and "spec_anchors(" in src

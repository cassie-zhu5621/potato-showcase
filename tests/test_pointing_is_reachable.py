"""Relation 4, and the threshold whose docstring was half wrong.

`arm_ray_from_points` says: "a resting/bent arm emits NO ray -- only a
near-straight arm reads as reaching/pointing. That single threshold is what
keeps #4 from firing on every idle person."

Half of that is measurably false, and it is the half the number was chosen for.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from perception.gaze import arm_ray_from_points
import robot.states as ST


def _arm(elbow_deg):
    """shoulder / elbow / wrist with a given elbow angle."""
    el = (0.0, 0.0)
    sh = (0.0, -100.0)
    a = math.radians(180 - elbow_deg)
    return sh, el, (100 * math.sin(a), 100 * math.cos(a))


def test_a_hanging_arm_passes_the_extension_test_at_either_setting():
    """THE DOCSTRING'S CLAIM, MEASURED. An arm hanging at the side is straight
    -- about 178 deg -- so it sails past 140 every time. The extension test was
    never what kept relation 4 off idle people; the ray having to HIT a
    detected box is, and a hanging arm points at the floor."""
    sh, el, wr = _arm(178)
    assert arm_ray_from_points(sh, el, wr, min_extension_deg=140.0) is not None
    assert arm_ray_from_points(sh, el, wr, min_extension_deg=110.0) is not None


def test_the_study_setting_excluded_the_gesture_people_actually_make():
    """A raised forearm and a finger -- what pointing looks like standing at a
    table rather than gesturing across a room. At 140 it emitted no ray at all:
    not a near miss, no participation."""
    sh, el, wr = _arm(115)
    assert arm_ray_from_points(sh, el, wr, min_extension_deg=140.0) is None
    assert arm_ray_from_points(sh, el, wr, min_extension_deg=110.0) is not None


def test_a_folded_arm_is_still_not_pointing():
    """Loosened, not removed. An arm folded across the chest emits nothing at
    either setting."""
    sh, el, wr = _arm(70)
    for deg in (140.0, ST.POINT_EXTENSION_DEG):
        assert arm_ray_from_points(sh, el, wr, min_extension_deg=deg) is None


def test_the_showcase_values_are_the_loose_ones_and_the_study_default_is_not():
    """An engine built with no arguments is the one the study ran. The showcase
    passes its own, so a session can still be reproduced from this checkout by
    putting two numbers back."""
    import inspect
    from perception.relations import RelationEngine
    sig = inspect.signature(RelationEngine.__init__).parameters
    assert sig["point_ext_deg"].default == 140.0
    assert sig["tol_point"].default == 15.0
    assert ST.POINT_EXTENSION_DEG == 110.0
    assert ST.POINT_TOL_DEG == 25.0

    src = inspect.getsource(
        __import__("planning.plan_view", fromlist=["x"]).PlanView.__init__)
    assert "POINT_EXTENSION_DEG" in src and "POINT_TOL_DEG" in src, \
        "the showcase has to pass them, or the defaults win silently"


def test_the_engine_actually_uses_them():
    """Threading a parameter in and then not reading it is the failure this
    file would otherwise miss entirely."""
    import inspect
    from perception.relations import RelationEngine
    src = inspect.getsource(RelationEngine)
    assert "min_extension_deg=self.point_ext_deg" in src
    assert "tol_deg=self.tol_point" in src

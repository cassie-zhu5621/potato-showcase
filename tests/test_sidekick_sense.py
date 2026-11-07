"""Per-frame sensing for the sidekick mode (perception/sidekick_sense.py)."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from perception.perceive import Detection                # noqa: E402
from perception.relations import PersonPose              # noqa: E402
from perception import sidekick_sense as SS              # noqa: E402
from robot import states as ST                           # noqa: E402

W, H = 1280, 720
POSE = {"pan": 10.0, "tilt": -12.0, "nod": 22.0}


def person(cx, sw, hand=None, pid=1):
    pts = {SS.NOSE: (cx, 200), SS.L_SH: (cx - sw / 2, 320), SS.R_SH: (cx + sw / 2, 320)}
    vis = {k: 0.9 for k in pts}
    if hand:
        pts[15] = hand
        vis[15] = 0.9
    return PersonPose(pid=pid, pts=pts, vis=vis)


def test_the_centre_of_the_frame_is_where_the_robot_already_looks():
    t = SS.to_target(W / 2, H / 2, W, H, POSE)
    assert abs(t.pan - 10.0) < 1e-6 and abs(t.nod - 22.0) < 1e-6
    assert abs(t.gaze - 10.0) < 1e-6


def test_the_edge_of_the_frame_is_half_the_lens_away():
    t = SS.to_target(W, H / 2, W, H, POSE)
    assert abs(abs(t.pan - 10.0) - ST.CAM_HFOV_DEG / 2) < 0.01


def test_near_and_passing_people_are_told_apart():
    p = SS.sense([person(400, 0.35 * W), person(1000, 0.10 * W, pid=2)], [],
                 (W, H), POSE, 0.0)
    assert p.near is not None and p.near.pid == 1
    assert [q.pid for q in p.people if not q.near] == [2]


def test_a_prop_in_a_hand_is_held_and_one_on_the_table_is_not():
    banana = Detection("banana", (500, 300, 640, 380))
    cup = Detection("cup", (900, 560, 980, 640))
    p = SS.sense([person(600, 0.35 * W, hand=(520, 370))], [banana, cup],
                 (W, H), POSE, 0.0)
    held = {q.label: q.held for q in p.props}
    assert held == {"banana": True, "cup": False}
    assert p.held.label == "banana"


def test_something_held_right_up_to_the_eye_counts_without_a_hand():
    big = Detection("teddy bear", (300, 100, 900, 600))
    p = SS.sense([], [big], (W, H), POSE, 0.0)
    assert p.held is not None


def test_people_and_furniture_are_not_props():
    p = SS.sense([], [Detection("person", (0, 0, 600, 700)),
                      Detection("chair", (0, 0, 300, 300))], (W, H), POSE, 0.0)
    assert p.props == []


def test_a_face_close_up_is_a_near_person_without_shoulders():
    """Close to the robot, the shoulders are out of frame and the body detector
    drops the person. The face alone must keep them there."""
    from perception.gaze import GazeRay
    face = GazeRay(origin=(640, 300), dir=(0, 1), yaw=0, pitch=0,
                   face_box=(520, 180, 760, 440))
    p = SS.sense([], [], (W, H), POSE, 0.0, faces=[face])
    assert p.near is not None
    assert abs(p.near.head.pan - POSE["pan"]) < 1.0


def test_a_face_inside_a_counted_body_is_not_a_second_person():
    from perception.gaze import GazeRay
    face = GazeRay(origin=(400, 200), dir=(0, 1), yaw=0, pitch=0,
                   face_box=(360, 150, 440, 250))
    p = SS.sense([person(400, 0.35 * W)], [], (W, H), POSE, 0.0, faces=[face])
    assert len(p.people) == 1


def test_the_target_may_be_a_weaker_detection():
    weak = Detection("earbud case", (600, 300, 660, 340), score=0.15)
    p = SS.sense([], [weak], (W, H), POSE, 0.0, props=("earbud case",))
    assert p.props == []                              # an ordinary prop: too weak
    p = SS.sense([], [weak], (W, H), POSE, 0.0, props=("earbud case",),
                 target_words=("earbud case",))
    assert len(p.props) == 1

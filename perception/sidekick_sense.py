"""
sidekick_sense.py -- what the sidekick mode needs from one camera frame.

One frame (people from PoseEstimator, boxes from the detector) plus the robot's
pose WHEN THE FRAME WAS TAKEN -> a Percept: where the nearest face is, whether
that person is close, who is passing further off, and which prop is being held
up or lying still. Everything is reported both in pixels and as ABSOLUTE robot
angles, because the head moves and a pixel means nothing once it has.

Per-frame only. Everything that needs time (held still, put down, taken) is the
brain's job (session/sidekick_brain.py), so this file stays a pure function of
its inputs and can be tested on numbers.

Angle convention: Blender degrees, the same as the clips. `gaze` is the eye's
elevation, tilt + nod: aiming moves only the nod, so a gaze change of g is a nod
change of g.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from robot import states as ST

# PoseLandmarker ids (perception/relations.py)
NOSE, L_SH, R_SH = 0, 11, 12
HAND_PTS = (15, 16, 17, 18, 19, 20)       # wrists, pinky and index knuckles
MIN_HAND_VIS = 0.5

# Shoulder width as a fraction of image width. 0.45 m shoulders on a 58-degree
# lens: about 0.41 at 1 m, 0.27 at 1.5 m, 0.20 at 2 m.
NEAR_SW_FRAC = 0.25        # closer than ~1.6 m: "with" the robot
PASSER_SW_FRAC = 0.07      # a body at all (further than ~6 m is not a passer-by)

# A FACE COUNTS AS A PERSON. The body detector needs both shoulders in frame,
# and someone standing close to a robot that is looking up at their face has
# no shoulders in frame -- on 2026-11-07 the robot woke, looked up at Cassie,
# lost her body, and went back to dozing while she stood there. A face's width
# is turned into the same "shoulder width" scale: a face is ~0.15 m across
# (landmark box), shoulders ~0.42 m.
FACE_TO_SHOULDER = 2.8

MIN_PROP_AREA = 0.004
PROP_CONF = 0.25           # an ordinary prop must be at least this sure
TARGET_CONF = 0.12         # the TARGET may be less sure: it is one known word,
                           # usually small and further off than when it was
                           # shown (an earbud case across a table is a weak
                           # detection, and missing it is the failure that
                           # matters here)
TARGET_MIN_AREA = 0.0015   # ... and smaller      # of the frame. Smaller is a detection of nothing.
HELD_CLOSE_AREA = 0.06     # this big is held up to the eye, hand seen or not
HAND_ON_MARGIN = 0.10      # of the box diagonal: a hand holding it (knuckles
                           # sit on the edge of a held thing, not inside it)
HAND_NEAR_MARGIN = 0.25    # a hand reaching for it

PROPS = ("cell phone", "keys", "wallet", "water bottle", "bottle", "cup", "mug",
         "glasses", "sunglasses", "book", "notebook", "pen", "umbrella", "bag",
         "hat", "toy", "stuffed animal", "teddy bear", "ball", "apple", "banana",
         "orange", "can", "headphones", "camera", "card", "remote control",
         "watch", "plant", "scissors")
"""What visitors carry and might hold up to show it. The detector is asked for
all of these so that "something is being held up" is noticed at once; the model
then names what it actually is (any object), and that name is added to this
list as the robot's target (sidekick_loop.py)."""


@dataclass
class Target:
    x: float
    y: float
    pan: float                 # absolute, where to point the head
    nod: float                 # absolute nod that centres it (tilt unchanged)
    gaze: float                # absolute eye elevation of the thing


@dataclass
class Person:
    pid: int
    head: Target
    sw_frac: float
    near: bool


@dataclass
class Prop:
    label: str
    box: Tuple[float, float, float, float]
    area: float
    at: Target
    held: bool                 # a hand is on it, or it is held up to the eye
    hand_near: bool            # any hand point near it (for guarding)


@dataclass
class Percept:
    t: float
    pose: Dict[str, float]
    wh: Tuple[int, int] = (1280, 720)
    people: List[Person] = field(default_factory=list)
    props: List[Prop] = field(default_factory=list)

    @property
    def nearest(self) -> Optional[Person]:
        return max(self.people, key=lambda p: p.sw_frac) if self.people else None

    @property
    def near(self) -> Optional[Person]:
        n = self.nearest
        return n if n and n.near else None

    @property
    def held(self) -> Optional[Prop]:
        hs = [p for p in self.props if p.held]
        return max(hs, key=lambda p: p.area) if hs else None


def vfov_deg(w: int, h: int, hfov: float = ST.CAM_HFOV_DEG) -> float:
    return math.degrees(2 * math.atan(math.tan(math.radians(hfov / 2)) * h / w))


def to_target(x: float, y: float, w: int, h: int, pose: Dict[str, float]) -> Target:
    """Pixel -> absolute angles, for a frame taken at `pose`. Rectilinear lens:
    the offset is an arctangent, not a proportion, so a thing at the edge of the
    frame is not under-aimed by a few degrees."""
    th = math.tan(math.radians(ST.CAM_HFOV_DEG / 2))
    tv = math.tan(math.radians(vfov_deg(w, h) / 2))
    dx = math.degrees(math.atan((x / w - 0.5) * 2 * th)) * ST.AIM_X_SIGN
    dy = math.degrees(math.atan((0.5 - y / h) * 2 * tv)) * ST.AIM_Y_SIGN
    return Target(x=x, y=y, pan=pose["pan"] + dx, nod=pose["nod"] + dy,
                  gaze=pose["tilt"] + pose["nod"] + dy)


def _head_point(person) -> Optional[Tuple[float, float]]:
    if NOSE in person.pts and person.vis.get(NOSE, 0) >= 0.5:
        return person.pts[NOSE]
    if L_SH in person.pts and R_SH in person.pts:
        mx, my = person.mid_shoulder
        return (mx, my - 0.6 * person.shoulder_w)
    return None


MIN_WRIST_VIS = 0.3        # PoseLandmarker always returns a wrist, guessing
                           # it when the hand is out of frame; a guessed wrist
                           # near the guarded thing would be a false "I see you"


def _hand_points(person):
    for j in HAND_PTS:
        if j not in person.pts:
            continue
        need = MIN_WRIST_VIS if j in (15, 16) else MIN_HAND_VIS
        if person.vis.get(j, 0) >= need:
            yield person.pts[j]


def sense(people: Sequence, dets: Sequence, wh: Tuple[int, int],
          pose: Dict[str, float], t: float,
          props: Sequence[str] = PROPS, faces: Sequence = (),
          target_words: Sequence[str] = ()) -> Percept:
    w, h = wh
    out = Percept(t=t, pose=dict(pose), wh=(w, h))
    targets = {x.strip().lower() for x in target_words if x}
    hands = []
    for p in people:
        if L_SH not in p.pts or R_SH not in p.pts:
            continue
        sw = p.shoulder_w / float(w)
        hp = _head_point(p)
        if hp is None or sw < PASSER_SW_FRAC:
            continue
        out.people.append(Person(pid=p.pid, head=to_target(hp[0], hp[1], w, h, pose),
                                 sw_frac=sw, near=sw >= NEAR_SW_FRAC))
        hands.extend(_hand_points(p))
    # Faces whose person the body detector missed (too close, or half out of
    # frame). A face inside a body already counted is that same person.
    for k, f in enumerate(faces):
        if getattr(f, "coarse", False):
            continue
        x0, y0, x1, y1 = f.face_box
        mx, my = 0.25 * (x1 - x0), 0.25 * (y1 - y0)
        if any(x0 - mx <= q.head.x <= x1 + mx and y0 - my <= q.head.y <= y1 + my
               for q in out.people):
            continue
        sw = FACE_TO_SHOULDER * (x1 - x0) / float(w)
        if sw < PASSER_SW_FRAC:
            continue
        nx, ny = f.origin
        out.people.append(Person(pid=-100 - k, head=to_target(nx, ny, w, h, pose),
                                 sw_frac=sw, near=sw >= NEAR_SW_FRAC))
    for d in dets:
        if d.label not in props:
            continue
        area = d.area / float(w * h)
        is_target = d.label.strip().lower() in targets
        if area < (TARGET_MIN_AREA if is_target else MIN_PROP_AREA):
            continue
        if getattr(d, "score", 1.0) < (TARGET_CONF if is_target else PROP_CONF):
            continue
        diag = math.hypot(d.w, d.h)
        x0, y0, x1, y1 = d.box

        def within(m):
            return any(x0 - m <= x <= x1 + m and y0 - m <= y <= y1 + m
                       for x, y in hands)
        hand_near = within(HAND_NEAR_MARGIN * diag)
        hand_on = within(HAND_ON_MARGIN * diag)
        out.props.append(Prop(label=d.label, box=tuple(d.box), area=area,
                              at=to_target(d.cx, d.cy, w, h, pose),
                              held=hand_on or area >= HELD_CLOSE_AREA,
                              hand_near=hand_near))
    return out

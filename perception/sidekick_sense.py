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

MIN_PROP_AREA = 0.004      # of the frame. Smaller is a detection of nothing.
HELD_CLOSE_AREA = 0.06     # this big is held up to the eye, hand seen or not
HAND_ON_MARGIN = 0.10      # of the box diagonal: a hand holding it (knuckles
                           # sit on the edge of a held thing, not inside it)
HAND_NEAR_MARGIN = 0.25    # a hand reaching for it

PROPS = ("banana", "apple", "orange", "teddy bear", "cup", "bottle",
         "rubber duck", "toy car", "ball", "book")
"""Candidates. robot/tools/sidekick_prop_check.py measures which of these the
detector finds reliably on the booth's lighting; keep the best three or four
and put the same words on the tray."""


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


def _hand_points(person):
    for j in HAND_PTS:
        if j in person.pts and (j in (15, 16) or person.vis.get(j, 0) >= MIN_HAND_VIS):
            yield person.pts[j]


def sense(people: Sequence, dets: Sequence, wh: Tuple[int, int],
          pose: Dict[str, float], t: float,
          props: Sequence[str] = PROPS) -> Percept:
    w, h = wh
    out = Percept(t=t, pose=dict(pose))
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
    for d in dets:
        if d.label not in props:
            continue
        area = d.area / float(w * h)
        if area < MIN_PROP_AREA:
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

"""
sidekick_brain.py -- what the robot does next, in the sidekick mode.

The conductor (sidekick_loop.py) feeds this three things -- a Percept for every
settled camera frame, a touch on the head, a hand held to the wake sensor -- and
it answers by asking the player for states and aims, and by emitting events the
conductor turns into tablet cards.

No hardware, no threads, no camera: a clock is injected, so every rule below can
be tested on made-up percepts (tests/test_sidekick_brain.py).

THE PHASES (what the robot is doing with the visitor; the player's state can be
a one-shot inside one of these)

  DOZE   resting, head up, seeing the room. Glances at passers-by.
  LOOK   someone is with it: it looks at their face.
  SHOW   they are showing it something: curious, then following the prop.
  GUARD  they put the prop down and let go: it guards it.
  CALL   the guarded thing was taken: it calls the owner.

THE TOUCH means one thing per phase (docs/SHOWCASE_1108_PLAN.md):
  DOZE / LOOK / SHOW   affection -> SK_PURR, then carry on
  GUARD                "I'm back" -> SK_ACK, stop guarding
  CALL                 "seen it"  -> SK_ACK, the story stays on the tablet
"""
from __future__ import annotations

import math
import time
from collections import deque
from typing import Callable, Optional

from robot import states as ST

# ---- timing (seconds) -------------------------------------------------------
WAKE_S = 0.6               # someone near this long wakes it (not a passer-by)
LOST_S = 6.0               # nobody near this long: back to dozing
GLANCE_REFRACTORY_S = 12.0  # at most one glance per this long
GLANCE_MIN_DEG = 8.0       # a glance must be a visible turn
HELD_FRAMES = 2            # a held prop on this many settled frames in a row
STILL_S = 1.2              # held still this long -> "got it"
STILL_DEG = 3.0            #   ... within this spread
SHOW_AGAIN_S = 8.0         # the same thing is not "new" again for this long
PROP_LOST_S = 2.5          # the prop out of sight this long: back to the face
PLACE_S = 1.0              # put down, let go and still this long -> guard it
DESK_GAZE = -15.0          # below this elevation a prop is on the table
GUARD_MATCH_DEG = 10.0     # the guarded thing is the same label within this
TAKEN_S = 1.2              # missing this long after a hand came near: taken
GONE_S = 5.0               # missing this long with no hand seen: taken anyway
                           # (the hand can be out of frame), but only this late,
                           # so a detector blink is never called a theft
GUARD_SETTLE_S = 2.0       # a guard younger than this cannot be "taken"
ALERT_REFRACTORY_S = 4.0
GUARD_MAX_S = 300.0        # nobody came back: give up guarding
CALL_MAX_S = 25.0          # nobody answered the call

KAOMOJI = {
    "DOZE": "-_-", "LOOK": "o_o", "SHOW": "o_O?", "FOLLOW": "O_O",
    "ACK": "^_^", "PURR": "=^_^=", "GUARD": ">_>",
    "ALERT": "O_O!", "CALL": "\\^o^/",
}


# ---- STAGES: built and tried one interaction at a time ----------------------
# Each stage adds one interaction and the clips it needs. `--stage N` runs the
# booth with only those, so a stage can be exported, tried and tuned on the
# robot before the next one exists.
FEATURES = ("touch", "notice", "show", "guard")
STAGES = {n: FEATURES[:n] for n in range(1, len(FEATURES) + 1)}
CLIPS_FOR = {
    "touch":  ("SK_PURR",),                 # touch its head: it leans into the hand
    "notice": ("SK_DOZE", "SK_GLANCE"),     # dozes, glances at passers-by, looks at you
    "show":   ("SK_CURIOUS", "SK_ACK"),     # show it a prop: curious, follows, "got it"
    "guard":  ("SK_GUARD_ALERT",),          # put it down: guards it, calls if taken
}


def clips_for_stage(n):
    return tuple(c for f in STAGES[n] for c in CLIPS_FOR[f])


class Brain:
    def __init__(self, player, on_event: Callable = None,
                 clock: Callable[[], float] = time.time, stage: int = 4):
        self.p = player
        self.on = set(STAGES[stage])
        # Before stage 2 there is no SK_DOZE clip: the robot rests in the paper's
        # S0_IDLE, and a touch is the only thing it answers.
        self.rest = "SK_DOZE" if "notice" in self.on else "S0_IDLE"
        self.emit = on_event or (lambda kind, **kw: None)
        self.now = clock
        self.phase = "DOZE"
        self.face = KAOMOJI["DOZE"]
        self.caption = ""
        t = self.now()
        self._near_since: Optional[float] = None
        self._last_near = -1e9
        self._last_glance = -1e9
        self._held_run = 0
        self._label: Optional[str] = None
        self._track = deque()            # (t, pan, gaze) of the followed prop
        self._prop_seen = -1e9
        self._acked: dict = {}           # label -> t of its "got it"
        self._down_since: Optional[float] = None
        self._guard = None               # dict(label, pan, gaze, since, seen, ...)
        self._call_since = -1e9
        self._entered = t

    # ---- outputs --------------------------------------------------------
    def _go(self, phase, face=None, say=None):
        self.phase = phase
        self.face = KAOMOJI[face or phase]
        if say is not None:
            self.caption = say
        self._entered = self.now()

    def _look_at(self, target, tilt=ST.LOOK_TILT):
        self.p.set_aim_deg(pan=target.pan, tilt=tilt, nod=target.nod)

    # ---- inputs ---------------------------------------------------------
    def on_tap(self):
        t = self.now()
        if self.phase == "DOZE" and "notice" not in self.on:
            # Stage 1: a touch is answered and the robot goes back to resting.
            self.p.request("SK_PURR", resume_to=self.rest)
            self.face = KAOMOJI["PURR"]
        elif self.phase == "DOZE":
            # A touch wakes it, and it leans into the hand as it wakes.
            pose = self.p.pose_deg()
            self.p.set_aim_deg(pan=pose["pan"], tilt=ST.LOOK_TILT, nod=ST.LOOK_NOD)
            self.p.request("SK_PURR", resume_to="SK_LOOK")
            self._last_near = t
            self._go("LOOK", face="PURR", say="Hello!")
        elif self.phase in ("LOOK", "SHOW"):
            self.p.request("SK_PURR")
            self.face = KAOMOJI["PURR"]
        elif self.phase == "GUARD":
            self.emit("guard_end", label=self._guard["label"], how="returned")
            self._guard = None
            self.p.request("SK_ACK", resume_to="SK_LOOK")
            self._last_near = t
            self._go("LOOK", face="ACK", say="Welcome back. All yours.")
        elif self.phase == "CALL":
            self.emit("call_answered")
            self.p.request("SK_ACK", resume_to="SK_LOOK")
            self._last_near = t
            self._go("LOOK", face="ACK", say="That's who took it.")

    def on_palm(self):
        if self.phase == "DOZE" and "notice" in self.on:
            pose = self.p.pose_deg()
            self.p.set_aim_deg(pan=pose["pan"], tilt=ST.LOOK_TILT, nod=ST.LOOK_NOD)
            self.p.request("SK_LOOK")
            self._last_near = self.now()
            self._go("LOOK", say="Hi! Show me something?")

    def tick(self):
        """Time-only rules, for when frames stop coming (nobody in view)."""
        t = self.now()
        if self.phase == "LOOK" and t - self._last_near > LOST_S:
            self._sleep()
        elif self.phase == "SHOW" and t - self._prop_seen > PROP_LOST_S:
            self.p.request("SK_LOOK")
            self._go("LOOK", say="")
        elif self.phase == "GUARD" and t - self._guard["since"] > GUARD_MAX_S:
            self.emit("guard_end", label=self._guard["label"], how="gave_up")
            self._guard = None
            self._sleep()
        elif self.phase == "CALL" and t - self._call_since > CALL_MAX_S:
            self.p.request("SK_LOOK")
            self._last_near = t
            self._go("LOOK", say="")

    def _sleep(self):
        self.p.clear_aim()
        self.p.request(self.rest)
        self._near_since = None
        self._go("DOZE", say="")

    def on_percept(self, pc):
        """One SETTLED frame's Percept (perception/sidekick_sense.py)."""
        getattr(self, "_see_" + self.phase.lower())(pc)
        self.tick()

    # ---- per phase ------------------------------------------------------
    def _see_doze(self, pc):
        if "notice" not in self.on:
            return
        t = pc.t
        near = pc.near
        if near:
            self._near_since = self._near_since or t
            if t - self._near_since >= WAKE_S:
                self._look_at(near.head)
                self.p.request("SK_LOOK")
                self._last_near = t
                self._go("LOOK", say="Hi! Show me something?")
            return
        self._near_since = None
        if self.p.state != self.rest or t - self._last_glance < GLANCE_REFRACTORY_S:
            return
        far = [q for q in pc.people if not q.near]
        if far:
            q = max(far, key=lambda q: q.sw_frac)
            if abs(q.head.pan - pc.pose["pan"]) >= GLANCE_MIN_DEG:
                self.p.set_glance_target_deg(q.head.pan)
                self.p.request("SK_GLANCE")
                self._last_glance = t

    def _see_look(self, pc):
        t = pc.t
        near = pc.near
        if near:
            self._last_near = t
            if self.p.state == "SK_LOOK":
                self._look_at(near.head)
        held = pc.held if "show" in self.on else None
        if held and t - self._acked.get(held.label, -1e9) > SHOW_AGAIN_S:
            self._held_run += 1
            if self._held_run >= HELD_FRAMES and self.p.state == "SK_LOOK":
                self._held_run = 0
                self._label = held.label
                self._track.clear()
                self._prop_seen = t
                self._down_since = None
                self._look_at(held.at, tilt=None)
                self.p.request("SK_CURIOUS")
                self._go("SHOW", say="Ooh, what's that?")
        else:
            self._held_run = 0

    def _see_show(self, pc):
        t = pc.t
        if pc.near:
            self._last_near = t
        mine = [q for q in pc.props if q.label == self._label] or pc.props
        if not mine:
            return
        # the followed thing: the candidate nearest to where it last was
        if self._track:
            _, lp, lg = self._track[-1]
            q = min(mine, key=lambda q: math.hypot(q.at.pan - lp, q.at.gaze - lg))
        else:
            q = max(mine, key=lambda q: q.area)
        self._label = q.label
        self._prop_seen = t
        self._track.append((t, q.at.pan, q.at.gaze))
        while self._track and t - self._track[0][0] > STILL_S:
            self._track.popleft()
        if self.p.state == "SK_FOLLOW":
            self._look_at(q.at, tilt=None)
            self.face = KAOMOJI["FOLLOW"]
        still = (len(self._track) >= 3 and t - self._track[0][0] >= STILL_S * 0.8
                 and max(math.hypot(a[1] - b[1], a[2] - b[2])
                         for a in self._track for b in self._track) <= STILL_DEG)
        if q.held:
            self._down_since = None
            if still and t - self._acked.get(q.label, -1e9) > SHOW_AGAIN_S \
                    and self.p.state == "SK_FOLLOW":
                self._acked[q.label] = t
                self.p.request("SK_ACK")          # resumes SK_FOLLOW
                self.face = KAOMOJI["ACK"]
                self.caption = f"A {q.label}! Put it down and I'll guard it."
                self.emit("shown", label=q.label, box=q.box, t=t)
        elif q.at.gaze <= DESK_GAZE and still and "guard" in self.on:
            self._down_since = self._down_since or t
            if t - self._down_since >= PLACE_S and self.p.state == "SK_FOLLOW":
                self._guard = dict(label=q.label, pan=q.at.pan, gaze=q.at.gaze,
                                   box=q.box, since=t, seen=t, hand_at=None,
                                   alert_at=-1e9)
                self._look_at(q.at, tilt=None)
                self.p.request("SK_GUARD")
                self._go("GUARD", say=f"I'll keep an eye on your {q.label}.")
                self.emit("guard_start", label=q.label, box=q.box, t=t)
        else:
            self._down_since = None

    def _see_guard(self, pc):
        t = pc.t
        g = self._guard
        cand = [q for q in pc.props if q.label == g["label"]
                and math.hypot(q.at.pan - g["pan"], q.at.gaze - g["gaze"]) <= GUARD_MATCH_DEG]
        if cand:
            q = min(cand, key=lambda q: math.hypot(q.at.pan - g["pan"], q.at.gaze - g["gaze"]))
            g["seen"] = t
            g["pan"], g["gaze"], g["box"] = q.at.pan, q.at.gaze, q.box
            if self.p.state == "SK_GUARD":
                self._look_at(q.at, tilt=None)
            if q.hand_near:
                g["hand_at"] = t
                if t - g["alert_at"] > ALERT_REFRACTORY_S and self.p.state == "SK_GUARD":
                    g["alert_at"] = t
                    self.p.request("SK_GUARD_ALERT")
                    self.face = KAOMOJI["ALERT"]
                    self.caption = "I see you..."
                    self.emit("alert", label=g["label"], t=t)
            elif self.p.state == "SK_GUARD":
                self.face = KAOMOJI["GUARD"]
            return
        # Gone. Only "taken" if the guard had settled and a hand was there:
        # a detector blinking for a second is not a theft.
        handled = g["hand_at"] is not None and g["hand_at"] >= g["seen"] - 1.0
        missing = t - g["seen"]
        if t - g["since"] >= GUARD_SETTLE_S and (
                (handled and missing >= TAKEN_S) or missing >= GONE_S):
            self.p.request("S5A_FOUND")
            self._call_since = t
            label = g["label"]
            self.emit("taken", label=label,
                      onset=g["hand_at"] if handled else g["seen"], t=t)
            self._guard = None
            self._go("CALL", say=f"Hey! Someone took your {label}!")

    def _see_call(self, pc):
        if pc.near:
            self._last_near = pc.t

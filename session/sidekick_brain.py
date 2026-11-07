"""
sidekick_brain.py -- what the robot does next, in the sidekick mode.

The conductor (sidekick_loop.py) feeds this four things -- a Percept for every
settled camera frame, a touch on the head, a hand held to the wake sensor, and
the model's answer to "what is this person showing me?" -- and it answers by
asking the player for states and aims, and by emitting events the conductor
turns into model calls and tablet cards.

No hardware, no threads, no camera: a clock is injected, so every rule below can
be tested on made-up percepts (tests/test_sidekick_brain.py).

THE PHASES (what the robot is doing with the visitor; the player's state can be
a one-shot inside one of these)

  SLEEP  head down (the paper's S0_IDLE pose): clearly asleep. The camera is on
         the table, so only a hand at the wake sensor or a touch wakes it.
  DOZE   just after someone left: head up, seeing the room, glances at
         passers-by and wakes by itself if someone comes close. If nobody comes
         for DOZE_TO_SLEEP_S, it nods off into SLEEP.
  LOOK   someone is with it: it looks at their face.
  TEACH  they hold something up to it: curious, it follows the thing while the
         model names it, then nods -- "I'll look out for that". The thing
         becomes its TARGET, replacing any earlier one (whoever showed it).
  CALL   it saw its target again: it points at it and calls.

Watching for the target runs underneath SLEEP, DOZE and LOOK: the robot goes on
with its ordinary life and calls when the thing turns up. The target only counts
as "turned up" after it has been out of sight for TARGET_AWAY_S -- right after
teaching it is still in the visitor's hand, and that is not a finding.

THE TOUCH means one thing per phase (docs/SHOWCASE_1108_PLAN.md):
  SLEEP / DOZE    wakes it, leaning up into the hand (SK_PURR), then LOOK
  LOOK / TEACH    affection -> SK_PURR, then carry on
  CALL            "seen it" -> SK_ACK, then LOOK
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from robot import states as ST

# ---- timing (seconds) -------------------------------------------------------
WAKE_S = 0.6               # someone near this long wakes it (not a passer-by)
LOST_S = 6.0               # nobody near this long: back to dozing (head up)
DOZE_TO_SLEEP_S = 20.0     # dozing this long with nobody near: head down, asleep
GLANCE_REFRACTORY_S = 12.0  # at most one glance per this long
GLANCE_MIN_DEG = 8.0       # closer to straight ahead than this: no turn, the
                           # glance is the head lift and the look alone
HELD_FRAMES = 2            # something held up on this many settled frames in a row
TEACH_MAX_S = 12.0         # the model never answered: give up, back to the face
TEACH_AGAIN_S = 6.0        # a failed or finished teach: no new one for this long
TARGET_AWAY_S = 3.0        # the target must be out of sight this long before
                           # seeing it again counts as finding it
FOUND_FRAMES = 2           # seen on this many settled frames in a row: found
CALL_MAX_S = 25.0          # nobody answered the call

KAOMOJI = {
    "SLEEP": "-_- zz", "DOZE": "-.-", "LOOK": "o_o", "TEACH": "o_O?",
    "FOLLOW": "O_O", "ACK": "^_^", "PURR": "=^_^=", "CALL": "\\^o^/",
}


# ---- STAGES: built and tried one interaction at a time ----------------------
# Each stage adds one interaction and the clips it needs. `--stage N` runs the
# booth with only those, so a stage can be exported, tried and tuned on the
# robot before the next one exists.
FEATURES = ("touch", "notice", "watch")
STAGES = {n: FEATURES[:n] for n in range(1, len(FEATURES) + 1)}
CLIPS_FOR = {
    "touch":  ("SK_PURR",),                 # touch its head: it leans into the hand
    "notice": ("SK_DOZE", "SK_GLANCE"),     # dozes, glances at passers-by, looks at you
    "watch":  ("SK_CURIOUS", "SK_ACK"),     # show it a thing: it looks out for it and
                                            # calls when it turns up (the call is the
                                            # paper's S5A_FOUND / S5B_BECKON)
}


def clips_for_stage(n):
    return tuple(c for f in STAGES[n] for c in CLIPS_FOR[f])


class Brain:
    def __init__(self, player, on_event: Callable = None,
                 clock: Callable[[], float] = time.time, stage: int = 3):
        self.p = player
        self.on = set(STAGES[stage])
        # Asleep is the paper's S0_IDLE pose at every stage: head down, which
        # reads as asleep from across a room (the head-up SK_DOZE did not).
        # From stage 2 SK_DOZE is the short drowsy spell between a visitor
        # leaving and falling asleep, when the camera can still see the room.
        self.rest = "S0_IDLE"
        self._doze_since = -1e9
        self.emit = on_event or (lambda kind, **kw: None)
        self.now = clock
        self.phase = "SLEEP"
        self.face = KAOMOJI["SLEEP"]
        self.caption = ""
        t = self.now()
        self._near_since: Optional[float] = None
        self._last_near = -1e9
        self._last_glance = -1e9
        self._held_run = 0
        self._teach = None               # dict(since, box, guess) while naming
        self._teach_done = -1e9
        self.target = None               # dict(term, name, since) once taught
        self._target_seen = -1e9         # last settled frame the target was in
        self._target_armed = False       # away long enough that seeing it counts
        self._found_run = 0
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
        if self.phase == "SLEEP" and "notice" not in self.on:
            # Stage 1: a touch is answered and the robot goes back to resting.
            # From the sleeping pose the purr is played AS AUTHORED: the head
            # comes all the way up into the hand first. Translated onto a head
            # hanging 42 deg down, the same rise never reached the hand.
            self.p.request("SK_PURR", resume_to=self.rest, as_authored=True)
            self.face = KAOMOJI["PURR"]
        elif self.phase in ("SLEEP", "DOZE"):
            # A touch wakes it, and it leans into the hand as it wakes.
            pose = self.p.pose_deg()
            self.p.set_aim_deg(pan=pose["pan"], tilt=ST.LOOK_TILT, nod=ST.LOOK_NOD)
            self.p.request("SK_PURR", resume_to="SK_LOOK", as_authored=True)
            self._last_near = t
            self._go("LOOK", face="PURR", say="Hello!")
        elif self.phase in ("LOOK", "TEACH"):
            self.p.request("SK_PURR")
            self.face = KAOMOJI["PURR"]
        elif self.phase == "CALL":
            self.emit("call_answered")
            self.p.request("SK_ACK", resume_to="SK_LOOK")
            self._last_near = t
            self._go("LOOK", face="ACK", say="")

    def on_palm(self):
        if self.phase in ("SLEEP", "DOZE") and "notice" in self.on:
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
        elif (self.phase == "DOZE" and "notice" in self.on
                and t - self._doze_since > DOZE_TO_SLEEP_S
                and self.p.state == "SK_DOZE"):
            self.p.request(self.rest)
            self._near_since = None
            self._go("SLEEP", say="")
        elif self.phase == "TEACH" and self._apply_held_answer():
            pass
        elif self.phase == "TEACH" and t - self._teach["since"] > TEACH_MAX_S:
            self._teach_failed("Hmm, I couldn't tell what that was.")
        elif self.phase == "CALL" and t - self._call_since > CALL_MAX_S:
            self.p.request("SK_LOOK")
            self._last_near = t
            self._go("LOOK", say="")

    def _sleep(self):
        """Nobody here any more: doze (head up) first, sleep later (tick)."""
        self.p.clear_aim()
        self._near_since = None
        if "notice" in self.on:
            self.p.request("SK_DOZE")
            self._doze_since = self.now()
            self._go("DOZE", say="")
        else:
            self.p.request(self.rest)
            self._go("SLEEP", say="")

    def on_percept(self, pc):
        """One SETTLED frame's Percept (perception/sidekick_sense.py)."""
        if not self._watch(pc):
            getattr(self, "_see_" + self.phase.lower())(pc)
        self.tick()

    # ---- teaching: the model's answer -----------------------------------
    def on_identified(self, name, term):
        """What the model said the visitor was showing (None: it could not
        tell). `term` is the detector's word for it ("water bottle"), `name`
        the robot's ("the blue water bottle")."""
        if self.phase != "TEACH":
            return
        # The curious beat plays to the end first: an answer that comes back
        # while the robot is still leaning in is held until it is following
        # the thing (_see_teach / tick apply it). A nod cutting the "hm?" off
        # reads as not having looked at all.
        if self.p.state == "SK_CURIOUS":
            self._teach["answer"] = (name, term)
            return
        if not term:
            self._teach_failed("Hmm, I couldn't tell what that was.")
            return
        self.target = dict(term=term, name=name or term, since=self.now())
        self._target_seen = self.now()     # it is in their hand right now
        self._target_armed = False
        self._found_run = 0
        self._teach_done = self.now()
        self._teach = None
        self.p.request("SK_ACK", resume_to="SK_LOOK")
        self._last_near = self.now()
        self._go("LOOK", face="ACK",
                 say=f"OK! I'll look out for {self.target['name']}.")
        self.emit("taught", term=term, name=self.target["name"])

    def _apply_held_answer(self):
        ans = self._teach.get("answer") if self._teach else None
        if ans is None or self.p.state == "SK_CURIOUS":
            return False
        self.on_identified(*ans)
        return True

    def _teach_failed(self, say):
        self._teach = None
        self._teach_done = self.now()
        self.p.request("SK_LOOK")
        self._last_near = self.now()
        self._go("LOOK", say=say)

    # ---- watching for the target, underneath everything else -------------
    def _watch(self, pc):
        """True if the target was just found (the phase handler is skipped)."""
        if not self.target or "watch" not in self.on:
            return False
        t = pc.t
        hits = [q for q in pc.props if q.label == self.target["term"]]
        # Being SHOWN to it is not finding it: a near person holding it up.
        hits = [q for q in hits if not (q.held and pc.near)]
        if not hits:
            self._found_run = 0
            if t - self._target_seen >= TARGET_AWAY_S:
                self._target_armed = True
            return False
        self._target_seen = t
        if not self._target_armed or self.phase in ("TEACH", "CALL"):
            self._found_run = 0
            return False
        self._found_run += 1
        if self._found_run < FOUND_FRAMES:
            return False
        q = max(hits, key=lambda q: q.area)
        self._found_run = 0
        self._target_armed = False
        self.p.clear_aim()
        self.p.set_found_pan_deg(q.at.pan)
        self.p.request("S5A_FOUND")
        self._call_since = t
        self._go("CALL", say=f"Look! {self.target['name'][:1].upper()}"
                              f"{self.target['name'][1:]}!")
        self.emit("found", term=self.target["term"], name=self.target["name"],
                  box=q.box, t=t)
        return True

    # ---- per phase ------------------------------------------------------
    def _see_sleep(self, pc):
        """Head down, the camera sees the table. If it does see someone close
        (leaning in over it), that wakes it; nothing else does but the hand
        and the touch."""
        if "notice" not in self.on:
            return
        near = pc.near
        if near:
            self._near_since = self._near_since or pc.t
            if pc.t - self._near_since >= WAKE_S:
                self._look_at(near.head)
                self.p.request("SK_LOOK")
                self._last_near = pc.t
                self._go("LOOK", say="Hi! Show me something?")
        else:
            self._near_since = None

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
        far = [q for q in pc.people if not q.near]
        if far:
            self._doze_since = t           # people about: stay drowsy, not asleep
        if self.p.state != "SK_DOZE" or t - self._last_glance < GLANCE_REFRACTORY_S:
            return
        if far:
            q = max(far, key=lambda q: q.sw_frac)
            # Someone almost straight ahead still gets the glance -- without the
            # turn. Requiring an 8-degree turn meant a passer-by right in front
            # of it (the commonest case at a stand) got nothing at all
            # (2026-11-07: four passers at bearings -2..+7, no reaction). The
            # head lift and the held look are the glance; the turn only aims it.
            target = (q.head.pan if abs(q.head.pan - pc.pose["pan"]) >= GLANCE_MIN_DEG
                      else pc.pose["pan"])
            self.p.set_glance_target_deg(target)
            self.p.request("SK_GLANCE")
            self._last_glance = t

    def _see_look(self, pc):
        t = pc.t
        near = pc.near
        if near:
            self._last_near = t
            if self.p.state == "SK_LOOK":
                self._look_at(near.head)
        held = pc.held if ("watch" in self.on and near) else None
        if (held and t - self._teach_done > TEACH_AGAIN_S
                and not (self.target and held.label == self.target["term"])):
            self._held_run += 1
            if self._held_run >= HELD_FRAMES and self.p.state == "SK_LOOK":
                self._held_run = 0
                self._teach = dict(since=t, box=held.box, guess=held.label)
                self._look_at(held.at, tilt=None)
                self.p.request("SK_CURIOUS")         # -> SK_FOLLOW while it is named
                self._go("TEACH", say="Ooh, what's that?")
                self.emit("identify", box=held.box, guess=held.label, t=t)
        else:
            self._held_run = 0

    def _see_teach(self, pc):
        """Follow the thing while the model names it."""
        if self._apply_held_answer():
            return
        if pc.near:
            self._last_near = pc.t
        held = pc.held or (max(pc.props, key=lambda q: q.area) if pc.props else None)
        if held and self.p.state == "SK_FOLLOW":
            self._look_at(held.at, tilt=None)
            self.face = KAOMOJI["FOLLOW"]

    def _see_call(self, pc):
        if pc.near:
            self._last_near = pc.t

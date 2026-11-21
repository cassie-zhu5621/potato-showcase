"""
booth_brain.py -- the 11.24 researcher booth (showcase-1124).

The 1108 sidekick brain (session/sidekick_brain.py), cut down to ONE loop that
a classmate can run with a single button (docs/SHOWCASE_1124_PLAN.md):

  ASLEEP    head down (S0_IDLE). Someone within the ToF distance in front of
            it gets one small stir of the head (SK_GLANCE, no turn), then it
            sleeps on. Nothing seen by the camera wakes it.
  WAKE      ONLY a pat on the head. The light goes from warm to blue (SK_LOOK).
  OWNER     whoever is closest when it first sees someone after waking is its
            owner for this visit. It follows the owner and nobody else.
  SHOW      only once it has an owner: something brought up to its eyes is
            named by the model, ack, then it looks out for it and calls.
  PAT       any time awake: purr. While calling: "seen it".
  NEXT      the operator's button: asleep, owner and object forgotten. Also by
            itself after OWNER_GONE_S with the owner out of sight.

Gone from 1108: waking by coming close, dozing, glancing at passers-by, waving
back, the very-close bounces, passing the object on to the next visitor.
"""
from __future__ import annotations

from robot import states as ST
from session import sidekick_brain as SB
from session.sidekick_brain import Brain

# ---- the owner ---------------------------------------------------------------
OWNER_GONE_S = 60.0        # owner out of sight this long: back to sleep, as Next
OWNER_SWITCH_S = 10.0      # ... this long: whoever is closest becomes the owner
OWNER_BEARING_DEG = 12.0   # someone this close to where the owner was IS the owner
OWNER_DRIFT_DPS = 25.0     # ... widening by this per second they are not seen
OWNER_BEARING_MAX = 45.0

# ---- the ToF stir while asleep -------------------------------------------------
TOF_DEFAULT_M = 0.8        # someone this close in front of it (web UI: - / +)
TOF_MIN_M, TOF_MAX_M = 0.3, 2.0
TOF_ENTER_S = 0.3          # within the distance this long: stir
TOF_EXIT_MARGIN_M = 0.10   # re-armed only once they are this much further out ...
TOF_REARM_S = 2.0          # ... for this long (someone standing there: one stir)
TOF_REFRACTORY_S = 6.0     # never two stirs closer than this


class BoothBrain(Brain):
    def __init__(self, player, on_event=None, clock=None, stage=3,
                 tof_m=TOF_DEFAULT_M, tof_on=True, **_ignored):
        kw = {} if clock is None else {"clock": clock}
        super().__init__(player, on_event=on_event, stage=stage, **kw)
        self.tof_m = tof_m
        self.tof_on = tof_on
        self._owner = False
        self._tof_in_since = None
        self._tof_out_since = None
        self._tof_armed = True
        self._stir_at = -1e9
        self.tof_last_mm = None

    # ---- the operator -------------------------------------------------------
    def next_visitor(self):
        """Asleep, owner and object forgotten. Settings (ToF) are kept."""
        tof_m, tof_on = self.tof_m, self.tof_on
        self._set_close(False)
        self.p.clear_aim()
        self.__init__(self.p, on_event=self.emit, clock=self.now, stage=self.stage,
                      tof_m=tof_m, tof_on=tof_on)
        self.p.request(self.rest)
        self.emit("next_visitor", name="")

    def set_tof(self, metres=None, on=None):
        if metres is not None:
            self.tof_m = round(min(TOF_MAX_M, max(TOF_MIN_M, float(metres))), 2)
        if on is not None:
            self.tof_on = bool(on)

    # ---- inputs -------------------------------------------------------------
    def on_palm(self):
        pass                                  # only a pat wakes it

    def on_tap(self):
        was_asleep = self.phase == "SLEEP"
        super().on_tap()
        if was_asleep and self.phase == "LOOK":
            self._owner = False               # a new visit: find who patted it
            self._track_pan, self._track_t = None, -1e9
            self.emit("wake", name="")

    def on_distance(self, mm, t=None):
        """One ToF reading (millimetres; negative = no valid reading)."""
        t = self.now() if t is None else t
        if mm is not None and mm >= 0:
            self.tof_last_mm = mm
        if not self.tof_on or self.phase != "SLEEP" or mm is None or mm < 0:
            self._tof_in_since = None
            return
        d = mm / 1000.0
        if d <= self.tof_m:
            self._tof_out_since = None
            if self._tof_in_since is None:
                self._tof_in_since = t
            if (self._tof_armed and t - self._tof_in_since >= TOF_ENTER_S
                    and t - self._stir_at >= TOF_REFRACTORY_S
                    and self.p.state == self.rest):
                self._tof_armed = False
                self._stir_at = t
                # A glance with no turn: the head lifts a little and settles
                # back into sleep (SK_GLANCE resumes what it interrupted).
                self.p.set_glance_target_deg(self.p.pose_deg()["pan"])
                self.p.request("SK_GLANCE")
                self.emit("stir", name=f"{d:.2f} m")
        else:
            self._tof_in_since = None
            if d > self.tof_m + TOF_EXIT_MARGIN_M:
                if self._tof_out_since is None:
                    self._tof_out_since = t
                if t - self._tof_out_since >= TOF_REARM_S:
                    self._tof_armed = True
            else:
                self._tof_out_since = None

    # ---- what 1108 did that this booth does not -----------------------------
    def _see_sleep(self, pc):
        pass                                  # the camera sees the table; nothing wakes it

    def _see_doze(self, pc):
        pass                                  # never dozes

    def _wave(self, pc):
        return False

    def _closeness(self, near, pc):
        pass

    # ---- time ---------------------------------------------------------------
    def tick(self):
        t = self.now()
        if self.phase in ("LOOK", "TEACH", "CALL") and t - self._last_near > OWNER_GONE_S:
            self.emit("auto_next", name=f"owner gone {OWNER_GONE_S:.0f} s")
            self.next_visitor()
        elif self.phase == "TEACH" and self._apply_held_answer():
            pass
        elif self.phase == "TEACH" and t - self._teach["since"] > SB.TEACH_MAX_S:
            self._teach_failed("Hmm, I couldn't tell what that was.")
        elif self.phase == "CALL" and t - self._call_since > SB.CALL_MAX_S:
            self.p.request("SK_LOOK")
            self._go("LOOK", say="")

    # ---- awake --------------------------------------------------------------
    def _see_look(self, pc):
        t = pc.t
        owner = self._follow_person(pc)
        if owner is not None:
            self._last_near = t
        # SHOWING NEEDS AN OWNER: the first part of the visit (being woken,
        # finding and following its person) always comes before the second.
        shown = (self._shown(pc) if (self._owner and "watch" in self.on
                                     and t - self._last_near < 1.5) else None)
        if (shown and t - self._teach_done > SB.TEACH_AGAIN_S
                and not (self.target and any(SB.same_thing(shown.label, w)
                                             for w in self.target["words"]))):
            if self._show_since is None:
                self._show_since = t
            if t - self._show_since >= SB.SHOW_S and self.p.state == "SK_LOOK":
                self._show_since = None
                self._teach = dict(since=t, box=shown.box, guess=shown.label)
                self._look_at(shown.at, tilt=None)
                self.p.request("SK_CURIOUS")
                self._go("TEACH", say="Ooh, what's that?")
                self.emit("identify", box=shown.box, guess=shown.label, t=t)
        else:
            self._show_since = None

    def _see_call(self, pc):
        q = self._owner_in(pc)
        if q is not None:
            self._last_near = pc.t

    def _owner_in(self, pc):
        """The owner in this frame, if they are in it (no aiming)."""
        if not self._owner or not pc.people or self._track_pan is None:
            return None
        gone = pc.t - self._track_t
        lim = min(OWNER_BEARING_MAX, OWNER_BEARING_DEG + OWNER_DRIFT_DPS * gone)
        pool = [q for q in pc.people if abs(q.head.pan - self._track_pan) <= lim]
        return min(pool, key=lambda q: abs(q.head.pan - self._track_pan)) if pool else None

    def _follow_person(self, pc):
        """Follow the OWNER, and nobody else.

        The first person seen after the pat -- the closest, which is whoever
        patted it -- becomes the owner. From then on only someone near where
        the owner was counts (the window widens the longer they are unseen,
        since people move); anyone else in the queue is ignored however close.
        Only after OWNER_SWITCH_S without the owner does the closest person
        take over."""
        t = pc.t
        q = None
        if not self._owner:
            if pc.people:
                q = max(pc.people, key=lambda q: q.sw_frac)
                self._owner = True
                self.emit("owner", name=f"size {q.sw_frac:.0%}, bearing {q.head.pan:+.0f}")
        else:
            q = self._owner_in(pc)
            if q is None and pc.people and t - self._track_t > OWNER_SWITCH_S:
                q = max(pc.people, key=lambda q: q.sw_frac)
                self.emit("owner", name=f"new: size {q.sw_frac:.0%}")
        if q is not None:
            pan, nod = q.head.pan, q.head.nod
            if self._track_pan is not None and t - self._track_t < 1.0:
                v = (pan - self._track_pan) / max(0.05, t - self._track_t)
                lead = max(-SB.LEAD_MAX_DEG, min(SB.LEAD_MAX_DEG, v * SB.LEAD_S))
            else:
                lead = 0.0
            self._track_pan, self._track_t = pan, t
            self._track_x = q.head.x / float(pc.wh[0])
            self._chased = False
            if self.p.state == "SK_LOOK":
                self.p.set_aim_deg(pan=pan + lead, tilt=ST.LOOK_TILT, nod=nod)
            return q
        # The owner is not in this frame. Left at an edge, recently: one
        # saccade on in their direction.
        if (self._track_pan is not None and not self._chased
                and t - self._track_t < SB.CHASE_WITHIN_S
                and abs(self._track_x - 0.5) > SB.EDGE_FRAC
                and self.p.state == "SK_LOOK"):
            side = 1.0 if self._track_x > 0.5 else -1.0
            step = SB.CHASE_DEG * side * ST.AIM_X_SIGN
            self.p.set_aim_deg(pan=pc.pose["pan"] + step, tilt=ST.LOOK_TILT,
                               nod=pc.pose["nod"])
            self._chased = True
        return None

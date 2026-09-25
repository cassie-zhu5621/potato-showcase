"""The approach gate: a stream of distances in, a handful of events out.

WHY THIS IS A MODULE AND NOT FOUR LINES IN THE LOOP. "Someone is within 60 cm"
is not a trigger, it is a reading, and every failure this thing can have comes
from treating the two as the same:

  * A person standing on the threshold makes the head rise and fall and rise
    again. That reads as broken, not as alive -- and it is the single most
    likely way the showcase looks bad.
  * At a showcase there is almost always somebody near, so a gate that fires on
    "near" fires forever. What starts an interaction is the TRANSITION.
  * A ToF returns nothing, or returns nonsense, several times a minute. Treated
    as a distance, a dropped reading is either zero (a face pressed to the lens)
    or infinity (the room emptied). Both are wrong and both are dramatic.

None of that is visible in a live demo -- it looks like the robot being moody --
so it is here, pure, with tests, where it can be looked at.

NO I/O. Feed it `(t, mm)` from anywhere: the serial link, a recorded CSV, or a
test. That is what lets the thresholds be fitted against a replayed trace
instead of by standing in front of the robot changing numbers.

THE BANDS, and why the table does the hard part. The robot sits on a table, so a
standing person's torso cannot get nearer than the table edge. Anything reading
closer than that is a hand or a face put there on purpose. So one axis carries
two different meanings without ambiguity:

    far ......... enter ......... near ......... 0
        nobody      a person        a hand
                    arrived        (SHY)

Every number below is PROVISIONAL and marked so. They come off a logged trace
with people actually walking up (docs/SHOWCASE_FLOW.md, "Before the
thresholds"). How much a standing person's reading wanders is what sets the
hysteresis width, and that cannot be reasoned about in advance.
"""
from __future__ import annotations

from collections import deque

# --------------------------------------------------------------------------- #
# MEASURED, from walkups.csv -- 2953 samples, 139 s, 2.3% dropped. Not guesses.
# Re-record and re-read these if the sensor moves; they are a property of the
# mounting and the room, not of the code.
#
#     empty room          1844 mm   the far wall. 435 readings, none under 1500
#     a person standing    330 - 550
#     a hand held in         0 - 250
#
# The gap between 550 and 1844 is enormous, so where ENTER goes inside it barely
# matters; 1000 catches somebody well before they stop.
# --------------------------------------------------------------------------- #
ENTER_MM = 1200.0     # cross this, inward, and somebody may have arrived
EXIT_MM = 1500.0      # ...and they have not left until they pass THIS going out
# NO FLOOR ON ARRIVING. This was `near_mm`, on the reasoning that something at
# 14 cm is a hand rather than somebody walking up -- which is true, and which
# meant that a hand waved at the sensor was the one gesture guaranteed NOT to
# get a reaction. R_SHY does not exist yet, so the floor bought nothing and
# blocked the only thing the showcase actually needs: come close, get looked at.
#
# `too_close` still fires and is still reported. It is the event R_SHY will
# read when there is an R_SHY; it just no longer suppresses the head coming up.
# Zero, and the comparison is strict, so a reading of exactly 0 still does not
# count. That is not a distance: it is the VL53L1X saturating against something
# touching its lens. Everything above it does count, which is the point.
ARRIVE_FLOOR_MM = 0.0

NEAR_MM = 250.0       # a hand: below where anyone stood (min 329)
NEAR_EXIT_MM = 310.0  # 60 mm of hysteresis on a 17 mm wander, and still clear
                      # of the closest standing reading

# THE ONE NUMBER THE TRACE CHANGED, and it was wrong by a factor of four.
#
# Walking straight past without stopping spends 1.03 s inside 600 mm and 1.24 s
# inside 1200 -- and it comes as close as 245 mm on the way through. At the 0.4 s
# guessed here before, a passer-by fired `arrived` AND `too_close`: the robot
# would have looked up at, and then flinched from, somebody on their way to the
# coffee machine.
#
# An arrival that means it holds for 23 s. The two are twenty times apart, so
# the cut is not delicate -- but it has to be above 1.24 s, and 0.4 was not.
#
# 1.5 s is not a delay. Somebody crossing 1 m at walking pace is decelerating,
# and 1.5 s later they have stopped: the head comes up as they settle, which
# reads as having been noticed arriving rather than as a motion detector firing.
# BOTH CONDITIONS, not either. `still` alone lets a pass through: at its
# closest point the distance stops changing -- the derivative crosses zero --
# so for a few hundred ms somebody walking past looks exactly like somebody
# standing. Measured: adding `still` without keeping a dwell turned take2's two
# passes into two arrivals, each followed by `left` a tenth of a second later.
#
# Swept over dwell 0.5-1.5, window 0.5-1.0, tolerance 40-120 mm: 58 of the 60
# combinations give exactly the right two arrivals on both traces. The choice
# is not delicate, so these sit in the middle of the region that works rather
# than at an edge of it.
# TUNED AGAINST THE CLOCK, because the head came up visibly late. The cost of
# an arrival is three things in series: the median filter's lag, the stability
# window having to clear of the approach, and then the dwell. At 0.8 + 1.0 that
# was about 1.8 s after somebody stopped, which reads as the robot thinking
# about it rather than noticing.
#
# Swept against both traces with one objective -- never fire during a pass, and
# be as early as possible otherwise. The floor is 1.14 s. Below it the passes
# start firing, on every combination, so that is not a tuning limit but the
# price of telling an arrival from a crossing at all.
#
# Of the two combinations that reach 1.14 s, this is the one whose work is done
# by the WINDOW rather than the dwell. Neither trace contains a slow amble past
# -- the thing no duration can reject -- and a longer stillness window is the
# half that would catch one, because an ambler has to hold still for it.
DWELL_S = 0.2         # ...of being inside AND still. See `still` in update().
STABLE_WIN_S = 0.8    # the window "still" is measured over. A pass is only
                      # momentarily flat, so this is what rejects one.
APPROACH_MM = 200.0   # a settled level this much nearer than the one before it
                      # is somebody arriving, even in a crowd. Three times the
                      # measured lean (61 mm) and twelve times the sway (17).
                      #
                      # AND THERE IS A LIMIT HERE THAT NO NUMBER FIXES. One
                      # forward-facing ToF reports the nearest thing and cannot
                      # count people. Replaying her trace with somebody already
                      # standing at 700 mm, her approach to 363 is a 337 mm step
                      # and is caught; at 500 it is 137 mm and is not; at 400 it
                      # is 37 mm, which is leaning. So a new arrival is only
                      # visible while the space directly in front is not already
                      # occupied at a similar distance -- and when it is, the
                      # robot is already attending to whoever is standing there,
                      # which is the tolerable version of being wrong.
STABLE_MM = 80.0      # movement inside it that still counts as stopped.
                      # Standing sway measured 8 mm median and 17 at the 95th,
                      # so this is nearly five times the noise and nothing like
                      # a walk.
REFRACTORY_S = 3.0    # after an arrival, ignore further arrivals for this long
LOST_S = 0.5          # readings must be missing this long before "left"
MEDIAN_N = 5          # samples in the spike filter


class Proximity:
    """Distances in, events out. One instance per sensor.

    Events, as strings, at most a few per approach:

        "arrived"    someone crossed in and stayed -- START of an interaction
        "left"       they went back out past the exit threshold
        "too_close"  inside the table edge: a hand or a face, on purpose
        "backed_off" ...and it went away again

    `arrived` is the one the state machine hangs off, and it is deliberately
    hard to emit: it needs a crossing, then a dwell, and then it will not happen
    again until the refractory has passed. The other three are cheap.
    """

    def __init__(self, enter_mm=ENTER_MM, exit_mm=EXIT_MM,
                 near_mm=NEAR_MM, near_exit_mm=NEAR_EXIT_MM,
                 dwell_s=DWELL_S, refractory_s=REFRACTORY_S,
                 lost_s=LOST_S, median_n=MEDIAN_N,
                 stable_win_s=STABLE_WIN_S, stable_mm=STABLE_MM,
                 approach_mm=APPROACH_MM, arrive_floor_mm=ARRIVE_FLOOR_MM):
        if exit_mm <= enter_mm:
            raise ValueError("exit_mm must be OUTSIDE enter_mm -- equal "
                             "thresholds are the flapping bug, not a config")
        if near_exit_mm <= near_mm:
            raise ValueError("near_exit_mm must be outside near_mm")
        if near_mm >= enter_mm:
            raise ValueError("the shy band must be INSIDE the approach band")
        self.enter_mm, self.exit_mm = float(enter_mm), float(exit_mm)
        self.near_mm, self.near_exit_mm = float(near_mm), float(near_exit_mm)
        self.dwell_s, self.refractory_s = float(dwell_s), float(refractory_s)
        self.lost_s = float(lost_s)
        self.stable_win_s, self.stable_mm = float(stable_win_s), float(stable_mm)
        self.approach_mm = float(approach_mm)
        self.arrive_floor_mm = float(arrive_floor_mm)
        self._settle = None          # when the current settle began
        self._ref = None             # the level it settled at last time
        self._ref_pending = True     # one arrival per settle, not per sample
        self._buf = deque(maxlen=int(median_n))
        self._win = []               # (t, mm) over stable_win_s, for `still`

        self.inside = False          # past enter_mm, by the hysteresis rule
        self.near = False            # inside the table edge
        self.distance = None         # last filtered reading, mm, or None
        self._since = None           # when the crossing happened, for the dwell
        self._armed = True           # False during the refractory
        self._last_arrival = None
        self._last_reading_t = None

    # ----------------------------------------------------------------- #
    def update(self, t, mm):
        """One sample. `mm` is None for a dropped or out-of-range reading.

        Returns a list of event strings -- usually empty. Call it at whatever
        rate the sensor runs; nothing here assumes a fixed period, because the
        serial link does not provide one.
        """
        out = []

        # A DROPPED READING IS NOT A DISTANCE. It is the absence of one, and the
        # only safe response is to keep the last state for a moment and then
        # declare the person gone -- never to invent a number. Treating it as 0
        # put a face against the lens; treating it as infinity emptied the room.
        if mm is None:
            if (self._last_reading_t is not None
                    and t - self._last_reading_t > self.lost_s):
                out += self._go_out(t)
                self.distance = None
            return out
        self._last_reading_t = t

        self._buf.append(float(mm))
        # MEDIAN, NOT MEAN. A ToF's bad samples are wild, not noisy -- a single
        # 40 mm spike from a reflection drags a mean through the near threshold
        # and the robot flinches at nothing. A median ignores it entirely.
        d = sorted(self._buf)[len(self._buf) // 2]
        self.distance = d

        # ---- the approach band -------------------------------------- #
        # HAVE THEY STOPPED. Measured over a trailing window, and it is what the
        # dwell is actually for.
        #
        # A duration test cannot tell an amble from an arrival; it can only tell
        # fast from slow. Both recorded traces happen to contain brisk passes
        # (0.4-1.33 s) so 1.5 s covers them, but nothing stops somebody
        # wandering past over three seconds, and no dwell long enough to reject
        # that is short enough to be worth having -- it would delay everyone who
        # really did arrive.
        #
        # Stopping is the thing that actually separates them, and it is trivial
        # to see: a person walking past sweeps through hundreds of mm, a person
        # who has stopped moves by their own sway, which measured 8 mm median
        # and 17 at the 95th. So the dwell runs on "inside AND still", not on
        # "inside", and it can then be short.
        self._win.append((t, d))
        while self._win and t - self._win[0][0] > self.stable_win_s:
            self._win.pop(0)
        vals = [v for _, v in self._win]
        still = (len(self._win) >= 3
                 and t - self._win[0][0] >= self.stable_win_s * 0.6
                 and max(vals) - min(vals) <= self.stable_mm)

        # ---- ARRIVING IS A SETTLE THAT IS NEARER THAN THE LAST ONE ---- #
        #
        # Crossing a threshold from outside cannot carry this on its own.
        # Re-arming that way requires going OUT past exit_mm, and in a crowd the
        # nearest thing is never that far, so the first person within range is
        # noticed and nobody after them ever is. Replayed against her own trace
        # with one other person standing at 700 mm, the approach at t=33 s
        # vanished completely.
        #
        # What survives a crowd is what she asked for: the nearest thing
        # suddenly got closer. So an arrival is a SETTLE whose level is a
        # person's-width nearer than the level before it -- true whether the
        # room was empty or somebody was already standing there.
        #
        # Leaning must not qualify and does not: she leaned 541 -> 480, 61 mm.
        # A hand does not either, hence the near_mm floor; that is `too_close`,
        # which is a different event about a different thing.
        #
        # Once the trigger is a STEP, the "must leave first" guard is redundant
        # and harmful -- what prevents repeats is that a second arrival needs a
        # second step, and standing still is not one. So re-arming is the
        # refractory alone.
        if not still:
            self._settle = None
            self._ref_pending = True
        elif self._settle is None:
            self._settle = t
        elif (self._ref_pending and t - self._settle >= self.dwell_s):
            self._ref_pending = False
            prev, self._ref = self._ref, d
            # prev is None on the FIRST settle of all -- the robot has just
            # been switched on. Somebody already standing there has arrived as
            # far as it is concerned; it has no history to say otherwise, and
            # booting next to a person and ignoring them is worse than greeting
            # someone who has been there a while.
            came_in = prev is None or prev > self.enter_mm
            stepped = prev is not None and d <= prev - self.approach_mm
            if (self._armed and self.arrive_floor_mm < d <= self.enter_mm
                    and (came_in or stepped)):
                self._armed = False
                self._last_arrival = t
                if not self.inside:
                    self.inside = True
                out.append("arrived")

        if not self.inside:
            if d > self.exit_mm:
                # THE DWELL IS CANCELLED BY THE OUTER THRESHOLD, NOT THE INNER
                # ONE. Cancelling on `d > enter_mm` looks right and is the same
                # flapping bug one level down: a person standing AT 60 cm sends
                # the median across the line every few samples, the dwell
                # restarts each time, and they stand there being not-noticed
                # forever. Hysteresis has to cover entering as well as leaving.
                self._since = None
            elif d <= self.enter_mm and still:
                # `inside` is the state the caller watches to know somebody is
                # there. The ARRIVAL is emitted above, off the settle step; this
                # only keeps the flag true so `left` has something to end.
                if self._since is None:
                    self._since = t
                elif t - self._since >= self.dwell_s:
                    self.inside = True
                    self._since = None
        else:
            # HYSTERESIS: leaving uses the OUTER threshold. With one threshold,
            # a person standing at 60 cm breathes and the head bobs.
            if d > self.exit_mm:
                out += self._go_out(t)

        # ---- the shy band, nested inside ---------------------------- #
        if not self.near and d <= self.near_mm:
            self.near = True
            out.append("too_close")
        elif self.near and d > self.near_exit_mm:
            self.near = False
            out.append("backed_off")

        # ---- re-arming ---------------------------------------------- #
        # The refractory runs from the arrival, and re-arming also requires
        # being OUT. At a showcase "somebody is near" is true almost
        # continuously, so a purely time-based re-arm would fire into a crowd
        # every few seconds at whoever happened to be standing closest.
        if (not self._armed and self._last_arrival is not None
                and t - self._last_arrival >= self.refractory_s):
            self._armed = True

        return out

    # ----------------------------------------------------------------- #
    def _go_out(self, t):
        out = []
        if self.inside:
            self.inside = False
            out.append("left")
        if self.near:
            self.near = False
            out.append("backed_off")
        self._since = None
        if (self._last_arrival is not None
                and t - self._last_arrival >= self.refractory_s):
            self._armed = True
        return out

    # ----------------------------------------------------------------- #
    def reset(self):
        """Forget everything. For a state change that invalidates the history --
        the robot being re-homed, or a session restarting."""
        self._buf.clear()
        self._win.clear()
        self._settle = self._ref = None
        self._ref_pending = True
        self.inside = self.near = False
        self.distance = self._since = self._last_arrival = None
        self._last_reading_t = None
        self._armed = True


def parse_dist(line):
    """`IN DIST <mm>` from the CoreS3 -> mm, or None.

    `IN`, not `EVT`. On this link `EVT` is the host talking to the board and
    `IN` is the board answering (`IN BODYTAP`, `IN PONG`), and a reading sent
    the wrong way arrives as a command the firmware does not recognise -- which
    is silent, because handleLine ignores what it cannot parse.

    `IN DIST -1` is the sensor's own way of saying out of range or no return,
    and it must arrive here as None rather than as a negative distance: a
    comparison against a threshold does not care that -1 is impossible, it just
    sees a very small number and reports a face against the lens.
    """
    parts = line.strip().split()
    if len(parts) < 3 or parts[0] != "IN" or parts[1] != "DIST":
        return None
    try:
        v = float(parts[2])
    except ValueError:
        return None
    return None if v < 0 else v

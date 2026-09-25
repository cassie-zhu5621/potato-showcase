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
# provisional, and every one of them is meant to be replaced by a measurement
# --------------------------------------------------------------------------- #
ENTER_MM = 600.0      # cross this, inward, and somebody has arrived
EXIT_MM = 900.0       # ...and they have not left until they pass THIS going out
NEAR_MM = 250.0       # inside the table edge: a hand, not a body
NEAR_EXIT_MM = 350.0
DWELL_S = 0.4         # must stay inside before it counts as an arrival
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
                 lost_s=LOST_S, median_n=MEDIAN_N):
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
        self._buf = deque(maxlen=int(median_n))

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
        if not self.inside:
            if d > self.exit_mm:
                # THE DWELL IS CANCELLED BY THE OUTER THRESHOLD, NOT THE INNER
                # ONE. Cancelling on `d > enter_mm` looks right and is the same
                # flapping bug one level down: a person standing AT 60 cm sends
                # the median across the line every few samples, the dwell
                # restarts each time, and they stand there being not-noticed
                # forever. Hysteresis has to cover entering as well as leaving.
                self._since = None
            elif d <= self.enter_mm:
                if self._since is None:
                    self._since = t
                elif t - self._since >= self.dwell_s:
                    # THE DWELL IS WHAT SEPARATES ARRIVING FROM WALKING PAST.
                    # Somebody crossing the beam on their way somewhere else is
                    # the commonest event in a busy room and it is not an
                    # interaction.
                    self.inside = True
                    self._since = None
                    if self._armed:
                        self._armed = False
                        self._last_arrival = t
                        out.append("arrived")
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
        if (not self._armed and not self.inside
                and self._last_arrival is not None
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

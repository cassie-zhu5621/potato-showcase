#!/usr/bin/env python3
"""
perform.py — play the robot from the keyboard, to music, beside the fish.

You tap the tempo, so you own the speed. The robot keeps a sway going at that
tempo, and the number keys drop gestures into it. Nothing is scripted and
nothing is synchronised between the two machines: the fish's pilot and you both
listen to the same track, which is a conductor neither of you has to be.

  python3 robot/tools/perform.py            # the real thing
  python3 robot/tools/perform.py --dry-run  # no servos, watch the numbers

  SPACE   tap the beat -- four taps sets it, keep tapping and it follows
  F       freeze / release      <- the strongest key here. Use it.
  N L D   sway shape: Nod only / Lean (gaze level) / Dip (whole body)
  ↑ ↓     amplitude
  ← →     nudge the phase, an eighth at a time
  T / G   trim the neck up / down, for looking at something above
  1..6    gestures, quantised
  0       stop the sway, hold still
  Q       quit

THE TWO THINGS THAT MAKE IT LOOK PLAYED RATHER THAN TRIGGERED

**Quantise.** A key is never pressed exactly on a beat. Pressing one queues the
gesture for the next beat instead of firing it, which is what a live looper
does and what makes an unsteady hand come out tight.

**Lead.** A servo takes time to arrive, so a command issued on the beat lands
after it. Everything here is therefore computed LEAD_S in the future: the
oscillator is evaluated ahead of now, and a gesture is fired early by its own
accent offset plus the lead. That is a fixed phase shift, not a tempo change --
it cannot drift, and the tempo is still entirely yours.

ACCENT OFFSETS ARE MEASURED, not guessed: the moment of peak angular speed in
each clip, read off the CSVs. They differ by a factor of four -- S5A_FOUND
lands 0.30 s in, S2_ACKNOWLEDGE 1.17 s in -- so aligning clip STARTS to the
beat would put half the vocabulary visibly off. This is the commonest reason a
robot looks like it cannot keep time, and it is not a tempo problem.
"""
from __future__ import annotations

import argparse
import math
import os
import select
import sys
import termios
import threading
import time
import tty

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

# Seconds into each clip at which its visual accent lands -- the peak of angular
# speed, computed from motion/clips/*.csv. Recompute with tools/clip_accents.py
# if a clip is re-exported.
ACCENT_S = {
    "S1_ATTEND": 0.43, "S2_ACKNOWLEDGE": 1.17, "S3_SCAN": 5.37,
    "S4A_SETTLE": 0.43, "S5A_FOUND": 0.30, "S5B_BECKON": 0.57,
    "S6_CORRECT": 0.47, "S7_ERROR": 2.10,
}
KEY_CLIP = {"1": "S2_ACKNOWLEDGE", "2": "S5A_FOUND", "3": "S5B_BECKON",
            "4": "S6_CORRECT", "5": "S1_ATTEND", "6": "S3_SCAN"}
CLIP_DUR = {"S1_ATTEND": 1.97, "S2_ACKNOWLEDGE": 1.63, "S3_SCAN": 6.13,
            "S4A_SETTLE": 1.20, "S5A_FOUND": 1.73, "S5B_BECKON": 6.53,
            "S6_CORRECT": 2.37, "S7_ERROR": 3.97}

# Mechanical lead. Measured once, by eye, against a click: raise it until the
# bottom of the sway lands ON the beat rather than after it.
LEAD_S = 0.12
AMPS = (3.0, 6.0, 10.0, 15.0)     # degrees, well inside the authored reach
RATE_HZ = 50.0


class Perf:
    def __init__(self, player, verbose=False):
        self.player, self.verbose = player, verbose
        self.bpm = 90.0
        self.t0 = time.perf_counter()     # phase origin: a beat falls here
        self.shape = "nod"                # nod | lean | dip
        self.amp_i = 1
        self.trim = 0.0                   # neck bias, for looking up
        self.frozen = True                # start still; F to begin
        self.taps = []
        self.pending = None               # (fire_at, clip)
        self.busy_until = 0.0
        self._stop = False
        self._th = threading.Thread(target=self._loop, daemon=True)

    # ---------------- tempo ----------------
    @property
    def period(self):
        return 60.0 / self.bpm

    def tap(self):
        now = time.perf_counter()
        self.taps = [t for t in self.taps if now - t < 3.0] + [now]
        if len(self.taps) >= 3:
            gaps = sorted(b - a for a, b in zip(self.taps, self.taps[1:]))
            med = gaps[len(gaps) // 2]
            if 0.2 < med < 2.0:
                self.bpm = 60.0 / med
        # EVERY TAP IS ALSO A DOWNBEAT. Re-anchoring the phase on each tap is
        # what lets you pull the robot back into line without stopping -- if it
        # has drifted against the record, you just tap where the beat really is.
        self.t0 = now

    def phase(self, at=None):
        """Beats since the origin, evaluated LEAD_S ahead so the motion arrives
        on the beat instead of departing on it."""
        t = (at if at is not None else time.perf_counter()) + LEAD_S
        return (t - self.t0) / self.period

    def next_beat(self, after=None):
        """The wall-clock time of the next MUSICAL beat.

        Not the next command time. `phase()` is already shifted by LEAD_S so
        that what it commands ARRIVES on the beat; a beat in wall clock is
        therefore plain `t0 + n * period`, with no lead in it. Returning the
        lead-shifted moment here and then subtracting the lead again in `fire`
        double-counted it, and gestures landed a fifth of a beat early.
        """
        t = after if after is not None else time.perf_counter()
        n = math.ceil((t - self.t0) / self.period + 1e-6)
        return self.t0 + n * self.period

    # ---------------- the sway ----------------
    def pose(self):
        """The oscillator. Phase 0 is the beat, and the beat is the BOTTOM of
        the dip -- the accent of a head bob is where it stops going down."""
        a = AMPS[self.amp_i]
        w = -math.cos(2 * math.pi * self.phase())      # -1 on the beat
        if self.shape == "nod":
            return dict(nod=self.trim + a * w)
        if self.shape == "lean":
            # tilt and nod in OPPOSITION: the body dips and the gaze stays put.
            # The musician's version -- a bassist's head is still while the
            # body moves -- and the same shape as S5A_FOUND's epistemic lean.
            return dict(tilt=a * w, nod=self.trim - a * w)
        return dict(tilt=a * w, nod=self.trim + a * w)   # dip: whole body

    # ---------------- gestures ----------------
    def fire(self, clip):
        """Queue a gesture so its ACCENT lands on a beat, not its first frame."""
        lead = ACCENT_S.get(clip, 0.0) + LEAD_S
        at = self.next_beat()
        # An accent later than one beat in has to be launched before the beat
        # before it. S2_ACKNOWLEDGE's is 1.17 s, which at any tempo over 51 BPM
        # is more than a beat -- so it goes to the next beat that is far enough
        # away, rather than to one that has already passed.
        while at - lead < time.perf_counter():
            at += self.period
        self.pending = (at - lead, clip, at)

    # ---------------- the driver ----------------
    def start(self):
        self._th.start()
        return self

    def stop(self):
        self._stop = True
        self._th.join(timeout=2)

    def _loop(self):
        dt = 1.0 / RATE_HZ
        while not self._stop:
            now = time.perf_counter()
            if self.pending and now >= self.pending[0]:
                _, clip, _ = self.pending
                self.pending = None
                self.busy_until = now + CLIP_DUR.get(clip, 2.0)
                if self.player:
                    self.player.request(clip)
            # THE PHASE KEEPS RUNNING WHILE A CLIP PLAYS. It is read off the
            # wall clock, not accumulated, so the sway resumes exactly in time
            # instead of wherever it was interrupted.
            if not self.frozen and now >= self.busy_until and self.player:
                self.player.drive_deg(**self.pose())
            time.sleep(dt)


def getch(timeout=0.1):
    if select.select([sys.stdin], [], [], timeout)[0]:
        c = sys.stdin.read(1)
        if c == "\x1b" and select.select([sys.stdin], [], [], 0.01)[0]:
            return "\x1b" + sys.stdin.read(2)
        return c
    return None


def main():
    ap = argparse.ArgumentParser(description="keyboard performance mode")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    player = None
    if not a.dry_run:
        from robot.clip_player import ClipPlayer
        from robot.scs import open_bus
        bus, _ = open_bus()
        player = ClipPlayer(bus, verbose=False).start(home=True)

    perf = Perf(player).start()
    old = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        last = 0.0
        while True:
            k = getch()
            if k:
                if k in ("q", "Q"):
                    break
                elif k == " ":
                    perf.tap()
                elif k in ("f", "F"):
                    perf.frozen = not perf.frozen
                elif k in ("n", "N"):
                    perf.shape = "nod"
                elif k in ("l", "L"):
                    perf.shape = "lean"
                elif k in ("d", "D"):
                    perf.shape = "dip"
                elif k == "\x1b[A":
                    perf.amp_i = min(len(AMPS) - 1, perf.amp_i + 1)
                elif k == "\x1b[B":
                    perf.amp_i = max(0, perf.amp_i - 1)
                elif k == "\x1b[C":
                    perf.t0 -= perf.period / 8
                elif k == "\x1b[D":
                    perf.t0 += perf.period / 8
                elif k in ("t", "T"):
                    perf.trim = min(30.0, perf.trim + 3)
                elif k in ("g", "G"):
                    perf.trim = max(-20.0, perf.trim - 3)
                elif k == "0":
                    perf.frozen = True
                elif k in KEY_CLIP:
                    perf.fire(KEY_CLIP[k])
            if time.perf_counter() - last > 0.1:
                last = time.perf_counter()
                beat = perf.phase() % 1.0
                pend = perf.pending[1] if perf.pending else "-"
                sys.stdout.write(
                    "\r  {:5.1f} BPM  {:5}  amp {:4.0f}d  trim {:+3.0f}  "
                    "{}  {}  next:{:<16}".format(
                        perf.bpm, perf.shape, AMPS[perf.amp_i], perf.trim,
                        "FROZEN" if perf.frozen else "  " + "*" * (1 + int(beat * 3)) + " " * (3 - int(beat * 3)),
                        " ", pend))
                sys.stdout.flush()
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
        perf.stop()
        print()
        if player:
            player.request("S0_IDLE")
            time.sleep(1.2)
            player.stop(relax=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

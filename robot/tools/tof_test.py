#!/usr/bin/env python3
"""
tof_test.py — the VL53L1X on Port A, on its own.

Two questions, and nothing else runs while it answers them: no servo bus, no
camera, no models. So a result here is about the sensor and its bracket and
cannot be anything else.

  1. IS IT THERE AND IS IT SANE?   --live
  2. WHERE DO THE THRESHOLDS GO?   --log

THE SECOND ONE IS THE POINT. docs/SHOWCASE_FLOW.md leaves every distance as
<measure> on purpose. The number that cannot be guessed is not the threshold,
it is the WANDER: a person standing still does not produce a constant reading,
and how much it moves is what sets how far apart the enter and exit thresholds
have to be. Too narrow and the head bobs at anyone who stands on the line; too
wide and it notices you late and forgets you slowly. There is no way to reason
that out in advance, so: record people walking up, and read it off.

  python3 robot/tools/tof_test.py                    # live, auto-detect
  python3 robot/tools/tof_test.py --log walkups.csv  # record a session
  python3 robot/tools/tof_test.py --fit walkups.csv  # ...then read it back
  python3 robot/tools/tof_test.py --replay walkups.csv --gate

WHAT TO RECORD, in one take, saying each out loud so it lands in the notes:
people walking up and stopping; standing still for ten seconds; leaning in;
reaching a hand right up to it; stepping back; walking PAST without stopping;
and two people arriving together. The last two are the cases the gate gets
wrong, so a trace without them cannot show that it is right.

THE GOTCHA THAT WASTES AN HOUR. Ambient light. The L1X tolerates far more of it
than the L0X, which is why it was the one to buy, but Long distance mode is the
mode that suffers most. If readings are fine in the lab and ragged at the venue,
that is the sun, not the bracket -- try Short mode before re-mounting anything.
"""
import argparse
import os
import statistics
import sys
import time

# Run me directly: the repo root is two levels up from robot/tools/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from session.cores3_link import CoreS3Link, find_cores3
from session.proximity import Proximity, parse_dist


def bar(mm, width=48, full=2000.0):
    """A distance is easier to judge as a length than as a number, and while you
    are walking towards the robot you are not reading four digits."""
    if mm is None:
        return "·" * width + "   --"
    n = max(0, min(width, int(width * (1.0 - min(mm, full) / full))))
    return "#" * n + "·" * (width - n) + f"  {mm:5.0f} mm"


# --------------------------------------------------------------------------- #
def live(args, rows, fired=None):
    """Stream to the terminal, and to a CSV if asked.

    `--gate` is what makes a second recording worth taking. The first trace
    FITTED the thresholds, so it cannot also test them; a held-out take can,
    and watching the events land while you walk is the whole point -- an
    ARRIVED that prints while you are still three steps away is obvious
    standing there and invisible in a CSV read afterwards.
    """
    gate = Proximity() if args.gate else None
    if fired is None:
        fired = []
    t0 = time.time()
    last_print = 0.0

    def on_line(s):
        nonlocal last_print
        mm = parse_dist(s)
        if mm is None and not s.startswith("IN DIST"):
            if s.startswith("IN TOF") or s.startswith("IN SCAN"):
                print(f"  {s}")
            return
        t = time.time() - t0
        rows.append((t, mm))
        evs = gate.update(t, mm) if gate else []
        for e in evs:
            fired.append((t, e, mm))
            print(f"\n  >>> {e.upper():<12} at {mm if mm else '--'} mm, t={t:6.2f}s")
        if time.time() - last_print > 0.05:
            last_print = time.time()
            print("\r" + bar(mm), end="", flush=True)

    port = args.port or find_cores3()
    if not port:
        sys.exit("no CoreS3 found -- pass the port, or set NOTICEBOT_CORES3")
    link = CoreS3Link(port, on_input=on_line)
    # ASK, do not wait for the boot line. USB CDC enumerates after setup() has
    # run, so IN TOF READY was printed before anything was listening.
    time.sleep(0.4)
    link.tof()
    time.sleep(0.4)
    if args.bus is not None:
        print(f"  re-initialising on {'Wire1' if args.bus else 'Wire'}...")
        link.tofbus(args.bus)
        time.sleep(1.0)
    if args.scan:
        link.scan()
        time.sleep(1.5)
    print(f"listening on {port}. Ctrl-C to stop.")
    print("the PING line above says which firmware is on the board. The ToF")
    print("needs v7 -- if it says v6 the upload did not land, whatever the")
    print("IDE reported, and nothing below this line is about the sensor.")
    print("no `IN TOF` line above?  the firmware predates the ToF -- reflash.")
    print("IN TOF FAIL?             wrong port (it is the RED one, Port A), or")
    print("                         the plug is not seated.")
    print("IN TOF READY but no bar? it is working and seeing nothing: out of")
    print("                         range, or aimed over everyone's head.\n")
    # READY AND SILENT IS ITS OWN FAULT, and it is not the one the notes above
    # describe. It means the board says the sensor initialised and then no
    # reading ever arrives -- a scheduling bug in checkTof, not a sensor or a
    # socket -- and without saying so here the symptom is indistinguishable
    # from "nobody has walked in front of it yet".
    try:
        t_start = time.time()
        warned = False
        while True:
            time.sleep(0.2)
            if (not warned and not rows and time.time() - t_start > 3.0):
                warned = True
                print("\n  READY, but three seconds and not one reading.")
                print("  That is the firmware, not the sensor: it initialised.")
                print("  asking the board what it is actually doing:\n")
                link.tofdiag()
                time.sleep(0.6)
                print("\n  calls=0    checkTof() is not being called from loop()")
                print("  ready=0    the sensor never raises data-ready: ranging")
                print("             is not running, or i2c!=0 means the reads")
                print("             themselves are failing")
                print("  emit>0     readings ARE arriving and something above")
                print("             is dropping them\n")
                print("  i2c=2 with ready=0 is the I2C controller being shared")
                print("  with M5Unified. Try the other one WITHOUT reflashing:")
                print("      python3 %s --bus 1\n" % sys.argv[0])
    except KeyboardInterrupt:
        print()
    finally:
        link.close()
    if gate is not None:
        print(f"\n{len(fired)} events over {rows[-1][0]:.0f}s:" if rows else "")
        for t, e, mm in fired:
            print(f"  {t:7.2f}s  {e:<12} {mm if mm is not None else '--'}")
        n = sum(1 for _, e, _ in fired if e == "arrived")
        print(f"\n  arrived x{n}.  One per person who actually stopped, and")
        print("  none for anyone who only walked past -- that is the test.")


# --------------------------------------------------------------------------- #
def fit(rows):
    """Read the bands off a recorded trace instead of guessing them."""
    got = [mm for _, mm in rows if mm is not None]
    if len(got) < 50:
        sys.exit(f"only {len(got)} valid readings -- record a longer trace")
    drop = 100.0 * (len(rows) - len(got)) / len(rows)

    print(f"\n{len(rows)} samples, {drop:.1f}% with no reading")
    print(f"range {min(got):.0f} .. {max(got):.0f} mm\n")

    # THE WANDER, WHICH IS THE WHOLE REASON FOR RECORDING.
    #
    # DETRENDED, and that is not a refinement. Taking max-minus-min over a
    # half-second window measures whatever the window contains, and half of a
    # useful trace is people WALKING -- so the first version of this reported a
    # 95th-percentile "wander" of 684 mm and suggested an exit threshold of
    # 2.65 m, which is the far wall. That is not noise, it is somebody crossing
    # the room, and no amount of hysteresis should absorb it.
    #
    # Fitting a line across the window and measuring the spread of the RESIDUALS
    # separates the two: walking is the slope, wander is what is left.
    win, wanders = [], []
    for t, mm in rows:
        if mm is None:
            continue
        win.append((t, mm))
        while win and t - win[0][0] > 0.5:
            win.pop(0)
        if len(win) < 6:
            continue
        # readings past ~1.5 m are noisier and are not where any threshold sits
        if statistics.median(m for _, m in win) > 1500:
            continue
        n = len(win)
        mt = sum(x for x, _ in win) / n
        mv = sum(v for _, v in win) / n
        sxx = sum((x - mt) ** 2 for x, _ in win)
        slope = (sum((x - mt) * (v - mv) for x, v in win) / sxx) if sxx else 0.0
        # AND ONLY WHILE THEY ARE STANDING STILL. Detrending removes a ramp but
        # not a step, and a hand reaching in is a step: on a mixed trace the
        # 95th percentile stayed at 570 mm, which is a person's arm, not the
        # sensor. The slope is the discriminator -- standing sway is tens of
        # mm/s, walking is hundreds -- so moving windows are dropped rather
        # than corrected.
        if abs(slope) > 150.0:            # mm/s
            continue
        res = [v - (mv + slope * (x - mt)) for x, v in win]
        wanders.append(max(res) - min(res))
    if len(wanders) < 20:
        print("not enough STANDING-STILL windows to measure the wander.")
        print("Record again with someone holding still in front of it for ten")
        print("seconds -- that stretch is the only part of the take this needs.")
        wanders = []
    if wanders:
        wanders.sort()
        p50 = wanders[len(wanders) // 2]
        p95 = wanders[int(len(wanders) * 0.95)]
        print(f"wander over 0.5 s, standing still ({len(wanders)} windows):")
        print(f"  median {p50:.0f} mm, 95th {p95:.0f} mm")
        print(f"  -> the gap between enter and exit should be at least {p95:.0f} mm,")
        print(f"     and comfortably more. Under that, someone standing on the")
        print(f"     line makes the head rise and fall.\n")

    # A dwell has to outlast a walk-past. The trace should contain some.
    print("Suggested starting point -- CHECK IT AGAINST --replay --gate:")
    enter = 600.0
    gap = max(200.0, (p95 if wanders else 100.0) * 3)
    print(f"  ENTER_MM      {enter:.0f}")
    print(f"  EXIT_MM       {enter + gap:.0f}      (enter + 3x the 95th wander)")
    print(f"  NEAR_MM       measure your table edge and subtract a little")
    print(f"  DWELL_S       0.4")
    if drop > 5:
        print(f"\n  {drop:.0f}% of readings were invalid. Over about 5%, look at the")
        print("  mounting and the light before tuning anything else -- a gate")
        print("  cannot fix a sensor that is not seeing.")


def replay(rows, gate):
    """Run a recorded trace through the gate. Changing a threshold and re-running
    this takes a second; changing one and walking up to the robot takes a minute
    and you cannot repeat the walk exactly."""
    n = 0
    for t, mm in rows:
        for e in gate.update(t, mm):
            n += 1
            print(f"  {t:7.2f}s  {e:<12} {mm if mm is not None else '--'}")
    print(f"\n{n} events over {rows[-1][0]:.0f}s from {len(rows)} samples")
    print("read it as a story: does every 'arrived' match a person you remember")
    print("walking up, and is there one per person rather than three?")


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="VL53L1X on Port A, nothing else")
    ap.add_argument("port", nargs="?", default=os.environ.get("NOTICEBOT_CORES3"),
                    help="the CoreS3 port; omitted = auto-detect")
    ap.add_argument("--log", metavar="CSV", help="record the trace while running")
    ap.add_argument("--fit", metavar="CSV", help="read bands off a recorded trace")
    ap.add_argument("--replay", metavar="CSV", help="run a trace through the gate")
    ap.add_argument("--bus", type=int, choices=(0, 1), default=None,
                    help="re-init the sensor on I2C controller 0 (Wire) or 1 "
                         "(Wire1) and carry on. For when TOFDIAG shows ready=0 "
                         "with i2c=2: M5Unified has the other one")
    ap.add_argument("--scan", action="store_true",
                    help="scan Port A's I2C on both pin orders and stop. Run "
                         "this when init fails: it separates a swapped pair "
                         "from a wrong socket from a unit that is not there")
    ap.add_argument("--gate", action="store_true",
                    help="also run the Proximity gate and print its events")
    a = ap.parse_args()

    if a.fit or a.replay:
        import csv
        path = a.fit or a.replay
        rows = []
        with open(path) as f:
            for r in csv.reader(f):
                if not r or r[0].startswith("#") or r[0] == "t":
                    continue
                rows.append((float(r[0]), None if r[1] in ("", "-1") else float(r[1])))
        if a.fit:
            fit(rows)
        else:
            replay(rows, Proximity())
        return 0

    rows, fired = [], []
    try:
        live(a, rows, fired)
    finally:
        if a.log and rows:
            with open(a.log, "w") as f:
                f.write("t,mm\n")
                for t, mm in rows:
                    f.write(f"{t:.3f},{'' if mm is None else int(mm)}\n")
            print(f"wrote {len(rows)} samples to {a.log}")
            print(f"now:  python3 {sys.argv[0]} --fit {a.log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

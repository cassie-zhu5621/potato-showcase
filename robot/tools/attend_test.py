#!/usr/bin/env python3
"""
attend_test.py — walk up to it and watch the head come up. Nothing else.

The first end-to-end piece of the showcase loop: the ToF on Port A, the
proximity gate, and the neck. No camera, no planner, no VLM, no network. So a
result here is about the trigger and the motion and cannot be anything else --
and it is the only way to find out whether 0.8 s of stillness FEELS like being
noticed, which no replay can answer.

  python3 robot/tools/attend_test.py                 # the real thing
  python3 robot/tools/attend_test.py --dry-run       # no servos, events only
  python3 robot/tools/attend_test.py --log t3.csv    # record while testing

WHAT TO TRY, in rough order of how likely it is to disappoint:

  1. Walk up and stop.                  The head should come up as you settle,
                                        not before and not a beat late.
  2. Walk straight past without stopping.   Nothing should happen. This is the
                                        one the thresholds were rebuilt around.
  3. Put a CHAIR at about 70 cm and leave it there, then walk up beside it.
     Still works -- and it is the whole reason arriving is a step closer rather
     than a threshold crossing. In a crowd the sensor never reads far again,
     and the first design went deaf after one person.
  4. Stand there and lean in and out.   Leaning is 61 mm and must not re-trigger.
  5. Reach a hand right up to it.       `too_close`. It does not move yet --
                                        R_SHY is not built.

THE HEAD IS SLOWER THAN THE GATE. S1_ATTEND is an authored clip on its own
clock; the gate fires in milliseconds and then the neck takes as long as it
takes. If the rise feels late, time the two separately before changing any
threshold -- `--dry-run` prints the events with no motion at all, and that is
the gate's own latency.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from session.cores3_link import CoreS3Link, find_cores3
from session.proximity import Proximity, parse_dist


def main():
    ap = argparse.ArgumentParser(description="approach -> the head comes up")
    ap.add_argument("--port", default=os.environ.get("NOTICEBOT_CORES3"),
                    help="the CoreS3; omitted = auto-detect")
    ap.add_argument("--dry-run", action="store_true",
                    help="no servo bus. The gate's own latency, with nothing "
                         "mechanical in front of it")
    ap.add_argument("--log", metavar="CSV", help="record the trace as well")
    ap.add_argument("--bus", type=int, choices=(0, 1), default=None,
                    help="re-init the ToF on I2C controller 0 (Wire) or 1. "
                         "The flashed default is 0")
    a = ap.parse_args()

    player, servo_port = None, None
    if not a.dry_run:
        from robot.clip_player import ClipPlayer
        from robot.scs import open_bus
        # open_bus returns (bus, port) -- every other tool in here unpacks it,
        # and passing the tuple straight to ClipPlayer fails four frames later
        # inside flush_input, where it looks like a driver problem.
        bus, servo_port = open_bus()
        player = ClipPlayer(bus, verbose=False).start(home=True)
        player.request("S0_IDLE")
        print("servos live. S0_IDLE.")
    else:
        print("dry run: no servo bus opened.")

    gate = Proximity()
    rows, t0 = [], time.time()
    state = {"s": "S0_IDLE"}
    hb = {"at": 0.0, "why": None}

    def go(clip, why):
        state["s"] = clip
        print(f"\n  >>> {clip:<16} {why}")
        if player:
            player.request(clip)

    def on_line(s):
        mm = parse_dist(s)
        if mm is None and not s.startswith("IN DIST"):
            # EVERYTHING the board says, not a whitelist. The first version
            # printed only lines starting "IN TOF", so a RESTART or a DIAG or a
            # boot message could arrive and be silently dropped -- and then the
            # symptom is "no reaction", which is the least informative thing a
            # tool can say.
            if s.strip():
                print(f"\n  {s}")
            return
        t = time.time() - t0
        rows.append((t, mm))
        for e in gate.update(t, mm):
            d0 = gate.distance
            if e == "arrived":
                go("S1_ATTEND", f"somebody stopped at {d0:.0f} mm")
            elif e == "left" and state["s"] != "S0_IDLE":
                go("S0_IDLE", "they went away")
            elif e == "too_close":
                # R_SHY is not authored yet. Saying so beats moving wrongly.
                # THE FILTERED DISTANCE, not the raw sample. Printing `mm`
                # here produced "too_close at 2093 mm", which is impossible --
                # the threshold is 250 -- and sent an hour looking at the
                # sensor instead of at this line.
                print(f"\n  ... too_close at {d0:.0f} mm  (R_SHY not built)")
            elif e == "backed_off":
                print(f"\n  ... backed_off")
        # A HEARTBEAT ON ITS OWN LINE, once a second, instead of a bar
        # rewritten in place. A \r bar looks better and cannot be pasted into a
        # message: the terminal keeps only its final state, so "no reaction"
        # arrives with no evidence attached. This prints what the gate is
        # actually thinking, which is the only thing that explains a silence.
        now = time.time()
        if now - hb["at"] >= 1.0:
            hb["at"] = now
            d = gate.distance
            win = [v for _, v in gate._win]
            spread = (max(win) - min(win)) if len(win) > 1 else 0.0
            st = spread <= gate.stable_mm and len(win) > 2
            print("  t={:5.1f}  d={:>7}  spread={:>5.0f}mm  still={}  "
                  "inside={}  armed={}  ref={}".format(
                      t, f"{d:.0f}mm" if d else "--", spread,
                      "Y" if st else "n",
                      "Y" if gate.inside else "n",
                      "Y" if gate._armed else "n",
                      f"{gate._ref:.0f}" if gate._ref else "--"))
            # WHY IT IS NOT FIRING, said out loud. Every silence here has a
            # reason the numbers above already contain, and reading them off
            # takes knowing the thresholds. Twice now the answer was that the
            # thing being held up was at 14 cm -- which is a hand by
            # definition, not somebody arriving -- and the tool sat there
            # looking broken instead of saying so.
            if st and d is not None and hb["why"] != "":
                if d <= gate.arrive_floor_mm:
                    why = ("reading 0 mm -- the sensor is saturated against "
                           "something on its lens, which is not a distance.")
                elif d > gate.enter_mm:
                    why = (f"{d:.0f} mm is beyond {gate.enter_mm:.0f}; nothing "
                           f"has come near enough to count as arriving.")
                elif not gate._armed:
                    why = "still inside the refractory; wait 3 s and try again."
                elif gate._ref is not None and d > gate._ref - gate.approach_mm:
                    why = (f"only {gate._ref - d:.0f} mm nearer than the last "
                           f"settle ({gate._ref:.0f}); needs "
                           f"{gate.approach_mm:.0f}.")
                else:
                    why = ""
                if why and why != hb["why"]:
                    hb["why"] = why
                    print(f"           ^ no arrival: {why}")

    # EXCLUDE THE SERVO PORT. Both boards enumerate as /dev/cu.usbmodem*, and
    # find_cores3 probes each candidate by opening it and writing PING -- which
    # on the Feetech adapter means resetting the servo bus mid-session, under a
    # ClipPlayer that is already driving it.
    port = a.port or find_cores3(exclude=(servo_port,) if servo_port else ())
    if not port:
        sys.exit("no CoreS3 found")
    link = CoreS3Link(port, on_input=on_line)
    time.sleep(0.4)
    link.tof()
    time.sleep(0.5)
    link.dist(True)          # the board does not stream unless asked
    time.sleep(0.3)
    if a.bus is not None:
        print(f"  re-initialising the ToF on {'Wire1' if a.bus else 'Wire'}...")
        link.tofbus(a.bus)
        time.sleep(1.2)
    print(f"\nlistening on {port}. Walk up to it. Ctrl-C to stop.\n")
    try:
        t_start, asked = time.time(), False
        while True:
            time.sleep(0.2)
            # READY AND SILENT. Opening the servo bus probes every
            # /dev/cu.usbmodem*, which resets the CoreS3, and find_cores3 then
            # opens it again -- so by the time we are listening the board has
            # rebooted twice and tofInit() has run on a sensor that never lost
            # power. Whether that is what breaks it is a question for TOFDIAG,
            # not for guessing: ready=0 with i2c=2 is the bus, calls=0 is the
            # loop, emit>0 means the readings are arriving and we are dropping
            # them here.
            if not asked and not rows and time.time() - t_start > 3.0:
                asked = True
                print("\n  three seconds, no readings. asking the board:")
                link.tofdiag()
                time.sleep(0.8)
                print("\n  if ready=0 try:  --bus 1")
                print("  if calls=0 the firmware is older than TOFDIAG\n")
    except KeyboardInterrupt:
        print()
    finally:
        link.close()
        if player:
            player.request("S0_IDLE")
            time.sleep(1.0)
            player.stop(relax=True)
        if a.log and rows:
            with open(a.log, "w") as f:
                f.write("t,mm\n")
                for t, mm in rows:
                    f.write(f"{t:.3f},{'' if mm is None else int(mm)}\n")
            print(f"wrote {len(rows)} samples to {a.log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

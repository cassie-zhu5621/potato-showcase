#!/usr/bin/env python3
"""
aim_check.py -- which way is "image right" for the head? Measured, not guessed.

  python3 robot/tools/aim_check.py --cam 1

The sidekick mode aims the head at things it sees (a face, a prop), so it needs
the sign between pixels and joints: does a thing on the RIGHT of the frame need
more pan or less, and a thing at the TOP more nod or less? Getting either wrong
makes the robot look away from everything it is shown, smoothly and confidently.

The robot measures it itself. It looks at whatever is in front of it, turns pan
by +8 deg, and finds how far the picture slid (phase correlation of the two
frames -- any textured scene works, nobody needs to stand there). Same for nod.
Then it prints the two lines for robot/states.py.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import cv2                                  # noqa: E402
import numpy as np                          # noqa: E402

from robot.scs import open_bus              # noqa: E402
from robot.clip_player import ClipPlayer    # noqa: E402
from robot import states as ST              # noqa: E402
from perception.headcam import HeadCam      # noqa: E402

STEP = 8.0


def grab(cam, settle=0.8):
    time.sleep(settle)
    seq = cam.seq
    while cam.seq < seq + 3:              # a few frames after the move ended
        time.sleep(0.02)
    g = cv2.cvtColor(cam.latest, cv2.COLOR_BGR2GRAY).astype(np.float32)
    return cv2.GaussianBlur(g, (0, 0), 2)


def ramp(player, **to):
    """drive_deg jumps; a ramp keeps every move here under ~60 deg/s."""
    frm = player.pose_deg()
    dist = max(abs(to[j] - frm[j]) for j in to)
    n = max(2, int(dist / 2.0))
    for i in range(1, n + 1):
        u = i / n
        player.drive_deg(**{j: frm[j] + (to[j] - frm[j]) * u for j in to})
        time.sleep(1 / 30)


def shift(a, b):
    (dx, dy), resp = cv2.phaseCorrelate(a, b)
    return dx, dy, resp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=0)
    ap.add_argument("--port", default=os.environ.get("NOTICEBOT_PORT"))
    a = ap.parse_args()

    bus, port = open_bus(a.port, 1_000_000)
    player = ClipPlayer(bus, verbose=False)
    player.start(home=True)            # a timed move to centre, then idle
    player.stop(relax=False)           # stop the thread; drive_deg owns the bus
    cam = HeadCam(a.cam)
    w = cam.latest.shape[1]
    px_per_deg = w / ST.CAM_HFOV_DEG
    base = dict(pan=0.0, tilt=ST.LOOK_TILT, nod=ST.LOOK_NOD)
    try:
        ramp(player, **base)
        f0 = grab(cam, 1.5)
        ramp(player, **dict(base, pan=base["pan"] + STEP))
        f1 = grab(cam)
        dx, _, r1 = shift(f0, f1)
        ramp(player, **base)
        f0 = grab(cam)
        ramp(player, **dict(base, nod=base["nod"] + STEP))
        f2 = grab(cam)
        _, dy, r2 = shift(f0, f2)
        ramp(player, **base)
    finally:
        cam.close()

    print(f"pan +{STEP:.0f} deg -> picture moved {dx:+.0f} px (confidence {r1:.2f})")
    print(f"nod +{STEP:.0f} deg -> picture moved {dy:+.0f} px (confidence {r2:.2f})")
    print(f"expected about {STEP * px_per_deg:.0f} px for each")
    if min(r1, r2) < 0.05 or min(abs(dx), abs(dy)) < 0.3 * STEP * px_per_deg:
        print("\n!! the measurement is weak. Point the head at something with "
              "texture (not a blank wall) and run again.")
        return 1
    # Turning +pan slides the picture by dx. A thing at image-right needs the
    # head to turn so the picture slides LEFT (negative dx) to centre it.
    xs = +1 if dx < 0 else -1
    # +nod slides the picture by dy (image y grows downward). A thing at the
    # TOP needs the picture to slide DOWN (positive dy) to centre it.
    ys = +1 if dy > 0 else -1
    print("\nset in robot/states.py:")
    print(f"AIM_X_SIGN = {xs:+d}")
    print(f"AIM_Y_SIGN = {ys:+d}")
    if (xs, ys) == (ST.AIM_X_SIGN, ST.AIM_Y_SIGN):
        print("(already set like this)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import cv2                                  # noqa: E402
import numpy as np                          # noqa: E402

from robot.scs import open_bus              # noqa: E402
from robot.clip_player import ClipPlayer    # noqa: E402
from robot import states as ST              # noqa: E402
from perception.headcam import HeadCam      # noqa: E402

CAM = None

STEP = 8.0
WIN = "head camera -- SPACE: measure   q: quit"


def show(cam, text=""):
    """The live picture, so you can see what the head is looking at."""
    im = cam.latest.copy()
    h, w = im.shape[:2]
    cv2.line(im, (w // 2 - 30, h // 2), (w // 2 + 30, h // 2), (0, 255, 255), 2)
    cv2.line(im, (w // 2, h // 2 - 30), (w // 2, h // 2 + 30), (0, 255, 255), 2)
    if text:
        cv2.putText(im, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                    (0, 255, 255), 2)
    s = 960.0 / w
    cv2.imshow(WIN, cv2.resize(im, (int(w * s), int(h * s))))
    return cv2.waitKey(1) & 0xFF


def wait(sec, cam, text):
    t0 = time.time()
    while time.time() - t0 < sec:
        show(cam, text)


def grab(cam, settle=0.8):
    wait(settle, cam, "measuring...")
    seq = cam.seq
    while cam.seq < seq + 3:              # a few frames after the move ended
        show(cam, "measuring...")
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
        if CAM is not None:
            show(CAM, "moving...")


def actual(player):
    """Where the servos REALLY are, read back from the bus (degrees)."""
    from robot.pose import IDS, unit_to_deg
    out = {}
    for j, sid in IDS.items():
        u = player.bus.read_pos(sid)
        out[j] = None if u is None else round(unit_to_deg(j, u), 1)
    return out


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
    global CAM
    CAM = cam
    w = cam.latest.shape[1]
    px_per_deg = w / ST.CAM_HFOV_DEG
    base = dict(pan=0.0, tilt=ST.LOOK_TILT, nod=ST.LOOK_NOD)
    try:
        ramp(player, **base)
        # LOOK FIRST. This is the head's own view; aim it (or turn the whole
        # robot) at something with texture, then press SPACE.
        while True:
            k = show(cam, "aim at something textured, then SPACE")
            if k == ord(" "):
                break
            if k in (ord("q"), 27):
                print("quit -- nothing measured")
                return 1
        # Everything is saved, so a bad result can be looked at instead of
        # guessed at: the four frames, and where the servos really were.
        out = os.path.join(ROOT, "session_feed",
                           "aim_check_" + time.strftime("%Y%m%d_%H%M%S"))
        os.makedirs(out, exist_ok=True)
        f0 = grab(cam, 0.5)
        p0 = actual(player)
        cv2.imwrite(os.path.join(out, "1_start.jpg"), cam.latest)
        ramp(player, **dict(base, pan=base["pan"] + STEP))
        f1 = grab(cam)
        p1 = actual(player)
        cv2.imwrite(os.path.join(out, "2_pan_plus8.jpg"), cam.latest)
        dx, _, r1 = shift(f0, f1)
        ramp(player, **base)
        f0b = grab(cam)
        cv2.imwrite(os.path.join(out, "3_back.jpg"), cam.latest)
        ramp(player, **dict(base, nod=base["nod"] + STEP))
        f2 = grab(cam)
        p2 = actual(player)
        cv2.imwrite(os.path.join(out, "4_nod_plus8.jpg"), cam.latest)
        _, dy, r2 = shift(f0b, f2)
        ramp(player, **base)
        diff_pan = float(np.abs(f1 - f0).mean())
        diff_nod = float(np.abs(f2 - f0b).mean())
        show(cam, "done -- see the terminal")
        cv2.waitKey(800)
    finally:
        cam.close()
        cv2.destroyAllWindows()

    print(f"servos read back: start {p0}  after pan {p1}  after nod {p2}")
    print(f"picture change (mean grey difference): pan {diff_pan:.1f}  nod {diff_nod:.1f}"
          f"   (near 0 = the picture did not change at all)")
    print(f"frames saved in {out}")
    if p0["pan"] is not None and p1["pan"] is not None and abs(p1["pan"] - p0["pan"]) < 4:
        print("\n!! the PAN SERVO DID NOT MOVE (read back above). Check the "
              "servo supply: python3 robot/tools/check_bus.py")
        return 1
    if max(diff_pan, diff_nod) < 1.0:
        print("\n!! the head moved but the picture did not change: this --cam is "
              "NOT the camera on the head. Try another number "
              "(python3 noticebot_loop.py --list-cams).")
        return 1
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

#!/usr/bin/env python3
"""
nap_pose.py -- find the 1124 resting pose: looks asleep, still sees people.

  python3 robot/tools/nap_pose.py --cam N

Moves the head to the nap pose (motion/sidekick/generate_sk_nap.py: body
leaning back, head drooping forward) and shows the head camera with what the
booth would sense there: shoulders / faces, and NEAR or passer, exactly as
perception/sidekick_sense.py judges them. Walk past it, stand at 1-3 m, and
adjust until people are seen while it still looks asleep.

Keys (in the camera window)
  w / s     body leans back / forward   (tilt +2 / -2)
  i / k     head up / droops more       (nod  +2 / -2)
  0         S0_IDLE's head-down pose, to compare (does the nap look as asleep?)
  n         back to the nap pose being tuned
  p         print the two lines for generate_sk_nap.py
  q         quit (the head stays where it is, torque on)
"""
import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import cv2                                  # noqa: E402

from robot.scs import open_bus              # noqa: E402
from robot.clip_player import ClipPlayer    # noqa: E402
from robot.pose import clamp_deg            # noqa: E402
from perception.headcam import HeadCam      # noqa: E402
from perception import sidekick_sense as SS  # noqa: E402

WIN = "nap pose -- w/s tilt  i/k nod  0 S0  n nap  p print  q quit"
S0 = dict(pan=0.0, tilt=-8.0, nod=-42.0)


def ramp(player, **to):
    frm = player.pose_deg()
    dist = max(abs(to[j] - frm[j]) for j in to)
    n = max(2, int(dist / 1.5))
    for i in range(1, n + 1):
        u = i / n
        player.drive_deg(**{j: frm[j] + (to[j] - frm[j]) * u for j in to})
        time.sleep(1 / 30)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=0)
    ap.add_argument("--port", default=os.environ.get("NOTICEBOT_PORT"))
    ap.add_argument("--tilt", type=float, default=15.0)
    ap.add_argument("--nod", type=float, default=-22.0)
    a = ap.parse_args()

    bus, port = open_bus(a.port, 1_000_000)
    player = ClipPlayer(bus, verbose=False)
    player.start(home=True)
    player.stop(relax=False)           # drive_deg owns the bus from here
    cam = HeadCam(a.cam)
    print("[cv] loading pose + face models ...")
    from perception.relations import PoseEstimator, Tracker
    from perception.gaze import HeadPoseEstimator
    poses, tracker = PoseEstimator(max_people=4), Tracker()
    faces = HeadPoseEstimator(max_faces=4)

    nap = dict(pan=0.0, tilt=a.tilt, nod=a.nod)
    showing = "nap"
    ramp(player, **nap)
    try:
        while True:
            want = nap if showing == "nap" else S0
            frame = cam.latest.copy()
            h, w = frame.shape[:2]
            people = tracker.assign(poses.estimate(frame), (w, h), time.time())
            rays = faces.estimate(frame)
            pc = SS.sense(people, [], (w, h), player.pose_deg(), time.time(),
                          faces=rays)
            for p in people:
                for j in (SS.L_SH, SS.R_SH, SS.NOSE):
                    if j in p.pts:
                        cv2.circle(frame, tuple(int(v) for v in p.pts[j]), 8,
                                   (0, 255, 255), -1)
            for q in pc.people:
                tag = "NEAR" if q.near else "passer"
                cv2.putText(frame, f"{tag} {q.sw_frac:.0%}",
                            (int(q.head.x) - 60, max(40, int(q.head.y) - 30)),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                            (60, 220, 60) if q.near else (200, 200, 200), 2)
            seen = (f"{len(pc.people)} seen" if pc.people else "NOBODY seen")
            cv2.rectangle(frame, (0, 0), (w, 60), (20, 20, 20), -1)
            cv2.putText(frame, f"{showing.upper()}  tilt {want['tilt']:+.0f}  "
                               f"nod {want['nod']:+.0f}  gaze "
                               f"{want['tilt'] + want['nod']:+.0f}   {seen}",
                        (16, 42), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 255), 2)
            s = 1100.0 / w
            cv2.imshow(WIN, cv2.resize(frame, (int(w * s), int(h * s))))
            k = cv2.waitKey(30) & 0xFF
            if k in (ord("q"), 27):
                break
            moved = True
            if k == ord("w"):
                nap["tilt"] = clamp_deg("tilt", nap["tilt"] + 2)[0]
            elif k == ord("s"):
                nap["tilt"] = clamp_deg("tilt", nap["tilt"] - 2)[0]
            elif k == ord("i"):
                nap["nod"] = clamp_deg("nod", nap["nod"] + 2)[0]
            elif k == ord("k"):
                nap["nod"] = clamp_deg("nod", nap["nod"] - 2)[0]
            elif k == ord("0"):
                showing = "S0"
            elif k == ord("n"):
                showing = "nap"
            elif k == ord("p"):
                print(f"NAP_TILT = {nap['tilt']:.1f}\nNAP_NOD = {nap['nod']:.1f}"
                      f"      # gaze {nap['tilt'] + nap['nod']:+.0f}")
                moved = False
            else:
                moved = False
            if moved:
                if k in (ord("w"), ord("s"), ord("i"), ord("k")):
                    showing = "nap"
                ramp(player, **(nap if showing == "nap" else S0))
    finally:
        print(f"last nap pose: NAP_TILT = {nap['tilt']:.1f}, NAP_NOD = {nap['nod']:.1f}")
        cam.close()
        poses.close()
        faces.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    sys.exit(main())

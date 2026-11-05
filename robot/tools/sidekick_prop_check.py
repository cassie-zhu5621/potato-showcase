#!/usr/bin/env python3
"""
sidekick_prop_check.py -- which props does the detector see reliably here?

  python3 robot/tools/sidekick_prop_check.py --cam 1

Hold each candidate up to the robot's camera at about arm's length for the
whole countdown, moving it a little the way a visitor would. For each one the
script asks YOLO-World for ALL the candidate words at once (as the booth does)
and reports how often the right word won, and what it was mistaken for.

Keep the three or four best (found in >= 80% of frames, rarely confused), put
those on the tray, and narrow PROPS in perception/sidekick_sense.py to them --
fewer words also means fewer chances to confuse one for another.
"""
import argparse
import collections
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from perception.headcam import HeadCam            # noqa: E402
from perception.perceive import make_detector     # noqa: E402
from perception import sidekick_sense as SS       # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=0)
    ap.add_argument("--conf", type=float, default=0.2)
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--props", default=",".join(SS.PROPS))
    a = ap.parse_args()
    props = [p.strip() for p in a.props.split(",") if p.strip()]
    det = make_detector("yoloworld", props, conf=a.conf)
    cam = HeadCam(a.cam)
    rows = []
    try:
        for want in props:
            input(f"\nhold up the {want.upper()} and press Enter (or Ctrl-C to stop) ")
            for k in (3, 2, 1):
                print(f"  {k}...")
                time.sleep(0.7)
            n, hit, other = 0, 0, collections.Counter()
            t0 = time.time()
            while time.time() - t0 < a.seconds:
                d = det.detect(cam.latest)
                n += 1
                labels = [x.label for x in d]
                if want in labels:
                    hit += 1
                for lb in labels:
                    if lb != want:
                        other[lb] += 1
            rate = hit / max(1, n)
            rows.append((want, rate, n, other.most_common(2)))
            print(f"  {want}: {rate:.0%} of {n} frames"
                  + (f"   also called: {other.most_common(2)}" if other else ""))
    except KeyboardInterrupt:
        pass
    finally:
        cam.close()
    print("\nbest first:")
    for want, rate, n, conf in sorted(rows, key=lambda r: -r[1]):
        mark = "KEEP" if rate >= 0.8 and sum(c for _, c in conf) < 0.2 * n else "    "
        print(f"  {mark}  {want:<12} {rate:5.0%}   confused with {conf or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

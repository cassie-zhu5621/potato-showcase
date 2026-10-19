#!/usr/bin/env python3
"""
annotate_frames.py — put the live overlay back onto saved frames.

  python3 robot/tools/annotate_frames.py \
      --plan  session_feed/<run>/sweeps/<t>/plan.json \
      --frames session_feed/<run>/llm/judge_group_<t>/frame_*.jpg \
      --out    fig/live

WHAT THIS IS FOR. The feed keeps the RAW frames on purpose -- the storyboard
panels are a record of what happened in the room, and `tools/replay_ui.py` says
the rest plainly: the per-frame CV overlay, "skeletons, gaze rays, the relation
ribbon", was never saved. It only ever existed in the live window.

So for a figure that needs the overlay -- the detector's boxes coloured by the
VLM's tiering, the pose skeletons, the gaze and pointing rays -- it has to be
recomputed. This does that offline, through the REAL `PlanView`: the same
detector, the same relation engine and the same `draw()` the live loop uses, so
the picture is the system's own output rather than an illustration of it.

NEEDS THE CV ENVIRONMENT (torch, ultralytics, mediapipe) -- the same one the
loop runs in. It is slow and that does not matter; nothing here is live.

IT IS A RECONSTRUCTION, AND THE FIGURE SHOULD SAY SO. The boxes come from
running the detector again now, not from what it found that day. The plan it is
tiered against IS the one recorded in plan.json, so the tiering is historical
even though the detections are not.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))


def main():
    ap = argparse.ArgumentParser(description="redraw the live overlay offline")
    ap.add_argument("--plan", required=True,
                    help="the sweep's plan.json -- supplies the watch-spec and "
                         "the focus/detect tiering the boxes are coloured by")
    ap.add_argument("--frames", nargs="+", required=True,
                    help="raw jpgs, in order. Globs are fine")
    ap.add_argument("--out", required=True)
    ap.add_argument("--detector", default="yoloworld")
    ap.add_argument("--conf", type=float, default=0.2)
    ap.add_argument("--header", default="",
                    help="text drawn top-left; empty for a clean figure")
    a = ap.parse_args()

    # A PLACEHOLDER IS NOT A MISSING FILE, and saying "no frames matched" to
    # somebody who pasted `<this folder>` sends them looking at their data.
    # The docs that shipped with this tool had angle brackets in a block that
    # reads as copy-pasteable, so this is the likelier mistake, not the rarer.
    for v in list(a.frames) + [a.plan, a.out]:
        if "<" in v or ">" in v:
            sys.exit(f"{v!r} still has a placeholder in it. Every path here "
                     f"wants to be absolute and real -- see the RUN_THIS.sh "
                     f"next to the frames, which has them filled in.")
    if not os.path.exists(a.plan):
        sys.exit(f"no plan at {a.plan!r}")
    paths = sorted(p for g in a.frames for p in glob.glob(g))
    if not paths:
        sys.exit(f"no frames matched {a.frames!r}. Quote the glob so the shell "
                 f"hands it over unexpanded, and check the directory exists.")
    plan = json.load(open(a.plan))
    spec = plan.get("watch_spec") or plan.get("spec") or {}
    os.makedirs(a.out, exist_ok=True)

    import cv2
    from planning.plan_view import PlanView

    view = PlanView(detector=a.detector, conf=a.conf,
                    vocab=sorted(set(plan.get("detect") or [])
                                 | set(plan.get("focus") or [])
                                 | {"person"}))
    view.set_plan(spec, plan.get("context", ""))

    # WARM IT ON THE FIRST FRAME, AND THROW THAT ONE AWAY. The relation engine
    # is stateful by design: hands-on needs a sustained contact, approach needs
    # a distance history, gathering needs a count that has settled. Drawing the
    # first frame it ever sees would show an engine that has not yet had time
    # to believe anything -- which is not what the live window looked like at
    # the moment being illustrated.
    t0 = time.time()
    first = cv2.imread(paths[0])
    if first is None:
        sys.exit(f"cannot read {paths[0]}")
    view.step(first, t0)

    for i, p in enumerate(paths):
        fr = cv2.imread(p)
        if fr is None:
            print(f"  skipped {p}: unreadable")
            continue
        # The frames are ~0.5 s apart in the burst; feeding real spacing keeps
        # the engine's own clocks honest rather than collapsing them.
        view.step(fr, t0 + 0.5 * (i + 1))
        out = os.path.join(a.out, f"{i:02d}_" + os.path.basename(p))
        cv2.imwrite(out, view.draw(fr.copy(), a.header))
        truth = sorted(k for k, v in (view.truth or {}).items() if v)
        print(f"  {out}   true: {truth or '-'}")

    print(f"\n  {len(paths)} frames. These are RECOMPUTED detections, tiered "
          f"against the plan recorded that day --\n  say so in the caption.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

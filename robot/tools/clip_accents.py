#!/usr/bin/env python3
"""
clip_accents.py — when each clip's visual accent lands, from the CSVs.

perform.py aligns a gesture's ACCENT to the beat, not its first frame, and the
offsets differ by a factor of four across the vocabulary. Re-run this after any
clip is re-exported and paste the result into perform.ACCENT_S -- a stale offset
does not look like a stale number, it looks like the robot cannot keep time.

The accent is taken as the peak of angular speed: the moment the gesture is
most obviously happening to an eye watching it.
"""
import csv, os, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLIPS = os.path.join(ROOT, "motion", "clips")

print("ACCENT_S = {")
for fn in sorted(os.listdir(CLIPS)):
    if not fn.endswith(".csv"):
        continue
    r = list(csv.DictReader(open(os.path.join(CLIPS, fn))))
    t = np.array([int(x["t_ms"]) for x in r]) / 1000.0
    p = np.array([[float(x["pan_deg"]), float(x["tilt_deg"]), float(x["nod_deg"])]
                  for x in r])
    v = np.linalg.norm(np.diff(p, axis=0), axis=1) / np.maximum(np.diff(t), 1e-6)
    if not len(v) or v.max() <= 0:
        continue
    print(f'    "{fn[:-4]}": {t[int(np.argmax(v))]:.2f},'
          f'   # of {t[-1]:.2f}s')
print("}")

# generate_sk_guard_alert.py -- SK_GUARD_ALERT (one-shot). showcase-1108.
# Run inside motion/src/SK_GUARD_ALERT.blend (Save As from S4_WATCH.blend).
#
# WHAT IT IS. The robot is guarding a visitor's thing (SK_GUARD, eye locked on
# it where it was put down) and
# a hand comes near it. Before anything is taken, the robot lets the hand know it
# has been seen: it straightens up and goes still. If the thing is then taken,
# the conductor goes to S5A_FOUND; if the hand withdraws, this clip finishes by
# easing back into the watch hold.
#
# NO ANTICIPATION, ON PURPOSE. Everything else in the library winds up first.
# A startle does not: it is the one reaction whose meaning is that there was no
# time to prepare. A wind-up here would read as a performance of alertness.
#
# THE GAZE DOES NOT MOVE. The neck straightens out of the watch lean while the
# head counter-rotates by the same amount, so the eye stays on the mat. That is
# S4A_SETTLE's lean-and-cancel morpheme run backwards: S4a arrives at a region
# by leaning in with the gaze fixed; the alert stands up out of it with the gaze
# fixed. Posture changes, attention does not.
#
# Pan is the watch bearing, held constant, so the player retargets it to the mat
# exactly as it does S4B_WATCH (PAN_RETARGETABLE).

import math
import bpy
import os

# ---- load sidekick_lib.py (shared plumbing) the way the S-generators load reach.py
def _find_lib():
    for s in (os.path.dirname(bpy.data.filepath), os.getcwd()):
        d = os.path.abspath(s or ".")
        for _ in range(8):
            for rel in (os.path.join("motion", "blender", "sidekick_lib.py"),
                        "sidekick_lib.py"):
                p = os.path.join(d, rel)
                if os.path.exists(p):
                    return p
            up = os.path.dirname(d)
            if up == d:
                break
            d = up
    raise RuntimeError("Cannot find motion/blender/sidekick_lib.py. Save the "
                       ".blend inside the repo (motion/src/) and run again.")
_lib = _find_lib()
with open(_lib) as _fh:
    exec(compile(_fh.read(), _lib, "exec"), globals())

HOLD_PAN = 25.0        # = generate_s4b_watch.py HOLD_PAN (template, retargeted)
HOLD_TILT = -12.0      # = generate_s4b_watch.py HOLD_TILT
HOLD_NOD = 12.0        # = generate_s4b_watch.py HOLD_NOD
UP_TILT = 12.0         # straighten fully: tilt -12 -> 0
                       # head cancels: nod 12 -> 0, gaze stays at 0

SNAP_S = 0.22          # fast: 12 deg at ~100 deg/s peak
FREEZE_S = 1.40        # stillness is the vigilance (puppetry: stillness carries focus)
RELAX_S = 0.80         # back into the watch hold if nothing happened
LED_HOLD = 3.0         # = S4B crest
LED_ALERT = 7.5        # jumps with the snap, held through the freeze

set_hue("cool")
reach.check("tilt", HOLD_TILT + UP_TILT, "upright")
reach.check("nod", HOLD_NOD - UP_TILT, "head cancels")
check_move("tilt", UP_TILT, SNAP_S, "snap upright")
check_move("nod", UP_TILT, SNAP_S, "head cancels")
check_move("tilt", UP_TILT, RELAX_S, "relax")

S_F, Z_F, R_F = frames(SNAP_S), frames(FREEZE_S), frames(RELAX_S)
END_F = S_F + Z_F + R_F + 1

for f in range(1, END_F + 1):
    i = f - 1
    up = seg(i, 0, S_F) - seg(i, S_F + Z_F, R_F)
    key_pose(f, HOLD_PAN, HOLD_TILT + UP_TILT * up, HOLD_NOD - UP_TILT * up)
    key_led(f, lerp(LED_HOLD, LED_ALERT, min(1.0, i / max(1.0, S_F / 2.0))
                    if i <= S_F + Z_F else 1.0 - seg(i, S_F + Z_F, R_F)))

finish(END_F, "SK_GUARD_ALERT", [
    f"snap upright {UP_TILT:.0f} deg in {SNAP_S}s, head cancels: gaze stays on the mat",
    f"freeze {FREEZE_S}s, relax in {RELAX_S}s. No wind-up (startle). {END_F}f ({END_F / FPS:.2f}s)",
])

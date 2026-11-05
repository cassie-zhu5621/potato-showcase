# generate_sk_curious.py -- SK_CURIOUS (one-shot, entry-relative). showcase-1108.
# Run inside motion/src/SK_CURIOUS.blend (Save As from any clip .blend with the
# 3-DOF rig, e.g. S2_ACKNOWLEDGE.blend).
#
# WHAT IT IS. Someone holds a thing up to the robot. Live aim has already turned
# the eye onto the thing; this clip is the robot's interest in it: "what's that?"
#
# ENTRY-RELATIVE. Authored from the live-aim base pose (LOOK_TILT, LOOK_NOD,
# pan 0); the player translates every joint so frame 1 is wherever the robot
# actually is. The prop decides the bearing, not the clip.
#
# BEATS
#   1 anticipation  a small pull BACK before leaning in (the wind-up)
#   2 lean in       the neck leans toward the thing and the head does NOT cancel
#                   it, so the gaze drops onto the thing: S5A_FOUND's epistemic
#                   lean ("looking closer"), at a smaller scale. Same morpheme,
#                   so the library keeps one meaning for it.
#   3 "hm?"         two small RISING head lifts, the second smaller. Rising, not
#                   dipping: a dip is assent (S2), a rise is a question.
#   4 hold          it stays leaned in. Live FOLLOW takes over from this pose, so
#                   the robot keeps its nose close to the thing while it moves.

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

LOOK_TILT = -12.0      # = robot/sidekick.py LOOK_TILT (live-aim base, neck)
LOOK_NOD = 22.0        # = robot/sidekick.py LOOK_NOD  (gaze +10: a held object
                       #   or a standing face)
BACK_TILT = 3.0        # anticipation: neck back (>= 2.05 floor)
LEAN_TILT = 10.0       # lean forward, net from the base
LEAN_NOD = 6.0         # head drops with it: gaze falls by 16 onto the thing
Q1 = 7.0               # first "hm?" lift
Q2 = 4.0               # second, smaller (>= 3.52 floor)

HOLD_IN_S = 0.05
BACK_S = 0.25
LEAN_S = 0.50
Q_HALF_S = 0.16        # rise and fall of each lift
Q_GAP_S = 0.06
HOLD_OUT_S = 0.30
LED_BASE = 3.0         # cool, attending
LED_PEAK = 5.0         # brightens on the first "hm?"

set_hue("cool")
for j, v, w in (("tilt", LOOK_TILT + BACK_TILT, "pull back"),
                ("tilt", LOOK_TILT - LEAN_TILT, "lean in"),
                ("nod", LOOK_NOD - LEAN_NOD + Q1, "hm? top")):
    reach.check(j, v, w)
check_move("tilt", BACK_TILT, BACK_S, "anticipation")
check_move("tilt", BACK_TILT + LEAN_TILT, LEAN_S, "lean in")
check_move("nod", LEAN_NOD, LEAN_S, "head drops with the lean")
check_move("nod", Q1, Q_HALF_S, "hm? 1")
check_move("nod", Q2, Q_HALF_S, "hm? 2")

H = frames(HOLD_IN_S)
B_F, L_F, QH_F, QG_F = frames(BACK_S), frames(LEAN_S), frames(Q_HALF_S), frames(Q_GAP_S)
L_AT = B_F
Q1_AT = L_AT + L_F
Q2_AT = Q1_AT + 2 * QH_F + QG_F
END_F = H + Q2_AT + 2 * QH_F + frames(HOLD_OUT_S) + 1


def lift(i, at, mag):
    return mag * (seg(i, at, QH_F) - seg(i, at + QH_F, QH_F))


for f in range(1, END_F + 1):
    i = (f - 1) - H
    t = (LOOK_TILT + BACK_TILT * seg(i, 0, B_F)
         - (BACK_TILT + LEAN_TILT) * seg(i, L_AT, L_F))
    n = (LOOK_NOD - LEAN_NOD * seg(i, L_AT, L_F)
         + lift(i, Q1_AT, Q1) + lift(i, Q2_AT, Q2))
    key_pose(f, 0.0, t, n)
    key_led(f, lerp(LED_BASE, LED_PEAK, lift(i, Q1_AT, 1.0)))

finish(END_F, "SK_CURIOUS", [
    f"pull back {BACK_TILT:.0f}, lean in {LEAN_TILT:.0f} (head drops {LEAN_NOD:.0f}: gaze onto the thing)",
    f"two rising 'hm?' lifts {Q1:.0f} / {Q2:.0f} deg; ends leaned in for FOLLOW",
    f"{END_F}f ({END_F / FPS:.2f}s). Translated onto the live pose at runtime.",
])

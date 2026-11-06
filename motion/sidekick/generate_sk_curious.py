# generate_sk_curious.py -- SK_CURIOUS (one-shot, entry-relative). showcase-1108.
# Run inside SK_CURIOUS.blend (Save As from any clip .blend with the
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
#   1 anticipation  a clear pull BACK, head lifting with it, held a beat: the
#                   wind-up, a small double-take (v2: was a 3-degree shift
#                   that did not read on the robot)
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

# ---- load sidekick_lib.py from THIS script's folder (motion/sidekick/) --------
# Found through the Text Editor's own record of where this script was opened
# from, so it works wherever the .blend is saved.
def _sk_dir():
    for t in bpy.data.texts:
        fp = bpy.path.abspath(t.filepath) if t.filepath else ""
        d = os.path.dirname(fp)
        if fp and os.path.exists(os.path.join(d, "sidekick_lib.py")):
            return d
    raise RuntimeError(
        "Open this script FROM its file (Text Editor > Open > "
        "showcase/motion/sidekick/" + "<this script>), not pasted in: "
        "sidekick_lib.py is found next to it.")
_SK_DIR = _sk_dir()
_lib = os.path.join(_SK_DIR, "sidekick_lib.py")
with open(_lib) as _fh:
    exec(compile(_fh.read(), _lib, "exec"), globals())

LOOK_TILT = -12.0      # = robot/sidekick.py LOOK_TILT (live-aim base, neck)
LOOK_NOD = 22.0        # = robot/sidekick.py LOOK_NOD  (gaze +10: a held object
                       #   or a standing face)
BACK_TILT = 8.0        # anticipation: neck back. v2: was 3 -- on the robot the
                       #   wind-up did not read; 8 is a visible recoil
BACK_NOD = 5.0         # v2: the head lifts with the recoil, chin up, a small
                       #   "oh!" -- a double-take rather than a lean shifting
                       #   its weight (>= 3.52 floor)
LEAN_TILT = 10.0       # lean forward, net from the base
LEAN_NOD = 6.0         # head drops with it: gaze falls by 16 onto the thing
Q1 = 7.0               # first "hm?" lift
Q2 = 4.0               # second, smaller (>= 3.52 floor)

HOLD_IN_S = 0.05
BACK_S = 0.30
BACK_HOLD_S = 0.40     # a beat held at the top of the recoil, so the
                       #   wind-up reads as its own moment before the lean.
                       #   v3: 0.15 -> 0.40, still too short to read on the robot
LEAN_S = 0.50
Q_HALF_S = 0.16        # rise and fall of each lift
Q_GAP_S = 0.06
HOLD_OUT_S = 0.30
LED_BASE = 3.0         # cool, attending
LED_PEAK = 5.0         # brightens on the first "hm?"

set_hue("cool")
for j, v, w in (("tilt", LOOK_TILT + BACK_TILT, "pull back"),
                ("tilt", LOOK_TILT - LEAN_TILT, "lean in"),
                ("nod", LOOK_NOD + BACK_NOD, "head up on the recoil"),
                ("nod", LOOK_NOD - LEAN_NOD + Q1, "hm? top")):
    reach.check(j, v, w)
check_move("tilt", BACK_TILT, BACK_S, "anticipation")
check_move("nod", BACK_NOD, BACK_S, "head up on the recoil")
check_move("nod", BACK_NOD + LEAN_NOD, LEAN_S, "head comes down into the lean")
check_move("tilt", BACK_TILT + LEAN_TILT, LEAN_S, "lean in")
check_move("nod", LEAN_NOD, LEAN_S, "head drops with the lean")
check_move("nod", Q1, Q_HALF_S, "hm? 1")
check_move("nod", Q2, Q_HALF_S, "hm? 2")

H = frames(HOLD_IN_S)
B_F, L_F, QH_F, QG_F = frames(BACK_S), frames(LEAN_S), frames(Q_HALF_S), frames(Q_GAP_S)
L_AT = B_F + frames(BACK_HOLD_S)
Q1_AT = L_AT + L_F
Q2_AT = Q1_AT + 2 * QH_F + QG_F
END_F = H + Q2_AT + 2 * QH_F + frames(HOLD_OUT_S) + 1


def lift(i, at, mag):
    return mag * (seg(i, at, QH_F) - seg(i, at + QH_F, QH_F))


for f in range(1, END_F + 1):
    i = (f - 1) - H
    t = (LOOK_TILT + BACK_TILT * seg(i, 0, B_F)
         - (BACK_TILT + LEAN_TILT) * seg(i, L_AT, L_F))
    n = (LOOK_NOD + BACK_NOD * seg(i, 0, B_F)
         - (BACK_NOD + LEAN_NOD) * seg(i, L_AT, L_F)
         + lift(i, Q1_AT, Q1) + lift(i, Q2_AT, Q2))
    key_pose(f, 0.0, t, n)
    key_led(f, lerp(LED_BASE, LED_PEAK, lift(i, Q1_AT, 1.0)))

# The rising sound belongs to the first rising lift: it starts as the head
# starts up, so the two read as one "hm?" (states.py SK_CURIOUS sfx_at).
SFX_AT = (H + Q1_AT) / float(END_F)
finish(END_F, "SK_CURIOUS", [
    f"recoil {BACK_TILT:.0f} back + head up {BACK_NOD:.0f}, hold {BACK_HOLD_S}s, "
    f"lean in {LEAN_TILT:.0f} (head drops {LEAN_NOD:.0f}: gaze onto the thing)",
    f"two rising 'hm?' lifts {Q1:.0f} / {Q2:.0f} deg; ends leaned in for FOLLOW",
    f"{END_F}f ({END_F / FPS:.2f}s). Translated onto the live pose at runtime.",
    f"SET states.py SK_CURIOUS sfx_at = {SFX_AT:.2f}",
])

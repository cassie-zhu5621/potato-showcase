# generate_sk_purr.py -- SK_PURR (one-shot interjection, entry-relative). showcase-1108.
# Run inside SK_PURR.blend (Save As from any 3-DOF clip .blend).
#
# WHAT IT IS. Someone touches the robot's head while it has no task. The robot
# answers the touch the way an animal answers a hand: it presses up INTO it.
# Then it returns to whatever it was doing (the player resumes the interrupted
# state), so a pat never costs the visitor their place.
#
# THE REFERENT IS THE HAND. Every beat is about the touch, which is above and on
# the head: the dip registers the contact, the rise goes toward the hand, the
# rocking is the head moving under it.
#
# NO PAN. Horizontal oscillation is negation in this library (S6 shakes, S7
# sways). A nuzzle drawn on pan would say "no" to the person stroking it, so the
# rub is drawn on the neck, forward and back.
#
# BEATS
#   1 registers     a small dip as the hand lands (anticipation)
#   2 leans in      head and neck rise into the hand, slow in / slow out
#   3 rub           two small forward-back rocks of the neck under the hand
#   4 lets go       back to the entry pose, the head overshooting a little below
#                   and settling (follow-through)

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

LOOK_TILT = -12.0      # template entry pose = live-aim base (robot/sidekick.py)
LOOK_NOD = 22.0
DIP_NOD = 4.0          # (>= 3.52 floor)
RISE_NOD = 16.0        # head up into the hand
RISE_TILT = 6.0        # neck rises with it
ROCK_TILT = 3.0        # each rock (>= 2.05 floor)
OVERSHOOT_NOD = 4.0    # follow-through below the entry pose on the way back

HOLD_IN_S = 0.0        # a touch answer must not wait
DIP_S = 0.15
RISE_S = 0.60
ROCK_HALF_S = 0.30
N_ROCKS = 2
RETURN_S = 0.60
SETTLE_S = 0.40
LED_BASE = 2.0
LED_GLOW = 6.0         # a warm swell that lasts the whole touch

set_hue("warm")
for j, v, w in (("nod", LOOK_NOD + RISE_NOD, "into the hand"),
                ("tilt", LOOK_TILT + RISE_TILT + ROCK_TILT, "rock top"),
                ("nod", LOOK_NOD - DIP_NOD, "registering dip"),
                ("nod", LOOK_NOD - OVERSHOOT_NOD, "overshoot")):
    reach.check(j, v, w)
check_move("nod", DIP_NOD, DIP_S, "registering dip")
check_move("nod", DIP_NOD + RISE_NOD, RISE_S, "rise into the hand")
check_move("tilt", RISE_TILT, RISE_S, "neck rises")
check_move("tilt", ROCK_TILT, ROCK_HALF_S, "rock")
check_move("nod", RISE_NOD + OVERSHOOT_NOD, RETURN_S, "let go")
check_move("tilt", RISE_TILT, RETURN_S, "neck back")
check_move("nod", OVERSHOOT_NOD, SETTLE_S, "settle")

D_F, R_F, K_F = frames(DIP_S), frames(RISE_S), frames(ROCK_HALF_S)
RISE_AT = D_F
ROCK_AT = RISE_AT + R_F
RET_AT = ROCK_AT + 2 * K_F * N_ROCKS
RET_F = frames(RETURN_S)
SET_AT = RET_AT + RET_F
SET_F = frames(SETTLE_S)
END_F = frames(HOLD_IN_S) + SET_AT + SET_F + 1


def rock(i):
    r = 0.0
    for k in range(N_ROCKS):
        a = ROCK_AT + 2 * K_F * k
        r += ROCK_TILT * (seg(i, a, K_F) - seg(i, a + K_F, K_F))
    return r


for f in range(1, END_F + 1):
    i = (f - 1) - frames(HOLD_IN_S)
    n = (LOOK_NOD - DIP_NOD * seg(i, 0, D_F)
         + (DIP_NOD + RISE_NOD) * seg(i, RISE_AT, R_F)
         - (RISE_NOD + OVERSHOOT_NOD) * seg(i, RET_AT, RET_F)
         + OVERSHOOT_NOD * seg(i, SET_AT, SET_F))
    t = (LOOK_TILT + RISE_TILT * seg(i, RISE_AT, R_F) + rock(i)
         - RISE_TILT * seg(i, RET_AT, RET_F))
    key_pose(f, 0.0, t, n)
    glow = seg(i, 0, D_F + R_F) - seg(i, RET_AT, RET_F + SET_F)
    key_led(f, lerp(LED_BASE, LED_GLOW, glow))

finish(END_F, "SK_PURR", [
    f"dip {DIP_NOD:.0f}, rise {RISE_NOD:.0f} nod / {RISE_TILT:.0f} tilt into the hand,"
    f" {N_ROCKS} rocks of {ROCK_TILT:.0f} on the neck, no pan",
    f"lets go through -{OVERSHOOT_NOD:.0f} and settles. {END_F}f ({END_F / FPS:.2f}s)",
])

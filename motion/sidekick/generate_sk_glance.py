# generate_sk_glance.py -- SK_GLANCE (one-shot, target-relative). showcase-1108.
# Run inside SK_GLANCE.blend (open SK_DOZE.blend after running
# generate_sk_doze.py, File > Save As SK_GLANCE.blend, then run this).
#
# WHAT IT IS. From SK_DOZE, the robot looks at someone who is passing or leaving,
# holds the look, and goes back. It is the only movement DOZE ever makes, and it
# always has a referent: the person the camera just detected (movement <=> result).
#
# AUTHORED AT A TEMPLATE BEARING OF +60 DEG, SCALED DOWN AT RUNTIME. The player
# scales the pan excursion to the person's real bearing (never up, so the speed
# check here is the worst case) and translates the clip onto the pose it is
# entered from. 60 is the widest glance the conductor will ask for.
#
# BEATS
#   1 anticipation  the head lifts a little BEFORE the body turns: the eyes
#                   lead, the way a person's do when something catches them.
#   2 turn          pan to the person, slow in / slow out.
#   3 look          hold. The head is up at a standing person's face height.
#   4 return        slower than the turn: going back is not an event.
#   5 settle        follow-through on the head, one small dip below doze and back.

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

ENTRY_PAN, ENTRY_TILT, ENTRY_NOD = 0.0, -3.0, 6.0   # = SK_DOZE's pose (template)
TARGET_PAN = 60.0      # template bearing; the player scales this to the person
LOOK_NOD = 14.0        # head up to a standing face: gaze +3 -> +17
LIFT_NOD = 5.0         # anticipation: part of the way up before the turn
SETTLE_DIP = 4.0       # follow-through below doze, then back (>= 3.52 floor)

HOLD_IN_S = 0.10
LIFT_S = 0.25
TURN_AT_S = 0.15       # the turn starts before the lift ends: one act, not two
TURN_S = 0.60
LOOK_S = 0.70          # the hold itself
RETURN_S = 0.90
SETTLE_S = 0.45
LED_BASE = 1.6         # inherits DOZE's mid-breath level
LED_LOOK = 3.2         # a soft rise while it looks: attention, not alarm

set_hue("warm")
for j, v, w in (("pan", ENTRY_PAN + TARGET_PAN, "template target"),
                ("nod", ENTRY_NOD + LOOK_NOD, "looking up"),
                ("nod", ENTRY_NOD - SETTLE_DIP, "settle dip")):
    reach.check(j, v, w)
check_move("nod", LIFT_NOD, LIFT_S, "anticipation lift")
check_move("pan", TARGET_PAN, TURN_S, "turn")
check_move("nod", LOOK_NOD - LIFT_NOD, TURN_S, "head up during turn")
check_move("pan", TARGET_PAN, RETURN_S, "return")
check_move("nod", LOOK_NOD + SETTLE_DIP, RETURN_S, "head down on return")
check_move("nod", SETTLE_DIP, SETTLE_S, "settle")

H = frames(HOLD_IN_S)
LIFT_F, TURN_AT_F, TURN_F = frames(LIFT_S), frames(TURN_AT_S), frames(TURN_S)
LOOK_AT_F = TURN_AT_F + TURN_F
RET_AT_F = LOOK_AT_F + frames(LOOK_S)
RET_F = frames(RETURN_S)
SET_AT_F = RET_AT_F + RET_F
SET_F = frames(SETTLE_S)
END_F = H + SET_AT_F + SET_F + 1

for f in range(1, END_F + 1):
    i = (f - 1) - H
    p = (ENTRY_PAN + TARGET_PAN * seg(i, TURN_AT_F, TURN_F)
         - TARGET_PAN * seg(i, RET_AT_F, RET_F))
    up = (LIFT_NOD * seg(i, 0, LIFT_F)
          + (LOOK_NOD - LIFT_NOD) * seg(i, TURN_AT_F, TURN_F))
    down = (LOOK_NOD + SETTLE_DIP) * seg(i, RET_AT_F, RET_F)
    back = SETTLE_DIP * seg(i, SET_AT_F, SET_F)
    key_pose(f, p, ENTRY_TILT, ENTRY_NOD + up - down + back)
    look = seg(i, TURN_AT_F, TURN_F) - seg(i, RET_AT_F, RET_F)
    key_led(f, lerp(LED_BASE, LED_LOOK, look))

finish(END_F, "SK_GLANCE", [
    f"template turn {TARGET_PAN:+.0f} deg in {TURN_S}s, look {LOOK_S}s, back in {RETURN_S}s",
    f"head lifts {LIFT_NOD:.0f} deg first, then to {LOOK_NOD:+.0f}; settles through -{SETTLE_DIP:.0f}",
    f"{END_F}f ({END_F / FPS:.2f}s). Pan is scaled to the person at runtime.",
])

# generate_sk_ack.py -- SK_ACK (one-shot, entry-relative). showcase-1108.
# Run inside motion/src/SK_ACK.blend (Save As from S2_ACKNOWLEDGE.blend).
#
# WHAT IT IS. S2_ACKNOWLEDGE's nod, without S2's journey. S2 opens on S1's
# listening pose and ends upright, ready to scan; in the sidekick mode "got it"
# happens wherever the robot is already looking (at a prop it has just
# examined, at the person who came back for their thing), so it has to be
# entry-relative. The nod itself is S2's, number for number, so the library
# keeps ONE affirmation: two dips, the second 0.545 of the first
# (generate_s2_acknowledge.py explains the ratio).

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

LOOK_TILT = -12.0      # template entry pose = live-aim base (robot/sidekick.py)
LOOK_NOD = 22.0
CYCLE1_MAG = 18.0      # = generate_s2_acknowledge.py
CYCLE_RATIO = 0.545    # = generate_s2_acknowledge.py
CYCLE2_MAG = CYCLE1_MAG * CYCLE_RATIO
CYCLE_S = 0.40         # = generate_s2_acknowledge.py
HOLD_IN_S = 0.10
HOLD_OUT_S = 0.25
LED_BASE = 3.0
LED_SWELL = 6.0        # = S2: one swell, on the first cycle only

set_hue("cool")
reach.check("nod", LOOK_NOD - CYCLE1_MAG, "cycle 1 bottom")
check_move("nod", CYCLE1_MAG, CYCLE_S / 2.0, "cycle 1")
check_move("nod", CYCLE2_MAG, CYCLE_S / 2.0, "cycle 2")

H = frames(HOLD_IN_S)
C_F = frames(CYCLE_S)
END_F = H + 2 * C_F + frames(HOLD_OUT_S) + 1


def dip(i, at, mag):
    half = C_F / 2.0
    return mag * (seg(i, at, half) - seg(i, at + half, half))


for f in range(1, END_F + 1):
    i = (f - 1) - H
    d = dip(i, 0, CYCLE1_MAG) + dip(i, C_F, CYCLE2_MAG)
    key_pose(f, 0.0, LOOK_TILT, LOOK_NOD - d)
    key_led(f, lerp(LED_BASE, LED_SWELL, dip(i, 0, 1.0)))

SFX_AT = (H + C_F / 2.0) / float(END_F)
finish(END_F, "SK_ACK", [
    f"S2's nod: {CYCLE1_MAG:.0f} + {CYCLE2_MAG:.1f} deg at {1 / CYCLE_S:.1f} Hz, no straighten",
    f"{END_F}f ({END_F / FPS:.2f}s). SET states.py SK_ACK sfx_at = {SFX_AT:.2f}",
])

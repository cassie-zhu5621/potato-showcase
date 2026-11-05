# generate_sk_doze.py -- SK_DOZE (loop). showcase-1108, sidekick mode only.
# Run inside SK_DOZE.blend (open S0_IDLE.blend, File > Save As
# SK_DOZE.blend, then run this). OVERWRITES all keys in that copy only.
#
# WHAT IT IS. The resting state of the sidekick mode, replacing S0_IDLE there
# (S0_IDLE stays the resting state of the paper flow). Asleep enough to be
# restful, awake enough to SEE: the head is up and the camera faces the room, so
# a passer-by can be noticed and answered with SK_GLANCE. S0's head-down pose
# looks at the table, which is why nothing could be glanced at from it.
#
# THE POSE IS THE WHOLE SIGNAL, AND THE BODY IS STILL. S0_IDLE's measurement
# applies unchanged: motion slow enough to be ambient cannot be smooth on these
# servos (8.8 deg/s smoothness floor vs ~5.4 deg/s ambient budget), and a
# periodic shift with no referent breaks the movement <=> result rule. So the
# body holds; the LED breathes; every movement out of this state is a GLANCE at
# someone who is really there.
#
# v2 (2026-11-05, after seeing it on the robot): the neck NO LONGER keeps S0's
# forward lean. With the neck at S0's -8 the whole head hung forward and the eye
# looked at the table edge -- it read as still asleep, and the camera saw
# visitors' bodies rather than their faces. The neck now stands almost upright
# (a few degrees forward, so it is relaxed rather than at attention) and the
# head tips up a little: eye level to slightly above, at standing faces.

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

DOZE_TILT = -3.0       # neck almost upright: relaxed, not at attention
DOZE_NOD = 6.0         # head tipped up a little: gaze +3 deg, standing faces
                       # at a few metres are in the middle of the frame
DOZE_PAN = 0.0         # facing out from the booth

BREATH_S = 4.2         # a little quicker than S0's 5.0: dozing, not asleep
BREATH_RISE = 0.34     # = S0: passive exhale longer than inhale
N_BREATHS = 6          # whole breaths, so the loop seam does not tick
LED_LO = 0.40          # never 0 (reads as off)
LED_HI = 2.8           # just above S0's 2.5: present, still not asking
SAMPLE_F = 3

set_hue("warm")
reach.check("tilt", DOZE_TILT, "doze neck")
reach.check("nod", DOZE_NOD, "doze head")

BREATH_F = frames(BREATH_S)
END_F = BREATH_F * N_BREATHS


def breath(i):
    p = (i % BREATH_F) / float(BREATH_F)
    if p < BREATH_RISE:
        return 0.5 * (1.0 - math.cos(math.pi * p / BREATH_RISE))
    return 0.5 * (1.0 + math.cos(math.pi * (p - BREATH_RISE) / (1.0 - BREATH_RISE)))


for f in list(range(1, END_F + 1, SAMPLE_F)) + [END_F]:
    i = f - 1
    key_pose(f, DOZE_PAN, DOZE_TILT, DOZE_NOD)
    key_led(f, LED_LO + (LED_HI - LED_LO) * breath(i))

finish(END_F, "SK_DOZE", [
    f"held pose pan {DOZE_PAN:+.0f} / tilt {DOZE_TILT:+.0f} / nod {DOZE_NOD:+.0f}"
    f" (gaze {DOZE_TILT + DOZE_NOD:+.0f} deg), body still",
    f"LED {LED_LO}-{LED_HI}, {N_BREATHS} breaths of {BREATH_S}s = {END_F / FPS:.1f}s loop",
])

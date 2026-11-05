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
# The neck keeps S0's angle and only the head comes up. Waking from S0 to DOZE
# is then one joint, read as "lifts its head", and DOZE -> S0 at the end of the
# day is the same act reversed.

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

SLEEP_TILT = -8.0      # = generate_s0_idle.py DROOP_TILT. Neck unchanged.
DOZE_NOD = 0.0         # head level with the neck: gaze -8 deg, the room at
                       # standing distance, not the table.
DOZE_PAN = 0.0         # facing out from the booth

BREATH_S = 4.2         # a little quicker than S0's 5.0: dozing, not asleep
BREATH_RISE = 0.34     # = S0: passive exhale longer than inhale
N_BREATHS = 6          # whole breaths, so the loop seam does not tick
LED_LO = 0.40          # never 0 (reads as off)
LED_HI = 2.8           # just above S0's 2.5: present, still not asking
SAMPLE_F = 3

set_hue("warm")
reach.check("tilt", SLEEP_TILT, "doze neck")
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
    key_pose(f, DOZE_PAN, SLEEP_TILT, DOZE_NOD)
    key_led(f, LED_LO + (LED_HI - LED_LO) * breath(i))

finish(END_F, "SK_DOZE", [
    f"held pose pan {DOZE_PAN:+.0f} / tilt {SLEEP_TILT:+.0f} / nod {DOZE_NOD:+.0f}"
    f" (gaze {SLEEP_TILT + DOZE_NOD:+.0f} deg), body still",
    f"LED {LED_LO}-{LED_HI}, {N_BREATHS} breaths of {BREATH_S}s = {END_F / FPS:.1f}s loop",
])

# generate_sk_nap.py -- SK_NAP (loop). showcase-1124, sidekick mode only.
# Run inside the working .blend (motion/sidekick/README.md), then export with
# export_sk_clip.py. OVERWRITES all keys in that .blend's action.
#
# WHAT IT IS. The 1124 booth's resting state: it is ASLEEP (only a touch wakes
# it) but must still SEE the room, so a passer-by can be answered with a small
# lift of the head. S0_IDLE's head-down pose cannot do that: its eye looks
# ~50 deg down, at the table, and no shoulders are ever in frame.
#
# THE TRICK: napping in a chair. The body LEANS BACK and the head DROOPS
# FORWARD on it. The droop (nod, relative to the neck) is what reads as
# asleep; the two angles mostly cancel, so the eye (gaze = tilt + nod) ends
# only a little below level, where standing people's shoulders are in view.
#
# Tune it on the robot first: python3 robot/tools/nap_pose.py --cam N shows
# the camera at this pose and moves it with keys; put what you settle on here.
#
# THE BODY IS STILL (as SK_DOZE: ambient motion this slow cannot be smooth on
# these servos). The LED breathes slowly, slower than SK_DOZE: asleep.

import math
import bpy
import os

# ---- load sidekick_lib.py from THIS script's folder (motion/sidekick/) --------
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

NAP_TILT = 15.0        # body leans BACK (positive tilt = back, as SK_CURIOUS's pull-back)
NAP_NOD = -22.0        # head droops FORWARD on it: this is the "asleep"
NAP_PAN = 0.0          # facing out from the booth
                       # gaze = tilt + nod = -7 deg: standing shoulders at
                       # 1.5-3 m are in the upper half of the frame

BREATH_S = 5.0         # = S0_IDLE: asleep, slower than SK_DOZE's 4.2
BREATH_RISE = 0.34     # passive exhale longer than inhale
N_BREATHS = 5          # whole breaths, so the loop seam does not tick
LED_LO = 0.30          # never 0 (reads as off)
LED_HI = 2.2           # dimmer than SK_DOZE: asleep, not asking
SAMPLE_F = 3

set_hue("warm")
reach.check("tilt", NAP_TILT, "nap: body leaning back")
reach.check("nod", NAP_NOD, "nap: head drooping")

BREATH_F = frames(BREATH_S)
END_F = BREATH_F * N_BREATHS


def breath(i):
    p = (i % BREATH_F) / float(BREATH_F)
    if p < BREATH_RISE:
        return 0.5 * (1.0 - math.cos(math.pi * p / BREATH_RISE))
    return 0.5 * (1.0 + math.cos(math.pi * (p - BREATH_RISE) / (1.0 - BREATH_RISE)))


for f in list(range(1, END_F + 1, SAMPLE_F)) + [END_F]:
    i = f - 1
    key_pose(f, NAP_PAN, NAP_TILT, NAP_NOD)
    key_led(f, LED_LO + (LED_HI - LED_LO) * breath(i))

finish(END_F, "SK_NAP", [
    f"held pose pan {NAP_PAN:+.0f} / tilt {NAP_TILT:+.0f} / nod {NAP_NOD:+.0f}"
    f" (gaze {NAP_TILT + NAP_NOD:+.0f} deg), body still",
    f"LED {LED_LO}-{LED_HI}, {N_BREATHS} breaths of {BREATH_S}s = {END_F / FPS:.1f}s loop",
])

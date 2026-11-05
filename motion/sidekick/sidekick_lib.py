# sidekick_lib.py -- shared plumbing for the showcase-1108 clip generators in
# this folder (generate_sk_*.py, export_sk_clip.py). Not run on its own: each
# script exec()s it, so it works from Blender's Text Editor, where the repo is
# not on sys.path.
#
# WHAT IS SHARED, AND WHY IT IS ONLY PLUMBING. Every number that is a design
# decision (poses, beats, timings) stays in the generator that owns it, in the
# same style as generate_s2_acknowledge.py. This file only holds what every
# generator has to do identically: find reach.py, clear and key the rig, key the
# LED, ease, and refuse a beat the hardware cannot perform.
#
# THE TWO HARDWARE FLOORS, enforced by check_move() for every authored segment
# (see generate_s0_idle.py's header for the measurements):
#   amplitude   >= 2.05 deg tilt, 3.52 deg nod, 1.76 deg pan, or nothing moves
#   smoothness  >= 8.8 deg/s average over the segment, or it moves in steps
# and the ceiling: peak <= 200 deg/s.

import bpy
import math
import os
import sys

FPS = 30
SMOOTH_DPS = 8.8
CEILING_DPS = 200.0
EASE_PEAK = 1.875          # minimum-jerk peak / average velocity


# WHERE THINGS ARE. Found from THIS FILE, never from the .blend.
#
# The .blend files live in the design folder (robot_motion/model/...), not in
# the showcase repo, so searching upward from the .blend finds nothing -- or
# worse, finds the OTHER repo's reach.py and calibration, and checks the clip
# against a robot that is not this one. The loader in each generator passes
# _SK_DIR = the folder this file is in (motion/sidekick/ of the showcase repo).
SK_DIR = globals().get("_SK_DIR") or os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(SK_DIR))
CLIPS_DIR = os.path.join(REPO, "motion", "clips")

_rp = os.path.join(REPO, "motion", "blender", "reach.py")
_cp = os.path.join(REPO, "robot", "calibration.py")
for _need in (_rp, _cp):
    if not os.path.exists(_need):
        raise RuntimeError(f"Expected {_need} -- is motion/sidekick/ still inside "
                           f"the showcase repo?")
reach = type(sys)("reach")
reach.__file__ = _rp
with open(_rp) as _fh:
    exec(compile(_fh.read(), _rp, "exec"), reach.__dict__)
# reach.py found A calibration by searching from the .blend. Replace it with
# THIS repo's, and recompute the reach from it.
_cal = {}
with open(_cp) as _fh:
    exec(compile(_fh.read(), _cp, "exec"), _cal)
reach.__dict__.update(CENTRE=_cal["CENTRE"], LIMITS=_cal["LIMITS"],
                      INVERT=_cal["INVERT"], FLOORS=_cal["FLOORS"], CAL_PATH=_cp)
reach.REACH = {j: reach._reach(j) for j in ("pan", "tilt", "nod")}
reach.FLOOR_DEG = {j: reach.FLOORS[j] / reach.UNITS_PER_DEG for j in reach.FLOORS}
print("[sidekick] " + reach.summary())

pan = bpy.data.objects["pan_pivot"]
tilt = bpy.data.objects["tilt_pivot"]
nod = bpy.data.objects.get("nod_pivot")
if not nod:
    raise RuntimeError("No nod_pivot. Start from a clip .blend that already has "
                       "the 3-DOF rig (e.g. S2_ACKNOWLEDGE.blend) and Save As.")
for _o in (pan, tilt, nod):
    if _o.animation_data and _o.animation_data.action:
        _o.animation_data_clear()

_led_strength = None
_led_color = None
_mat = bpy.data.materials.get("led_mat")
if _mat and _mat.use_nodes:
    if _mat.node_tree.animation_data:
        _mat.node_tree.animation_data_clear()
    for _n in _mat.node_tree.nodes:
        if _n.type == 'EMISSION':
            _led_strength = _n.inputs['Strength']
            _led_color = _n.inputs['Color']
            break

# Preview colours only. The robot's real hue comes from states.py `hue`.
HUES = {"warm": (1.00, 0.72, 0.42, 1.0), "cool": (0.24, 0.59, 0.90, 1.0)}


def set_hue(name):
    if _led_color is not None:
        _led_color.default_value = HUES[name]
        _mat.diffuse_color = HUES[name]


def key(obj, axis, frame, deg):
    idx = {"x": 0, "z": 2}[axis]
    obj.rotation_euler[idx] = math.radians(deg)
    obj.keyframe_insert(data_path="rotation_euler", index=idx, frame=frame)


def key_pose(frame, p, t, n):
    key(pan, "z", frame, p)
    key(tilt, "x", frame, t)
    key(nod, "x", frame, n)


def key_led(frame, value):
    if _led_strength is not None:
        _led_strength.default_value = value
        _led_strength.keyframe_insert(data_path="default_value", frame=frame)


def ease(t):
    """Minimum jerk (Flash & Hogan 1985), zero velocity at both ends."""
    t = max(0.0, min(1.0, t))
    return t * t * t * (10.0 + t * (-15.0 + 6.0 * t))


def lerp(a, b, t):
    return a + (b - a) * t


def seg(i, start_f, dur_f):
    """Eased 0..1 progress of a segment at frame-offset i."""
    if i <= start_f:
        return 0.0
    if i >= start_f + dur_f:
        return 1.0
    return ease((i - start_f) / float(dur_f))


def check_move(joint, deg, dur_s, what, allow_slow=False):
    """Both floors and the ceiling, for one eased segment."""
    if abs(deg) < 1e-6:
        return
    reach.check_floor(joint, deg, what)
    avg = abs(deg) / dur_s
    if avg * EASE_PEAK > CEILING_DPS:
        raise RuntimeError(f"{what}: {joint} {deg:+.1f} deg in {dur_s:.2f} s "
                           f"peaks at {avg * EASE_PEAK:.0f} deg/s, over "
                           f"{CEILING_DPS:.0f}.")
    if avg < SMOOTH_DPS and not allow_slow:
        raise RuntimeError(f"{what}: {joint} {deg:+.1f} deg in {dur_s:.2f} s "
                           f"averages {avg:.1f} deg/s, under the {SMOOTH_DPS} "
                           f"deg/s smoothness floor -- it will step.")


def frames(s):
    return int(round(s * FPS))


def finish(end_f, title, lines):
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = end_f
    for ln in lines:
        print(f"[{title}] {ln}")

    def draw(self, context):
        for ln in lines:
            self.layout.label(text=ln)
        self.layout.label(text="Then: save, and run export_sk_clip.py "
                               "(writes straight into motion/clips/)")
    bpy.context.window_manager.popup_menu(draw, title=title, icon='INFO')

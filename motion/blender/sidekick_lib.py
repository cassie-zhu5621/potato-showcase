# sidekick_lib.py -- shared plumbing for the showcase-1108 clip generators
# (generate_sk_*.py). Not run on its own: each generator exec()s it the same way
# the S-clip generators exec reach.py, so it works from Blender's text editor
# where imports from the repo are not on sys.path.
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


def _find_up(rel, starts, levels=8):
    for s in starts:
        if not s:
            continue
        d = os.path.abspath(s)
        for _ in range(levels):
            p = os.path.join(d, rel)
            if os.path.exists(p):
                return p
            try:
                subs = sorted(os.listdir(d))
            except OSError:
                subs = []
            for name in subs:
                if name.startswith("."):
                    continue
                p = os.path.join(d, name, rel)
                if os.path.exists(p):
                    return p
            up = os.path.dirname(d)
            if up == d:
                break
            d = up
    return None


_starts = [os.path.dirname(bpy.data.filepath), os.getcwd()]
_rp = (_find_up(os.path.join("motion", "blender", "reach.py"), _starts)
       or _find_up("reach.py", _starts))
if not _rp:
    raise RuntimeError("Cannot find motion/blender/reach.py. Save the .blend "
                       "inside the repo (motion/src/) and run again.")
reach = type(sys)("reach")
reach.__file__ = _rp
with open(_rp) as _fh:
    exec(compile(_fh.read(), _rp, "exec"), reach.__dict__)

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
        self.layout.label(text="Then: save, run export_clip.py, copy "
                               "motion/src/export/<NAME>.csv to motion/clips/")
    bpy.context.window_manager.popup_menu(draw, title=title, icon='INFO')

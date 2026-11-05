# export_sk_clip.py -- export the clip the last generate_sk_*.py made, straight
# into the showcase repo's motion/clips/. Run in Blender's Text Editor right
# after the generator.
#
# Same sampling and CSV format as motion/blender/export_clip.py, except:
#   * it writes to <repo>/motion/clips/<clip>.csv directly -- nothing to copy;
#   * <clip> is whichever generate_sk_*.py ran last in this .blend, so ONE
#     working .blend can make every clip (the file does not need saving first);
#   * it only writes SK_*.csv. The nine paper clips are never overwritten.

import bpy
import csv
import math
import os

FPS = bpy.context.scene.render.fps
MAX_SAFE_DEG_S = 200.0
LED_FULL = 8.0        # Strength that maps to 255 (= export_clip.py)


def _sk_dir():
    for t in bpy.data.texts:
        fp = bpy.path.abspath(t.filepath) if t.filepath else ""
        d = os.path.dirname(fp)
        if fp and os.path.exists(os.path.join(d, "sidekick_lib.py")):
            return d
    raise RuntimeError("Open this script FROM its file in showcase/motion/sidekick/ "
                       "(Text Editor > Open), not pasted in.")


REPO = os.path.dirname(os.path.dirname(_sk_dir()))
CLIPS = os.path.join(REPO, "motion", "clips")

# THE CLIP'S NAME COMES FROM THE LAST GENERATOR RUN, not from the file name.
# One working .blend is used for every clip, so its file name says nothing about
# what is in it -- the first version named the CSV after the file and wrote
# GLANCE over SK_PURR.csv. Each generator stamps the scene with its clip name.
name = bpy.context.scene.get("sk_clip")
if not name:
    raise RuntimeError("Run a generate_sk_*.py first: it records which clip "
                       "this is. Nothing was written.")
if not str(name).startswith("SK_"):
    raise RuntimeError(f"{name!r} is not an SK clip. Only SK_* clips are "
                       f"exported from here, so a paper clip is never overwritten.")
name = str(name)

pan = bpy.data.objects["pan_pivot"]
tilt = bpy.data.objects["tilt_pivot"]
nod = bpy.data.objects.get("nod_pivot")
led_socket = None
_mat = bpy.data.materials.get("led_mat")
if _mat and _mat.use_nodes:
    for _n in _mat.node_tree.nodes:
        if _n.type == 'EMISSION':
            led_socket = _n.inputs['Strength']
            break

scene = bpy.context.scene
f_start, f_end = scene.frame_start, scene.frame_end


def to_unit(deg):
    return max(0, min(1023, round((deg + 150.0) / 300.0 * 1023.0)))


rows = []
for f in range(f_start, f_end + 1):
    scene.frame_set(f)
    t_ms = round((f - f_start) * 1000.0 / FPS)
    p = round(math.degrees(pan.rotation_euler.z), 2)
    ti = round(math.degrees(tilt.rotation_euler.x), 2)
    no = round(math.degrees(nod.rotation_euler.x), 2) if nod else 0.0
    led = 0
    if led_socket is not None:
        led = max(0, min(255, round(led_socket.default_value / LED_FULL * 255)))
    rows.append((t_ms, p, ti, no, led))

max_v = 0.0
for r0, r1 in zip(rows, rows[1:]):
    dt = (r1[0] - r0[0]) / 1000.0
    if dt > 0:
        for a, b in zip(r0[1:4], r1[1:4]):
            max_v = max(max_v, abs(b - a) / dt)
if max_v > MAX_SAFE_DEG_S:
    raise RuntimeError(f"{name}: peak {max_v:.0f} deg/s is over {MAX_SAFE_DEG_S:.0f}. "
                       f"Not written. Re-run the generator; do not hand-edit.")

os.makedirs(CLIPS, exist_ok=True)
path = os.path.join(CLIPS, f"{name}.csv")
with open(path, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["t_ms", "pan_deg", "tilt_deg", "nod_deg",
                "pan_unit", "tilt_unit", "nod_unit", "led"])
    for t_ms, p, ti, no, led in rows:
        w.writerow([t_ms, p, ti, no, to_unit(p), to_unit(ti), to_unit(no), led])

leds = [r[4] for r in rows]
msg = (f"{name}: {len(rows)} frames ({rows[-1][0] / 1000.0:.1f}s), peak "
       f"{max_v:.0f} deg/s, led {min(leds)}-{max(leds)}")
print(msg + f" -> {path}")


def draw(self, context):
    self.layout.label(text=msg)
    self.layout.label(text=f"Written: showcase/motion/clips/{name}.csv")


bpy.context.window_manager.popup_menu(draw, title="Export OK", icon='INFO')

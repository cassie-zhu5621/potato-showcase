import os, types, math
FILE = os.environ.get("FAKE_BLEND", "/sessions/jolly-pensive-meitner/mnt/showcase/motion/src/X.blend")
class Obj:
    def __init__(s, n): s.name=n; s.rotation_euler=[0.0,0.0,0.0]; s.animation_data=None; s.keys={}
    def keyframe_insert(s, data_path, index, frame): s.keys.setdefault(index,{})[frame]=s.rotation_euler[index]
    def animation_data_clear(s): s.keys={}
class Sock:
    def __init__(s): s.default_value=0.0; s.keys={}
    def keyframe_insert(s, data_path, frame): s.keys[frame]=s.default_value
class Node: 
    def __init__(s): s.type='EMISSION'; s.inputs={'Strength':Sock(),'Color':Sock()}
class NT: 
    def __init__(s): s.animation_data=None; s.nodes=[Node()]
class Mat:
    def __init__(s): s.use_nodes=True; s.node_tree=NT(); s.diffuse_color=None
objs={n:Obj(n) for n in ("pan_pivot","tilt_pivot","nod_pivot")}
class Objs(dict):
    def get(s,k,d=None): return dict.get(s,k,d)
mats={"led_mat":Mat()}
SCRIPT = os.environ.get("FAKE_SCRIPT", "")
texts=[types.SimpleNamespace(filepath=SCRIPT)] if SCRIPT else []
data=types.SimpleNamespace(objects=Objs(objs), materials=Objs(mats), filepath=FILE, texts=texts)
path=types.SimpleNamespace(abspath=lambda p: p)
scene=types.SimpleNamespace(frame_start=1, frame_end=1, render=types.SimpleNamespace(fps=30))
context=types.SimpleNamespace(scene=scene, window_manager=types.SimpleNamespace(popup_menu=lambda *a,**k: None))

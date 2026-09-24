"""S5B_BECKON holds one bearing for its whole loop, and the runtime depends on it.

Clip v5 (2026-08-08) removed S5B_BECKON's user leg. The reason is in the header of
generate_s5b_beckon.py: the participant places the robot anywhere on the desk and
nothing measures where they then sit, so a beat that turns toward the person was
turning toward an authored template -- an empty corner, three times a loop, with
full confidence.

THIS FILE EXISTS BECAUSE OF WHAT THAT CHANGED AT THE CALL SITE. clip_player used
`remap_share_pan` for S5A_FOUND and S5B_BECKON alike: a two-point rescale that maps the user
plateau to the seat and the object plateau to the finding. S5B_BECKON now takes
`shift_pan_centre` instead -- a pure translation, which is correct ONLY while
the curve has a single plateau.

Put an alternating S5B_BECKON back under a translation and nothing raises. The whole
curve slides, so the object leg still lands on the finding and looks right,
while the vestigial user leg lands 85 deg past it -- the robot swinging to a
bearing that means nothing, in the one clip whose entire job is to say where to
look. Silent, plausible on the bench, wrong in the room.

So the invariant is asserted against the exported CSV rather than the generator:
the generator is the intent, the CSV is what the servos receive, and it is the
CSV that goes stale when someone edits the .blend and forgets to export.
"""
import csv
import pathlib

CLIP = pathlib.Path(__file__).resolve().parents[1] / "motion" / "clips" / "S5B_BECKON.csv"


def _pan():
    with CLIP.open() as fh:
        return [float(r["pan_deg"]) for r in csv.DictReader(fh)]


def test_s5b_beckon_never_turns():
    pan = _pan()
    assert pan, f"{CLIP} is empty"
    spread = max(pan) - min(pan)
    assert spread < 0.5, (
        f"S5B_BECKON.csv sweeps {spread:.0f} deg of pan ({min(pan):+.0f} .. "
        f"{max(pan):+.0f}), so it is still the alternating v4 build.\n"
        f"clip_player now applies a TRANSLATION to this clip, which would move "
        f"the whole sweep -- the finding leg would land correctly and the leftover "
        f"user leg would land {spread:.0f} deg past it.\n"
        f"Fix: open S5B_BECKON.blend, run motion/blender/generate_s5b_beckon.py, then "
        f"export_clip.py, and copy the result over motion/clips/S5B_BECKON.csv.")


def test_s5b_beckon_opens_where_s7a_closes():
    """The two clips are played back to back with nothing in between, so S5A_FOUND's
    last frame IS S5B_BECKON's first. A mismatch is not a jump in the data -- it is a
    jump in the room, at the moment the robot is trying to look deliberate."""
    a = CLIP.parent / "S5A_FOUND.csv"
    with a.open() as fh:
        last = list(csv.DictReader(fh))[-1]
    with CLIP.open() as fh:
        first = next(csv.DictReader(fh))
    for col in ("pan_deg", "tilt_deg", "nod_deg"):
        assert abs(float(last[col]) - float(first[col])) < 0.5, (
            f"{col}: S5A_FOUND ends at {float(last[col]):+.1f} but S5B_BECKON opens at "
            f"{float(first[col]):+.1f}. Keep OBJECT_PAN / LEAN_DEG / OBJECT_NOD "
            f"in sync between the two generators.")

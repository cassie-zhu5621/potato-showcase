# motion/sidekick -- the clips of the sidekick booth (showcase-1108)

Everything for the new clips is in this folder, apart from the old ones in
`motion/blender/`.

| file | what it is |
|---|---|
| `generate_sk_purr.py` | **stage 1** -- touch: presses up into the hand |
| `generate_sk_doze.py`, `generate_sk_glance.py` | stage 2 -- dozing, glancing at passers-by |
| `generate_sk_curious.py`, `generate_sk_ack.py` | stage 3 -- "what's that?", "got it" |
| `generate_sk_guard_alert.py` | stage 4 -- "I see you" |
| `export_sk_clip.py` | writes the open SK_*.blend to `motion/clips/SK_*.csv` |
| `sidekick_lib.py` | shared helper. Not run by itself |

## Making a clip

One working .blend makes every clip -- keep it local (motion/sidekick/*.blend is
git-ignored; only the CSVs ship).

1. Open your working .blend (any file with the 3-DOF rig: pan, tilt, nod).
2. **Text Editor > Open** `showcase/motion/sidekick/generate_sk_<name>.py` > Run.
   Open it from the file, do not paste it: it finds `sidekick_lib.py` next to
   itself. A popup lists the beats; an error means a beat would not work on the
   servos, and says which.
3. **Text Editor > Open** `showcase/motion/sidekick/export_sk_clip.py` > Run.
   It writes `showcase/motion/clips/SK_<NAME>.csv`, named after the generator
   that just ran (not after the .blend), so the next clip is just: next
   generator, exporter again.
4. On the robot: `python3 robot/tools/play_on_hardware.py motion/clips/SK_<NAME>.csv`

Every check (reach, amplitude floor, smoothness floor, 200 deg/s) uses THIS
repo's `robot/calibration.py`, wherever the .blend is saved.

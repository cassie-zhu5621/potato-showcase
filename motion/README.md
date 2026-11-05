# motion — the movement design

```
src/        one .blend per state (plus rig.blend, the master rig)
blender/    scripts run INSIDE Blender: the rig builders, the clip generators,
            and export_clip.py
clips/      the exported CSVs the robot actually plays -- BUILD ARTEFACTS
```

Read `../docs/MOTION_AUTHORING.md` before changing anything here. The one rule:
never hand-edit a file in `clips/`.

A CSV row is `t_ms, pan_deg, tilt_deg, nod_deg, pan_unit, tilt_unit, nod_unit,
led`. `*_deg` is Blender's frame (positive nod = UP); `*_unit` is the Feetech
0-1023 position with the rig zero at 512. `led` is the antenna envelope, 0-255,
authored alongside the motion so the light and the movement cannot drift apart.

## Sidekick clips (branch showcase-1108)

Six new clips for the sidekick mode, all `SK_*`. The nine S-clips and their
`.blend` files are not touched: every SK file is a **Save As copy**.

| clip | start from | generator |
|---|---|---|
| SK_DOZE | S0_IDLE.blend | generate_sk_doze.py |
| SK_GLANCE | SK_DOZE.blend | generate_sk_glance.py |
| SK_CURIOUS | S2_ACKNOWLEDGE.blend | generate_sk_curious.py |
| SK_ACK | S2_ACKNOWLEDGE.blend | generate_sk_ack.py |
| SK_PURR | S2_ACKNOWLEDGE.blend | generate_sk_purr.py |
| SK_GUARD_ALERT | S4_WATCH.blend | generate_sk_guard_alert.py |

For each: open the "start from" file, **File > Save As** `motion/src/<clip>.blend`,
open the generator in the Text Editor, Run, save, run `export_clip.py`, copy
`motion/src/export/<clip>.csv` to `motion/clips/`.

All six share `sidekick_lib.py`, which refuses any beat under the amplitude or
smoothness floors or over 200 deg/s, so a generator that runs is a clip the
servos can perform.

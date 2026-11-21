# Showcase 11.24 -- researcher booth (handed over to a classmate)

Branch `showcase-1124` (from showcase-1108). Not pushed until decided.

## Audience and operator
Researchers, not children. A classmate runs it. It should explain itself in one
play, and the operator's only job is pressing **Next**.

## The loop (decided 2026-11-22)
1. **Asleep** (most of the time), in the NAP pose (SK_NAP): looks asleep but the
   camera still sees the room. A passer-by or someone coming close gets only a
   small lift of the head toward them, then back: alive, not awake.
2. **A pat on the head wakes it** (only a pat; coming close does not).
3. Awake: looks at you, waits to be shown something (brought up to its eyes).
4. Gemini names it -> ack -> watch -> call, as in 1108.
5. A pat while awake: purr. A pat while it calls: "seen it".
6. Operator presses **Next**: back to asleep, the object forgotten.

## Web UI (replaces the cv2 view)
Big live camera picture in the middle with the same overlays; above it, large:
"Looking for: <object>"; beside it a big **NEXT** button.

## Open
- NAP pose values: tune on the robot with `python3 robot/tools/nap_pose.py --cam N`,
  then `motion/sidekick/generate_sk_nap.py` -> export SK_NAP.
- Visitor leaves without Next: auto-return to sleep after some time, or not?
- Where the web UI is opened (booth laptop full screen, or the classmate's phone).
- Buttons besides Next (mute?).

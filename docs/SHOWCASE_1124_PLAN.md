# Showcase 11.24 -- researcher booth (handed over to a classmate)

Branch `showcase-1124` (from showcase-1108). Run: docs/RUNBOOK_1124.md.

## Audience and operator
Researchers, not children. A classmate runs it. It should explain itself in one
play; the operator's only job is pressing **NEXT** on the web UI.

## The loop (decided 2026-11-22)
1. **Asleep**, head down (S0_IDLE). Someone within the ToF distance in front of
   it (default 0.8 m, set on the web UI) gets ONE small stir of the head
   (SK_GLANCE, no turn); it stirs again only after they have left (2 s beyond
   the distance + 0.1 m). The camera sees the table here, so nothing it sees
   wakes it.
2. **Only a pat wakes it.** Light warm -> blue (SK_LOOK).
3. **Owner**: the closest person it sees after the pat. It follows the owner and
   nobody else (someone within 12 deg of where the owner was, widening while
   they are unseen); after 10 s without the owner, the closest person takes over.
4. **Showing needs an owner** (so part 1 always comes before part 2): something
   brought up to its eyes -> Gemini names it -> ack -> watch -> call (as 1108).
5. **Pat** any time awake: purr. While calling: "seen it".
6. **NEXT** (operator): asleep, owner and object forgotten. The same happens by
   itself after 60 s without the owner.

Gone from 1108: waking by coming close, dozing, glancing via the camera, waving
back, very-close bounces, passing the object on to the next visitor.

## Web UI (webui/booth_page.py, http://localhost:8000/)
Live camera picture with the overlays; "Looking for: <object>" above it; NEXT;
the ToF distance (- / +, on/off, the current reading). The setting is kept in
`session_feed/booth_settings.json`.

## Tried and dropped
- A "nap" pose that looks asleep but keeps the camera level (SK_NAP,
  `motion/sidekick/generate_sk_nap.py`, `robot/tools/nap_pose.py`): shoulders are
  only in view for seated people. Replaced by the ToF stir.

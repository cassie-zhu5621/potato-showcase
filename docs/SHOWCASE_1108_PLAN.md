# Showcase 11.8 — plan (built; how to run it: docs/SHOWDAY_1108.md)

Branch `showcase-1108`. `main` (the pushed showcase) is not touched.

## The shift

The showcase on `main` is the paper's delegation cycle: wake, choose a request,
scan, watch, wait for someone else to act the event out, call. Unguided, a
visitor rarely sees the payoff, and when they do it takes minutes.

This version moves from **noticing FOR you** to **attending WITH you**. Every
behaviour answers something the visitor just did, within about a second, and
every movement is the signature of a real detection (the movement-result rule).
Notice delegation survives as one short, self-contained game ("guard it").

## What a visitor does (the whole interface)

Sign on the table: **"Show it something. Give it something to guard."**
A tray of 3–4 props YOLO-World detects reliably, and one marked mat.

| visitor does | robot does | carried by |
|---|---|---|
| walks past | DOZE: head half up, sees the room; glances at the passer-by, then back | GLANCE (new clip, target-relative) |
| comes close / hand up | wakes, looks at their face, keeps looking at them while they move | S1_ATTEND, then LOOK (new live mode) |
| holds a prop up to it | leans in at the prop (epistemic lean, gaze drops onto it), "hm?" | CURIOUS (new clip) |
| moves the prop around | follows the prop with pan + tilt, like a cat | FOLLOW (new live mode) |
| keeps it still ~1 s | nods "got it", takes a photo; tablet shows the prop's name and a one-line comment in the robot's own voice | S2_ACKNOWLEDGE + card |
| puts a prop on the mat | turns to the mat, settles, guards (watch) | S4A_SETTLE, S4B_WATCH (fixed bearing, no scan, no VLM plan) |
| someone reaches for it | snaps upright: "I see you" | GUARD_ALERT (new clip) |
| it is taken away | calls the owner; tablet shows who took it as a storyboard | S5A_FOUND, S5B_BECKON + storyboard |
| owner touches its head while it guards | nods, "you're back", stops guarding | S2_ACKNOWLEDGE, release |
| touches its head otherwise | leans up into the hand, warm light, soft sound | PURR (new clip) |
| leaves | looks after them briefly, dozes again | GLANCE, DOZE |

Speech still works as a hidden staff path (hold to talk = the full original
cycle), so the paper demo can still be shown on request. The four-line tap menu
goes.

## Tap meaning, one rule per context

| context | tap means |
|---|---|
| awake, no task | affection -> PURR |
| guarding | "I'm back" -> release |
| calling (S5B) | "seen it" -> storyboard on tablet, back to LOOK |

Correct (S6) is not reachable in this mode: the guard bearing is the mat, so
there is nothing to redirect.

## New motion (Blender)

New generator scripts in `motion/blender/`, run in new `.blend` files. The nine
existing clips and their `.blend` files stay as they are. Library rules apply:
a clip inherits the pose of the state it is entered from; servo limits from
`robot/calibration.py`; LED authored in the clip.

| clip | type | beats |
|---|---|---|
| DOZE | loop | head half up so the camera sees the room; slow breath; replaces S0 as the resting pose in this mode |
| GLANCE | one-shot, target-relative | anticipation (small dip), pan to the person, hold ~0.6 s, ease back |
| CURIOUS | one-shot, target-relative | anticipation, lean in without cancel (gaze drops onto the prop), two small rising nods |
| PURR | one-shot | head rises into the hand (nod up), slow tilt sway, settle; warm LED swell |
| GUARD_ALERT | one-shot | fast upright from the watch hold, held stillness, LED brightens; returns to watch if nothing is taken |

LOOK and FOLLOW are not clips; they are live aiming (below).

## Player and loop changes

1. **Live aim** (LOOK, FOLLOW): a target pan + tilt from the detector, rate- and
   acceleration-limited, with a small breathing layer so it never looks frozen.
   Today only pan can be overridden, and only on two states.
2. **Target-relative clips** (GLANCE, CURIOUS): translate pan and tilt to the
   runtime target. `shift_pan_centre` already does pan.
3. **Interjection one-shots** (PURR, GUARD_ALERT): play and return to the state
   that was interrupted.
4. **Perception**: held-prop detector (YOLO-World box overlapping a hand, close
   to the camera), face position for LOOK (the MediaPipe face pipeline exists in
   `perception/gaze.py`), "on the mat" and "hand at the mat" (the hands-on
   relation already triggers reliably).
5. **Guard flow**: fixed mat bearing set once at setup, no scan, no VLM plan;
   VLM only for the storyboard text.
6. **Tablet**: the robot's big face (existing typographic faces), a live caption
   of what it is doing, and a wall of "things people showed me" and "who took
   it" storyboards. One-line comments in the robot's own voice (the paper lists
   this as future work).

## Order of work

1. Player features + state table + tests (no Blender needed).
2. Perception: held prop, face target, mat.
3. Generator scripts for the five clips; Cassie runs them in Blender and exports.
4. Tablet.
5. Booth rehearsal; rewrite SHOWDAY for this mode.

## Open decisions

- Who runs Blender: the generators are written here, but they run inside
  Blender on the Mac.
- Props: which 3–4 objects, and where the mat sits relative to the robot.
- Whether DOZE replaces S0_IDLE only in this mode (proposed) or everywhere.

## Decisions taken while building (2026-11-05)

- **No fixed mat.** The robot guards a prop wherever it is put down, as long as
  it followed it there: show it, put it down in view, let go. The mat on the
  table is only an affordance. Guarding is a live hold (SK_GUARD) aimed at the
  prop, because the prop lies below the eye and S4B_WATCH holds a level gaze.
- **Six clips, not five.** SK_ACK is S2's nod made entry-relative, so the
  library keeps one affirmation and "got it" can happen wherever the robot is
  looking.
- **Live aim is saccadic.** The servos step below 8.8 deg/s, so the head holds,
  then jumps to the target when it has moved past a dead band, like eyes do.
- **Speech is not in this program.** The paper demo stays `noticebot_loop.py`;
  switching is Ctrl-C and the other command.
- **Firmware v19**: purr and alert sounds, and one big-face screen (EVT SKFACE)
  so the CoreS3 wears the same face as the tablet.

# Show day 11.8 -- the sidekick booth

Branch `showcase-1108`. The paper demo (`main`, docs/SHOWDAY.md) is untouched
and still runs from this branch: it is a different program, not a setting.

## What a visitor does

Sign on the table: **"Show it something. Put it down for it to guard. Touch its head."**
A tray of the 3-4 props that passed the prop check (step 4).

| visitor | robot | tablet |
|---|---|---|
| walks past | dozing, head up; glances at them, goes back | `-_-` breathing |
| comes close (~1.5 m) | wakes, looks at their face, follows it | `o_o` "Hi! Show me something?" |
| holds a prop up | pulls back, leans in, "hm?" twice, then follows it | `o_O?` / `O_O` |
| holds it still ~1 s | nods; a card appears with a line in its own voice | `^_^` |
| puts it down and lets go | turns to it and guards it | `>_>` "I'll keep an eye on your ..." |
| a hand comes near it | snaps upright and freezes, eye still on it | `O_O!` "I see you..." |
| someone takes it | calls; the tablet shows who took it as a strip | `\^o^/` |
| owner touches its head while it guards | nods, "welcome back", stops guarding | `^_^` |
| touches its head otherwise | presses up into the hand | `=^_^=` |
| leaves | dozes again after ~6 s | `-_-` |

What to say, in full: **"Show it something."** Everything else follows from it.

## Before the day -- once

### 1. Export the six new clips (Blender)

See `motion/README.md`, "Sidekick clips". For each SK clip: open the "start
from" .blend, **Save As** `motion/src/<clip>.blend`, run its generator, save,
run `export_clip.py`, copy `motion/src/export/<clip>.csv` to `motion/clips/`.
A generator that runs is a clip the servos can perform: it refuses anything
under the amplitude or smoothness floors or over 200 deg/s.

Then on the robot, one at a time, watch each:

```bash
python3 robot/tools/play_on_hardware.py motion/clips/SK_PURR.csv
```

### 2. Flash firmware v19

v19 adds two sounds (purr, alert) and the big-face screen. Same as every flash:

```bash
lsof /dev/cu.usbmodem*
pio run -t upload
python3 robot/tools/tof_test.py      # first line must say v19
```

A v18 board still runs the booth, with no purr/alert sound and the old screen.

### 3. Which way is "image right" (30 s, nobody needed)

```bash
python3 robot/tools/aim_check.py --cam N
```

Point the head at something with texture first (not a blank wall). It turns
8 deg each way, measures how the picture slid, and prints `AIM_X_SIGN` and
`AIM_Y_SIGN` for `robot/states.py`. **Wrong signs = the robot confidently looks
away from everything it is shown.** Do this before anything else on hardware.

### 4. Which props it sees (5 min)

```bash
python3 robot/tools/sidekick_prop_check.py --cam N
```

Hold each candidate up at arm's length while it counts. Keep the ones marked
KEEP (found in >= 80% of frames, rarely confused). Put only those on the tray,
and pass only those words (fewer words, fewer confusions):

```bash
--props "banana,cup,teddy bear"
```

## Run it

```bash
cd ~/Documents/potatobot/showcase
python3 sidekick_loop.py --cam N --cores3 --props "banana,cup,teddy bear"
```

`--mute` while testing beside people. `--offline` if the network is bad: the
robot's lines become the built-in ones, everything else is the same.

Tablet: `http://<laptop IP>:8000/`, full screen. Nothing on it is a button.

Stop with Ctrl-C: it lies down to doze and lets go of the servos.

## Switching to the paper demo

Ctrl-C this, then run the demo exactly as in docs/SHOWDAY.md. Two programs that
never share a process cannot leak into each other.

## When something is off

**It never wakes.** It wakes on someone close (shoulders a quarter of the
frame wide, about 1.5 m). Further than that it only glances. A hand in front of
the wake sensor or a touch on the head also wakes it.

**It turns away from things.** The signs in step 3. Re-run `aim_check.py`.

**It never gets curious.** The prop is not in the list it was given, or is
too small in frame (hold it nearer), or the detector does not see it here --
step 4.

**It does not start guarding.** It needs to have followed the prop down: show
it first, then put it down in view, let go, keep still about a second. A prop
put down while it was looking at your face is not seen.

**"I see you" when nobody is near.** A guessed wrist. Raise `MIN_WRIST_VIS` in
`perception/sidekick_sense.py` (0.3 now).

**It says "taken" when the prop was only hidden.** Without a hand seen near it
the robot waits 5 s (`GONE_S` in `session/sidekick_brain.py`) before calling it
taken; with a hand seen, 1.2 s.

**The tablet shows people.** It does: the "who took it" strip is camera
frames. Tell people at the table; the images live in
`session_feed/sidekick_<time>/` (gitignored) -- delete the folder after the show.

## Numbers worth knowing

All in `session/sidekick_brain.py` unless said otherwise.

| | value | meaning |
|---|---|---|
| WAKE_S | 0.6 s | someone close this long wakes it |
| LOST_S | 6 s | nobody close this long: dozes |
| GLANCE_REFRACTORY_S | 12 s | at most one glance per this long |
| STILL_S / STILL_DEG | 1.2 s / 3 deg | "held still" for the nod |
| PLACE_S / DESK_GAZE | 1.0 s / -15 deg | put down and still, below the eye -> guard |
| TAKEN_S / GONE_S | 1.2 s / 5 s | missing after a hand / without one -> taken |
| CALL_MAX_S | 25 s | the call gives up |
| AIM_DEAD_DEG (states.py) | pan 4, tilt 3, nod 5 | how far a target moves before the head re-aims |

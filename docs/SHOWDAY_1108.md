# Show day 11.8 -- the sidekick booth

Branch `showcase-1108`. The paper demo (`main`, docs/SHOWDAY.md) is untouched
and still runs from this branch: it is a different program, not a setting.

A simple first try toward the next paper: interaction first, little or no
guidance needed.

## What a visitor does

Sign on the table: **"Hold something up to show it what to look out for. Touch its head."**

| visitor | robot | face |
|---|---|---|
| (nobody for a while) | asleep, head down -- woken by a hand at the sensor or a touch | `-_- zz` |
| walks past (just after a visit) | dozing, head up; glances at them (also straight ahead), goes back | `-.-` |
| comes close (~1.5 m) | wakes, looks at their face, follows it | `o_o` |
| holds something up | pulls back, holds, leans in, "hm?" (rising sound), follows it while the model names it | `o_O?` / `O_O` |
| -- named | nods and SAYS "OK! I'll look out for a blue water bottle." (also under its face and on the tablet) | `^_^` |
| keeps holding it / puts it away | nothing: being shown is not finding | |
| later, that kind of thing is in its view again | points at it with the call sound (no speech); tablet: "spotted it!" with the picture | `\^o^/` |
| touches its head while it calls | nods, "seen it", back to looking at you | `^_^` |
| touches its head otherwise | presses up into the hand | `=^_^=` |
| someone else holds up something else | the new thing replaces the old one | |
| leaves | dozes (head up) after ~6 s; falls asleep (head down) after ~20 s more -- only if it has nothing to look out for | `-.-` then `-_- zz` |

"The same thing" means the same kind (any water bottle), found by YOLO-World
with the word the model gave it. Anything can be shown: the model names it.

## One interaction at a time

Three stages; each adds ONE interaction and needs only its own clips.
`--stage N` runs exactly that much.

| stage | the visitor can | clips | also needs |
|---|---|---|---|
| 1 touch | touch its head: it presses up into the hand | SK_PURR | no camera |
| 2 notice | + sleeps/dozes, glances at passers-by, wakes and looks at you | + SK_DOZE, SK_GLANCE | camera |
| **3 watch** | + show it something; it looks out for it and calls when it turns up | + SK_CURIOUS, SK_ACK (+ the paper's S5A/S5B for the call) | network (Gemini names the thing) |

Clips are made in Blender: `motion/sidekick/README.md`.

## Run it

```bash
cd ~/Documents/potatobot/showcase
conda activate sidekick
python3 sidekick_loop.py --stage 3 --cam N --cores3 --view
```

- `N`: the InnoMaker head camera (`python3 noticebot_loop.py --list-cams`).
- `--view`: debug window -- people (NEAR / passer), things it sees, its phase.
- `--mute` beside people who are working. `--offline` without a network: the
  thing is named by the detector's own word and the lines are built-in ones.
- Tablet: `http://<laptop IP>:8000/`, full screen. Nothing on it is a button.
- Stop with Ctrl-C: it lies down and lets go of the servos.

On the laptop alone (no robot): `python3 sidekick_loop.py --no-robot --cam 0`
(keys in the window: t = touch, p = palm, q = quit).

## Before the day -- once

1. **Firmware v20** (sounds, big-face screen, and v20: it SPEAKS its lines and
   shows them under its face): `pio run -t upload`, then
   `python3 robot/tools/tof_test.py` must say v20. The voice is macOS `say`
   (`--voice Zarvox` by default, robotic; `say -v ?` lists others).
2. **Aim signs** are measured and set (AIM_X_SIGN -1, AIM_Y_SIGN +1,
   2026-11-07). Re-run `python3 robot/tools/aim_check.py --cam N` only if the
   camera or a servo is remounted.
3. **Servo supply**: `python3 robot/tools/check_bus.py`, 5-6 V.

## Switching to the paper demo

Ctrl-C this, then run the demo exactly as in docs/SHOWDAY.md.

## When something is off

Read the terminal: `[sense]` says what it sees (nobody / passer / NEAR),
`[brain]` what it does, `[identify]` what the model named.

**It never wakes.** Someone close (about 1.5 m) wakes it from dozing; asleep
(head down) only a hand at the sensor or a touch does.

**It never gets curious.** The thing must be held up, close and near the middle
of its view, by someone it sees as NEAR. Very unusual objects may not be among
the detector's words (`PROPS` in `perception/sidekick_sense.py`).

**"I couldn't tell what that was."** The model said nothing was clearly being
shown, or did not answer in 12 s (`TEACH_MAX_S`). Hold it closer, still.

**It calls while the visitor still holds it.** It should not: the thing must be
out of sight 3 s (`TARGET_AWAY_S`) before seeing it again counts.

**The tablet shows people.** "Spotted it" pictures are crops around the thing,
but people can be in them. Images live in `session_feed/sidekick_<time>/`
(gitignored) -- delete the folder after the show.

## Numbers worth knowing

All in `session/sidekick_brain.py` unless said otherwise.

| | value | meaning |
|---|---|---|
| WAKE_S | 0.6 s | someone close this long wakes it |
| LOST_S | 6 s | nobody close this long: dozes |
| DOZE_TO_SLEEP_S | 20 s | dozing this long: falls asleep, head down |
| GLANCE_REFRACTORY_S | 12 s | at most one glance per this long |
| HELD_FRAMES | 2 | held up this many frames: curious |
| TEACH_MAX_S | 12 s | the model gets this long to name it |
| TARGET_AWAY_S | 3 s | out of sight this long before seeing it again counts |
| FOUND_FRAMES | 2 | seen this many frames: found |
| CALL_MAX_S | 25 s | the call gives up |
| AIM_DEAD_DEG (states.py) | pan 4, tilt 3, nod 5 | how far a target moves before the head re-aims |

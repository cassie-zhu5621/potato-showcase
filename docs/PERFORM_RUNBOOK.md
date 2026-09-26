# Performance runbook

The robot played from the keyboard, to music, beside the floating fish.
Nobody synchronises anything: the fish's pilot and the robot's player both
listen to the same track. That is a conductor neither of them has to be.

Read `THE_THREE_MODES.md` first if it is not obvious why this is not the same
program as the study loop.

---

## 1. Flash, once, before anything

The firmware changed after the ToF bring-up: **v8**. If a line is being
spoken, bake it BEFORE flashing so it goes in the same trip.

```bash
cd ~/Documents/potatobot/showcase

# optional, and only if there is a line: try wordings first, writes nothing
python3 robot/tools/make_voice.py --preview "I was watching." "I'll remember that one."

# then bake the ones that survived -- writes voice.h next to the sketch
python3 robot/tools/make_voice.py "I was watching." "I'll remember that one."

# and flash. pio, not the IDE: it applies --no-stub and 115200, which is what
# this board's native USB needs. See GETTING_STARTED.
lsof /dev/cu.usbmodem*          # anything listed is holding the port -- kill it
pio run -t upload
```

**Check it landed.** An upload can fail after the sketch compiles, leaving the
old build running and answering exactly as before:

```bash
python3 robot/tools/tof_test.py     # first line must say v8
```

An older number means the upload did not land, whatever the IDE reported.

## 2. Before the doors open

- **Servo supply on the blue terminal**, 5–6 V. If the bus reads 4.3 V it is
  running on USB back-feed and will brown out under load — see HARDWARE_SETUP.
- **Two USB ports**: the servo adapter and the CoreS3. Both enumerate as
  `/dev/cu.usbmodem*`; the tools tell them apart by PING, so no configuration.
- **Nothing else holding either port.** `attend_test.py` left running in
  another window is the usual culprit.
- **Calibrate LEAD_S once** — see §5. It is the only hand-set constant here.

## 3. Start

```bash
python3 robot/tools/perform.py
```

It homes the neck, finds the CoreS3 for the light, and waits. It starts
**frozen**: nothing moves until `F`.

```
  SPACE   tap the beat -- four taps sets it, keep tapping and it follows
  F       freeze / release          <- the strongest key here
  N L D   sway: Nod only / Lean (gaze stays level) / Dip (whole body)
  ↑ ↓     amplitude          ← →   nudge the phase, an eighth at a time
  T / G   trim the neck up / down, for looking at something above
  B       light on/off       W C R S   warm / cool / red / summon
  1..6    gestures: nod · found+lean · beckon · shake · attend · sweep
  [ ]     pick which spoken line      V   say it
  0       stop the sway       Q   quit
```

## 4. How to play it

**Tapping is also the downbeat.** Every tap re-anchors the phase, so if the
robot has drifted against the record you tap where the beat really is and it
comes back. No stopping, no menu.

**Freeze is the best thing in the vocabulary.** After thirty seconds of
movement, a machine that stops dead is more arresting in a noisy room than
anything it can do by moving. Use `F` before the chorus, not during it.

**`L` for most of it.** In lean, the neck dips and the head counter-rotates, so
the body grooves and the gaze stays on the fish. A bassist's head is still. `D`
is for an accent, not for a section.

**Light carries the room, motion does not.** A 24° lean is invisible from five
metres; the flash on every beat is not. If only one channel is going to reach
the back of the room it is that one.

**The amplitude key is a request.** What plays is capped at what the tempo
allows — a `!` in the status line means the cap is active. Above roughly
`amplitude × BPM = 1150` the servo cannot reach the turnaround before the
waveform has left, and a big slow sway becomes a small fast tremble.

**The voice is the end.** `V` freezes first, then speaks. Music off, people
close: the point of a voice in the body is that the sound is located there, and
that only survives while nothing louder is playing.

## 5. The one calibration

`LEAD_S` in `perform.py` is currently **0.12 s** and it is a guess. It is the
time the neck takes to arrive, and everything is computed that far ahead so the
motion lands on the beat rather than departing on it.

Put a metronome on, run with `N` and a middling amplitude, and watch the bottom
of the nod against the click:

- **nod bottoms out after the click** → raise `LEAD_S`
- **before it** → lower it

It is a fixed phase offset, not a tempo change, so it cannot drift once set.

Gestures are separately offset by where each clip's accent falls — measured,
in `ACCENT_S`, and recomputed by `robot/tools/clip_accents.py` if a clip is
ever re-exported. A stale offset there does not look like a stale number; it
looks like the robot cannot keep time.

## 6. Rehearse these, in this order

1. Tap into a track and just sway. Fix `LEAD_S` until it sits in the pocket.
2. `F` on and off against the music. Find where a freeze lands well.
3. `2` (found + lean) on a downbeat you can hear coming.
4. The ending: `F`, two beats of nothing, `V`.
5. Only then with the fish, and only then worry about what it is doing.

## 7. When something goes wrong

| | |
|---|---|
| neck does not move | is it still frozen? `F`. Then: servo supply at 5–6 V, not 4.3 |
| no light | "no CoreS3 found" at startup — it runs without one. Check the port |
| sway looks like a tremble | the amplitude cap; `!` in the status line. Slow the tempo or drop the amplitude |
| gestures land late | `LEAD_S`, §5. Do not change the tempo, it cannot help |
| `V` says nothing happens | no `voice.h` baked, or flashed before baking. `IN SAY none` says so |
| light flashes early | the light takes no lead; if this ever appears, something applied `LEAD_S` to it |
| it all stops | Ctrl-C returns the neck to idle and relaxes it. Nothing is left energised |

## 8. Afterwards

`Q` or Ctrl-C. The neck goes to `S0_IDLE`, then torque off. Power down the
servo supply before unplugging USB.

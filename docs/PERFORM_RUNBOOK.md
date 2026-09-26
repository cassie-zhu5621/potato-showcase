# Performance runbook

**Frozen at tag `perform-v1`.** The robot played from the keyboard, to music,
beside the floating fish.

Nobody synchronises anything: the fish's pilot and the robot's player both
listen to the same track. That is a conductor neither of them has to be.

Read `THE_THREE_MODES.md` if it is not obvious why this is not the same program
as the study loop.

---

## 1. Flash, once

Firmware **v9** — or anything newer. The firmware is shared by all four modes
and grows only by addition, with every optional thing off until a mode asks, so
reflashing for the demo does not change what this one does. `perform.py` claims
the board on startup and turns off what it does not want.

```bash
cd ~/Documents/potatobot/showcase
lsof /dev/cu.usbmodem*          # anything listed is holding the port -- kill it
pio run -t upload
```

`pio`, not the Arduino IDE: it applies `--no-stub` and 115200, which is what
this board's native USB needs. The IDE loses the connection partway through
writing often enough to be the default suspect.

**Check it landed.** An upload can fail after the sketch compiles, leaving the
old build running and answering exactly as before:

```bash
python3 robot/tools/tof_test.py     # v9 or newer. Ctrl-C after.
```

A number BELOW v9 means the upload did not land, whatever the IDE
reported. Above is fine.

## 2. Before the doors open

- **Servo supply on the blue terminal**, 5–6 V. If the bus reads 4.3 V it is
  running on USB back-feed and will brown out under load — see HARDWARE_SETUP.
- **Two USB ports**: the servo adapter and the CoreS3. Both enumerate as
  `/dev/cu.usbmodem*`; the tools tell them apart by PING, so no configuration.
- **Nothing else holding either port.** `attend_test.py` left running in
  another window is the usual culprit.
- **Calibrate `LEAD_S` once** — §5. It is the only hand-set constant here.

## 3. Start

```bash
python3 robot/tools/perform.py
```

It homes the neck, finds the CoreS3 for the light and the face, and waits. It
starts **frozen**: nothing moves until `F`.

```
  SPACE   tap the beat -- four taps sets it, keep tapping and it follows
  F       freeze / release          <- the strongest key here
  0       stop the sway and hold still        Q   quit

  N L D   sway: Nod only / Lean (gaze stays level) / Dip (whole body)
  ↑ ↓     amplitude                 ← →   nudge the phase, an eighth at a time
  T / G   trim the neck up / down, for looking at something above
  , .     turn left / right, 15 deg a press   /   face front again

  1..6    gestures, quantised:
            1 nod   2 found+lean   3 beckon   4 shake   5 attend   6 sweep

  B       the antenna on / off      W C R S   warm / cool / red / summon
  E       the big bouncing face on the CoreS3 on / off
  M       gesture sounds on / off   (off by default)
  [ ]  V  pick and play a spoken line -- not used in this version, see §7
```

The status line under it is rewritten ten times a second and shows what is
actually moving, not what was asked for:

```
  90.0 BPM  lean   amp 12.7!  trim  +0  pan  +30  ***     say1  next:S5A_FOUND
                          ^ the tempo limiter is holding the amplitude down
```

## 4. How to play it

**Tapping is also the downbeat, and does not need a freeze.** Every tap pulls
the phase toward where you tapped — a quarter of the error each time, locked
within about four. So if it has drifted against the record you tap where the
beat really is and it comes back, without stopping and without a lurch.

**Freeze is the best thing in the vocabulary.** After thirty seconds of
movement, a machine that stops dead is more arresting in a noisy room than
anything it can do by moving. Use `F` before the chorus, not during it.

**`L` for most of it.** In lean, the neck dips and the head counter-rotates, so
the body grooves and the gaze stays on the fish. A bassist's head is still. `D`
is for an accent, not for a section.

**Light and face carry the room; motion does not.** A 24° lean is invisible
from five metres. The flash on every beat and a face filling the screen are
not. If only one channel reaches the back of the room it is those.

**The amplitude key is a request.** What plays is capped at what the tempo
allows — a `!` in the status line means the cap is active. Above roughly
`amplitude × BPM = 1150` the servo cannot reach the turnaround before the
waveform has left, and a big slow sway becomes a small fast tremble. The change
swells over about a beat rather than stepping, so it is a crescendo.

**Gestures land on the beat, not when you press.** Pressing queues; the clip
fires early by its own accent offset so the accent itself lands on the beat.
`1` (nod) has an accent 1.17 s in, longer than a beat above 51 BPM, so it takes
a later beat — press it a beat earlier than feels right.

## 5. The one calibration

`LEAD_S` in `perform.py` is **0.12 s** and it is a guess. It is the time the
neck takes to arrive, and everything mechanical is computed that far ahead so
the motion lands on the beat rather than departing on it.

Metronome on, `N`, middling amplitude, and watch the bottom of the nod against
the click:

- **nod bottoms out after the click** → raise `LEAD_S`
- **before it** → lower it

A fixed phase offset, so it cannot drift once set. **If gestures ever feel
late, it is still this number and never the tempo.**

The light, the face and the sounds take no lead — they have nothing to travel.
If any of them ever flashes early, something has applied `LEAD_S` to it.

## 6. Rehearse these, in this order

1. Tap into a track and just sway. Fix `LEAD_S` until it sits in the pocket.
2. `F` on and off against the music. Find where a freeze lands well.
3. `2` (found + lean) on a downbeat you can hear coming.
4. `,` and `.` — turning to the audience and back, slowly, mid-phrase.
5. Only then with the fish, and only then worry about what it is doing.

## 7. What is deliberately not used here

**The voice.** `SAY` and `make_voice.py` work and are not part of this version:
no `voice.h` is baked, so `V` prints `IN SAY none` and nothing happens. To add
one later, bake **before** flashing — it goes into the firmware, so it is one
trip, not two.

**Gesture sounds are off.** `M` turns them on. A 1 W speaker in a printed shell
loses to a room with music in it, so whether they are worth having is a
question about the venue.

## 8. When something goes wrong

| | |
|---|---|
| neck does not move | still frozen? `F`. Then: servo supply at 5–6 V, not 4.3 |
| no light, no face | "no CoreS3 found" at startup — it runs without one |
| sway looks like a tremble | the tempo limiter; `!` in the status line. Slow the tempo or drop the amplitude |
| gestures land late | `LEAD_S`, §5. Not the tempo, which cannot help |
| the face does not appear | `IN FACE no memory` at startup means the sprite would not allocate |
| it all stops | Ctrl-C returns the neck to idle and relaxes it. Nothing is left energised |

## 9. Afterwards

`Q` or Ctrl-C. The neck goes to `S0_IDLE`, the screen is handed back to `idle`,
then torque off. Power down the servo supply before unplugging USB.

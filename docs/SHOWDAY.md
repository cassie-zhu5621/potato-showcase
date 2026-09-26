# Show day

The card for the day itself. Flash in the morning, then switch modes all day
without touching the firmware again.

Full detail per mode: `DEMO_VLM_RUNBOOK.md`, `PERFORM_RUNBOOK.md`.

---

## Morning -- once, in this order

```bash
cd ~/Documents/potatobot/showcase
lsof /dev/cu.usbmodem*          # anything listed is holding a port -- kill it
pio run -t upload
```

`pio run -t upload` is the ONCE. The firmware is one build shared by all four
modes, so it is flashed in the morning and not again -- not when a mode
restarts, not when a terminal is reopened, not when you switch modes. Only when
the firmware itself changes.

`lsof` is not part of flashing and is not a ritual. It answers one question --
is anything holding the port -- and it is asked here because flashing needs the
port to itself. The rest of the day it is a diagnostic, not a step.

**Check it landed.** An upload can fail after the sketch compiles, leaving the
old build running and answering exactly as before:

```bash
python3 robot/tools/tof_test.py
```

- first line must say **v11 or newer**
- the bar must move when you put a hand in front of the sensor

Ctrl-C it. Below v11, or no `IN TOF` line at all, means the upload did not land
whatever it reported -- the tool now says so and prints the command with the
port already filled in.

**Find the camera.** The index moves whenever anything USB is replugged, so
this is a per-morning check, not a number to write down:

```bash
python3 noticebot_loop.py --list-cams
```

Take the one it calls the InnoMaker head camera. Not the Mac's built-in
(square sensor), not anything that "opens but yields no frame" -- that is
Continuity Camera and it will hang the loop for 8 s and then fail.

Close Zoom, FaceTime and Photo Booth before running this or the list comes back
short.

**Then check, before people arrive:**

- servo supply on the blue terminal reads **5-6 V**, not 4.3. At 4.3 it is
  running on USB back-feed and the neck will not reach its poses -- the symptom
  is `!! did not arrive: nod=641/626` in the log, and it gets worse as the day
  warms up
- both USB plugged in: the servo adapter and the CoreS3
- the ToF on its bracket, horizontal, about 40 cm, pointing where people walk
  up. **Move the sensor and every threshold measured for it is void**

That is the last time the firmware is touched today.

---

## The two modes

### Demo -- the whole cycle with the VLM. Two terminals.

Loop first. It is the one that fails: port busy, camera busy, no network. Start
it alone so its first lines are on a clean screen.

```bash
python3 noticebot_loop.py --serve --cores3 --approach --feedback robot --detector yoloworld --cam 1
```

Watch for this in the first few lines, before CV output buries it:

```
[cores3] approach trigger ARMED -- walking up presses the button
```

**No ARMED line means walking up will do nothing.** Nothing else will look
wrong.

Same for **`--feedback robot`**, and this one is worse because it fails later:
without it the whole cycle runs, the judge confirms, `[FEEDBACK]` prints -- and
the robot never calls. The loop warns at startup; the warning is the line to
look for if it all works and nothing ever happens.

Wait for `[gemini] warm in ...`, then the second terminal:

```bash
python3 robot/tools/standing_prompt.py
```

It prints the audience address and then stays quiet, so it is still on screen
an hour later. Leave that window visible.

**Nobody walks up until both are running.** The ToF is live from the moment the
board is powered, and the loop takes ten or fifteen seconds to come up. A
visitor arriving in that gap gets the one behaviour this mode exists to avoid.

### Performance -- played from the keyboard, beside the fish. One terminal.

```bash
python3 robot/tools/perform.py
```

Starts frozen. `F` to begin, `SPACE` to tap the beat.

---

## Switching

```
Ctrl-C            everything that is running
                  (demo = two windows, both of them)
        wait two seconds
start the other
```

**That is the whole procedure.** No reflash, no power cycle, nothing to
remember to switch off -- each mode sets the board to what it wants on the way
in, so whatever the last one left behind is overwritten.

The two seconds are for the ports to come free. Starting immediately is the
commonest way to see `no CoreS3 found` on a machine where nothing is wrong.

You do not need `lsof` here. It belongs to the section below.

---

## If a mode will not start

Nine times in ten it is the previous one still holding a port in a window you
forgot about. Find it and Ctrl-C it in its own window -- that is the clean way,
and it is the only one that needs no commands.

**If there is no window to go back to** -- the terminal crashed, or was closed,
or the process outlived it -- then this:

```bash
pgrep -fl "noticebot_loop|perform.py|attend_test|standing_prompt"
```

`pgrep`, not `lsof`, and this is worth knowing on the day: `lsof
/dev/cu.usbmodem*` finds a process holding the SERIAL port, and misses one
holding only the camera or the microphone. An orphan with the camera still open
gives `camera 1 opened but produced no frames in 8s`, which looks like a
hardware fault and is not one. The `pgrep` line covers all four modes and every
device at once.

Then, with the pid:

```bash
kill -INT <pid>
```

**`-INT`, not plain `kill`.** SIGTERM ends Python without running the teardown,
and the teardown is where the unfinished story is written out, the neck is
returned to idle and **the servos are de-energised**. Killed the other way, the
motors stay powered holding whatever pose they were in -- which is invisible
for half an hour and then the horn is too hot to touch. `kill -INT` is exactly
what Ctrl-C sends.

Wait two seconds, run `pgrep` again. Only if it is genuinely stuck: `kill -9`,
and then power-cycle the servo supply, because nothing turned the torque off.

The rest, in the order they happen:

| | |
|---|---|
| `no CoreS3 found` | the other mode still has it, or you did not wait two seconds, or the cable |
| `camera N opened but produced no frames` | an orphan has it, or the index moved -- `--list-cams` again |
| servos do not move | performance starts **frozen** -- press `F`. Otherwise the 5-6 V supply |
| `!! did not arrive` in the log | supply voltage, every time. Not a software setting |
| walking up does nothing (demo) | is `approach trigger ARMED` in the loop's first lines? If not, `--approach` did not arrive |
| it wakes once and never again | v10 or older on the board. Fixed in v11 -- check `tof_test.py` |
| the robot performs an error (demo) | `standing_prompt.py` is not running |
| the face does not appear (performance) | `IN FACE no memory` at startup, or `E` turned it off |

---

## The thirty-second check after any restart

Worth doing once each time the demo comes back up, because it is the whole
interaction and it takes four steps:

1. walk up -> head comes up
2. step back **past 1.5 m** and stand there two seconds
3. walk up again -> **head comes up again**
4. walk up and stay put -> it does **not** wake over and over

Step 2 is the one people skip and it is the one that was broken: leaving is a
timeout on the sensor going quiet, not a far reading, because walking away
means walking into open space where the sensor has nothing to bounce off.

If step 3 fails, the board is on v10 or older.

---

## Retyping the prompt mid-show

The tablet page has a prompt row along the bottom, on every screen including
the sleeping one. Type a sentence, press return, `sent` flashes.

It re-plans from whatever state the robot is in, **including error** -- so it
is also the way to pull it out of one without touching the laptop.

Concrete and about the audience, or the planner has nothing to compile:

    tell me when someone comes close to the table
    tell me when someone points at something
    tell me when two people look at the same thing

---

## End of day

Ctrl-C everything. The neck goes to idle and the torque comes off on its own.

Power down the servo supply **before** unplugging USB.

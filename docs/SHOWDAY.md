# Show day

The card for the day itself. Flash in the morning, then switch modes all day
without touching the firmware again.

Full detail per mode: `DEMO_VLM_RUNBOOK.md`, `PERFORM_RUNBOOK.md`.

---

## Morning — once

```bash
cd ~/Documents/potatobot/showcase
lsof /dev/cu.usbmodem*          # anything listed is holding a port -- kill it
pio run -t upload
python3 robot/tools/tof_test.py
```

`tof_test` must say **v10 or newer** on its first line, and the bar must move
when you put a hand in front of the sensor. Ctrl-C it.

That is the last time the firmware is touched today.

Also check, before people arrive:

- servo supply on the blue terminal reads **5–6 V**, not 4.3
- both USB plugged in: the servo adapter and the CoreS3
- the ToF on its bracket, horizontal, about 40 cm, pointing where people walk up

---

## The two modes

**Demo** — the whole cycle with the VLM. Two terminals.

```bash
python3 noticebot_loop.py --serve --cores3 --approach --detector yoloworld
python3 robot/tools/standing_prompt.py
```

The second window prints the address for the audience screen and then stays
quiet. Leave it visible.

**Performance** — played from the keyboard, beside the fish. One terminal.

```bash
python3 robot/tools/perform.py
```

Starts frozen. `F` to begin, `SPACE` to tap the beat.

---

## Switching

```
Ctrl-C            everything that is running
                  (demo = two windows, both of them)

start the other
```

**That is the whole procedure.** No reflash, no power cycle, nothing to
remember to switch off — each mode sets the board to what it wants on the way
in, so whatever the last one left behind is overwritten.

Give it two seconds between stopping and starting. The ports take a moment to
come free.

---

## If a mode will not start

Nine times in ten it is the previous one still holding a port in a window you
forgot about.

```bash
lsof /dev/cu.usbmodem*
```

Kill whatever it lists, then start again.

The rest, in the order they happen:

| | |
|---|---|
| `no CoreS3 found` | the other mode still has it, or the cable |
| servos do not move | performance starts **frozen** — press `F`. Otherwise the 5–6 V supply |
| walking up does nothing (demo) | is `approach trigger ARMED` in the loop's first lines? If not, `--approach` did not arrive |
| the robot performs an error (demo) | `standing_prompt.py` is not running |
| the face does not appear (performance) | `IN FACE no memory` at startup, or `E` turned it off |

---

## End of day

Ctrl-C everything. The neck goes to idle and the torque comes off on its own.

Power down the servo supply **before** unplugging USB.

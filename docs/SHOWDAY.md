# Show day

The card for the day itself. Flash in the morning, then switch modes all day
without touching the firmware again.

Full detail per mode: `DEMO_VLM_RUNBOOK.md`, `PERFORM_RUNBOOK.md`.

**The demo command below is the study command plus `--approach`.** It is
derived from `STUDY_IPAD_RUNBOOK.md`, which is the one that has actually run a
session, rather than assembled from the flags that seemed necessary -- which is
how `--feedback robot` went missing for an evening and made the whole pipeline
work with a robot that never called.

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

- first line must say **v18 or newer**
- the bar must move when you put a hand in front of the sensor

Ctrl-C it. Below v18, or no `IN TOF` line at all, means the upload did not land
whatever it reported -- the tool says so and prints the command with the port
already filled in.

**Find the camera.** The index moves whenever anything USB is replugged, so
this is a per-morning check, not a number to write down:

```bash
python3 noticebot_loop.py --list-cams
```

Take the one it calls the InnoMaker head camera. Not the Mac's built-in (square
sensor), not anything that "opens but yields no frame" -- that is Continuity
Camera and it will hang the loop for 8 s and then fail. Close Zoom, FaceTime
and Photo Booth first or the list comes back short.

**Check the servo supply.** Not with a multimeter -- the servos report it
themselves, and `tof_test.py` cannot: that talks to the CoreS3, which is a
different board on a different bus.

```bash
python3 robot/tools/check_bus.py
```

Three servos must answer -- 1 pan, 2 tilt, 3 nod -- each with a voltage beside
it. **5-6 V.** It warns by itself below 4.5. At 4.3 the robot is running on USB
back-feed and the neck will not reach its poses: the symptom is
`!! did not arrive` in the log, and it gets worse as the day warms up.

This reads the bus AT REST, which is the easy case. A supply that passes here
can still sag under a fast pan -- so if `!! did not arrive` appears during a
run, believe that over this, and the line now prints the voltage it measured at
the moment the move failed:

```
[player] !! did not arrive: pan=168/156 -- bus reads 4.3V under load -- THE
         SUPPLY. Below ~4.8 V the servo cannot hold, and nothing in software helps
[player] !! did not arrive: pan=168/156 -- bus reads 5.6V, which is fine -- so
         torque off or jammed
```

**Then, before people arrive:**

- both USB plugged in: the servo adapter and the CoreS3
- the ToF on its bracket, horizontal, pointing **out over the front edge of the
  table at about chest height** -- that is where a hand will go. Put a sign
  beside it. **Move the sensor and every threshold measured for it is void**
- **nothing in front of the lens, including the bracket's own face.** This is
  worth thirty seconds because it cost an evening: a blocked sensor does not
  report an error, it reports `0 mm` with a valid status, and every explanation
  for a zero points at software. `tof_test.py --diag` says it in one line --
  `signal` in the tens with `ambient` at `0.00` is a sensor looking at itself,
  and a healthy one reads the far wall with `signal` around 1-2 and `ambient`
  above zero

That is the last time the firmware is touched today.

If you are going to test for a while before the doors open, and there are
people working nearby, add `--mute` -- see **Testing next to people** below. It
cannot be left behind.

---

## The two modes

### Demo -- the whole cycle with the VLM. One terminal.

```bash
python3 noticebot_loop.py \
    --cam 0 \
    --cores3 \
    --detector yoloworld \
    --cv-hz 4 \
    --conf 0.2 \
    --feedback robot \
    --approach \
    --no-view \
    --serve
```

Every flag, and why it is not optional:

| | |
|---|---|
| `--cam 0` | whatever `--list-cams` said this morning. Not a number to memorise |
| `--cores3` | bare, so it auto-detects by PING. The port moves between sessions |
| `--detector yoloworld --cv-hz 4` | the detector, and the only one |
| `--conf 0.2` | **0.3 is too high for a phone in a hand.** Measured: 0.39 and 0.48 at arm's length, right on the edge, blinking in and out several times a second |
| `--feedback robot` | lets a confirmed finding drive the call. `console` prints the judgment and **moves nothing** |
| `--approach` | arms the board's ToF to press the button |
| `--wake palm` | the default. A **hand held in front of the sensor** wakes it. `--wake approach` is the old "somebody walks up" |
| `--no-view` | **no cv2 preview window.** See below -- it is the most likely cause of the segfaults, and at a stand nobody looks at it anyway |
| `--serve` | the web pages, for you and for the audience |
| `--mute` | **testing only.** No chirps, for working next to people. Take it off before the doors open |

Watch for this in the first few lines, before CV output buries it:

```
[cores3] wake ARMED (palm) -- a hand held in front of the sensor presses the button
```

**No ARMED line means walking up will do nothing.** And if the loop prints a
`!! --approach without --feedback robot` warning, stop and add the flag: the
whole cycle will otherwise run, the judge will confirm, `[FEEDBACK]` will
print, and the robot will never call. Nothing looks broken. That is the worst
way for it to be broken and it cost an evening.

**Nobody walks up until it has printed `[gemini] warm in ...`.** The ToF is
live from the moment the board is powered and the loop takes ten or fifteen
seconds to come up.

**`standing_prompt.py` is no longer part of this.** It answered on a silent
visitor's behalf, back when the only other way out of Attend was an error. The
menu now covers somebody who wants something, and the sleep rule covers
somebody who wants nothing -- so it was left answering for people who had just
spent fifteen seconds showing they were not asking, and sending the robot off
to watch for three minutes on a request nobody made.

`python3 robot/tools/standing_prompt.py --after 10` brings it back for a
session where the whole pipeline has to be seen with nobody touching the
tablet. It prints the audience address either way.

### Performance -- played from the keyboard, beside the fish. One terminal.

```bash
python3 robot/tools/perform.py
```

Starts frozen. `F` to begin, `SPACE` to tap the beat.

---

## If it segfaults

```
zsh: segmentation fault  python3 noticebot_loop.py ...
```

A native crash, so there is no Python traceback worth reading and nothing can
catch it. The faulthandler dump names the line it died on -- it has been inside
the preview-window path both times.

**Run with `--no-view`.** OpenCV's macOS capture backend runs on the camera
thread while HighGUI (`cv2.imshow` / `cv2.waitKey`) runs on the main one, and
that pair is a known crasher on this platform. `--no-view` removes HighGUI from
the process entirely. It costs nothing here: the tablet and the developer page
are the display, and the keyboard keys work from the terminal either way.

This is not a proof -- a segfault does not leave one. It removes the most
likely cause, and if it crashes again with `--no-view` on, that is worth
knowing and narrows it a lot.

Also check **`--cam`**. `--cam 0` is the Mac's built-in camera, which on Apple
silicon is a square Center Stage sensor that rescales itself; the head camera
is a different index and `--list-cams` says which.

---

## Testing next to people

Add `--mute` -- to the loop, or to `attend_test.py`, which is the one you run
twenty times in a row while tuning:

```bash
python3 robot/tools/attend_test.py --mute
```

The chirps fire on every state change, which over an afternoon of debugging is
a lot of them.

**It does not stick.** Any mode started without `--mute` says the volume out
loud on the way in and the sound comes back, so a muted afternoon cannot leave
you with a silent robot on the day -- which is the failure this shape is chosen
to avoid, because a robot with no voice looks like a broken speaker and the
mode you are running is not where the setting was made.

---

---

## Switching

```
Ctrl-C            everything that is running
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
forgot about. Find it and Ctrl-C it in its own window -- that is the clean way
and it needs no commands.

**If there is no window to go back to** -- the terminal crashed, or was closed,
or the process outlived it:

```bash
pgrep -fl "noticebot_loop|perform.py|attend_test|standing_prompt"
```

`pgrep`, not `lsof`. `lsof /dev/cu.usbmodem*` finds a process holding the
SERIAL port and misses one holding only the camera or the microphone -- and an
orphan with the camera open gives `camera 1 opened but produced no frames in
8s`, which looks like a hardware fault and is not one. The `pgrep` line covers
all four modes and every device at once.

Then, with the pid:

```bash
kill -INT <pid>
```

**`-INT`, not plain `kill`.** SIGTERM ends Python without running the teardown,
and the teardown is where the unfinished story is written out, the neck is
returned to idle and **the servos are de-energised**. Killed the other way the
motors stay powered holding whatever pose they were in, which is invisible for
half an hour and then the horn is too hot to touch. `kill -INT` is exactly what
Ctrl-C sends.

Wait two seconds, run `pgrep` again. Only if it is genuinely stuck: `kill -9`,
and then power-cycle the servo supply, because nothing turned the torque off.

| | |
|---|---|
| `no CoreS3 found` | the other mode still has it, or you did not wait two seconds, or the cable |
| `camera N opened but produced no frames` | an orphan has it, or the index moved -- `--list-cams` again |
| servos do not move | performance starts **frozen** -- press `F`. Otherwise the 5-6 V supply |
| `!! did not arrive` in the log | the line itself now says which: a voltage under load, or torque off / jammed |
| a hand does nothing | is `wake ARMED (palm)` in the loop's first lines? If not, `--approach` did not arrive. Then: is the hand close enough -- inside **30 cm**, and `tof_test.py` shows the number it is actually reading |
| it wakes with nobody there | something is in front of the lens, or the film is still on it: that reads 0 mm. `tof_test.py` will sit at the far end of the bar |
| it wakes once and never again | v10 or older on the board. Fixed in v11 -- check `tof_test.py` |
| the robot performs an error | it should be close to unreachable now -- read the reason it prints and tell Cassie |
| the face does not appear | `IN FACE no memory` at startup, or `E` turned it off |

---

## When it runs but never notices anything

The whole chain works and nothing happens. The loop names the first broken link
every 8 s -- **read the `[cv]` and `[gate]` lines**, they are ordered so the
first miss is the one reported:

```
[cv]   no pose at all -- MediaPipe found nobody
       -> relations are about PEOPLE. A phone alone lights nothing

[cv]   1 person(s), but the detector does not see phone -- it sees no objects
       -> the detector, not the geometry. --conf lower, or move closer

[gate] held back -- the relation landed on desk, but this card names phone
       -> the hand is on the wrong thing, or the noun in the prompt is wrong

[cv]   HAND is on the phone, held 0.3s of the 0.6s needed
       -> nothing is wrong. Keep still half a second longer
```

`[FEEDBACK] ...` means the judge **accepted** it. If that prints and the robot
still does nothing, it is `--feedback robot`.

---

## It lets go of an abandoned request after three minutes

`VISIT_MAX_S = 180`. Three minutes with **nobody touching it** -- no finding
delivered, no OK, no correction, no new request -- and it goes back to idle
with the sleeping face, ready to be woken.

This is the crowded-stand fix and it is less obvious than it looks: a request
belongs to the person who asked for it, and `ptt_down` is **ignored in any
state but idle**. So a robot still watching a request whose owner left is a
robot nobody else can start anything with. A busy table is exactly where it
looks most alive and is least reachable.

Any interaction restarts the clock, and a judge in flight postpones it, so it
cannot end a conversation in progress -- only an abandoned one.

**Meanwhile anyone can take over at any time** from the prompt row at the
bottom of the tablet. That path never waits for the robot to be idle.

---

## It looks around by itself after a quiet minute

`REPLAN_IDLE_S = 60`. If the angle it is watching produces **nothing** for a
minute, it sweeps and re-plans on the request already on record. That is what
keeps a plan made for whoever was standing there ten minutes ago from outliving
the room it was made for, without anybody retyping a prompt for each new face.

**It cannot interrupt a visitor.** A rule that keeps landing keeps pushing the
clock out, and a correction or a report in progress is never cut off. The other
timer -- `REPLAN_PERIOD_S`, which goes off on a clock whatever is happening --
is deliberately **off**: at a stand it swings the head away from the person who
just asked it to watch something.

So a head that turns away after a quiet minute is working, not lost. It costs
about 6 s of sweeping and one VLM round trip. Both live in `robot/states.py`.

---

## The thirty-second check after any restart

1. hold a hand in front of the sensor, close -> head comes up
2. take the hand away and wait two seconds
3. hold it there again -> **head comes up again**
4. walk past the table without reaching -> it does **nothing**

Step 4 is the whole reason for the change. The approach wake fired on anybody
crossing the cone at a metre and was then held shut by the crowd standing
around the table -- a robot that woke at nobody, and then would not wake for
anybody. Neither was a threshold problem: both were the sensor answering the
question it had been asked. A hand inside 30 cm is a different question, because
nobody's body is there by accident.

If step 3 fails, the board is on v10 or older.

---

## What a visitor actually does

```
hand up to it     the head comes up; the tablet lists four things
TOUCH ITS HEAD    the highlight moves down the list. Touch again to keep going
stop touching     2.5 s later it takes the highlighted one
                  -> got it, looking around, then watching
```

**They choose by touching the robot, not the tablet.** The tablet is a display
here and the cards are deliberately not touch targets. Nothing commits until
somebody taps at least once -- touch nothing and it goes back to sleep at 15 s,
which is the rule that says standing there is not asking for anything.

What to say to a visitor, in full: **"hold your hand up to it, then touch its
head until it says the one you want."** That is the whole interface.

**It is a capacitive pad on the head (TTP223, Grove Port C), not a knock** --
so it wants a finger resting for a moment, not a tap. `TAP_G` in the firmware
is for the IMU path and does nothing here; `TAP_SRC` is 1.

If it fires with nobody touching it, the SIG line is floating -- harmless while
it is asking, and in S4B_WATCH every false one is a correction. `RUNBOOK.md`
has that.

**The wake is a hand, held close.** Measured on the bench: a hand where it
falls naturally reads 40-50 mm and the empty room reads 2720-2750, so the gate
at 300 mm is not balancing anything -- there is nothing in between. Tell people
"hold your hand up to it", not a distance.

**They do not have to speak, or find a screen.** The room is loud and half of
them are speaking a second language; a spoken sentence that fails to transcribe
spends the whole ninety seconds performing not-having-understood, and a tablet
is not an encounter with a robot. Speech still works and still wins -- anything
actually said lands first and the list never appears.

**If they walk off, it goes back to sleep.** The board says `IN LEFT` when the
visitor who woke it has gone, and before a request exists that returns the
robot to idle. It used to sit there and then perform an error at an empty
table, which the next visitor would walk up to.

Once a request EXISTS, leaving means nothing -- the whole point is that it
watches while you get on with something, so "I left the room" is the normal
case for a delegated task and never cancels it.

**If somebody stays and does nothing, it goes back to sleep at 15 s.** Standing
in front of it is not asking for anything, and at a stand that is most of the
people who trip the sensor: they walk up, look, and go on with their day.
Sleeping is not a failure and does not read as one -- and waking it again costs
a step back and a step in.

The timeline, since the numbers get confused:

```
 0.0 s   walks up -> head up, tablet shows the menu
 4.5 s   the board releases the button (APPR_HOLD, firmware)
 ~5  s   Whisper returns '' -- DROPPED in demo mode, it is not a failed
         request when nobody was asked to speak. Words that were misheard
         still go through: that error is the robot being honest
15.0 s   nobody asked for anything -> BACK TO SLEEP (ATTEND_MAX_S). Not an
         error, and short enough that the error below is unreachable by
         standing still
19.5 s   the flow would give up -> S7_ERROR (4.5 + STT_TIMEOUT_S)
 any     they walk away -> IN LEFT -> back to idle, no error
```

Between the menu, the sleep rule and `IN LEFT`, a visitor cannot reach the
error state by anything they do or fail to do.

Edit the four lines in `webui/booth.py`, `PRESETS`, near the top.

**"tell me if there's something interesting" is the weak one.** Vague requests
give the planner nothing to compile and it returns something thin or nothing at
all. It is on the list because it is what people reach for when none of the
others is what they meant -- worth watching how often the plan behind it is any
good, and worth replacing if it is not.

---

## Showing someone how to set it off

Tell them the ACTION, not the rule. Each one has to be held about two seconds
-- half a second of contact, two frames, then the judge.

| preset | what to do |
|---|---|
| holding a phone | hold it in view of the head camera, still, not flat against your body |
| drinks a coffee | pick the cup up and hold it. Raising it to your mouth is the clearest |
| more people gather | **have a second person step into frame and stay.** The easiest one by far |
| something interesting | the weak one. Expect a thin plan or none |

**`gather` is the reliable one, so lead with it.** It watches the number of
people in frame changing and holding -- no object has to be detected, and it is
the only preset that does not depend on a small thing being boxed in somebody's
hand. At a busy stand it fires on its own.

Both people have to be whole enough to read as bodies, and the new count has to
hold for about a second and a half. Somebody walking through does not count;
somebody arriving and staying does.

**Pointing is not on the menu.** It needs a visible shoulder, elbow and wrist,
a ray past the extension test, and a detected box within tolerance -- and the
gesture everybody tries first, aiming at the robot, cannot work: the ray is
computed in the image plane, so an arm pointed at the camera foreshortens to a
point and hits nothing. It is still in the vocabulary, so `points at the cup`
typed into the prompt row can still compile; it is just not offered as a
one-tap promise.

If a preset refuses to fire, name the object in the prompt -- `holding the red
cup` rather than `holding something`. That binds the rule to the cup instead of
relying on the VLM having put it in the focus tier.

---

## Retyping the prompt mid-show

The tablet page has a prompt row along the bottom, on every screen including
the sleeping one. Type a sentence, press return, `sent` flashes.

It re-plans from whatever state the robot is in, **including error** -- so it
is also the way to pull it out of one without touching the laptop.

Concrete and about the audience, or the planner has nothing to compile:

    tell me when there's something interesting
    tell me when someone points at something
    tell me when someone is holding a phone

---

## End of day

Ctrl-C everything. The neck goes to idle and the torque comes off on its own.

Power down the servo supply **before** unplugging USB.

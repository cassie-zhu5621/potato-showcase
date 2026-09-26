# Demo runbook — the whole cycle, with the VLM, triggered by walking up

The study build with two things added: the board's ToF presses the button, and
a companion posts a standing prompt so nobody has to speak. Everything else —
camera, detector, planner, judge, sweep, the report, the tablet page — is the
study loop, unchanged.

`THE_THREE_MODES.md` says how this differs from the other two.

---

## 1. What happens

```
  nobody              S0 Idle
    │  somebody comes within 90 cm and stays 0.7 s
    │  -> the board sends IN PTT_DOWN / PTT_UP, exactly as the button does
    ▼
  S1 Attend           head up, microphone open
    ├── they speak         -> the loop takes it, the companion stands aside
    └── 3 s of silence     -> the companion posts the standing prompt
    ▼
  S2 Acknowledge      two nods
    ▼
  S3 Scan             sweeps, five stations, then the planner
    ▼
  S4 Watch            holds, watching for the spec to fire
    ├── head tap  -> S6 Correct -> back to Watch, re-aimed
    ▼  a watch entry fires and is confirmed
  S5 Call             the lean, bright yellow, the rising chirp
    ▼  OK, or ignored for 30 s
  S4 Watch
```

**This is the full loop, so it has the full loop's costs.** Every arrival
re-plans: six seconds of sweeping and then a VLM round trip, with the visitor
standing there. That is the known price of route A, and it is why
`SHOWCASE_FLOW.md` designs a different loop for the showcase itself. For a
demo, where the point is that the whole pipeline is visible, it is the right
trade.

## 2. Flash

Firmware **v9** or later. v9 is the one that has the approach gate. Same as everything else:

```bash
cd ~/Documents/potatobot/showcase
lsof /dev/cu.usbmodem*          # kill anything listed
pio run -t upload
python3 robot/tools/tof_test.py     # first line must say v9. Ctrl-C after
```

## 3. Run, in two terminals

```bash
# 1 -- the loop, as usual, plus --approach
python3 noticebot_loop.py --serve --cores3 --approach --detector yoloworld

# 2 -- the companion
python3 robot/tools/standing_prompt.py
```

On startup terminal 1 prints:

```
  [cores3] approach trigger ARMED -- walking up presses the button
```

If that line is missing, `--approach` did not reach the board and walking up
will do nothing.

The laptop page is the loop's own: `http://<this machine>:8000/booth` full
screen for the audience, `/` for the developer view.

## 4. The standing prompt is the part that matters

It is not a technical choice and the default is only a starting point.

```bash
python3 robot/tools/standing_prompt.py --say "tell me when someone points at something"
```

**Vague prompts are how this fails.** "Tell me if anything interesting
happens" gives the planner nothing to compile into a watch-spec; it returns
garbage or nothing, and nothing routes to Error. Concrete and high-frequency,
and about the **audience**, because the audience is the thing guaranteed to be
present and moving:

    "tell me when someone comes close to the table"
    "tell me when someone points at something"
    "tell me when two people look at the same thing"

The payoff is that the report on the laptop is about the person reading it.

At a demo you want it to fire often. The study's thresholds are tuned for the
opposite — rarely and correctly — so expect to loosen rather than inherit.

## 5. What the two additions are, exactly

**The approach gate is in the firmware**, not in Python, and that is forced:
the loop holds the CoreS3 port, so no companion process can read the distance
at all. It emits `IN PTT_DOWN` then `IN PTT_UP`, and `session_flow` never
learns a sensor exists.

It is **deliberately dumber** than `session/proximity.py` — a threshold, a
dwell and a refractory, no hysteresis, no stillness test, no median. That one
has to tell an arrival from somebody crossing a busy room; this runs in a demo
where the robot is what people are walking up to. Anything cleverer here would
be a second copy of a tested thing, drifting.

Numbers, in `cores3_sidekick.ino`: `APPR_ENTER 900`, `APPR_EXIT 1300`,
`APPR_DWELL 700 ms`, `APPR_REFRACTORY 12 s`.

**The companion exists to keep it out of `S7 Error`.** A visitor has no idea
what they were supposed to say, so a robot performing not-having-understood
reads as broken rather than as communicative — and it is the one thing the room
will remember. It polls `/booth.json`, and if the robot has been listening for
`--after` seconds with nothing heard it posts the standing prompt to
`/context`, which `session_flow` accepts from any state and always re-plans.

`--after` defaults to 3 s against a 15 s speech timeout, so there is no race.

## 6. When something goes wrong

| | |
|---|---|
| walking up does nothing | the ARMED line missing from terminal 1? Then `--approach` did not arrive. Otherwise `tof_test.py` — is the sensor reading at all |
| it wakes at people walking past | `APPR_ENTER` is 900 mm. Lower it, or aim the sensor across the approach rather than down the room |
| it wakes over and over | `APPR_REFRACTORY` is 12 s |
| it reaches Error anyway | the companion is not running, or `--after` is above the speech timeout, or the standing prompt does not compile — try a more concrete one |
| the report never comes | the spec is too tight for the room. Loosen the prompt before touching thresholds |
| nothing on the tablet page | the loop's own page, so the loop's own problem: check `--serve` and the address it printed |

## 7. Afterwards

Ctrl-C the companion, then the loop. The loop returns the neck to idle and
relaxes it. Power down the servo supply before unplugging USB.

**No power-cycling between modes.** The approach gate does stay armed on the
board until reset, but every mode claims the board on startup and says all
three switches including the offs -- so starting the performance or the study
loop afterwards turns it off, whatever this run left behind. See
THE_THREE_MODES.md.

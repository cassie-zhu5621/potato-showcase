# Four modes, one robot

Nothing here runs at the same time as anything else here. All three want the
servo bus and the CoreS3, and there is one of each.

| | command | what it is |
|---|---|---|
| **Study** | `python3 noticebot_loop.py …` | the notice loop: camera, VLM planner, the eight-state cycle. Unchanged |
| **Demo** | the same, `--approach`, plus `standing_prompt.py` | the whole cycle with the VLM, started by walking up. `DEMO_VLM_RUNBOOK.md` |
| **Showcase** | `python3 robot/tools/attend_test.py` | somebody comes close, the head comes up. No planner, no network |
| **Performance** | `python3 robot/tools/perform.py` | played from the keyboard, to music, beside the fish. `PERFORM_RUNBOOK.md` |

## What the showcase work changed under the study loop

Almost nothing, and the parts that did are listed here rather than left to be
discovered:

**The state names.** `S1_IDLE` became `S0_IDLE`, `S7a` became `S5A_FOUND`, and
so on — clip, .blend, generator and runtime ID are one string now, and it is
the paper's. `STATE_NAMES.md` has the map. This touched every file; the 394
tests that existed before it still pass.

**`ClipPlayer.drive_deg()`** is new and nothing else calls it. It exists so the
performance oscillator can move the neck without a clip while still leaving
exactly one object owning the bus.

**`CoreS3Link` gained `tof`, `scan`, `tofdiag`, `tofbus`, `dist` and `say`.**
All additive. `FIRMWARE_V` went v6 → v7.

**The firmware gained the ToF, TOFDIAG, SCAN, TOFBUS, SAY and a voice.** All
additive, all behind `USE_TOF` / `__has_include`.

## The one that did bite, and how it was fixed

`checkTof()` printed `IN DIST <mm>` at 20 Hz, and `noticebot_loop`'s CoreS3
handler prints every line the board says. Running the study loop with v7
firmware therefore buried PTT, BODYTAP, OK and STOP under 1200 lines a minute
of distance readings — the loop still worked, and you could not see it working.

**The board is silent unless asked now.** The sensor still runs, so `TOFDIAG`
stays truthful, but `IN DIST` is only emitted after `EVT DIST 1`. The three
tools that want the stream ask for it on connect; the study loop never does and
needs no change.

The general rule, worth keeping: **a device does not stream telemetry nobody
asked for.** Anything added later that chatters — the IMU's tap strength, a mic
level — gets the same treatment.

## The demo is the study build plus two things, not a fork of it

The board's ToF emits `IN PTT_DOWN` / `IN PTT_UP`, so walking up is
indistinguishable from pressing the button and `session_flow` never learns a
sensor exists; and a companion posts a standing prompt over HTTP when nobody
speaks, so the flow never reaches Error. `--approach` arms the first. With
neither, the loop is exactly what it was.

The gate has to be in the firmware because the loop holds the CoreS3 port --
no companion process can read the distance at all. It is deliberately dumber
than `session/proximity.py`; the reasoning is in DEMO_VLM_RUNBOOK §5.

## One board, four modes, and none of them can reach the others

**The firmware is shared and is not part of any mode's freeze.** It grows only
by addition, every optional thing in it arrives OFF, and a mode gets what it
asks for and nothing it did not. So reflashing for one mode does not change
another: `perform-v1` on a v9 board behaves exactly as it did on v8, because
the only thing v9 added is a gate that starts closed.

**Every switch persists until the board is reset**, which is the part that
would have bitten. Run the demo and the approach gate stays armed; run the
performance next and the board is still pressing its own button through it.

Asking each mode to tidy up on the way OUT is the arrangement that fails the
first time one is killed with Ctrl-C, which is how every session ends. So each
mode **claims** the board on the way IN -- `link.claim(...)` says all three
switches including the offs -- and the modes stop being able to reach each
other at all.

A default that is currently right is a default that stops being said, and then
it stops being right. Hence "including the offs".

**The version check warns only about an OLDER board.** A board ahead of the
checkout understands everything it will be sent, and warning about it would cry
wolf every time any one mode was reflashed -- the fastest way to teach someone
to ignore the warning that matters.

## What is deliberately NOT shared

The showcase reflex layer does not go through `session_flow`. It could have —
the states are the same — and it must not: the flow's timeouts, its Error
state and its planner coupling are all built for a study where a request has to
be understood, and a showcase has no request. Wiring them together would mean
every future change to one had to be defended against the other.

`SAY` is not wired to any state for the same reason. It is played by hand, at
the end, with the music off.

# What the showcase build cost, and why

A record of the traps, written while they were still fresh. Not a changelog --
`git log` is that. This is the part that is expensive to rediscover: the bugs
whose symptom pointed somewhere other than their cause, and the decisions that
are only defensible if you know what they replaced.

Dates are 2026. Every claim here has a commit and a test behind it.

---

## The ones that lied about where they were

**A blocked ToF reports `0 mm` with a valid status, not an error.** Three
evenings. `RangeValid` is **0** in Pololu's enum, so a failed I2C read -- which
leaves the struct as it found it, all zeros -- comes out of
`status == RangeValid` as the most trustworthy measurement there is. Every
explanation for a zero distance points at software. Fixed in v15 by also
requiring `last_status == 0` and `range_mm > 0`; a true zero is the absence of
a measurement wearing the costume of one. `7c798ca`

**The diagnostic broke what it was measuring.** `SCAN` walks both pin orders,
so it re-`begin()`s the bus with the pins swapped under a sensor that is
mid-ranging -- and nothing put it back. `--diag` scanned first and sampled
second, so it reported its own damage as the symptom, and two more explanations
were built on that trace. v16 restores the bus and says so; the tool samples
before it scans, because the fix in the firmware is not enough on its own --
the tool has to work against the board that has the bug. `b86820b`

**What finally settled it was `signal` and `ambient`**, which `TOFDIAG` could
not reach. A huge signal with zero ambient is a receiver flooded by its own
emitter: something is on the lens. 1-2 with ambient above zero is a sensor
looking at a room. `TOFRAW` prints both. `72b9773`, `347b4e2`

**`--feedback console` is the study's right default and the demo's silent
death.** Every stage works, the judge confirms, `[FEEDBACK]` prints, and the
robot never calls. Nothing looks broken. The code was never wrong -- the
runbook I wrote omitted the flag, so following it could not succeed. Lesson:
derive a new command from one that has actually run a session, never assemble
it from the flags that seem necessary. `c00d567` and the `--feedback robot`
guard in `test_modes_do_not_leak.py`

**The candidate gate stayed shut after the first finding.** It was released on
`S5B_BECKON -> S4B_WATCH`, which is the route taken when a report is IGNORED.
Pressing OK -- the normal case, the thing the whole gesture exists for -- goes
through `S2_ACKNOWLEDGE` first, because the robot nods. So acknowledging a
finding was what broke it, and the robot could report exactly one thing per
run. Now it releases on leaving the reporting states by any route. `3506a0c`

**A state is not an animation.** Touch feedback used
`player.request("S2_ACKNOWLEDGE")` for a nod; that clip is authored with
`then="S3_SCAN"`, so one touch launched a scan. The rule was already in the
file four hundred lines down -- *an EVENT into the flow, never
`player.request()`* -- and it holds for feedback too. `081cc51`

**Two clocks measuring different things.** `truth` is windowed (held within the
last 2 s, so a dropped frame does not end a contact); `viz` is this frame only.
The focus gate compared them, so a phone at 0.39 confidence blinking in and out
left the card satisfied on exactly the frames where the gate could see nothing
to have landed on. Blocked every time, for minutes, with a hand visibly on a
phone. `962731f`

---

## Decisions, and what they replaced

**Wake: a palm at 300 mm, not somebody walking up.** The approach gate was not
insensitive, it was ambiguous: a body at a metre fires on everyone walking
past, and the same crowd standing round the table holds the latch shut. A robot
that wakes at nobody and then will not wake for anybody -- neither fixable by
moving a threshold. A hand inside 30 cm is a different question, because
nobody's body is there by accident. Measured: hand 40-50 mm, empty room
2720-2750. `ed6a517`, `d55085c`

**Choosing: touch the robot's head.** A tablet is not an encounter with a
robot, and a stranger at a loud stand will not speak into a laptop microphone.
The list rests on the first line, every touch moves down one, and a 3 s pause
commits -- a pause rather than a confirm gesture, because stopping is what
somebody does anyway once they see the one they want. A visible draining bar,
because without it the first touch still reads as a decision. `8e094a1`,
`d0d4c46`

**Error is close to unreachable, on purpose.** Walking away before asking goes
to idle (`IN LEFT`, v13). Standing there asking for nothing sleeps at 15 s
(`ATTEND_MAX_S`), which is shorter than the error path so it cannot be reached
by standing still. Silence while the menu is up is dropped rather than refused
-- nobody was asked to speak. A failed plan watches the richest angle instead
of performing the planner's bad day. `e1c97ca`, `6393c56`, `a8fa2e3`, `4402b1a`

**An abandoned visit ends after 3 minutes.** `ptt_down` is ignored in any state
but idle, so a robot still watching a request whose owner left is a robot
nobody else can start anything with. A busy table is where it looks most alive
and is least reachable. `4402b1a`

**`gathering` replaced `pointing` in the menu.** Pointing needs a visible
shoulder/elbow/wrist, a ray past the extension test, and a boxed object within
tolerance -- and the gesture everybody tries first, aiming at the robot, cannot
work: the ray is computed in the image plane. Loosening 140 to 110 deg was not
enough. It stays in the vocabulary and out of the menu, because a preset that
mostly does not fire teaches a visitor that the robot mostly does not work.
`731745b`, `6ae4183`

**The standing prompt is off.** It answered for silent visitors back when the
only other way out of Attend was an error. The menu covers somebody who wants
something; the sleep rule covers somebody who wants nothing. What was left was
a companion answering on behalf of a person who had just spent fifteen seconds
showing they were not asking. `0976e10`

---

## Things that were true about the tests, not the code

**A test file ran, recorded failures, and could not fail.**
`test_session_flow.py`'s summary sat in the middle of the file, so three
appended sections filled `fails` and were never looked at again -- green under
pytest whatever they found. The second time it happened, the buried section was
the one for the bug under investigation. Guarded now by
`test_the_flow_suite_can_fail.py`, which also injects a deliberate failure to
prove the suite can go red. `3506a0c`

**Six test files were never committed.** `commit -am` does not add untracked
files, so 848 lines of coverage existed only on one machine. `cd6be84`

**A version has to mean one sketch.** `PALM_ENTER` went 250 to 300 inside v17,
so a board flashed that morning and the repo that evening both answered `v17`
while behaving differently -- and everything downstream trusts that number. The
old test checked that the sketch and `cores3_link` agreed about the string;
both can agree and both be stale. Now the sketch is hashed into
`VERSION_LOCK.json`, and `lock_firmware.py` refuses to re-lock without a bump.
The failure message's real content is **REFLASH**. `810cfdb`

**Guards are only worth what they catch.** Every guard added here was verified
by breaking the thing it guards and watching it go red. Several did not, first
time -- including one that could only be satisfied by deleting its own
explanatory comment.

---

## Still open

- **R_GREET has no nod.** It should be S2's forward-and-down accent, once.
  `S4B_WATCH` is `loop: True` and `drive_deg` is explicitly unsafe during a
  clip, and the only other way to move is a state. Needs a one-shot that
  interrupts a looping clip and resumes it, inside the one object that owns the
  bus. See `GREET_*` in `robot/states.py`. `cc5c22a`
- **Segfaults** in the preview path, twice. `--no-view` removes HighGUI from
  the process and is in the demo command; it is a mitigation, not a diagnosis.
- **`LEAD_S` in `perform.py`** is still 0.12 and still a guess. The one
  hand-set constant there; calibrate against a metronome.
- **The two API keys** pasted into chat early on still need rotating.

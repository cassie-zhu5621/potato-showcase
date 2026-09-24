# Showcase flow

A one-to-two hour demo for new students. No explanation, no briefing, nobody
standing next to it. Someone walks up and something happens.

Everything here is a deliberate departure from the study build, and the reason
is the same every time: **the study was tuned for selectivity and the showcase
needs the opposite.** A study wants the robot to call rarely and correctly. A
showcase wants it to do something every thirty seconds, to whoever is standing
there, and to keep doing it for an hour without anyone resetting it.

Numbers marked `<measure>` are deliberately blank. They come off the logged ToF
trace, not off a guess — see "Before the thresholds" at the end.

---

## 1. The thing that decides the architecture

Perception runs at `NOTICEBOT_CV_HZ`, default **1 Hz**, and the planner is a VLM
round trip with a 90 s timeout. Those are the right numbers for "look at a room,
think, report". They are fatal here: at 1 Hz a person can walk up, wait, and
leave inside one perception frame.

So the showcase adds a **reflex layer that never waits for anything**:

    sensor  ->  clip
    ~ms, in-process, no planner, no network, no CV model

The planner stays, and the VLM stays, because the finding they produce is the
payoff. Neither is ever in the path of a reaction. If the network dies mid-show
the reflex layer keeps working and nobody in the room can tell.

**Degrade, never error.** Any upstream timeout falls back to the standing
watch-spec and the reflexes. `S7 Error` is not performed in showcase mode at
all — it goes to the laptop log. A visitor does not know what they should have
said, so a robot performing failure reads as broken, not as communicative.

---

## 2. The main loop

```
S0 Idle                         curled, head down, warm white, slow breath
  │   nobody near. Every <measure> s, one self-directed beat (S3 Scan):
  │   a still robot is not read as a waiting robot, it is read as an exhibit.
  │   This beat is what draws people over, and it is half the design.
  ▼  ToF crosses IN and holds  (see §4)
S1 Attend                       head rises, finds the person, cool blue
  │   ★ HOLD HERE. The mic is live in this window and nowhere else.
  │   The hold is the most valuable second in the loop: it is when the person
  │   works out that it is waiting for them. Nodding immediately makes it a
  │   vending machine.
  ├── speech arrives (VAD -> Whisper, usable)   -> replaces the standing spec
  ├── nothing for <measure> s                   -> keeps the standing spec
  ▼
S2 Acknowledge                  two nods
  │   spoke:     "I heard you"
  │   said nothing: "fine, I'll go and find something"
  ▼
S4 Watch                        (normally straight back -- see §3)
  │
  ├── head tap ──► S6 Correct ──► S4 Watch, re-aimed  (see §5)
  ▼  a watch entry fires
S5 Call                         freeze, counter-move, lean, bright yellow,
  │                             rising chirp
  ▼  ToF goes OUT, or <measure> s
S4 Watch, or S0 if nobody is near
```

The per-visitor path is **rise -> hold -> nod -> back to watching**, and it has
to fit inside about ten seconds. A hundred students will walk past; each one
gets a short loop, not a session.

---

## 3. When Scan and Plan actually run

Scanning is 6.13 s of sweep plus a VLM round trip. Run per visitor, it lands
exactly on the person who just arrived and is waiting to see what happens, and
they leave during it.

It is not removed, because scanning on site is what makes "interesting" mean
something in *this* room rather than in general, and because a spoken request
has to be compilable into a real watch-spec.

**Runs when:**

| trigger | why |
|---|---|
| startup, before anyone arrives | the first visitor must not pay the 6 s. The robot boots, scans an empty room, and is already watching when the doors open |
| a spoken prompt arrives | it has to be compiled |
| the replan timer | `REPLAN_PERIOD_S` — currently **0**, inherited from the exhibition stand. Set it to `<measure>` (order of 5–10 min) |
| S6 exhausts its candidate angles | five rejections in a row means the whole sweep was wrong, not just the aim. See §5 |

**Does not run** for a visitor who says nothing. That is the default case and
it is the whole point.

### The standing prompt

**A vague prompt is the most likely way this fails.** "Tell me if something
interesting happens" gives the planner nothing to compile into a watch-spec; it
produces either garbage or nothing, and nothing routes to Error.

The standing prompt must be **concrete but high-frequency**, and it should be
about the audience, because the audience is the thing guaranteed to be present
and moving:

    "tell me when someone comes close to the table"
    "tell me when someone points at something"
    "tell me when two people look at the same thing"

At a showcase these fire constantly, which is correct here and would be wrong in
a study. Thresholds should be loosened deliberately, not inherited.

The payoff is that the report on the laptop is about the person reading it.

---

## 4. Approach, and how it differs from too-close

One sensor, one axis, two thresholds — and they are not in competition, they
are consecutive beats of one story: it looks up at you, you keep coming, it
pulls back.

**The table does the hard part.** The robot sits on a table, so a standing
person's torso physically cannot get nearer than the table edge. Anything
reading closer than that is a hand or a face put there on purpose. That is
geometry, not a heuristic, and it is the cleanest discriminator available.

| band | meaning | goes to |
|---|---|---|
| > `<measure>` (out) | nobody | S0 Idle |
| crosses `<measure>` in, held `<measure>` s | someone arrived | S1 Attend |
| < `<measure>` (inside the table edge) | a hand or a face, deliberately | R_SHY |
| closing faster than `<measure>` m/s | thrust, not a walk | R_STARTLE |

Hysteresis on every one of them: enter and exit are different numbers, or a
person standing on the boundary makes the head bob up and down, which reads as
broken rather than alive.

A refractory period after S1 Attend fires, or a crowd retriggers it forever. At
a showcase "somebody is near" is true almost continuously, so the trigger is the
**transition**, and it tracks the nearest person, not the fact of a person.

### Mounting

**On the base, not the head.** The head moves; a rangefinder on a moving head
reports where it has turned to, not where the person is. Fixed to the base,
pointing forward, it is a stable trigger that is independent of where the robot
is looking.

**About 40 cm, horizontal.** That lands on a standing adult's thigh or hip: a
large, flat, always-present target that does not depend on where they are facing
— the opposite of a face, which is why the camera was ruled out for this.

**Rigidly, on a printed bracket.** The thresholds are absolute millimetres from
a fixed origin. Tape lets the origin drift, and a drifted origin presents as
"the robot is being weird today", which is nearly impossible to diagnose in a
room full of people.

---

## 5. Correct, and the bug it has

`noticebot_loop.py:next_best_pan(current)` ranks the five sweep stations by
score and returns the highest-scoring one at least 8 degrees from where it is
now. `current` is **one angle, not the set of angles already rejected**, so:

    watching A (top score)  -> tap -> returns B (next, >=8 deg from A)
    watching B              -> tap -> ranking is still [A,B,C,D,E]
                                      first one >=8 deg from B is A
                                   -> back to A

It toggles A -> B -> A -> B and C, D, E are never reached.

**Fix:** keep `rejected` as a set for the life of a watch-spec, exclude all of
it, and clear it when the spec changes. Then taps walk the ranking.

**And when the set is exhausted, re-sweep.** Five rejections in a row is not a
complaint about the aim, it is a complaint about the sweep, and re-scanning is
the honest answer. This is the fourth Scan trigger in §3.

Correct is the best thing in the demo and it should be made *easier* to fire
here, not harder: it is the only moment where a person touches the robot and
the robot visibly changes its mind, and horizontal shake reads as "no" without
a word of explanation.

---

## 6. The reflexes

Named `R_*` on purpose. **`S0`–`S7` is a closed set of eight and it is drawn in
the paper.** The moment a showcase beat becomes `S8`, the figure and the code
start diverging again, which is exactly what `docs/STATE_NAMES.md` was written
to end. Reflexes live in their own namespace and never enter the state machine's
numbering.

| reflex | channel | hardware | detector |
|---|---|---|---|
| **R_FLINCH** covered eyes | vision | head camera, **already there** | frame mean brightness AND variance collapse in one step. Dark alone is the lights going off; uniform alone is a white wall; both together is a hand |
| **R_STARTLE** clap / shout | hearing | CoreS3 mic, **already there** | `EVT LEVEL <0-100>` is already streamed for the recording bar. Watch it for a spike above the room's own distribution |
| **R_CLAP_BACK** copy a rhythm | hearing | same detector as R_STARTLE | three or more claps, take the median interval, nod back at that period |
| **R_LIFTED** picked up | body | CoreS3 IMU, **already there** | sustained change in the gravity vector, not a spike. The CoreS3 is on the base, so lifting the robot lifts it too |
| **R_SHY** too close | distance | **ToF4M — the only thing to buy** | inside the table-edge band, §4 |

Three of the five need nothing that is not already on the robot, so they can be
built before the ToF arrives. They are on three different channels, so they can
be tuned and tested independently.

**R_CLAP_BACK is the one to get right.** Dancing is a performance; clapping back
is a conversation, and the brief asks for reaction. It reuses R_STARTLE's
detector, needs no music, no speakers and no BPM, and it has no latency problem
because the person finishes clapping before the robot starts.

### Two firmware changes the reflexes need

**Tap strength is already computed and thrown away.** `checkTap()` under
`TAP_SRC 2` computes `d = |dax| + |day| + |daz|` and then only asks whether it
crossed `TAP_G`. Report `d` — `IN BODYTAP <d>` — and a light tap and a hard tap
become different events, with no new hardware. Small shake, big shake.

**TTP223 and the IMU should not be either/or.** `TAP_SRC` currently picks one.
They answer different questions and both are wanted: the TTP223 is capacitive
and unbothered by servo vibration, so it answers *the head was touched*; the IMU
answers *what happened to the whole body* — how hard, picked up, shaken, tilted.

**The IMU needs gating during playback.** The servos shake the robot, so
IMU-sourced taps will fire on the robot's own motion. The existing 400 ms
refractory does not cover this. Ignore IMU taps while a clip is playing, or
raise the threshold for that window.

### Authoring the reflex clips

They are ordinary Blender clips and can be made now; the motion and the trigger
are decoupled, so none of this waits on the ToF.

The one property that separates a reflex from a state: **it has to be faster
than any `S*` clip.** A reflex that eases in reads as a decision. `R_FLINCH` is
roughly fast in (~150 ms) -> hold -> slow recovery, with the LED dropping on the
way in. Amplitudes against the calibrated limits (pan −70/+76, tilt −29/+29,
nod −26/+47) and not past them.

---

## 7. What the laptop shows

The booth page is already a web page — `webui/server.py` serves `/booth`, and
`/stream.mjpg` is the live view. Open it full screen in a browser. The iPad code
does not change.

The CoreS3's own screen does not change either: small face, small status, as it
is. The laptop and the CoreS3 are two surfaces, not one moved.

What matters on the laptop is that the audience can see **what the robot is
looking at**: the live view large with the locked target boxed, and the reports
arriving beside it. The `listen` screen can be dropped — most visitors will not
speak.

---

## 8. Deferred

**Dancing to music.** Easy in the version that matters — the music is chosen in
advance, so the BPM is known and no beat detection is needed at all; Blender can
show the waveform on the timeline and the clip is authored against it. It needs
a playback rate multiplier in `clip_player` (clips are `{t, pose}`; scale `t`)
so one loop authored at a reference tempo covers any track.

Not done first because it is a performance rather than an interaction, it is the
hardest motion profile on the servos, and fast repeated pan reversals work the
camera cable, which is already what limits pan. When it is built: dance on
**nod** — a human head-bob is pitch, not yaw, so the natural axis is also the
safe one — keep pan small and slow, and let the LED carry the beat, since it
reads across a room and costs nothing mechanically.

---

## Before the thresholds

Every `<measure>` above comes from one session with the sensor and a log, not
from a guess:

1. Mount the ToF on its bracket, at the height it will actually run at.
2. Log distance against time while people walk up, stand, lean in, reach out,
   and leave. Include a few who stop at the boundary and hover there.
3. Read the bands off that trace. A standing person's reading is not a constant
   — how much it wanders is what sets how wide the hysteresis has to be, and
   that number cannot be reasoned about in advance.
4. Separately, log room audio for ten minutes with the crowd in. Put the
   R_STARTLE threshold outside that distribution's tail, not at a fixed level.

#!/usr/bin/env python3
"""
Exercise every path through session_flow with a fake clock and no hardware.

  python3 test_session_flow.py

Worth having as a test rather than as something to try on the robot: the awkward
paths -- STOP mid-scan, a transcript that arrives after a timeout, a tap during
the wrong state -- are exactly the ones that are tedious to trigger by hand and
the ones a participant will find in the first five minutes.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from session.session_flow import SessionFlow, transcript_usable
from robot import states as ST

CLOCK = [0.0]
fails = []


def flow():
    CLOCK[0] = 0.0
    return SessionFlow(now=lambda: CLOCK[0])


def run(f, events, label):
    trail = []
    for e in events:
        for kind, val in f.feed(e):
            trail.append((kind, val))
    return trail


def expect(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


print("--- the happy path ---")
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:find the blue mug"], "happy")
expect(f.state == "S2_ACKNOWLEDGE", f"usable transcript -> S2_ACKNOWLEDGE (got {f.state})")
expect(f.transcript == "find the blue mug", "transcript kept for the planner")
f.feed("arrived:S3_SCAN"); f.feed("arrived:S4B_WATCH")
expect(f.state == "S4B_WATCH" and f.screen == "planning",
       "holds at planning while the VLM is still deciding where to look")
f.feed("planned")
expect(f.screen == "tracking", "only says tracking once the direction is known")
f.feed("finding")
expect(f.state == "S5A_FOUND" and f.noticed == 1, "finding -> S5A_FOUND, count 1")
f.feed("arrived:S5B_BECKON"); f.feed("ok")
# OK NODS FIRST. S7 v6 rests exactly where S4b watches from -- 0.0 degrees apart
# in tilt and nod -- so returning to watching is no longer a visible movement and
# the acknowledgement had nothing to carry it. S2_ACKNOWLEDGE is borrowed for it, with
# `ack_then` arming the landing because its own `then` is S3_SCAN.
expect(f.state == "S2_ACKNOWLEDGE", "OK -> a nod of assent")
expect(any(k == "ack_then" and v == "S4B_WATCH" for k, v in f.out),
       "the nod is armed to land on watching, not to walk into a sweep")
f.feed("arrived:S4B_WATCH")
expect(f.state == "S4B_WATCH", "OK -> back to watching")

print("\n--- planner failure is visible ---")
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:find the blue mug",
        "arrived:S3_SCAN", "arrived:S4B_WATCH"], "")
expect(f.screen == "planning", "waits visibly while the planner is in flight")
f.feed("plan_failed:503 unavailable")
expect(f.state == "S7_ERROR" and not f.plan_pending,
       "planner failure exits planning and enters S7_ERROR")

print("\n--- the waiting screen ---")
f = flow()
out = run(f, ["ptt_down"], "")
expect(("ui", "recording") in out, "PTT down -> recording screen")
expect(("rec", "start") in out, "recording actually starts")
out = run(f, ["ptt_up"], "")
expect(("ui", "waiting") in out, "PTT up -> waiting screen")
expect(("state", "S2_ACKNOWLEDGE") not in out, "does NOT nod before the words exist")

print("\n--- unusable requests go to S8 ---")
for bad, why in [("", "silence"), ("uh", "one syllable"),
                 ("...", "punctuation only"), ("ok", "single word")]:
    f = flow()
    run(f, ["ptt_down", "ptt_up", f"transcript:{bad}"], "")
    expect(f.state == "S7_ERROR", f"{why!r:22} -> S7_ERROR (got {f.state})")

print("\n--- a misread is NOT an error: it is retyped ---")
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:find the blue mug"], "")
expect(f.state == "S2_ACKNOWLEDGE", "the corrected text goes straight through")

print("\n--- STT timeout: 15s of nothing -> S8 ---")
f = flow()
run(f, ["ptt_down", "ptt_up"], "")
CLOCK[0] = 10.0
f.feed("tick")
expect(f.state == "S1_ATTEND", "still waiting at 10s")
CLOCK[0] = 16.0
f.feed("tick")
expect(f.state == "S7_ERROR", f"past {ST.STT_TIMEOUT_S:.0f}s -> S7_ERROR")

# busy may postpone the deadline; it may not postpone it forever.
f = flow()
run(f, ["ptt_down", "ptt_up"], "")
f.stt_busy = True
CLOCK[0] = 25.0
f.feed("tick")
expect(f.state == "S1_ATTEND", "a RUNNING transcription is not a timeout")
CLOCK[0] = 31.0
f.feed("tick")
expect(f.state == "S7_ERROR",
       f"but past the {ST.STT_HARD_TIMEOUT_S:.0f}s ceiling it errors anyway -- "
       f"a wedged worker must not strand a participant")

print("\n--- S7 ignored for 30s ---")
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:watch the door"], "")
f.feed("arrived:S3_SCAN"); f.feed("arrived:S4B_WATCH"); f.feed("finding")
f.feed("arrived:S5B_BECKON")
CLOCK[0] += 20
f.feed("tick")
expect(f.state == "S5B_BECKON", "still beckoning at 20s")
CLOCK[0] += 15
out = f.feed("tick")
expect(f.state == "S4B_WATCH", "past 30s -> back to watching, not escalating")
expect(f.noticed == 1, "the finding stays counted -- it is in the feed")

print("\n--- STOP works from everywhere ---")
for st_events in (["ptt_down"],
                  ["ptt_down", "ptt_up"],
                  ["ptt_down", "ptt_up", "transcript:find the mug"],
                  ["ptt_down", "ptt_up", "transcript:find the mug", "arrived:S3_SCAN"],
                  ["ptt_down", "ptt_up", "transcript:find the mug",
                   "arrived:S3_SCAN", "arrived:S4B_WATCH"],
                  ["ptt_down", "ptt_up", "transcript:find the mug",
                   "arrived:S3_SCAN", "arrived:S4B_WATCH", "finding"]):
    f = flow()
    run(f, st_events, "")
    before = f.state
    out = f.feed("stop")
    expect(f.state == "S0_IDLE" and f.transcript is None,
           f"STOP from {before:<12} -> S0_IDLE, task discarded")
    expect(f.noticed == 0 and ("noticed", 0) in out,
           f"STOP from {before:<12} resets the noticed counter")

print("\n--- tap only means 'not that' while watching ---")
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:find the mug"], "")
out = f.feed("tap")
expect(f.state == "S2_ACKNOWLEDGE", "tap during S3 is ignored")
f.feed("arrived:S3_SCAN"); f.feed("arrived:S4B_WATCH")
out = f.feed("tap")
expect(f.state == "S6_CORRECT", "tap during S5 -> S6")
out = f.feed("reaim:-30")
expect(("pan", -30.0) in out, "re-aim emits a pan target")
# S4A, not S4B: an ANSWERED correction changed the target, so the crane onto it
# is an authored beat. The timeout path below is the one that goes straight to
# S4B -- nothing was decided there, so nothing is performed. S4_S5_DESIGN sec 9.4.
expect(f.state == "S4A_SETTLE", "an answered re-aim announces the arrival (S4a)")

print("\n--- S6 does not wait for an answer nobody can give ---")
# REAIM_TIMEOUT_S was 15 s, which assumed the person being asked could answer.
# During S6 the CoreS3 draws only STOP; `reaim` comes solely from the web UI or
# the researcher's keyboard. So the robot shook its head and stood motionless
# for 12.6 s waiting on a channel that does not exist. It now acts on its own
# refusal as soon as the shake is over -- and a later click still steers it,
# through S4B_WATCH, which is why that path was always accepted there.
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:find the mug",
        "arrived:S3_SCAN", "arrived:S4B_WATCH", "tap"], "")
CLOCK[0] += 1.0
f.feed("tick")
expect(f.state == "S6_CORRECT", "still shaking at 1s -- does not race its clip")
out = f.feed("reaim:30")
expect(f.state == "S4A_SETTLE" and ("pan", 30.0) in out,
       "a direction DURING the shake is an answer -- S4a announces the arrival")

f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:find the mug",
        "arrived:S3_SCAN", "arrived:S4B_WATCH", "tap"], "")
CLOCK[0] += ST.REAIM_TIMEOUT_S + 0.5
out = f.feed("tick")
expect(f.state == "S4B_WATCH",
       f"no answer within {ST.REAIM_TIMEOUT_S:.1f}s -> moves on by itself")
expect(("pan_next", True) in out, "...to the sweep's next-best angle")

# The same click a moment later must still work. It goes through S4B_WATCH, so
# there is no S4a arrival beat -- nothing was decided in a turn, so nothing is
# performed. Losing the beat is the point, not a regression.
out = f.feed("reaim:30")
expect(("pan", 30.0) in out and f.state == "S4B_WATCH",
       "a click AFTER the shake still steers it, quietly")

f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:find the mug",
        "arrived:S3_SCAN", "arrived:S4B_WATCH"], "")
out = f.feed("reaim:-60")
expect(("pan", -60.0) in out and f.state == "S4B_WATCH",
       "a nudge while already watching is accepted too")

print("\n--- PTT after STOP starts fresh ---")
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:find the mug", "stop"], "")
out = f.feed("ptt_down")
expect(("state", "S1_ATTEND") in out and f.transcript is None,
       "a new request, not a resume")

print("\n--- typed text: the researcher's fallback, usable from a dead session ---")
# The bug this covers: `typed` was routed as `transcript`, which only S1_ATTEND
# accepted. So the one input that exists to rescue a broken session was silently
# dropped in every state the session could actually be broken in.
for start, label in [([], "S0_IDLE"),
                     (["ptt_down", "ptt_up", "transcript:x"], "S7_ERROR")]:
    f = flow()
    run(f, start, "")
    expect(f.state == label, f"precondition: in {label}")
    out = f.feed("typed:watch the blue mug")
    expect(f.state == "S2_ACKNOWLEDGE", f"typed from {label} -> S2_ACKNOWLEDGE (got {f.state})")
    expect(("plan", "watch the blue mug") in out, "and it reaches the planner")

f = flow()
run(f, ["ptt_down", "ptt_up"], "")
f.feed("typed:watch the door")
expect(f.state == "S2_ACKNOWLEDGE", "typed during S2 corrects a misread, as before")

# Nonsense errors whatever it arrived on. What a participant can see is the
# robot, not the keyboard, so "it did not understand" has to look the same way
# every time.
for ev, who in [("typed", "researcher"), ("transcript", "participant")]:
    f = flow()
    if ev == "transcript":
        run(f, ["ptt_down", "ptt_up"], "")
    f.feed(f"{ev}:zz")
    expect(f.state == "S7_ERROR", f"nonsense from the {who} -> S7_ERROR")

print("\n--- noises are not requests ---")
# These pass the length and word-count tests and are plainly not requests. A
# participant who beeps at the robot must see it fail to understand, not watch
# it plan confidently against a noise.
for junk, why in [("beep beep beep", "an onomatopoeia, repeated"),
                  ("la la la", "singing"),
                  ("agaeirughsrihrsi", "keyboard mash, one word"),
                  ("asdfghjkl qwertyuiop", "keyboard mash, two words"),
                  ("ggggg hhhhh", "no vowels at all"),
                  ("test test", "the same word twice")]:
    ok, reason = transcript_usable(junk)
    expect(not ok, f"{junk!r:24} rejected -- {why} ({reason})")
    f = flow()
    f.feed(f"typed:{junk}")
    expect(f.state == "S7_ERROR", f"{junk!r:24} typed from idle -> S7_ERROR")

# ...and the rejection must not be so eager that it eats real requests.
for good in ["watch the roundtable area at my lab",
             "tell me when someone points at the whiteboard",
             "keep an eye on the door", "find the blue mug",
             "the strengths of the team", "look left"]:
    ok, reason = transcript_usable(good)
    expect(ok, f"{good[:44]!r:46} still accepted ({reason})")

# Typed text re-plans from EVERY state, including mid-watch. This is the wizard
# channel and it has to feel immediate; gating it on state made it read as broken.
for extra, label in [(["arrived:S3_SCAN"], "S3_SCAN"),
                     (["arrived:S3_SCAN", "arrived:S4B_WATCH"], "S4B_WATCH"),
                     (["arrived:S3_SCAN", "arrived:S4B_WATCH", "tap"], "S6_CORRECT")]:
    f = flow()
    run(f, ["ptt_down", "ptt_up", "transcript:find the mug"] + extra, "")
    expect(f.state == label, f"precondition: in {label}")
    out = f.feed("typed:watch the whiteboard instead")
    expect(f.state == "S2_ACKNOWLEDGE" and ("plan", "watch the whiteboard instead") in out,
           f"typed from {label} re-plans immediately")

print("\n--- PTT release must survive the screen it was pressed on ---")
# Mirrors the firmware latch. On hardware the recording screen has no buttons, so
# a release tied to the drawn button never fired and S2 hung with no armed
# timeout. Here: assert ptt_up is what arms the deadline at all.
f = flow()
run(f, ["ptt_down"], "")
CLOCK[0] = 60.0
f.feed("tick")
expect(f.state == "S1_ATTEND",
       "held button = still recording, no timeout (this is why a lost PTT_UP hung)")
out = run(f, ["ptt_up"], "")
expect(("rec", "stop") in out, "release stops the recorder")
CLOCK[0] = 69.0
f.feed("tick")
expect(f.state == "S1_ATTEND", "9s after release is still inside the 15s deadline")
CLOCK[0] = 76.0
f.feed("tick")
expect(f.state == "S7_ERROR", "and only then does the STT deadline run")

print("\n--- a cold recogniser is not a dead one ---")
# The first PTT of every session used to fail and the second work: loading the
# whisper model takes longer than STT_TIMEOUT_S, so the request was thrown away
# while it was being successfully transcribed.
f = flow()
run(f, ["ptt_down", "ptt_up"], "")
f.stt_busy = True
CLOCK[0] = 20.0
f.feed("tick")
expect(f.state == "S1_ATTEND", "no timeout while a transcription is RUNNING")
f.stt_busy = False
f.feed("transcript:watch the roundtable")
expect(f.state == "S2_ACKNOWLEDGE", "the late transcript is still accepted")
f = flow()
run(f, ["ptt_down", "ptt_up"], "")
CLOCK[0] = 20.0
f.feed("tick")
expect(f.state == "S7_ERROR", "but a recogniser that never answers still errors")

print("\n--- STOP reaches perception, not just the motors ---")
for st_events, label in [
        (["ptt_down", "ptt_up", "transcript:find the mug", "arrived:S3_SCAN"], "S3_SCAN"),
        (["ptt_down", "ptt_up", "transcript:find the mug",
          "arrived:S3_SCAN", "arrived:S4B_WATCH"], "S4B_WATCH")]:
    f = flow()
    run(f, st_events, "")
    out = f.feed("stop")
    expect(("idle", True) in out,
           f"STOP from {label} tells the loop to tear the watch-spec down")

print("\n--- the screen does not claim to be tracking early ---")
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:watch the roundtable",
        "arrived:S3_SCAN"], "")
expect(f.screen == "planning", "S4 -> planning")
f.feed("arrived:S4B_WATCH")
expect(f.screen == "planning",
       "S5 begins (head holds the last swept angle) but still says planning")
f.feed("planned")
expect(f.screen == "tracking", "the VLM answered -> tracking")

f = flow()                         # a re-plan re-arms it
run(f, ["ptt_down", "ptt_up", "transcript:watch the door",
        "arrived:S3_SCAN", "arrived:S4B_WATCH", "planned"], "")
f.feed("typed:watch the whiteboard instead")
f.feed("arrived:S3_SCAN"); f.feed("arrived:S4B_WATCH")
expect(f.screen == "planning", "a re-plan puts it back to planning")

print("\n--- ignored 'not that' moves ON, not back to the same view ---")
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:find the mug",
        "arrived:S3_SCAN", "arrived:S4B_WATCH", "planned", "tap"], "")
CLOCK[0] += 20
out = f.feed("tick")
expect(("pan_next", True) in out,
       "no answer in 15s -> ask for the NEXT-best angle, not the rejected one")
expect(f.state == "S4B_WATCH", "and it goes back to watching")

print("\n--- a planner that never answers ---")
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:watch the desk",
        "arrived:S3_SCAN", "arrived:S4B_WATCH"], "")
expect(f.state == "S4B_WATCH" and f.screen == "planning",
       "holds at planning while the VLM is out")
CLOCK[0] += ST.PLAN_TIMEOUT_S - 5
f.feed("tick")
expect(f.state == "S4B_WATCH",
       "a slow answer is not a timeout -- still waiting at 40s")
CLOCK[0] += 10
f.feed("tick")
expect(f.state == "S7_ERROR",
       "no plan within PLAN_TIMEOUT_S -> S8, not a permanent 'planning...'")

f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:watch the desk",
        "arrived:S3_SCAN", "arrived:S4B_WATCH", "planned"], "")
CLOCK[0] += ST.PLAN_TIMEOUT_S + 10
f.feed("tick")
# The claim is NO LATE S8, and it was written as `== S4B_WATCH` back when
# nothing else could move the machine on a tick. The re-plan timers can, and
# 100 s of quiet is well past both, so staying in S4B_WATCH is now the WRONG
# expectation -- asserting it would be asserting that the re-plan is still dead.
expect(f.state != "S7_ERROR",
       "an answered plan disarms the deadline -- no late S8")


print("\n--- S4 re-fires on its own (REPLAN_IDLE_S / REPLAN_PERIOD_S) ---")
# These two constants sat in states.py, documented and unread, while the robot
# watched one angle until somebody tapped it.
#
# THE MECHANISM IS TESTED WITH THE CONSTANTS SUPPLIED HERE, and the live values
# are tested separately below by asking the constant rather than by assuming a
# branch's answer. The two must stay apart: switching a feature off for one
# study must not delete the coverage that says it works, and a test that hard-
# codes one branch's setting has to be edited every time the branch changes --
# which is how it comes to be edited without being read.
_IDLE, _PERIOD = ST.REPLAN_IDLE_S, ST.REPLAN_PERIOD_S
ST.REPLAN_IDLE_S, ST.REPLAN_PERIOD_S = 30.0, 300.0

f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:watch the desk",
        "arrived:S3_SCAN", "arrived:S4B_WATCH", "planned"], "")
CLOCK[0] += ST.REPLAN_IDLE_S - 1
f.feed("tick")
expect(f.state == "S4B_WATCH", "just under REPLAN_IDLE_S -- still watching")
CLOCK[0] += 2
kinds = [k for k, _ in f.feed("tick")]
expect(f.state == "S3_SCAN", "REPLAN_IDLE_S of nothing -> sweep again")
expect("plan" in kinds,
       "...and it re-arms the sweep, rather than only changing state")

# A finding restarts the idle clock: the angle just proved it is not barren.
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:watch the desk",
        "arrived:S3_SCAN", "arrived:S4B_WATCH", "planned"], "")
CLOCK[0] += ST.REPLAN_IDLE_S - 2
run(f, ["finding:cup", "ok", "arrived:S4B_WATCH"], "")   # ok nods, then lands
CLOCK[0] += ST.REPLAN_IDLE_S - 2
f.feed("tick")
expect(f.state == "S4B_WATCH",
       "a finding restarts the idle clock -- a productive angle is not abandoned")

# Neither timer interrupts a turn the person is part of.
for st, label in (("S6_CORRECT", "a correction in progress"),
                  ("S5B_BECKON", "a report being delivered")):
    f = flow()
    run(f, ["ptt_down", "ptt_up", "transcript:watch the desk",
            "arrived:S3_SCAN", "arrived:S4B_WATCH", "planned"], "")
    f.state = st
    CLOCK[0] += ST.REPLAN_PERIOD_S + 1
    f.feed("tick")
    expect(f.state != "S3_SCAN", f"{label} is not interrupted to go and sweep")

ST.REPLAN_IDLE_S, ST.REPLAN_PERIOD_S = _IDLE, _PERIOD

# THE IDLE ONE IS A PER-BRANCH DECISION TOO, so this asks the constant.
#
# Showcase (60): the room turns over every couple of minutes and nobody retypes
# a prompt for each new face, so a plan that has produced nothing for a minute
# is about a room that has gone. It cannot interrupt anyone -- a rule that keeps
# landing keeps pushing the clock out.
# Study (0): quiet is the NORMAL condition in a 15-minute session, so this fired
# about thirteen times and left the aim close to random when an event finally
# happened.
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:watch the desk",
        "arrived:S3_SCAN", "arrived:S4B_WATCH", "planned"], "")
if ST.REPLAN_IDLE_S:
    CLOCK[0] += ST.REPLAN_IDLE_S - 1
    f.feed("tick")
    expect(f.state == "S4B_WATCH", "just under REPLAN_IDLE_S -- still watching")
    CLOCK[0] += 2
    f.feed("tick")
    expect(f.state == "S3_SCAN",
           f"{ST.REPLAN_IDLE_S:.0f}s of nothing at this angle -> look elsewhere")
else:
    CLOCK[0] += 480
    f.feed("tick")
    expect(f.state == "S4B_WATCH",
           "REPLAN_IDLE_S=0 -> eight minutes of quiet alone never re-sweeps")

# THE PERIODIC ONE IS A PER-BRANCH DECISION, so the test asks the constant
# rather than hard-coding one branch's answer.
#
# Study (540 s): one self-directed sweep per session is the only evidence the
# robot has any initiative, and 540 places it in the 8-10 minute gap between the
# scripted events.
# Exhibition (0): the same sweep lands in the middle of a stranger's ninety
# seconds, and the head swinging off the thing they just asked it to watch reads
# as a fault. Every visitor re-plans anyway.
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:watch the plant",
        "arrived:S3_SCAN", "arrived:S4B_WATCH", "planned"], "")
_t0 = CLOCK[0]
if ST.REPLAN_PERIOD_S:
    # KEEP THE ANGLE PRODUCTIVE while the period runs down. With REPLAN_IDLE_S
    # on, plain waiting re-sweeps for the idle reason long before the period is
    # reached, and the test would then be watching the wrong timer -- passing,
    # and proving nothing about the one it names.
    while ST.REPLAN_PERIOD_S - 30 > 0 and CLOCK[0] < _t0 + ST.REPLAN_PERIOD_S - 30:
        CLOCK[0] += 20
        run(f, ["finding:cup", "ok", "arrived:S4B_WATCH"], "")
        f.feed("tick")
    expect(f.state == "S4B_WATCH", "just before the period -- still watching")
    CLOCK[0] += 60
    out = f.feed("tick")
    expect(f.state == "S3_SCAN",
           f"at {ST.REPLAN_PERIOD_S/60:.0f} min it goes and looks again, once")
    expect(("plan", "watch the plant") in out,
           "...on the request already on record, not a new one")
else:
    # A FINDING EVERY HALF MINUTE, because with REPLAN_IDLE_S on, plain quiet is
    # no longer the right probe: it would re-sweep for the OTHER reason and the
    # test would pass while proving nothing about the period. A productive angle
    # keeps the idle clock pushed out, so anything that sweeps here is the
    # periodic rule -- which is what is meant to be off.
    for _ in range(8):
        CLOCK[0] += 30
        run(f, ["finding:cup", "ok", "arrived:S4B_WATCH"], "")
        f.feed("tick")
    expect(f.state == "S4B_WATCH",
           "REPLAN_PERIOD_S=0 -> four minutes of a WORKING angle is never "
           "interrupted by a clock")

print("\n--- transcript_usable thresholds ---")
for text, want in [("find the blue mug", True), ("", False), ("hm", False),
                   ("!?!?", False), ("look left", True)]:
    ok, why = transcript_usable(text)
    expect(ok == want, f"{text!r:22} usable={ok} ({why})")
ok, _ = transcript_usable("find the mug", no_speech_prob=0.9)
expect(not ok, "high no_speech_prob rejected even with good words")
ok, _ = transcript_usable("find the mug", avg_logprob=-2.0)
expect(not ok, "very low avg_logprob rejected -- hallucination")



print("\n--- a judge in flight is not an empty angle ---")
# Hardware, 2026-08-05: a judge started at 15:01:10, REPLAN_IDLE_S fired while it
# ran, and the reply 114 s later -- selected_index 0, both cards confirmed --
# was dropped as `stale candidate discarded`. Correct finding, correct
# judgement, deleted by a clock measuring the wrong thing.
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:watch the desk",
        "arrived:S3_SCAN", "arrived:S4B_WATCH", "planned"], "")
f.judge_busy = True
CLOCK[0] += ST.REPLAN_IDLE_S * 3
f.feed("tick")
expect(f.state == "S4B_WATCH",
       "the idle clock does not run while a candidate is being judged")

f.judge_busy = False
CLOCK[0] += ST.REPLAN_IDLE_S - 1
f.feed("tick")
expect(f.state == "S4B_WATCH",
       "...and it restarts from the moment judging ended, not from before it")
CLOCK[0] += 2
f.feed("tick")
expect(f.state == "S3_SCAN", "...then re-plans normally once the angle is quiet")

# The PERIOD timer is structural -- the room may have changed -- so it is not
# postponed. But it must not fire mid-judgement either, for the same reason.
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:watch the desk",
        "arrived:S3_SCAN", "arrived:S4B_WATCH", "planned"], "")
f.judge_busy = True
CLOCK[0] += ST.REPLAN_PERIOD_S + 1
f.feed("tick")
expect(f.state == "S4B_WATCH",
       "the 5-minute timer also waits for the verdict")


print("\n--- S8 gives up on its own ---")
# S8's exit was STOP-only, which assumed a reader who could press it. A
# participant cannot: S8 is entered from a failed plan, an unusable transcript,
# a dead camera, and the CoreS3 shows them only STOP without saying what for.
# 16 s is four passes of the 3.97 s loop -- and `sfx_every = 4` means the robot
# cries once, sways four times, and stops, instead of crying three times.
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:watch the plant"], "")
f.feed("plan_failed:503")
expect(f.state == "S7_ERROR", "a failed plan lands in S8")
CLOCK[0] += ST.S8_RECOVER_S - 1
f.feed("tick")
expect(f.state == "S7_ERROR", f"still drooping just under {ST.S8_RECOVER_S:.0f}s")
CLOCK[0] += 2
out = f.feed("tick")
expect(f.state == "S0_IDLE", f"past {ST.S8_RECOVER_S:.0f}s -> back to idle")
expect(not f.plan_pending,
       "anything still in flight is abandoned -- a late transcript must not "
       "resurrect a turn the person watched it end")

print("\n--- an abandoned visit goes back to idle (VISIT_MAX_S) ---")
# A task belongs to the person who asked for it, and at a stand that person
# left several visitors ago. `ptt_down` is ignored in any state but S0_IDLE, so
# a robot still watching an abandoned request is a robot nobody else can start
# anything with -- a busy table is where it looks most alive and is least
# reachable.
# ISOLATE THE TIMER UNDER TEST. REPLAN_IDLE_S re-sweeps after 60 s of nothing,
# so two minutes of quiet moves the robot for the OTHER reason and this section
# would be reading a state it did not cause. Holding the angle productive would
# also restart the visit clock -- a finding is somebody being served -- so the
# only honest isolation is to switch the other one off.
_VIS, _IDL = ST.VISIT_MAX_S, ST.REPLAN_IDLE_S
ST.VISIT_MAX_S, ST.REPLAN_IDLE_S = 120.0, 0.0

f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:watch the desk",
        "arrived:S3_SCAN", "arrived:S4B_WATCH", "planned"], "")
CLOCK[0] += ST.VISIT_MAX_S - 5
f.feed("tick")
expect(f.state == "S4B_WATCH", "just under -- still watching")
CLOCK[0] += 10
out = f.feed("tick")
expect(f.state == "S0_IDLE", "abandoned -> idle, so the next person can wake it")
expect(f.transcript is None, "...and the request goes with it")
expect(("idle", True) in out,
       "...through the same channel STOP uses, so perception stops too")

# ANY interaction restarts it. This must end an abandoned conversation, never
# one in progress -- a visitor reading a report has not abandoned anything.
for ev, label in [("ok", "an OK"), ("tap", "a correction"),
                  ("finding:cup", "a finding being delivered")]:
    f = flow()
    run(f, ["ptt_down", "ptt_up", "transcript:watch the desk",
            "arrived:S3_SCAN", "arrived:S4B_WATCH", "planned"], "")
    CLOCK[0] += ST.VISIT_MAX_S - 5
    run(f, [ev, "arrived:S4B_WATCH"], "")
    CLOCK[0] += ST.VISIT_MAX_S - 5
    f.feed("tick")
    expect(f.state != "S0_IDLE", f"{label} restarts the visit clock")

# A new request from the tablet is a NEW visitor, and starts a fresh visit.
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:watch the desk",
        "arrived:S3_SCAN", "arrived:S4B_WATCH", "planned"], "")
CLOCK[0] += ST.VISIT_MAX_S - 5
run(f, ["typed:tell me when someone is holding a phone",
        "arrived:S3_SCAN", "arrived:S4B_WATCH", "planned"], "")
CLOCK[0] += ST.VISIT_MAX_S - 5
f.feed("tick")
expect(f.state != "S0_IDLE", "a new request is a new visit, not the old one")

ST.VISIT_MAX_S = 0.0
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:watch the desk",
        "arrived:S3_SCAN", "arrived:S4B_WATCH", "planned"], "")
CLOCK[0] += 36000
f.feed("tick")
expect(f.state == "S4B_WATCH",
       "VISIT_MAX_S=0 -> the study never abandons a participant's task")
ST.VISIT_MAX_S, ST.REPLAN_IDLE_S = _VIS, _IDL



print("\n--- pressing OK leaves the reporting states via the nod ---")
# THE ROUTE THAT BROKE THE CANDIDATE GATE. The loop released the gate on
# `S5B_BECKON -> S4B_WATCH`, which is what happens when a finding is IGNORED
# for 30 s. Acknowledging it -- the normal case -- goes through S2_ACKNOWLEDGE,
# so `last_state` at S4B_WATCH was S2 and the release never ran: one report per
# run, and being a good visitor was what broke it.
#
# Recorded here, in the flow's own tests, because the route is the flow's fact.
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:watch the desk",
        "arrived:S3_SCAN", "arrived:S4B_WATCH", "planned"], "")
run(f, ["finding:cup", "arrived:S5A_FOUND", "arrived:S5B_BECKON"], "")
expect(f.state == "S5B_BECKON", "reporting")
out = f.feed("ok")
expect(f.state == "S2_ACKNOWLEDGE",
       "OK nods FIRST -- it does not go straight back to watching")
expect(("ack_then", "S4B_WATCH") in out, "...and lands on watching after the nod")
run(f, ["arrived:S4B_WATCH"], "")
expect(f.state == "S4B_WATCH", "so the report ended via S2, not via S5B")

# The ignored route, for contrast: this one DID release the gate, which is why
# the bug only showed up for visitors who answered.
f = flow()
run(f, ["ptt_down", "ptt_up", "transcript:watch the desk",
        "arrived:S3_SCAN", "arrived:S4B_WATCH", "planned"], "")
run(f, ["finding:cup", "arrived:S5A_FOUND", "arrived:S5B_BECKON"], "")
CLOCK[0] += ST.S7_TIMEOUT_S + 1 if hasattr(ST, "S7_TIMEOUT_S") else 31
f.feed("tick")
expect(f.state != "S5B_BECKON", "an ignored finding also leaves the report")


# THE SUMMARY GOES LAST, and it did not.
#
# It sat in the middle of the file, so everything appended after it -- the
# judge-in-flight section, S8 giving up, and the abandoned visit -- ran, filled
# `fails`, and was never looked at again. Under pytest the module imports
# cleanly and the run is green whatever those sections found. Three sections of
# coverage that existed, executed, and could not fail.
print("\n" + "=" * 60)
print(f"{len(fails)} failure(s)" if fails else "all paths pass")
if __name__ == "__main__":
    sys.exit(1 if fails else 0)
if fails:
    raise AssertionError("; ".join(fails))

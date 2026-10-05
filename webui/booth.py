"""booth.py — the tablet the participant watches, in the lab.

WHAT THIS IS FOR. The robot speaks the interaction: motion, light, sound and a
face. None of that says WHICH WAY IT IS LOOKING with any precision, and that is
the one question a participant has from the moment the sweep starts. This page
answers it, and nothing else about the robot changes to make it possible.

    the robot   motion, light, sound, a face, and the request itself
    this page   which way it is looking, and the report afterwards

THE REQUEST IS ON THIS PAGE AGAIN, for the showcase. In the study it was spoken
-- holding the button on the robot, in the participant's own words -- and a menu
would have decided for them the one thing the study was asking them to decide.
A stranger at a stand is not being asked anything, has ninety seconds, no
briefing and a loud room, so the menu is back and the button is gone: walking up
presses it for them. Speech still wins when there is any.
What the page shows during that moment is what Whisper HEARD -- large, as it
lands -- so a misread is visible while it can still just be said again, instead
of being discovered three states later when the head turns the wrong way.

THE SCREENS. Fewer than there are states, on purpose -- the strip along the top
carries the state, and a page swap is reserved for a change in what the
participant can DO:

    sleep    a sleeping face and one line. Nothing is asked of the tablet here;
             the way in is A HAND HELD IN FRONT OF THE SENSOR -- the board's
             ToF presses the button on the visitor's behalf -- and the page
             says so. Walking up was the way in before, and the sensor could
             not tell an arrival from somebody passing behind them. It said
             "hold the button" for the study build, where there was one and the
             participant had been shown it. A stranger at a stand has not, and
             telling them to press something they cannot find is worse than
             saying nothing.
    listen   the sentence, as Whisper returns it. Rejected text is shown too,
             marked -- the robot is about to perform not having understood, and
             a participant who can read what it thought it heard understands
             that performance instead of being puzzled by it.
    room     scanning AND watching, which used to be two -- and the nod between
             them, which is 1.7 s and does not deserve a page of its own. Five
             stations fill in as the head captures them, the planner's boxes and
             a red frame arrive with the plan, and the red frame MOVES when the
             head is corrected. The watched direction is the LIVE camera, not
             the photograph taken during the sweep; tapping it fills the screen
             with the rule beside it, tapping again puts it back. The sixth cell
             of the 3x2 grid holds the rule itself.
    notice   the same prompt as the robot's own screen, either of which takes
             the OK.
    report   AFTER OK THE TABLET STOPS FOLLOWING THE ROBOT. The robot goes
             straight back to watching -- right, it has a job -- but the
             participant is owed the report they just asked for, and the
             storyboard takes another 6-45 s to narrate it. Following the robot
             back to the room grid threw that away and made OK look like it had
             cancelled something. The page waits here, on its own, until the
             story count rises, then shows that one story.
    wall     every story of the session, reachable from any idle moment.

Polling, not sockets: 200 ms on a LAN is imperceptible and the codebase already
polls. The study page's 1200 ms was too slow here -- the prompt has to land with
the chirp, and 1.2 s of lag reads as two separate machines.
"""
from __future__ import annotations

import json
import time

# The relation vocabulary, WRITTEN OUT. English on purpose -- these are the
# system's own terms and an onlooker reading over a visitor's shoulder is
# usually the person who wants to see them.
#
# Not abbreviated, which is the change from the first version. `appr` and
# `prox` save space the cell does not need and cost the only thing the cell is
# for: one chip of a rule is the whole of what a visitor learns about how this
# machine decides, and `appr` teaches them nothing. The developer page may
# shorten; this one may not.
#
# The IDS are the contract -- they are what the planner compiles to and what
# `truth` is keyed by -- so a test holds them against the relation catalogue.
# The wording here is free to read however it reads best.
REL_NAMES = {
    1: "gazing at", 2: "joint attention", 3: "eye contact", 4: "pointing",
    5: "proximity", 6: "F-formation", 7: "approaching", 8: "leaning in",
    9: "hands on", 10: "gathering", 11: "taking turns",
}

# THE ROBOT'S OWN FACES, copied from the firmware's uiFace(). Deliberately the
# same characters: the strip on the tablet and the face on the robot are then
# one vocabulary rather than two, and a visitor who looks from one to the other
# sees the same thing twice instead of having to learn a second code.
#
# S4 has no face on the robot -- planning is the one screen whose job is to send
# the eye to the room instead of the screen -- so the strip shows a looking mark
# rather than inventing an expression the robot does not wear.
FACES = [
    ("S0_IDLE",     "-_-",    "asleep"),
    ("S1_ATTEND",   "._.",    "listening"),
    ("S2_ACKNOWLEDGE",      "^o^",    "got it"),
    ("S3_SCAN",     "\u30fb\u30fb\u30fb",    "looking"),
    ("S4B_WATCH",   "o_o",    "watching"),
    ("S6_CORRECT", ">_<",    "not that"),
    ("S5B_BECKON",         "\\^o^/", "calling"),
]

# states that light the same lamp
_FACE_OF = {"S4A_SETTLE": "S4B_WATCH", "S5A_FOUND": "S5B_BECKON", "S7_ERROR": "S6_CORRECT"}


def face_key(state):
    """Which lamp in the strip is lit for this state."""
    state = _FACE_OF.get(state, state)
    return state if any(k == state for k, _f, _l in FACES) else "S0_IDLE"


# --------------------------------------------------------------------------- #
def booth_state(STATE, feed_records, sweep_meta):
    """Everything the tablet needs, in one poll.

    Assembled here rather than in the page so the page has no logic to get
    wrong, and so `phase` is decided ONCE -- the tablet and the robot must never
    disagree about which moment this is.
    """
    states = STATE.get("states") or []
    now = ""
    for s in states:
        if s.get("now"):
            now = s.get("name") or ""
            break
    now = now or STATE.get("flow_state") or ""

    if now in ("S5A_FOUND", "S5B_BECKON"):
        phase = "notice"
    elif (now in ("S3_SCAN", "S4A_SETTLE", "S4B_WATCH", "S6_CORRECT")
            or STATE.get("plan_pending")):
        # SCANNING AND WATCHING ARE ONE SCREEN. They were two, and the watching
        # one said "tracking..." over an empty page, which tells a visitor
        # nothing they cannot already see -- the robot is right there, holding
        # still. The five frames answer the only question worth asking, WHICH WAY
        # IS IT LOOKING, and they answer it continuously: the grid fills in as
        # the head captures it, the red frame lands when the plan does, and it
        # MOVES when the head is corrected. Which state it is in is a glance at
        # the strip.
        phase = "room"
    elif now == "S2_ACKNOWLEDGE":
        # THE NOD DOES NOT GET A SCREEN. It is 1.7 s, and a page that appears and
        # vanishes inside two seconds is a flash, not information. It also
        # happens in two different places -- after a choice, and after OK -- so
        # any one screen would be wrong in one of them. The strip shows ^o^ and
        # the page stays where the visitor's attention already is: about to
        # sweep, or reading the report they just acknowledged.
        phase = "room"
    elif now == "S0_IDLE" or not now:
        # ASLEEP IS A FACE, NOT A MENU. A stand with a list of options on it is
        # a kiosk; a stand with something sleeping on it is a thing you want to
        # wake. It also gives the head tap a consequence on BOTH screens at
        # once, which is what teaches the gesture -- and the gesture is how
        # everything else here starts.
        phase = "sleep"
    else:
        # S1_ATTEND AND S7_ERROR LAND HERE, and they want the same screen: the
        # sentence. While the button is held there is nothing yet and the page
        # says it is listening; when Whisper returns, the words appear; and if
        # they were rejected, the marked text is exactly what explains the
        # performance the robot is about to give.
        phase = "listen"

    # WHICH FRAME IS RED: the station nearest where it is ACTUALLY AIMED, not
    # the one the sweep scored highest. They agree until the visitor taps the
    # head -- and that tap is the whole point of the Correct beat, so the red
    # frame has to move with it or the gesture has no answer on the tablet.
    # Before an aim exists (mid-sweep), the sweep's own pick stands in.
    shots, chosen = [], None
    if sweep_meta:
        aim = STATE.get("aimed_pan")
        pans = [sh.get("pan") for sh in (sweep_meta.get("shots") or [])
                if sh.get("pan") is not None]
        if aim is not None and pans:
            chosen = min(pans, key=lambda p: abs(p - float(aim)))
        else:
            chosen = sweep_meta.get("richest_pan")
        for sh in sweep_meta.get("shots") or []:
            shots.append({
                "pan": sh.get("pan"),
                "file": sh.get("file"),
                "dir": sweep_meta.get("dir") or "",
                "n": len(sh.get("dets") or []),
                "focus": sum(1 for d in (sh.get("dets") or [])
                             if d.get("tier") == "focus"),
            })

    # The judge's sentence is written BEFORE S7 plays, so it is already here at
    # the moment the visitor is asked to press OK. The strip takes another
    # 6-45 s; showing this first means OK is never answered by a blank screen.
    return {
        "phase": phase,
        "state": now,
        "faces": FACES,
        "face": face_key(now),
        # HEARD vs REQUEST. The first is the microphone's last word and belongs
        # only to the listening screen; the second is what the flow accepted and
        # is what every later screen echoes back.
        "heard": STATE.get("heard") or "",
        "heard_ok": bool(STATE.get("heard_ok", True)),
        "request": STATE.get("request") or "",
        "shots": shots,
        "chosen_pan": chosen,
        # THE WATCH-SPEC, in the developer page's own vocabulary. The grid has
        # five stations in six cells, and the empty one is where "what would
        # make it call you" belongs: a visitor who can read hands-on + bag knows
        # what to DO, and an onlooker can see the system is running a rule
        # rather than a guess. Same fields the LIVE panel renders from -- see
        # webui.server.build_status -- so the two cannot drift.
        "watch": [{"label": r.get("label") or "",
                   "on": r.get("onobj") or "",
                   "all": r.get("all") or [], "any": r.get("any") or [],
                   "not": r.get("not") or [], "then": r.get("then") or [],
                   "sat": bool(r.get("sat")), "cool": bool(r.get("cool")),
                   # WHETHER IT IS ON THAT OBJECT RIGHT NOW, which is not the
                   # same as the relation being true: `hands on` is true of a
                   # hand on anything. Without this the object chip is a label,
                   # and a visitor cannot tell a rule about to fire from one
                   # landing on the wrong thing.
                   "on_now": bool(r.get("on_now")),
                   "truth": r.get("on") or {}}
                  for r in (STATE.get("status") or [])],
        "rel_names": REL_NAMES,
        # Whether anyone is mid-choice, for standing_prompt.py. Short-lived:
        # each tap refreshes it, and a visitor who wandered off mid-menu stops
        # holding the companion back a few seconds later.
        "choosing": bool(time.time() - float(STATE.get("choosing_at") or 0)
                         < CHOOSING_HOLD_S),
        # WHICH PRESET THE HEAD TAPS ARE ON, and whether any tap has happened.
        # `pick_at` None means untouched, which is a different screen from
        # "resting on the first one".
        "pick_i": int(STATE.get("pick_i") or 0),
        "pick_on": bool(STATE.get("pick_at")),
        "describe": STATE.get("describe") or "",
        "noticed": STATE.get("noticed_n") or 0,
        # THE WHOLE WALL, newest first, and a COUNT the page can compare
        # against. After OK the tablet stops following the robot and waits for a
        # story to appear -- it cannot know one has landed without a number that
        # changes. The robot, meanwhile, has already gone back to watching; the
        # two are doing different things on purpose from that moment.
        "stories": feed_records[-40:][::-1],
        "n_stories": len(feed_records),
        "seen": (STATE.get("seen") or [])[:8],
    }


# WHAT THE MENU OFFERS. Edited here and nowhere else.
#
# CONCRETE AND HIGH-FREQUENCY, and about the AUDIENCE -- the audience is the
# thing guaranteed to be present and moving.
#
# POINTING WAS HERE AND IS NOT ANY MORE. It needs three things to line up at
# once -- a visible shoulder/elbow/wrist, a ray in the IMAGE PLANE that clears
# the extension test, and a detected box within tolerance -- and the one
# everybody does naturally, aiming at the robot, cannot work at all, because an
# arm pointed at the camera foreshortens to a point and hits nothing. Loosening
# the extension from 140 to 110 deg was not enough. It stays in the vocabulary
# and out of the menu: a preset that mostly does not fire teaches a visitor
# that the robot mostly does not work.
#
# `gathering` replaces it because it is the opposite: it is about people, needs
# no object detected and no object gate at all (arity `none`, so the focus gate
# passes it straight through), and the thing it watches for -- the number of
# people co-present changing -- is what a crowded stand does continuously
# without anyone being asked. A vague request gives the planner
# nothing to compile into a watch-spec and it returns garbage or nothing, which
# routes to the one state a showcase must not perform. The last line is the
# deliberate exception: it is what a visitor reaches for when none of the
# others is what they meant, and it is worth watching how often the plan it
# produces is any good.
CHOOSING_HOLD_S = 15.0   # a tap holds the companion off this long

PRESETS = [
    "tell me when someone drinks a coffee",
    "tell me when more people gather around",
    "tell me when someone is holding a phone",
    "tell me if there's something interesting",
]

PAGE = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,user-scalable=no,viewport-fit=cover">
<meta name=apple-mobile-web-app-capable content=yes>
<title>NoticeBot</title><style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:#141414;color:#f2f0ea;display:flex;flex-direction:column;
  font-family:-apple-system,"SF Pro Text",Helvetica,Arial,sans-serif;
  height:100vh;overflow:hidden;user-select:none}

/* THE STATE STRIP. Small, at the top, always there. A state change is worth a
   glance, not a screen -- swapping the whole page when the robot lifts its head
   took the two task buttons away at the moment the visitor needed them. */
/* Faces centred, the way into the day's stories on the right. Same height as
   a face chip: it is a way out, not an offer, and it must not compete with the
   two things a visitor is actually being asked to choose between. */
#top{display:flex;align-items:center;flex:none;padding:14px 20px 0;gap:8px}
#strip{display:flex;gap:8px;justify-content:center;flex:1}
/* ONE rule for #app, not two. It carried height:100% AND flex:1 at the same
   time, so with the strip above it the page ran past the viewport and the
   bottom -- the grid, the buttons -- was clipped away under overflow:hidden. */
#app{flex:1;min-height:0;display:flex;flex-direction:column;
  padding:16px 28px 28px;gap:14px}
.f{font:14px ui-monospace,monospace;color:#3f3f3a;background:#1a1a17;
  border-radius:9px;padding:5px 10px;letter-spacing:.06em;
  transition:color .18s,background .18s}
.f.on{color:#141414;background:#cfe33a;font-weight:700}
.f b{display:block;font-weight:400;font-size:9px;letter-spacing:0;opacity:.55;
  margin-top:1px}
h1{font-weight:600;font-size:clamp(26px,3.4vh,40px);line-height:1.3;margin:0;letter-spacing:.02em}
.sub{font-size:clamp(15px,1.9vh,21px);color:#8a867d;margin-top:8px}
.grow{flex:1;min-height:0;display:flex;flex-direction:column;gap:18px}

/* NO `font:` SHORTHAND ON THIS PAGE, and it is not a style preference.
   `font: 700 40px/1.3 inherit` is INVALID -- `inherit` is a CSS-wide keyword,
   legal only as an entire value, never as the family slot -- so the browser
   drops the whole declaration and the element renders at the inherited default.
   Every size on this page was being thrown away that way, which is why the
   choice buttons stayed at 16px however large the number was set. Longhands
   only; the family comes down from body by inheritance anyway.

   THE SENTENCE IS THE WHOLE SCREEN. It is the only text in the study the
   participant wrote themselves, and the one thing they must be able to check
   before the robot acts on it -- so it is set large enough to read at a glance
   from where they are sitting, and centred with nothing beside it. clamp()
   keeps it right on an iPad mini and a 12.9 alike without a media query.
   NOT a touch target: nothing on this screen is tappable, because the way to
   correct a misread is to say it again, or to choose from the menu. */
.heard{background:#1d1d1a;border:3px solid #33332e;border-radius:28px;
  padding:28px;color:#f2f0ea;text-align:center;
  font-weight:800;font-size:clamp(34px,min(6.4vw,8vh),86px);line-height:1.24;
  letter-spacing:.01em;
  flex:1;display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:18px}
/* REJECTED TEXT IS SHOWN, NOT HIDDEN. The robot is about to perform not having
   understood; a participant who can read what it thought it heard reads that
   performance correctly instead of wondering what went wrong. */
.heard.no{border-color:#5a3230;color:#c88e88}
.heard small{font-weight:400;font-size:clamp(15px,2vw,26px);color:#8a867d;
  letter-spacing:.04em}
.heard.no small{color:#a2625c}
/* WAITING FOR THE FIRST WORD. Three dots that breathe, so an open microphone
   with nothing said into it yet still looks like a machine that is receiving.
   Only reached when somebody HAS spoken and it came back unusable -- silence
   shows the menu instead. */
.lst{font-family:ui-monospace,monospace;color:#6f6c65;
  font-size:clamp(30px,5vw,64px);letter-spacing:.3em}
.lst i{font-style:normal;animation:blink 1.4s ease-in-out infinite}
.lst i:nth-child(2){animation-delay:.22s}
.lst i:nth-child(3){animation-delay:.44s}
@keyframes blink{0%,100%{opacity:.2}50%{opacity:1}}
.card:active small{color:#3a3a20}

/* THE MENU, shown while it is listening. A stand is loud and half the visitors
   are speaking a second language, so asking for a spoken sentence and then
   performing not-having-understood is a worse first impression than a list.
   Speech still works: anything said lands first and the loop takes it. */
.picks{flex:1;display:flex;flex-direction:column;gap:12px;min-height:0;
  overflow-y:auto;-webkit-overflow-scrolling:touch}
.pick{background:#1d1d1a;border:3px solid #33332e;border-radius:20px;
  padding:clamp(14px,2.2vh,26px) clamp(16px,2.5vw,30px);color:#e8e6e0;
  font-size:clamp(18px,2.6vh,30px);line-height:1.25;cursor:pointer;
  display:flex;align-items:center;gap:16px}
.pick:active{border-color:#8a867d}
/* CHOSEN, NOT SUBMITTED -- the difference is the whole reason this screen
   exists. A tap that fired immediately would let them pick exactly one thing,
   and the interesting requests are two things at once. */
.pick.on{border-color:#cfe33a;background:#232616}
/* THE ONES NOT CHOSEN STAY LEGIBLE. Hiding them would make the list feel like
   a slot machine; dimming says "these are still here, keep tapping". */
.pick.dim{opacity:.38}
.tick{flex:none;width:clamp(26px,3.4vh,38px);height:clamp(26px,3.4vh,38px);
  border-radius:9px;border:2px solid #4a4a44;display:flex;align-items:center;
  justify-content:center;font-size:clamp(16px,2.2vh,24px);color:#141414}
.pick.on .tick{background:#cfe33a;border-color:#cfe33a}
.go{background:#cfe33a;color:#141414;border:0;border-radius:16px;
  padding:20px 0;width:100%;font-weight:700;font-size:23px;flex:none}
.go[disabled]{background:#262623;color:#5e5b54}
.go:active{background:#e6f96a}

.grid{flex:1;display:grid;grid-template-columns:repeat(3,1fr);gap:12px;min-height:0}
.cell{position:relative;background:#1d1d1a;border:3px solid #2a2a27;
  border-radius:14px;overflow:hidden;display:flex;align-items:center;
  justify-content:center}
.cell img{width:100%;height:100%;object-fit:cover;display:block}
.cell.on{border-color:#e0554a;box-shadow:0 0 0 3px rgba(224,85,74,.35)}
.cell .tag{position:absolute;left:8px;bottom:6px;font:12px ui-monospace,monospace;
  color:#cfe33a;background:rgba(20,20,20,.72);padding:2px 7px;border-radius:7px}
.cell.wait{border-style:dashed;color:#54544c;font:22px ui-monospace,monospace}
.cell.live{border-color:#e0554a}          /* the frame; the picture is #live */

#live{position:fixed;display:none;object-fit:cover;z-index:5;
  border:3px solid #e0554a;border-radius:14px;
  box-shadow:0 0 0 3px rgba(224,85,74,.35);
  transition:left .22s,top .22s,width .22s,height .22s}
#live.big{border-radius:18px;box-shadow:0 0 0 4px rgba(224,85,74,.3)}
/* EXPANDED: everything except the picture and the rule goes quiet. The rule is
   NOT redrawn beside the live view -- it is already in the sixth cell, and the
   expanded picture is sized to stop short of it, so the one copy stays where
   the visitor last saw it. */
#app.dim > *{opacity:.14;transition:opacity .22s}
#app.dim .grid{opacity:1}
#app.dim .cell{opacity:.10;transition:opacity .22s}
#app.dim .cell.spec{opacity:1}
#app.dim .bar{display:none}
.hint{position:fixed;z-index:6;font-size:clamp(13px,1.5vw,19px);color:#6f6c65;
  font-family:ui-monospace,monospace;display:none}
.hint.on{display:block}

/* THE WAIT AFTER OK. 6-45 s with one small line of text on it reads as a
   machine that has stopped. The bar is deliberately NOT a real measure of
   anything -- nothing here knows how long the narration will take, and a bar
   that claimed to would be lying -- it is a sign of life, which is the only
   honest thing to show. The face is doing the same job the robot's own face
   does: it is what makes waiting feel like being waited WITH. */
/* ASLEEP. A stand with a list of options on it is a kiosk; a stand with
   something sleeping on it is a thing you want to wake -- and waking it is how
   everything else here starts, so the page has to ask for that and nothing
   else. Same face the robot's own screen wears in idle. */
.sleep{flex:1;display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:30px}
.sface{font-size:clamp(64px,12vw,180px);font-family:ui-monospace,monospace;
  color:#4a4a44;position:relative;animation:breathe 4.4s ease-in-out infinite}
.sface i{position:absolute;left:104%;top:-.15em;font-size:.34em;
  font-style:normal;color:#3a3a35;letter-spacing:.24em;
  animation:zzz 4.4s ease-in-out infinite}
@keyframes breathe{0%,100%{opacity:.55}50%{opacity:1}}
@keyframes zzz{0%,100%{opacity:.15;transform:translateY(4px)}
               50%{opacity:.9;transform:translateY(-6px)}}
.stap{font-size:clamp(20px,2.6vw,34px);color:#8a867d;text-align:center;
  line-height:1.5}

.waitbox{flex:1;display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:22px}
.wface{font-size:clamp(28px,4.5vw,60px);font-family:ui-monospace,monospace;
  color:#cfe33a;animation:bob 2.2s ease-in-out infinite}
@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-9px)}}
.wtxt{font-size:clamp(19px,2.4vw,30px);color:#8a867d}
.wbar{width:min(62%,520px);height:12px;border-radius:99px;background:#22221e;
  overflow:hidden}
.wbar i{display:block;height:100%;width:38%;border-radius:99px;
  background:linear-gradient(90deg,#cfe33a,#88e4ea);
  animation:slide 1.7s cubic-bezier(.6,0,.4,1) infinite}
@keyframes slide{0%{transform:translateX(-110%)}100%{transform:translateX(280%)}}

/* THE SIXTH CELL. Five stations in a 3x2 grid leave one empty, and what belongs
   there is the rule -- a visitor who can read hands-on + bag knows what to DO,
   and an onlooker can see the system is running a condition rather than
   guessing. Same fields and same words as the developer page's LIVE panel. */
.spec{border-style:solid;border-color:#2a2a27;background:#161614;
  flex-direction:column;justify-content:center;gap:9px;padding:12px;
  font-family:ui-monospace,monospace}
.spec .lb{font-size:clamp(12px,1.25vw,17px);color:#6f6c65;letter-spacing:.08em}
.spec .row{display:flex;flex-wrap:wrap;gap:5px;align-items:center;
  justify-content:center}
/* ONE LINE PER RULE, stacked, and scrollable rather than clipped -- a fourth
   rule that silently falls off the bottom is the same lie as showing one. */
.rules{display:flex;flex-direction:column;gap:7px;width:100%;
  overflow-y:auto;-webkit-overflow-scrolling:touch;min-height:0}
.rule{display:flex;flex-wrap:wrap;gap:5px;align-items:center;
  justify-content:center;padding:5px 4px;border-radius:9px}
/* The one that is true right now, against the others. The cell border already
   went red; this says WHICH of them did it, which with three rules up is the
   only thing the border cannot tell you. */
.rule.sat{background:#2a1a1a}
/* Shrink with the count instead of letting the last one fall off. */
.rules.n2 .rel,.rules.n2 .obj{font-size:clamp(11px,1.15vw,16px);padding:4px 8px}
.rules.n3 .rel,.rules.n3 .obj{font-size:clamp(10px,1.0vw,14px);padding:3px 7px}
.rules.n4 .rel,.rules.n4 .obj{font-size:clamp(9px,0.9vw,13px);padding:3px 6px}
.rules.n3 .op,.rules.n4 .op{font-size:clamp(9px,0.85vw,12px)}
/* Sentence face, not monospace, and the words wrap rather than being cut: the
   chips read as English now, and "joint attention" ellipsised to "joint att..."
   would undo the whole reason for writing them out. */
.rel{font-family:-apple-system,"SF Pro Text",Helvetica,Arial,sans-serif;
  font-size:clamp(12px,1.35vw,19px);padding:5px 11px;border-radius:10px;
  border:1px solid #3a3a35;color:#7c796f;white-space:nowrap}
.rel.t{background:#88e4ea;border-color:#88e4ea;color:#101010;font-weight:700}
.op{font-size:clamp(11px,1.1vw,15px);color:#55524b}
.obj{font-size:clamp(12px,1.3vw,18px);padding:4px 9px;border-radius:10px;
  background:#1c1c19;border:1px solid #3a3a35;color:#cfe33a}
/* Lit when the relation is landing on THIS object, not merely when the rule
   names it. Same fill as a true relation chip, so one glance reads the whole
   row: relation true, and true ABOUT the right thing. */
.obj.t{background:#cfe33a;border-color:#cfe33a;color:#101010;font-weight:700}
.spec.sat{border-color:#d95b5b;background:#201616}

/* THE PROMPT ROW. Slim and at the foot of every screen, including the sleep
   one -- the moment you most want to retype the standing prompt is before
   anybody has walked up, and a box that only exists once the robot is already
   watching is a box you cannot reach when you need it. */
#ctxbar{flex:none;display:flex;align-items:center;gap:10px;
  padding:10px 20px calc(10px + env(safe-area-inset-bottom));
  border-top:1px solid #26262333;background:#121210}
#ctx{flex:1;min-width:0;background:#1b1b18;color:#f2f0ea;
  border:1px solid #33332e;border-radius:10px;padding:11px 14px;
  font-family:-apple-system,"SF Pro Text",Helvetica,Arial,sans-serif;
  font-size:16px;   /* 16px EXACTLY: iOS Safari zooms the whole page in on any
                       focused input below 16px, and on a wall-mounted tablet
                       nothing zooms it back out again. */
  user-select:text;-webkit-user-select:text}
#ctx:focus{outline:none;border-color:#cfe33a}
#ctx::placeholder{color:#5e5b54}
#ctxok{flex:none;font-size:14px;color:#cfe33a;opacity:0;transition:opacity .2s;
  font-family:ui-monospace,monospace}
#ctxok.on{opacity:1}

.bar{font-size:15px;color:#8a867d;display:flex;gap:14px;align-items:center}
.dot{width:11px;height:11px;border-radius:50%;background:#cfe33a;
  animation:p 1.4s ease-in-out infinite}
@keyframes p{0%,100%{opacity:.25}50%{opacity:1}}

/* ABOVE EVERYTHING, ALWAYS. The live view is z-index 5 and can be expanded to
   most of the screen; the one thing that must never be behind it is the robot
   asking to be answered. */
#veil{position:fixed;inset:0;background:rgba(10,10,10,.9);display:none;
  z-index:20;align-items:center;justify-content:center;padding:34px}
#veil.on{display:flex}
.pop{background:#faf9f6;color:#141414;border-radius:26px;padding:36px;
  max-width:640px;width:100%;text-align:center}
.pop h2{font-weight:700;font-size:30px;line-height:1.3;margin:0 0 14px}
.pop p{font-size:19px;line-height:1.6;color:#3a3a35;margin:0 0 26px}
.ok{background:#141414;color:#faf9f6;border:0;border-radius:16px;
  padding:20px 0;width:100%;font-weight:700;font-size:23px}
.ok:active{background:#cfe33a;color:#141414}

/* A STORY IS THE STRIP ITSELF. The storyboard composites its panels into one
   wide jpg -- that IS the shape of the finding, several moments in a row -- so
   it is shown at full height and scrolled sideways rather than squeezed into a
   thumbnail. The sentence sits under the picture, where a caption goes. */
.story{background:#1d1d1a;border-radius:18px;padding:14px;margin-bottom:14px}
.pan{overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;
  border-radius:12px;background:#101010;scrollbar-width:none}
.pan::-webkit-scrollbar{display:none}
.pan img{height:clamp(150px,26vh,340px);width:auto;max-width:none;display:block}
.story p{margin:14px 4px 2px;font-size:clamp(19px,2.4vw,32px);line-height:1.4;
  color:#e6e3da}
.story span{display:block;margin:6px 4px 0;color:#7a776f;
  font:13px ui-monospace,monospace}
.swipe{font-size:12px;color:#54544c;margin:6px 4px 0;
  font-family:ui-monospace,monospace}

.wallbtn{flex:none;cursor:pointer}
.wallbtn:active{color:#141414;background:#cfe33a}
#stories{overflow-y:auto;flex:1;-webkit-overflow-scrolling:touch}
</style></head><body>
<!-- THE LIVE VIEW LIVES OUTSIDE #app AND IS NEVER RE-CREATED.
     An <img> on an MJPEG stream holds an open connection; putting it inside the
     innerHTML that render() rewrites would tear that connection down and open a
     new one every poll -- 5 times a second -- which is a black flicker and a new
     TCP connection each time. It is positioned OVER the cell instead, by
     rectangle, so the grid can be rewritten as often as it likes. -->
<img id=live onpointerdown="zoom()">
<div id=top><div id=strip></div>
  <div class="f wallbtn" id=wb onpointerdown="wall()"></div></div>
<div id=app></div>
<!-- THE PROMPT ROW LIVES OUT HERE, for the same reason #live does. render()
     rewrites the whole of #app on every poll -- five times a second -- and an
     <input> inside that innerHTML is destroyed and rebuilt between keystrokes:
     the caret jumps, the text vanishes, and it looks like the tablet is broken
     rather than like a bug. Outside #app it is never touched. -->
<div id=ctxbar>
  <input id=ctx autocomplete=off autocapitalize=sentences spellcheck=false
         placeholder="tell it what to watch for, then press return">
  <span id=ctxok>sent</span>
</div>
<div class=hint id=hint>tap again to go back</div>
<div id=veil><div class=pop>
  <h2 id=pt>I noticed something</h2><p id=pd></p>
  <button class=ok onpointerdown="ok()">OK</button>
</div></div>
<script>
let S={phase:'sleep'},sent=0;

// THE TABLET STOPS FOLLOWING THE ROBOT AFTER OK. The robot goes straight back
// to watching -- that is right, it has a job -- but the visitor is owed the
// report they just asked for, and it takes another 6-45 s to write. Sending the
// tablet back to the room grid with it threw that away and looked like the OK
// had cancelled something. MODE overrides `phase` while it is set; null means
// follow the robot again.
// WHAT IS TICKED LIVES OUT HERE, like #live and the prompt row, because render()
// rewrites the whole of #app five times a second. A tick kept in the DOM would
// be erased between one tap and the next; kept here, the cards are rebuilt
// from it on every poll and the selection is the thing that persists.
const PRESETS = __PRESETS__;
let PICKED = new Set();
// WHAT WAS SUBMITTED, while the flow catches up. The tablet polls at 5 Hz and
// the robot has a nod and a sweep to start, so there is a gap between the tap
// and the screen changing for the real reason. This fills it.
let SENT = null;

function pick(i){
  PICKED.has(i) ? PICKED.delete(i) : PICKED.add(i);
  render();
  // Tell the loop somebody is here and deciding, so the standing prompt does
  // not answer on their behalf while they are halfway through. Fire and
  // forget: if it fails they lose nothing but the grace period.
  fetch('/booth/choosing',{method:'POST'}).catch(()=>{});
}

async function sendPicks(){
  if(!PICKED.size || SENT) return;     // and no double-submit on a fast table
  // ONE SENTENCE, because the planner compiles one context into as many watch
  // entries as it needs. Joined in the order they are listed rather than the
  // order they were tapped, so two visitors who chose the same two things get
  // the same plan.
  const text=PRESETS.filter((_,i)=>PICKED.has(i)).join('; ');
  // HOLD A SCREEN INSTEAD OF BLINKING THE MENU. Clearing the ticks here and
  // re-rendering put the empty menu back for the ~200 ms until the next poll
  // saw the new state -- so the last thing the visitor saw after pressing the
  // button was their choice gone and `choose one to begin`, which reads as the
  // tap having been thrown away.
  SENT=text; render();
  try{
    await fetch('/context',{method:'POST',body:text});
    PICKED=new Set();
  }catch(e){
    // AND IF IT DID NOT GET THERE, GIVE THEM THEIR CHOICE BACK rather than
    // holding a screen that says it worked. The ticks were never cleared.
    SENT=null; render();
  }
}

let MODE=null;        // null | 'report' | 'wall'
let WAIT_FROM=0;      // how many stories existed when OK was pressed
let BIG=false;        // the live view, expanded

function zoom(){BIG=!BIG;place();}

// PUT #live WHERE IT BELONGS THIS FRAME. Over the red cell normally; filling
// the left of the screen when expanded, with the rule beside it. Measuring the
// cell rather than styling the image into the grid is what lets the grid be
// rewritten five times a second without ever touching the stream.
function place(){
  const el=document.getElementById('live'), hint=document.getElementById('hint');
  const cell=document.getElementById('livecell'), app=document.getElementById('app');
  const spec=document.querySelector('.cell.spec');
  if(!cell || MODE!==null){ el.style.display='none'; hint.classList.remove('on');
                            app.classList.remove('dim'); BIG=false; return; }
  if(!el.src) el.src='/stream.mjpg';      // opened once, on first need
  el.style.display='block';
  el.classList.toggle('big',BIG);
  app.classList.toggle('dim',BIG);
  hint.classList.toggle('on',BIG);
  if(BIG && spec){
    // STOP SHORT OF THE RULE. The sixth cell is the only other thing left lit,
    // so the picture takes the grid's area minus that column -- one copy of the
    // rule, exactly where it already was, no second rendering to keep in step.
    const g=document.querySelector('.grid').getBoundingClientRect();
    const r=spec.getBoundingClientRect();
    Object.assign(el.style,{left:g.left+'px',top:g.top+'px',
                            width:(r.left-g.left-14)+'px',height:g.height+'px'});
    Object.assign(hint.style,{left:r.left+'px',
                              top:(r.bottom+10)+'px',width:r.width+'px'});
  }else{
    const r=cell.getBoundingClientRect();
    Object.assign(el.style,{left:r.left+'px',top:r.top+'px',
                            width:r.width+'px',height:r.height+'px'});
  }
}
addEventListener('resize',place);

async function ok(){
  if(Date.now()-sent<800) return; sent=Date.now();
  document.getElementById('veil').classList.remove('on');
  WAIT_FROM=S.n_stories||0; MODE='report';        // wait for the NEXT one
  render();
  await fetch('/booth/ok',{method:'POST'});
}
function wall(){MODE='wall';render();}
function back(){MODE=null;render();}
const esc=s=>String(s==null?'':s).replace(/[<>&]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]));

// THE RULE AS IT WAS COMPILED, in words. The chips ARE the watch-spec -- the
// ids the planner emitted and the executor is testing every frame -- and each
// one lights the moment its relation is true, so a visitor watching the cell
// sees the machine decide rather than being told afterwards that it did.
//
// Which is exactly why the words are written out. `appr AND prox` is the same
// rule and teaches nobody anything.
// EVERY RULE, NOT THE FIRST ONE.
//
// This read `S.watch[0]` from a build where one spoken sentence made one
// entry, so the first was the only one. The menu takes several on purpose --
// two things at once is the interesting case and the button says `watch for 2
// things` -- and the cell went on showing one of them. A visitor who picked
// three and saw one has been told, on the robot's own screen, that two of
// their choices were dropped.
function ruleRow(w){
  const ids=[...w.all,...w.any,...w.then];
  const op = w.then.length ? 'THEN' : (w.any.length && !w.all.length ? 'OR' : 'AND');
  const chips=ids.map((id,k)=>
    (k?`<span class=op>${op}</span>`:'')+
    `<span class="rel${w.truth[String(id)]?' t':''}">${esc(S.rel_names[id]||id)}</span>`
  ).join('');
  return `<div class="rule${w.sat?' sat':''}">${chips}${w.on?`<span class=op>on</span>
    <span class="obj${w.on_now?' t':''}">${esc(w.on)}</span>`:''}</div>`;
}

function specInner(){
  const ws=S.watch||[];
  if(!ws.length) return '<span class=lb>NO RULE YET</span>';
  const anySat=ws.some(w=>w.sat);
  // THE COUNT IS PART OF THE ANSWER. "watching for 3" is what tells somebody
  // their second and third choices arrived, even before they read them.
  const head=anySat?'TRUE NOW'
                   :`WATCHING FOR ${ws.length} THING${ws.length>1?'S':''}`;
  // Sized by how many there are: three rules in a sixth of the grid cannot be
  // read at the size one rule is comfortable at, and shrinking all of them is
  // better than letting the third fall off the bottom.
  return `<span class=lb>${head}</span>
    <div class="rules n${Math.min(ws.length,4)}">${ws.map(ruleRow).join('')}</div>`;
}

function specCell(){
  const anySat=(S.watch||[]).some(w=>w.sat);
  return `<div class="cell spec${anySat?' sat':''}">${specInner()}</div>`;
}

function cells(){
  const out=[];
  for(let i=0;i<5;i++){
    const sh=S.shots[i];
    const pan=[-60,-30,0,30,60][i];
    if(!sh){out.push(`<div class="cell wait">${pan>0?'+':''}${pan}\u00b0</div>`);continue;}
    const on = S.chosen_pan!=null && sh.pan===S.chosen_pan;
    // THE CHOSEN CELL CARRIES NO PICTURE OF ITS OWN. It is the frame; #live is
    // laid over it, so the one direction the robot is actually watching shows
    // the live camera rather than a photograph taken during the sweep.
    out.push(on
      ? `<div class="cell live" id=livecell>
           <span class=tag>${sh.pan>0?'+':''}${sh.pan}° LIVE</span></div>`
      : `<div class=cell>
           <img src="/sweepimg/${esc(sh.dir)}/${esc(sh.file)}">
           <span class=tag>${sh.pan>0?'+':''}${sh.pan}°</span></div>`);
  }
  out.push(specCell());       // the sixth cell of the 3x2 grid
  return out.join('');
}

function strip(){
  document.getElementById('strip').innerHTML=(S.faces||[]).map(
    ([k,f,l])=>`<div class="f${k===S.face?' on':''}">${esc(f)}<b>${esc(l)}</b></div>`
  ).join('');
  const w=document.getElementById('wb');
  w.innerHTML=`\u2630 ${S.n_stories||0}<b>stories</b>`;
  w.style.visibility = MODE==='wall' ? 'hidden' : 'visible';
}

function story1(s){
  // /frame/ not /thumb/: the frame IS the strip, several panels wide. The
  // thumbnail is one squashed copy of it and loses the thing that makes a
  // story a story -- that it went on.
  const wide=(s.shots||1)>1;
  return `<div class=story>
    <div class=pan><img src="/frame/${esc(s.frame||s.thumb)}"></div>
    ${wide?'<div class=swipe>\u2190 swipe sideways</div>':''}
    <p>${esc(s.note)}</p><span>${esc(s.time)}</span></div>`;
}

function render(){
  strip();
  const a=document.getElementById('app');
  if(MODE==='wall'){
    const n=(S.stories||[]).length;
    a.innerHTML=`<div><h1>What it has noticed</h1>
      <div class=sub>${n} ${n===1?'story':'stories'} so far</div></div>
      <div id=stories>`+(S.stories||[]).map(story1).join('')
      +`</div><button class=ok onpointerdown="back()">back</button>`;
    return;
  }
  if(MODE==='report'){
    const fresh=(S.n_stories||0)>WAIT_FROM ? S.stories[0] : null;
    a.innerHTML=`<div><h1>${fresh?'Here is what it saw':'Writing it up'}</h1>
      <div class=sub>${esc(S.request)}</div></div>
      <div class=grow>`+(fresh
        ? story1(fresh)+`<button class=ok onpointerdown="back()">close</button>`
        : `<div class=waitbox>
             <div class=wface>\uff08\u30fb\u03c9\u30fb\uff09</div>
             <div class=wtxt>writing it up\u2026</div>
             <div class=wbar><i></i></div>
           </div>`)+`</div>`;
    return;
  }
  if(S.phase==='sleep'){
    a.innerHTML=`<div class=sleep>
        <div class=sface>(-_-)<i>z z z</i></div>
        <div class=stap>hold your hand in front of it<br>to wake it up</div>
      </div>`;
    return;
  }
  if(S.phase==='listen'){
    // SPEECH WINS IF THERE IS ANY. The menu is the fallback for a loud room,
    // not a replacement: a visitor who did speak gets the old screen, because
    // showing them a list while their own words are on their way back reads as
    // the robot having ignored them.
    const said=S.heard||'';
    if(SENT){
      // The same shape as the report screen: the tablet stops following the
      // robot for a moment because the visitor is owed an answer to the thing
      // they just did. It clears itself when the flow actually moves.
      a.innerHTML=`<div><h1>Got it</h1>
        <div class=sub>telling it now</div></div>
        <div class=grow><div class=picks>`+SENT.split('; ').map(t=>
          `<div class="pick on"><span class=tick>&#10003;</span>
             <span>${esc(t)}</span></div>`).join('')+`</div>
          <div class=lst><i>&#9679;</i><i>&#9679;</i><i>&#9679;</i></div>
        </div>`;
      return;
    }
    if(!said){
      // THE TABLET IS A DISPLAY HERE, NOT AN INPUT. The choice is made by
      // tapping the robot's head, so these are not touch targets -- a card
      // that looks tappable and is not is worse than one that does not.
      const on=S.pick_on, i=S.pick_i|0;
      a.innerHTML=`<div><h1>${on?'Watch for this?':'What should it watch for?'}</h1>
        <div class=sub>${on?'tap again to change \u2014 stop to choose'
                          :'tap the robot on the head'}</div></div>
        <div class=grow>
          <div class=picks>`+PRESETS.map((p,k)=>
            `<div class="pick${on&&k===i?' on':''}${on&&k!==i?' dim':''}">
               <span>${esc(p)}</span></div>`).join('')+`</div>
        </div>`;
      return;
    }
  }
  if(S.phase==='listen'){
    // WHAT IT HEARD, WHILE THERE IS STILL TIME TO SAY IT AGAIN. Empty means the
    // button is down and nothing has come back yet; rejected text is shown and
    // marked, because the robot is about to perform not understanding and this
    // is what makes that performance legible rather than puzzling.
    const t=S.heard||'';
    a.innerHTML=`<div><h1>${t?(S.heard_ok?'I heard':'I did not catch that'):'Listening'}</h1>
      <div class=sub>say it out loud, or choose below</div></div>
      <div class=grow>
        <div class="heard${t&&!S.heard_ok?' no':''}">`+(t
          ? esc(t)+(S.heard_ok?'':'<small>say it again, or choose from the list</small>')
          : `<div class=lst><i>\u25cf</i><i>\u25cf</i><i>\u25cf</i></div>`)
        +`</div></div>`;
  } else {
    // ONE SCREEN FOR SCANNING AND FOR WATCHING. The only question a visitor has
    // in either is which way it is looking, and the grid answers it the whole
    // time: cells fill as the head captures them, the red frame lands with the
    // plan, and it moves when the head is corrected. "tracking..." over an empty
    // page told them nothing the robot in front of them was not already saying.
    const done = S.chosen_pan!=null;
    a.innerHTML=`<div><h1>${done?'Watching this way':'Looking around the room'}</h1>
      <div class=sub>${esc(S.request)}</div></div>
      <div class=grid>${cells()}</div>
      <div class=bar>${done
        ? (S.noticed? S.noticed+(S.noticed===1?' story':' stories')+' so far \u00b7 ' : '')
          + 'touch its head if you want it to look somewhere else'
        : '<span class=dot></span>five directions taken \u2014 deciding which one to watch'}</div>`;
  }
}

// RETURN SENDS IT, and the same POST /context the developer page and
// standing_prompt.py use -- so there is one way in, and a sentence typed here
// re-plans from whatever state the robot is in, including S7_ERROR.
const ctx=document.getElementById('ctx');
ctx.addEventListener('keydown',async e=>{
  if(e.key!=='Enter') return;
  const v=e.target.value.trim();
  if(!v) return;
  e.target.value='';
  e.target.blur();          // drop the iPad keyboard; it covers half the grid
  try{
    await fetch('/context',{method:'POST',body:v});
    const k=document.getElementById('ctxok');
    k.classList.add('on'); setTimeout(()=>k.classList.remove('on'),1400);
  }catch(err){ e.target.value=v; }   // hand it back rather than eat it
});
// NOT WHILE SOMEBODY IS TYPING. The body listens for taps to zoom the live
// view and the page steals focus on re-render; neither should reach the box.
ctx.addEventListener('pointerdown',e=>e.stopPropagation());

async function poll(){
  try{
    const r=await fetch('/booth.json',{cache:'no-store'});
    const n=await r.json();
    const changed = JSON.stringify(n)!==JSON.stringify(S);
    // A NEW VISITOR GETS A BLANK MENU. Leaving the previous person's ticks up
    // is worse than it sounds: they are someone else's request, one tap from
    // being submitted as this person's.
    if(S.phase==='listen' && n.phase!=='listen'){ PICKED=new Set(); SENT=null; }
    S=n;
    if(changed) render();
    place();
    const veil=document.getElementById('veil');
    // NOT while the tablet is on a report or the wall. The robot re-enters S7
    // on the NEXT finding, and a prompt reappearing over the report the visitor
    // is still reading is the same interruption OK was meant to end.
    if(S.phase==='notice' && MODE===null){
      document.getElementById('pd').textContent=S.describe||'';
      veil.classList.add('on');
    } else veil.classList.remove('on');
  }catch(e){}
}
setInterval(poll,200); poll();
</script></body></html>""".replace("__PRESETS__", json.dumps(PRESETS))

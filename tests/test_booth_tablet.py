"""The tablet: one state, one set of screens, and no dead ends.

This file is the part that is TRUE OF BOTH BUILDS -- the exhibition stand
(demo-expo-2026, a Japanese menu) and the study (this branch, a spoken request).
What differs between them lives in test_booth_listen.py; what is here is the
machinery underneath: the phase is decided ONCE, in the loop, both surfaces read
it, the red frame follows where the head is actually aimed, and an `arm_next`
belongs to the clip that was playing when it was armed.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import webui.server as W
from webui.booth import booth_state


def _st(**kw):
    s = dict(W.STATE)
    s.update(kw)
    return s


# ------------------------------------------------------------- the phases --
def test_the_phase_follows_the_robot_not_the_tablet():
    """Every screen is a function of the flow state, so a visitor cannot get the
    tablet onto a page the robot is not on."""
    # Scanning and watching are ONE screen -- see the note in booth_state. The
    # visitor's question in both is which way it is looking, and the grid
    # answers that continuously; "tracking..." over an empty page said nothing
    # the robot standing in front of them was not already saying.
    cases = [("S0_IDLE", "sleep"), ("S2_ACKNOWLEDGE", "room"), ("S3_SCAN", "room"),
             ("S4A_SETTLE", "room"), ("S4B_WATCH", "room"),
             ("S6_CORRECT", "room"), ("S5A_FOUND", "notice"), ("S5B_BECKON", "notice")]
    for state, phase in cases:
        assert booth_state(_st(flow_state=state), [], None)["phase"] == phase, state


def test_the_wait_after_the_sweep_is_not_a_second_choice():
    """The head finishes S4 and moves on while the VLM is still out -- 5 to 20 s
    of it. Falling back to `choose` there would offer the visitor a second
    choice while the first is still being compiled."""
    s = booth_state(_st(flow_state="S4A_SETTLE", plan_pending=True), [], None)
    assert s["phase"] == "room"


def test_the_red_frame_follows_the_aim_so_a_tap_has_an_answer():
    """Correcting the head is a gesture that has to be answered on the tablet.
    Reddening the sweep's own highest-scoring station instead would leave the
    frame where it was and make the tap look ignored."""
    meta = {"dir": "d", "richest_pan": -60,
            "shots": [{"pan": p, "file": f"p{p}.jpg", "dets": []}
                      for p in (-60, -30, 0, 30, 60)]}
    # mid-sweep: no aim yet, so the sweep's own pick stands in
    assert booth_state(_st(flow_state="S3_SCAN"), [], meta)["chosen_pan"] == -60
    # watching where the plan aimed it
    assert booth_state(_st(flow_state="S4B_WATCH", aimed_pan=-58.0),
                       [], meta)["chosen_pan"] == -60
    # tapped, re-aimed: the frame moves with it
    assert booth_state(_st(flow_state="S6_CORRECT", aimed_pan=28.0),
                       [], meta)["chosen_pan"] == 30


def test_the_loop_publishes_where_it_is_aimed():
    src = open(os.path.join(ROOT, "noticebot_loop.py")).read()
    assert 'UI.STATE["aimed_pan"] = ctxd.get("aimed_pan")' in src


# ------------------------------------------------------ the visitor's tap --
def test_asleep_is_a_face_and_it_says_where_the_way_in_is():
    """Idle is a sleeping face, not a menu, on both builds. What the line under
    it asks for is the one thing that differs, so this only checks that a line
    is there and that S2 leaves the sleep screen at all."""
    from webui.booth import PAGE
    assert booth_state(_st(flow_state="S0_IDLE"), [], None)["phase"] == "sleep"
    assert booth_state(_st(flow_state=""), [], None)["phase"] == "sleep"
    assert booth_state(_st(flow_state="S1_ATTEND"), [], None)["phase"] != "sleep"
    assert "class=sface" in PAGE and "class=stap" in PAGE


def test_the_strip_says_the_state_instead():
    """A state change is worth a glance, not a screen."""
    from webui.booth import FACES, face_key
    s = booth_state(_st(flow_state="S1_ATTEND"), [], None)
    assert s["face"] == "S1_ATTEND"
    assert s["phase"] == "listen", "the strip changes, the page does not"
    assert [f[0] for f in s["faces"]][0] == "S0_IDLE"


def test_the_faces_are_the_robots_own():
    """Copied from the firmware's uiFace(). Two surfaces, one vocabulary -- a
    visitor looking from the tablet to the robot sees the same thing twice
    rather than having to learn a second code."""
    from webui.booth import FACES
    ino = open(os.path.join(ROOT, "robot", "firmware", "cores3_sidekick",
                            "cores3_sidekick.ino")).read()
    for state, face, _label in FACES:
        if state == "S3_SCAN":
            continue          # planning wears no face on the robot, by design
        # The .ino is C: a backslash in the face is written doubled there. What
        # has to match is what the two screens DISPLAY, not how each language
        # spells it.
        as_c = face.replace("\\", "\\\\")
        assert f'"{as_c}"' in ino, f"{state}: {face} is not what the board shows"


def test_every_state_lights_exactly_one_lamp():
    from webui.booth import FACES, face_key
    keys = {k for k, _f, _l in FACES}
    for state in ("S0_IDLE", "S1_ATTEND", "S2_ACKNOWLEDGE", "S3_SCAN", "S4A_SETTLE",
                  "S4B_WATCH", "S6_CORRECT", "S5A_FOUND", "S5B_BECKON", "S7_ERROR", ""):
        assert face_key(state) in keys, state


def test_the_sentence_is_set_large_enough_to_read_from_a_seat():
    """Driven off the WIDTH, which is the dimension a sentence actually runs
    out of, with a floor high enough that a small laptop window still shows it
    big -- that window is where it gets checked, and the reason the size was
    wrong for two rounds is that the number in the source looked right."""
    import re
    from webui.booth import PAGE
    css = re.sub(r"/\*.*?\*/", "", PAGE, flags=re.S)
    block = re.search(r"\.heard\{[^}]*\}", css).group(0)
    size = re.search(r"font-size:clamp\((\d+)px", block)
    assert size and int(size.group(1)) >= 30, block
    assert "text-align:center" in block


def test_app_is_laid_out_once():
    """Two live #app rules gave it height:100% AND flex:1. With the strip above
    it the page ran past the viewport and overflow:hidden cut the bottom off --
    the grid on one screen, the second button on the other."""
    import re
    from webui.booth import PAGE
    css = re.sub(r"/\*.*?\*/", "", PAGE, flags=re.S)
    assert len(re.findall(r"#app\{", css)) == 1


def test_no_font_shorthand_ending_in_inherit():
    """`font: 700 40px/1.3 inherit` is invalid CSS -- `inherit` is a CSS-wide
    keyword, legal only as an entire value, never as the shorthand's family
    slot. The browser drops the whole declaration, so the element renders at the
    inherited default and the size is silently ignored. Every size on this page
    was being thrown away that way, and setting a bigger number changed nothing.
    """
    import re
    from webui.booth import PAGE
    # Comments out first -- the rule is explained in one, and the explanation
    # necessarily quotes the thing it forbids.
    css = re.sub(r"/\*.*?\*/", "", PAGE, flags=re.S)
    bad = [d for d in re.findall(r"font:[^;}]*", css) if "inherit" in d]
    assert not bad, bad


def test_an_override_belongs_to_the_clip_that_was_playing_when_it_was_armed():
    """Both directions of this were bugs on 2026-08-18, and they pull opposite
    ways -- which is why the rule is about ORDER, not about interruption.

    Stale override left alive: the head tap arms S0_IDLE and plays S2, the
    visitor picks a task while S2 is still running, S2 is cut short, and
    S2_ACKNOWLEDGE's `then` (S3_SCAN) is replaced by S0_IDLE. Nod, sleep, no sweep.

    Cleared on the interrupt instead: OK arms S4B_WATCH and requests S2_ACKNOWLEDGE,
    that request interrupts S5B_BECKON, and the arming meant for S2_ACKNOWLEDGE is wiped a
    microsecond after it was made -- S2_ACKNOWLEDGE falls back to S3_SCAN and the robot
    re-scans. Reported as "OK still goes back to scan".

    Only the caller knows which clip an override was for, and it says so by
    calling request() first and arm_next() second.
    """
    import inspect
    from robot.clip_player import ClipPlayer
    src = inspect.getsource(ClipPlayer.request)
    assert "self._next_override = None" in src

    play = open(os.path.join(ROOT, "robot", "clip_player.py")).read()
    i = play.index("completed = self._play_once(frames)")
    assert "_next_override" not in play[i:i + 400], "not on the interrupt path"


def test_every_caller_requests_first_and_arms_second():
    src = open(os.path.join(ROOT, "noticebot_loop.py")).read()
    # The S1_ATTEND pair belonged to the exhibition build's wake tap, which this
    # branch does not have. S2_ACKNOWLEDGE is the one that broke in BOTH directions on
    # 2026-08-18 and it is the one worth guarding.
    for a, b in [('player.request("S2_ACKNOWLEDGE")', 'player.arm_next("S0_IDLE")')]:
        i = src.index(a)
        assert b in src[i:i + 200], f"{a} must be followed by {b}"


def test_ok_emits_the_state_before_the_arming():
    """The loop turns ("state", X) into player.request(X), which clears any
    pending override -- so the arming has to be emitted on the far side of it."""
    import session.session_flow as F
    f = F.SessionFlow(now=lambda: 0.0)
    f.state, f.transcript = "S5B_BECKON", "x"
    kinds = [k for k, _ in f.feed("ok")]
    assert kinds.index("state") < kinds.index("ack_then")


# ------------------------------------------------------------ the sweep --
def test_the_chosen_station_is_marked_and_the_rest_are_not():
    meta = {"dir": "20260817_181729", "richest_pan": -60,
            "shots": [{"pan": p, "file": f"pan_{p:+04d}.jpg",
                       "dets": [{"tier": "focus"}] if p == -60 else []}
                      for p in (-60, -30, 0, 30, 60)]}
    s = booth_state(_st(flow_state="S3_SCAN"), [], meta)
    assert len(s["shots"]) == 5
    assert s["chosen_pan"] == -60
    assert [sh["dir"] for sh in s["shots"]] == ["20260817_181729"] * 5


def test_no_sweep_yet_is_empty_not_broken():
    s = booth_state(_st(flow_state="S3_SCAN"), [], None)
    assert s["shots"] == [] and s["chosen_pan"] is None


def test_the_sixth_cell_shows_the_rule_in_the_developer_pages_words():
    """Five stations in a 3x2 grid leave one cell empty, and what belongs there
    is the condition. A visitor who can read hands-on + bag knows what to DO --
    which at a stand is the difference between a demo that gets triggered and
    one that does not."""
    from webui.booth import REL_NAMES
    import webui.server as WS
    st = _st(flow_state="S4B_WATCH", status=[{
        "label": "touching the bag", "onobj": "bag",
        "all": [9], "any": [], "not": [], "then": [],
        "sat": True, "cool": False, "on": {"9": True}}])
    w = booth_state(st, [], None)
    assert w["watch"][0]["on"] == "bag"
    assert w["watch"][0]["all"] == [9]
    assert w["watch"][0]["truth"]["9"] is True
    # the same ids the developer page names, so the two cannot drift
    assert set(REL_NAMES) == set(WS.REL_NAMES)
    assert REL_NAMES[9].startswith("hands")


def test_the_nod_does_not_get_a_screen_of_its_own():
    """1.7 s. A page that appears and vanishes inside two seconds is a flash,
    not information -- and S2_ACKNOWLEDGE happens in two different places (after a
    choice, after OK), so any one screen would be wrong in one of them."""
    from webui.booth import PAGE
    assert booth_state(_st(flow_state="S2_ACKNOWLEDGE"), [], None)["phase"] == "room"
    assert "phase==='ack'" not in PAGE


def test_it_reads_the_same_fields_the_live_panel_does():
    """build_status is the one place an entry becomes a row. Deriving these
    from the spec separately would give the tablet its own opinion of what is
    satisfied."""
    from webui.booth import PAGE
    i = PAGE.index("function ruleRow(")
    block = PAGE[i:PAGE.index("function specCell(")]
    for k in ("w.all", "w.any", "w.then", "w.truth", "w.on", "w.sat"):
        assert k in block, k
    assert "THEN" in block and "AND" in block and "OR" in block


def test_the_tablet_spells_the_relations_out():
    """One chip of a rule is the whole of what a visitor learns about how this
    machine decides, and `appr` teaches them nothing. The developer page may
    abbreviate; this one may not."""
    from webui.booth import REL_NAMES
    for i, name in REL_NAMES.items():
        assert len(name) >= 6, f"{i}: {name!r} is an abbreviation"
    assert REL_NAMES[7] == "approaching" and REL_NAMES[5] == "proximity"


def test_the_tablet_vocabulary_covers_the_catalogue_exactly():
    """The WORDS here are free to read however they read best. The IDS are the
    contract -- the planner compiles to them and `truth` is keyed by them -- so
    a row added to the catalogue must not silently render as a bare number."""
    from planning.planner import _CATALOG
    from webui.booth import REL_NAMES
    assert set(REL_NAMES) == {r["id"] for r in _CATALOG["relations"]}


def test_the_grid_has_six_cells_and_the_last_is_the_rule():
    from webui.booth import PAGE
    i = PAGE.index("function cells(")
    block = PAGE[i:i + 1400]
    assert "i<5" in block, "five stations"
    assert "out.push(specCell())" in block, "and the rule in the sixth"


def test_only_the_watched_direction_is_live_and_it_survives_a_re_render():
    """An <img> on an MJPEG stream holds an open connection. Inside the
    innerHTML render() rewrites, that connection would be torn down and
    reopened five times a second -- a black flicker and a new TCP connection
    each poll. It sits outside #app and is positioned over the cell instead."""
    from webui.booth import PAGE
    assert "<img id=live" in PAGE
    i = PAGE.index("function cells(")
    grid = PAGE[i:i + 1400]
    assert "/stream.mjpg" not in grid, "the stream is not in the rewritten markup"
    assert 'id=livecell' in grid, "the chosen cell is an empty frame to lay it over"
    assert grid.count("/sweepimg/") == 1, "the other four stay as sweep stills"

    place = PAGE[PAGE.index("function place("):]
    assert "getBoundingClientRect" in place[:1800], "measured, not styled into the grid"
    assert "if(!el.src)" in place[:1800], "opened once, not every frame"


def test_expanding_dims_everything_but_the_picture_and_the_one_rule():
    """The rule is NOT redrawn beside the live view -- it is already in the sixth
    cell. A second copy is a second thing to keep in step, and the visitor has
    to find it again in a new place."""
    import re
    from webui.booth import PAGE
    assert 'onpointerdown="zoom()"' in PAGE
    i = PAGE.index("function place(")
    block = PAGE[i:i + 1600]
    assert "app.classList.toggle('dim',BIG)" in block
    assert "specInner()" not in block, "one copy of the rule, not two"
    assert "spec.getBoundingClientRect()" in block, "sized to stop short of it"

    css = re.sub(r"/\*.*?\*/", "", PAGE, flags=re.S)
    assert "#app.dim .cell.spec{opacity:1}" in css, "the rule stays lit"
    assert "#app.dim .bar{display:none}" in css, "the bottom row goes"


def test_the_prompt_is_never_behind_the_expanded_view():
    """The live view can fill most of the screen. The one thing that must never
    be behind it is the robot asking to be answered."""
    import re
    from webui.booth import PAGE
    css = re.sub(r"/\*.*?\*/", "", PAGE, flags=re.S)
    live = int(re.search(r"#live\{[^}]*z-index:(\d+)", css).group(1))
    veil = int(re.search(r"#veil\{[^}]*z-index:(\d+)", css).group(1))
    assert veil > live, f"veil {veil} must sit above live {live}"


def test_the_wait_has_a_face_and_a_bar_that_promises_nothing():
    """6-45 s with one small line on it reads as a machine that has stopped.
    Nothing here knows how long the narration will take, so a bar that claimed
    to would be lying -- it is a sign of life, not a measure."""
    import re
    from webui.booth import PAGE
    assert "class=wface" in PAGE and "class=wbar" in PAGE
    css = re.sub(r"/\*.*?\*/", "", PAGE, flags=re.S)
    bar = re.search(r"\.wbar i\{[^}]*\}", css).group(0)
    assert "animation:slide" in bar
    assert "width:38%" in bar, "a fixed sliver -- it is not tracking progress"


# ------------------------------------------------------------ the notice --
def test_ok_is_never_answered_by_a_blank_screen():
    """The strip takes another 6-45 s to close, but the judge's sentence was
    written from five frames BEFORE S7 played -- so it is already here at the
    moment the visitor is asked to press OK."""
    s = booth_state(_st(flow_state="S5B_BECKON", describe="Someone reached for the bag."),
                    [], None)
    assert s["phase"] == "notice"
    assert s["describe"] == "Someone reached for the bag."


def test_the_wall_shows_the_most_recent_first():
    recs = [{"note": f"n{i}", "thumb": f"t{i}.jpg", "time": "12:00"}
            for i in range(9)]
    s = booth_state(_st(flow_state="S4B_WATCH"), recs, None)
    assert [r["note"] for r in s["stories"]][:3] == ["n8", "n7", "n6"]
    assert s["n_stories"] == 9


def test_the_count_is_what_tells_the_tablet_a_report_has_landed():
    """After OK the tablet stops following the robot and waits. It cannot know a
    story has been written without a number that changes -- the robot has
    already gone back to watching, so its state says nothing about the report."""
    before = booth_state(_st(flow_state="S5B_BECKON"), [{"note": "a"}], None)
    after = booth_state(_st(flow_state="S4B_WATCH"),
                        [{"note": "a"}, {"note": "b"}], None)
    assert after["n_stories"] > before["n_stories"]
    assert after["stories"][0]["note"] == "b", "newest first"


def test_the_tablet_leaves_the_robot_behind_after_ok():
    """The robot returns to watching immediately, which is right -- it has a job.
    The visitor is owed the report they just asked for, and it takes another
    6-45 s to write. Following the robot back to the room grid threw that away
    and made OK look like it had cancelled something."""
    from webui.booth import PAGE
    i = PAGE.index("async function ok(")
    block = PAGE[i:i + 400]
    assert "MODE='report'" in block
    assert "WAIT_FROM=S.n_stories" in block, "wait for the NEXT story, not any"


def test_a_new_prompt_does_not_cover_the_report_being_read():
    """The robot re-enters S7 on the next finding. A prompt reappearing over the
    report is the same interruption OK was pressed to end."""
    from webui.booth import PAGE
    i = PAGE.index("if(S.phase==='notice'")
    assert "MODE===null" in PAGE[i:i + 120]


def test_the_wall_is_a_chip_in_the_top_row_not_a_button_in_the_way():
    """It is a way out, not an offer. At the size of a state face, in the top
    corner, it cannot compete with the two things a visitor is actually being
    asked to choose between."""
    from webui.booth import PAGE
    assert 'class="f wallbtn" id=wb' in PAGE
    assert 'onpointerdown="wall()"' in PAGE
    assert "function back()" in PAGE, "and a way out of it"
    assert "これまでに気づいたこと（" not in PAGE, "the full-width button is gone"


def test_a_story_is_the_wide_strip_not_a_thumbnail():
    """The storyboard composites its panels into one wide jpg -- that IS the
    shape of a finding, several moments in a row. The thumbnail is one squashed
    copy and loses the thing that makes a story a story: that it went on."""
    from webui.booth import PAGE
    i = PAGE.index("function story1(")
    block = PAGE[i:i + 600]
    assert "/frame/" in block
    # thumb appears only as the fallback inside the same expression
    assert block.index("/frame/") < block.index("s.thumb")
    assert "class=pan" in block, "scrolled sideways, not squeezed"


def test_the_strip_scrolls_sideways_at_full_height():
    import re
    from webui.booth import PAGE
    css = re.sub(r"/\*.*?\*/", "", PAGE, flags=re.S)
    pan = re.search(r"\.pan\{[^}]*\}", css).group(0)
    assert "overflow-x:auto" in pan
    img = re.search(r"\.pan img\{[^}]*\}", css).group(0)
    assert "width:auto" in img, "let it be as wide as it is"


def test_the_showcase_re_sweeps_when_idle_but_never_on_a_clock():
    """Two timers, opposite answers, and the difference is whether it can
    interrupt somebody.

    REPLAN_IDLE_S fires only when the watched angle has produced NOTHING for a
    minute, so a rule that keeps landing keeps pushing it out and a visitor is
    never cut off mid-interaction. At a stand that is what keeps a ten-minute-old
    plan from outliving the room it was made for.

    REPLAN_PERIOD_S goes off on a clock whatever is happening -- a good beat in
    a 15-minute session, and at a stand it swings the head away from the person
    who just asked it to watch something. Stays off.
    """
    import robot.states as ST
    assert ST.REPLAN_IDLE_S == 60.0
    assert ST.REPLAN_PERIOD_S == 0.0


# ------------------------------------------------------------ the routes --
def test_the_page_and_the_poll_serve(tmp_path):
    W.ARGS = __import__("argparse").Namespace(feed_dir=str(tmp_path), web_port=8123)
    W.serve(W.ARGS)
    time.sleep(0.4)
    base = "http://127.0.0.1:8123"
    page = urllib.request.urlopen(base + "/booth", timeout=5).read().decode()
    assert "user-scalable=no" in page, "an iPad will pinch-zoom the layout apart"
    assert "setInterval(poll,200)" in page, "1200ms lags visibly behind the chirp"
    assert 'lang=en' in page

    # THE SENTENCE LIVES IN THE POLL, NOT IN THE PAGE. The page holds no copy of
    # any request, so nothing on the tablet can drift from what the planner was
    # actually given -- which is the property that matters whether the sentence
    # came from a menu or from a microphone.
    raw = urllib.request.urlopen(base + "/booth.json", timeout=5).read()
    data = json.loads(raw)
    assert data["phase"] in ("sleep", "listen", "room", "notice")
    assert "heard" in data and "request" in data
    assert "choices" not in data, "the menu belongs to the exhibition build"


def test_the_tablet_address_is_printed_at_startup(capsys):
    """So nobody has to guess which interface is Wi-Fi. `ipconfig getifaddr en0`
    is the usual advice and it is wrong often enough to matter -- en0 is not
    always Wi-Fi, and the venue changes the number anyway."""
    W.serve(__import__("argparse").Namespace(feed_dir=".", web_port=8125))
    out = capsys.readouterr().out
    ip = W.lan_address()
    assert ip is None or f"http://{ip}:8125/booth" in out
    # A URL, not the word -- the line deliberately SAYS "http, not https",
    # because Safari autocompletes to https and then fails on a certificate
    # error, which sends you looking at the wrong layer entirely.
    assert "https://" not in out, "the server is plain HTTP"
    assert ".local" not in out, "mDNS is intermittently refused on iOS"


def test_finding_the_address_sends_no_packet():
    """A UDP connect() only picks a route. Anything that actually reached the
    network would hang for the timeout when the venue's wifi is down, which is
    exactly when this line is being read."""
    import inspect
    src = inspect.getsource(W.lan_address)
    assert "SOCK_DGRAM" in src
    assert "192.0.2." in src, "TEST-NET-1: reserved, guaranteed never routed"


def test_both_screens_can_take_the_ok():
    """The CoreS3 sends IN OK; this is the same event from the tablet. The loop
    drains one flag, so whichever arrives first is the one that counts."""
    src = open(os.path.join(ROOT, "noticebot_loop.py")).read()
    i = src.index('UI.STATE.get("pending_ok")')
    assert 'ui_events.append("ok")' in src[i:i + 240]
    assert 'UI.STATE["pending_ok"] = False' in src[i:i + 240]


def test_the_tablet_fields_are_published_on_a_normal_run():
    """They were written inside the `view is None` arm -- the fallback for a
    detector that failed to load -- so on every real run they never executed.
    The tablet sat on the choose screen for the whole session: no sweep, no red
    frame, no notice. Nothing raised, because an unset flow_state is just a
    string that matches no state.

    Asserted by POSITION, since that is what was wrong: the publish has to come
    before the branch, not inside either half of it.
    """
    src = open(os.path.join(ROOT, "noticebot_loop.py")).read()
    pub = src.index('UI.STATE["flow_state"] = flow.state')
    branch = src.index("                if view is not None:\n"
                       "                    view.publish(")
    assert pub < branch, "the booth publish is inside the detector-failed arm again"
    for field in ("plan_pending", "noticed_n", "describe", "sweep_meta"):
        assert f'UI.STATE["{field}"]' in src[pub:branch], field


# ----------------------------------------------------- one gesture, one job --
def test_the_tap_only_ever_means_not_that_one():
    """On the exhibition build this gesture carried a second meaning -- asleep
    it woke the robot -- because there the tap was the only way in. Here the way
    in is the button and a spoken sentence, so the wake is gone and the tap is
    left saying exactly one thing, which is what a seven-minute briefing can
    afford to explain."""
    src = open(os.path.join(ROOT, "noticebot_loop.py")).read()
    i = src.index('elif "BODYTAP" in line:')
    block = src[i:i + 1800]
    assert 'flow.state == "S0_IDLE"' not in block
    assert 'player.request("S1_ATTEND")' not in block
    assert 'events.append("tap")' in block


def test_the_prompt_row_is_outside_the_part_that_is_re_rendered():
    """render() rewrites the whole of #app five times a second. An <input>
    inside that innerHTML is destroyed between keystrokes -- the caret jumps and
    the text disappears -- which is the same trap #live was pulled out of.
    """
    from webui.booth import PAGE
    body = PAGE[PAGE.index("<body>"):PAGE.index("<script>")]
    app = body.index("<div id=app>")
    bar = body.index("<div id=ctxbar>")
    assert bar > app, "the prompt row must not be nested in #app"
    render = PAGE[PAGE.index("function render("):PAGE.index("async function poll(")]
    assert "ctxbar" not in render and "id=ctx" not in render, \
        "render() must never touch the prompt row"


def test_the_prompt_goes_to_the_one_endpoint_that_re_plans():
    """Same POST /context the developer page and standing_prompt.py use, so a
    sentence typed on the tablet is accepted from every state -- including
    S7_ERROR, which is the state it is most often typed to get out of."""
    from webui.booth import PAGE
    assert "fetch('/context',{method:'POST'" in PAGE
    assert "e.key!=='Enter'" in PAGE, "return sends it"


def test_the_prompt_box_is_16px_so_ios_does_not_zoom_the_page():
    """Safari zooms in on a focused input under 16px and a wall-mounted tablet
    has nobody to pinch it back out."""
    from webui.booth import PAGE
    css = PAGE[PAGE.index("#ctx{"):PAGE.index("#ctx:focus")]
    assert "font-size:16px" in css


def test_the_relation_ribbon_is_gone_from_the_frame_entirely():
    """It printed rows 1-11 across the bottom of the annotated frame -- and that
    one frame feeds the developer page and the visitor's tablet alike, so
    eleven abbreviations from a vocabulary nobody in the room has read sat over
    the bottom of the picture a visitor was looking at.

    Gone, not behind a flag. A debug view that reaches the audience by default,
    kept alive by a switch nobody remembers on the day, is the same failure with
    an extra step in front of it."""
    import inspect
    from planning import plan_view
    from perception import overlay
    assert not hasattr(overlay, "draw_relation_ribbon")
    assert not hasattr(overlay, "LIVE_ABBR")
    assert "ribbon" not in inspect.signature(plan_view.PlanView.__init__).parameters
    assert "draw_relation_ribbon" not in inspect.getsource(plan_view.PlanView)
    assert "--ribbon" not in open("noticebot_loop.py").read()


def test_the_tablet_shows_every_rule_not_the_first_one():
    """The menu takes several on purpose -- two things at once is the
    interesting case, and the button itself says `watch for 2 things`. A
    visitor who picked three and saw one has been told, on the robot's own
    screen, that two of their choices were dropped."""
    from webui.booth import PAGE
    assert "(S.watch||[])[0]" not in PAGE, "this is the bug: only the first"
    i = PAGE.index("function specInner(")
    block = PAGE[i:PAGE.index("function cells(")]
    assert "ws.map(ruleRow)" in block, "every entry gets a row"
    assert "ws.some(w=>w.sat)" in block, "and ANY of them can turn the cell"
    assert "ws.length" in block, "the count is part of the answer"


def test_a_fourth_rule_does_not_fall_off_the_bottom():
    """Showing three of four is the same lie as showing one of three, and it
    is the kind that looks fine in a screenshot."""
    import re
    from webui.booth import PAGE
    css = re.sub(r"/\*.*?\*/", "", PAGE, flags=re.S)
    rules = re.search(r"\.rules\{[^}]*\}", css).group(0)
    assert "overflow-y:auto" in rules
    assert "min-height:0" in rules, "or the flex parent refuses to let it scroll"
    assert ".rules.n3" in css and ".rules.n4" in css, \
        "and the chips shrink with the count"

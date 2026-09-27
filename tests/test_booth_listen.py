"""The participant's tablet, on the study build: no menu, and a listening screen.

WHY THESE ARE THE TESTS. Every bug this page has had was invisible in the
source and only appeared on the iPad: the publish written into the wrong branch
so `flow_state` stayed empty all session, a `font:` shorthand with `inherit` in
the family slot so every size was silently dropped, two live `#app` rules so the
bottom of the page was clipped away. None of them raised anything. So these
assert the PROPERTY -- the position, the branch, the absence -- rather than the
presence of a string, because presence was never what was missing.

The render tests run the page's own `render()` under jsdom when node and jsdom
are available, and skip otherwise. Running the real function beats grepping the
template: the template is one long string and a branch that never executes reads
exactly like one that does.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from webui import booth


# --------------------------------------------------------------------------- #
# the state machine behind the page
# --------------------------------------------------------------------------- #
def st(state, **kw):
    d = {"flow_state": state}
    d.update(kw)
    return booth.booth_state(d, kw.pop("_recs", []), kw.get("sweep_meta"))


@pytest.mark.parametrize("state,phase", [
    ("S0_IDLE",     "sleep"),
    ("",            "sleep"),
    ("S1_ATTEND",   "listen"),
    ("S7_ERROR",    "listen"),
    ("S2_ACKNOWLEDGE",      "room"),
    ("S3_SCAN",     "room"),
    ("S4A_SETTLE",  "room"),
    ("S4B_WATCH",   "room"),
    ("S6_CORRECT", "room"),
    ("S5A_FOUND",         "notice"),
    ("S5B_BECKON",         "notice"),
])
def test_every_state_lands_on_a_screen(state, phase):
    assert st(state)["phase"] == phase


def test_the_nod_does_not_get_a_screen_of_its_own():
    """1.7 s. A page that appears and vanishes inside two seconds is a flash."""
    assert st("S2_ACKNOWLEDGE")["phase"] == st("S3_SCAN")["phase"]


def test_the_menu_is_back_for_the_showcase_but_not_the_old_one():
    """THE STUDY REMOVED A MENU ON PURPOSE and this build puts one back, so the
    reason has to be said rather than quietly reversed.

    The study's reason: a tappable list of sentences decides for the
    participant the one thing the study asks them to decide, which is what they
    want noticed. That still holds -- for a study.

    A showcase asks nobody anything. The room is loud, half the visitors are
    speaking a second language, and ninety seconds is the whole interaction: a
    spoken sentence that fails to transcribe spends that budget performing
    not-having-understood. The list is the fallback and SPEECH STILL WINS --
    anything actually said lands first and the loop takes it.

    What must NOT come back is the old implementation: a separate /booth/choose
    route with its own state. The menu posts the same /context every other
    input uses, so there is one way a request enters the flow.
    """
    src = open(os.path.join(ROOT, "webui", "booth.py")).read()
    for gone in ("CHOICES", "english_for", "/booth/choose", "S.choices",
                 "request_ja", "booth_choice_ja"):
        assert gone not in src, gone
    assert "choices" not in st("S1_ATTEND"), \
        "the presets are baked into the page; they are not per-poll state"
    assert "PRESETS" in src and "fetch('/context'" in src


def test_the_menu_takes_more_than_one_and_waits_for_the_button():
    """The interesting requests are two things at once, and a tap that fired
    immediately would allow exactly one."""
    src = open(os.path.join(ROOT, "webui", "booth.py")).read()
    i = src.index("function pick(")
    assert "PICKED.delete" in src[i:i + 200], "tapping toggles"
    assert "render()" in src[i:i + 200], "and redraws rather than submitting"
    send = src[src.index("async function sendPicks("):][:1400]
    assert "fetch('/context'" in send, "only the button submits"
    assert "join('; ')" in send, "several presets become one context sentence"


def test_the_selection_survives_the_re_render_and_not_the_visitor():
    """render() rewrites #app five times a second, so a tick held in the DOM is
    erased between one tap and the next -- the same trap #live and the prompt
    row were pulled out of. And the NEXT visitor must not inherit ticks that
    are one tap from being submitted as their request."""
    src = open(os.path.join(ROOT, "webui", "booth.py")).read()
    body = src[src.index("<body>"):src.index("<script>")]
    assert "PICKED" not in body, "the selection must not live in the markup"
    assert "let PICKED" in src
    assert "n.phase!=='listen'" in src and "PICKED=new Set()" in src


def test_the_choose_route_is_gone_from_the_server_too():
    """A dead POST route that still sets STATE is worse than none: it works."""
    src = open(os.path.join(ROOT, "webui", "server.py")).read()
    assert "/booth/choose" not in src
    assert "english_for" not in src and "CHOICES" not in src
    assert "/booth/ok" in src, "the OK from either screen must survive"


def test_heard_and_request_are_different_fields():
    """`heard` is the microphone's last word, right or wrong, and belongs only
    to the listening screen. `request` is what the flow ACCEPTED, and is what
    every later screen echoes -- a report must name the request it answers."""
    d = st("S1_ATTEND", heard="beep beep beep", heard_ok=False,
           request="tell me if someone touches my bag")
    assert d["heard"] == "beep beep beep"
    assert d["heard_ok"] is False
    assert d["request"] == "tell me if someone touches my bag"


def test_rejected_text_survives_to_the_page():
    """It is shown, not hidden: the robot is about to perform not having
    understood, and reading what it thought it heard is what makes that
    performance legible instead of puzzling."""
    d = st("S7_ERROR", heard="mmhm", heard_ok=False)
    assert d["phase"] == "listen" and d["heard"] == "mmhm"
    assert d["heard_ok"] is False


def test_nothing_a_participant_reads_is_still_japanese():
    src = open(os.path.join(ROOT, "webui", "booth.py")).read()
    # the kaomoji are escaped codepoints on purpose; bare CJK is a missed string
    bad = [ln for ln in src.splitlines()
           if any("　" <= c <= "鿿" or "＀" <= c <= "ﾟ"
                  for c in ln)]
    assert not bad, bad[:3]
    assert "lang=en" in src
    for label in ("asleep", "listening", "watching", "calling"):
        assert label in src


# --------------------------------------------------------------------------- #
# the bugs that only ever showed up on the iPad
# --------------------------------------------------------------------------- #
def test_no_font_shorthand_anywhere_on_the_page():
    """`font: 700 40px/1.3 inherit` is INVALID -- `inherit` is a CSS-wide
    keyword, legal only as a whole value, never as the family slot -- so the
    browser drops the declaration and the element renders at the inherited
    size. Every size on this page was thrown away that way once, and the symptom
    was 'the text is still small' with a larger number visible in the source."""
    # Comments first. The page carries a long note ABOUT this bug, and a test
    # that trips over the explanation of the thing it is checking is a test
    # that will be deleted by whoever hits it next.
    css = re.sub(r"/\*.*?\*/", "", booth.PAGE, flags=re.S)
    offenders = [ln.strip() for ln in css.splitlines()
                 if "font:" in ln and "inherit" in ln]
    assert not offenders, offenders


def test_only_one_live_app_rule():
    """It carried height:100% AND flex:1 at once, so with the strip above it the
    page ran past the viewport and the grid and buttons were clipped away under
    overflow:hidden."""
    assert booth.PAGE.count("\n#app{") == 1


def test_the_stream_lives_outside_the_markup_render_rewrites():
    """An <img> on an MJPEG stream holds an open connection. Inside the
    innerHTML that render() rewrites it would be torn down and reopened five
    times a second -- a black flicker and a new TCP connection each poll."""
    page = booth.PAGE
    assert page.index("<img id=live") < page.index("<div id=app>")
    assert "id=live" not in page[page.index("function render()"):]


def test_the_notice_prompt_is_above_the_expanded_live_view():
    """The live view is z-index 5 and can fill most of the screen. The one thing
    that must never be behind it is the robot asking to be answered."""
    css = booth.PAGE
    live_z = int(css.split("#live{")[1].split("z-index:")[1].split(";")[0])
    veil_z = int(css.split("#veil{")[1].split("z-index:")[1].split(";")[0])
    assert veil_z > live_z


def test_the_loop_publishes_outside_the_detector_failed_branch():
    """`flow_state` once sat in the `view is None` arm, so on a normal run it
    never executed: the tablet showed one screen for the whole session, sweep
    and all. Nothing raised -- an unwritten key just reads as the default."""
    src = open(os.path.join(ROOT, "noticebot_loop.py")).read()
    for key in ('UI.STATE["flow_state"]', 'UI.STATE["heard"]',
                'UI.STATE["request"]'):
        assert src.index(key) < src.index("if view is not None:\n                    view.publish"), key


def test_the_head_tap_no_longer_wakes_it():
    """PTT is the only way in on this build. A gesture that means two things
    needs saying out loud, and a study should not spend its briefing on a
    second meaning nobody needs."""
    src = open(os.path.join(ROOT, "noticebot_loop.py")).read()
    i = src.index('elif "BODYTAP" in line:')
    branch = src[i:i + 1400]
    assert 'player.request("S1_ATTEND")' not in branch
    assert 'events.append("tap")' in branch


def test_a_new_turn_clears_the_last_sentence():
    """Otherwise the tablet shows the previous request through the whole of the
    next person's speaking, which reads as the robot having already decided what
    they were going to say."""
    src = open(os.path.join(ROOT, "noticebot_loop.py")).read()
    i = src.index('if "PTT_DOWN" in line:')
    assert 'heard["text"], heard["ok"] = "", True' in src[i:i + 700]


# --------------------------------------------------------------------------- #
# run the page's own render(), rather than grepping the template
# --------------------------------------------------------------------------- #
HAS_NODE = shutil.which("node") is not None


def _render(state_obj):
    """Return the #app innerHTML the real render() produces for this state."""
    harness = r"""
const {JSDOM} = require(process.env.JSDOM_PATH);
const fs = require('fs');
let page = fs.readFileSync(process.env.PAGE_FILE, 'utf8');
const S0 = process.env.STATE_JSON;
page = page.replace('setInterval(poll,200); poll();', 'S=' + S0 + ';render();');
const dom = new JSDOM(page, {runScripts: 'dangerously'});
process.stdout.write(dom.window.document.getElementById('app').innerHTML);
"""
    env = dict(os.environ)
    env["JSDOM_PATH"] = "/tmp/node_modules/jsdom"
    env["STATE_JSON"] = json.dumps(state_obj)
    pf = "/tmp/_booth_page.html"
    open(pf, "w").write(booth.PAGE)
    env["PAGE_FILE"] = pf
    r = subprocess.run(["node", "-e", harness], capture_output=True,
                       text=True, env=env, timeout=60)
    if r.returncode:
        pytest.skip("jsdom unavailable: " + r.stderr.strip()[:120])
    return r.stdout


def cls(name, html):
    """Is there an element with exactly this class attribute?

    jsdom re-serialises `class=grid` as `class="grid"`, so asserting on the
    template's own unquoted spelling passes in the source and fails on the
    rendered output -- which is the wrong way round for a test whose whole
    point is to run the real function.
    """
    return ('class="%s"' % name) in html


needs_node = pytest.mark.skipif(not HAS_NODE, reason="node not installed")


@needs_node
def test_render_sleep_asks_for_the_button_not_the_tablet():
    html = _render(st("S0_IDLE"))
    assert "hold the button on the robot" in html
    assert "(-_-)" in html


@needs_node
def test_render_listen_shows_dots_before_the_first_word():
    """A held button with nothing said into it yet must still look like a
    machine that is receiving."""
    html = _render(st("S1_ATTEND", heard="", heard_ok=True))
    assert cls("lst", html) and "Listening" in html


@needs_node
def test_render_listen_shows_the_sentence_large():
    html = _render(st("S1_ATTEND", heard="tell me if someone touches my bag",
                      heard_ok=True))
    assert "tell me if someone touches my bag" in html
    assert cls("heard", html) and "I heard" in html


@needs_node
def test_render_listen_marks_a_misread_and_says_what_to_do():
    html = _render(st("S1_ATTEND", heard="beep beep beep", heard_ok=False))
    assert cls("heard no", html), "the rejected styling must be applied"
    assert "say it again" in html
    assert "beep beep beep" in html, "showing it is the point"


@needs_node
def test_render_room_echoes_the_accepted_request_not_the_last_thing_heard():
    d = st("S4B_WATCH", heard="something else entirely", heard_ok=True,
           request="tell me if people gather around")
    html = _render(d)
    assert "tell me if people gather around" in html
    assert "something else entirely" not in html


@needs_node
def test_render_room_is_the_same_screen_for_scanning_and_watching():
    """The only question either state raises is which way it is looking, and
    the grid answers it continuously. 'tracking...' over an empty page told a
    participant nothing the robot in front of them was not already saying."""
    scan = _render(st("S3_SCAN", request="r"))
    watch = _render(st("S4B_WATCH", request="r"))
    assert cls("grid", scan) and cls("grid", watch)


@needs_node
def test_render_room_has_six_cells_and_the_sixth_is_the_rule():
    html = _render(st("S4B_WATCH", request="r"))
    assert len(re.findall(r'class="cell\b', html)) == 6
    assert "spec" in html


def test_the_confirmation_holds_the_screen_until_the_flow_moves():
    """THE MENU USED TO BLINK BACK EMPTY for the ~200 ms between the tap and
    the next poll, so the last thing a visitor saw after pressing the button
    was their choice gone and `choose one to begin`. It reads as the tap having
    been thrown away, which is the opposite of what just happened."""
    src = open(os.path.join(ROOT, "webui", "booth.py")).read()
    send = src[src.index("async function sendPicks("):][:1400]
    assert "SENT=text; render();" in send
    assert send.index("SENT=text") < send.index("fetch('/context'"), \
        "the holding screen must go up BEFORE the round trip, not after it"
    assert "PICKED.size || SENT" in send, "and a second tap must do nothing"


def test_a_failed_post_gives_the_choice_back():
    """Holding a screen that says it worked when it did not is worse than the
    blink was."""
    src = open(os.path.join(ROOT, "webui", "booth.py")).read()
    send = src[src.index("async function sendPicks("):][:1400]
    catch = send[send.index("catch(e)"):]
    assert "SENT=null" in catch
    assert "PICKED=new Set()" not in catch, "the ticks must still be there"


def test_the_holding_screen_does_not_outlive_the_visitor():
    src = open(os.path.join(ROOT, "webui", "booth.py")).read()
    assert "PICKED=new Set(); SENT=null;" in src


def test_silence_is_not_a_failed_request_while_the_menu_is_up():
    """THE ERROR THAT ARRIVED WHILE SHE WAS STILL READING.

    The microphone is open for 4.5 s whether or not anyone intends to speak,
    and at a stand the normal thing a visitor does in those 4.5 s is read the
    menu. Whisper returns '' at about 5 s, transcript_usable refuses it, and
    the flow performs S7_ERROR -- not on a timeout, but early, and every single
    time.

    So in demo mode an EMPTY transcript is dropped and the flow is left
    listening; the menu, the typed prompt and the standing prompt are all still
    coming and any of them re-plans from S1_ATTEND.
    """
    src = open(os.path.join(ROOT, "noticebot_loop.py")).read()
    i = src.index("def on_transcript")
    block = src[i:i + 2200]
    assert 'a.approach and not ok and not (text or "").strip()' in block
    assert block.index("a.approach") < block.index("transcripts.append"), \
        "it has to be dropped before it reaches the flow"


def test_words_that_were_misheard_still_reach_the_flow():
    """Somebody who SPOKE and was misheard is owed the error performance: that
    is the robot saying it did not understand, which is true and is legible.
    Swallowing that would make a real failure look like being ignored."""
    src = open(os.path.join(ROOT, "noticebot_loop.py")).read()
    i = src.index("def on_transcript")
    block = src[i:i + 2200]
    assert '.strip()' in block, "only the EMPTY case is dropped"
    assert "not ok and not" in block, "not `not ok` alone"


def test_the_study_path_is_untouched():
    """No --approach, no menu, and silence after a held button means what it
    has always meant. The guard is on the demo flag for exactly this reason."""
    src = open(os.path.join(ROOT, "noticebot_loop.py")).read()
    i = src.index("def on_transcript")
    block = src[i:i + 2200]
    j = block.index("not ok and not")
    assert "a.approach and" in block[j - 40:j], \
        "the drop must be gated on demo mode, not applied to every run"

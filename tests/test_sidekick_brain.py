"""The sidekick mode's decisions, on made-up percepts (session/sidekick_brain.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from robot import states as ST                                  # noqa: E402
from perception.sidekick_sense import Percept, Person, Prop, Target   # noqa: E402
from session import sidekick_brain as B                         # noqa: E402


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class FakePlayer:
    def __init__(self):
        self.state = "SK_DOZE"
        self.aim = {}
        self.glance = None
        self.log = []
        self._resume = None

    def request(self, s, resume_to=None, as_authored=False):
        self.as_authored = as_authored
        spec = ST.STATES[s]
        if spec.get("resume"):
            self._resume = resume_to or self.state
        self.log.append(s)
        self.state = s

    def finish(self):
        """The current one-shot ends, as the real player would end it."""
        spec = ST.STATES[self.state]
        assert not spec["loop"] and not spec.get("live"), self.state
        if spec["then"]:
            self.state = spec["then"]
        elif spec.get("resume"):
            self.state, self._resume = self._resume, None

    def set_aim_deg(self, **d):
        self.aim = {k: v for k, v in d.items() if v is not None}

    def clear_aim(self):
        self.aim = {}

    def set_glance_target_deg(self, d):
        self.glance = d

    def set_found_pan_deg(self, d):
        self.found_pan = d

    def pose_deg(self):
        return {"pan": 0.0, "tilt": -8.0, "nod": 0.0}


def tgt(pan=0.0, gaze=10.0):
    return Target(x=0, y=0, pan=pan, nod=gaze + 12.0, gaze=gaze)


def face(pan=0.0, near=True):
    return Person(pid=1, head=tgt(pan, 15.0), sw_frac=0.35 if near else 0.1, near=near)


def prop(label="banana", pan=0.0, gaze=5.0, held=True, hand_near=None):
    return Prop(label=label, box=(0, 0, 10, 10), area=0.02, at=tgt(pan, gaze),
                held=held, hand_near=held if hand_near is None else hand_near)


def pc(clock, people=(), props=()):
    return Percept(t=clock.t, pose={"pan": 0.0, "tilt": -12.0, "nod": 22.0},
                   people=list(people), props=list(props))


def setup():
    clock, player, events = Clock(), FakePlayer(), []
    brain = B.Brain(player, on_event=lambda k, **kw: events.append((k, kw)),
                    clock=clock)
    return clock, player, brain, events


def step(clock, brain, dt, **kw):
    clock.t += dt
    brain.on_percept(pc(clock, **kw))


def awake(clock, player, brain):
    for _ in range(4):
        step(clock, brain, 0.25, people=[face(20.0)])
    assert brain.phase == "LOOK" and player.state == "SK_LOOK"


def test_someone_close_wakes_it_and_it_looks_at_them():
    clock, player, brain, _ = setup()
    step(clock, brain, 0.25, people=[face(20.0)])
    assert brain.phase == "SLEEP"            # a moment is a passer-by
    awake(clock, player, brain)
    assert abs(player.aim["pan"] - 20.0) < 1e-6
    assert player.aim["tilt"] == ST.LOOK_TILT


def dozing():
    """Someone just left: the robot is dozing, head up, before it falls asleep."""
    clock, player, brain, events = setup()
    brain._sleep()
    assert brain.phase == "DOZE" and player.state == "SK_DOZE"
    player.log.clear()
    return clock, player, brain, events


def test_a_passer_by_gets_one_glance_not_a_stream():
    clock, player, brain, _ = dozing()
    step(clock, brain, 0.25, people=[face(-30.0, near=False)])
    assert player.log == ["SK_GLANCE"] and player.glance == -30.0
    player.finish()
    step(clock, brain, 0.25, people=[face(-30.0, near=False)])
    assert player.log == ["SK_GLANCE"]


def test_a_touch_is_affection_otherwise():
    clock, player, brain, _ = setup()
    brain.on_tap()                             # dozing: wakes into the hand
    assert player.state == "SK_PURR"
    player.finish()
    assert player.state == "SK_LOOK"
    brain.on_tap()
    assert player.state == "SK_PURR"
    player.finish()
    assert player.state == "SK_LOOK"


def test_alone_it_dozes_then_falls_asleep_head_down():
    clock, player, brain, _ = setup()
    awake(clock, player, brain)
    for _ in range(int(B.LOST_S / 0.25) + 2):
        step(clock, brain, 0.25)
    assert brain.phase == "DOZE" and player.state == "SK_DOZE"
    for _ in range(int(B.DOZE_TO_SLEEP_S / 0.25) + 2):
        step(clock, brain, 0.25)
    assert brain.phase == "SLEEP" and player.state == "S0_IDLE"


def test_passers_by_keep_it_drowsy_rather_than_asleep():
    clock, player, brain, _ = dozing()
    for _ in range(int(B.DOZE_TO_SLEEP_S / 0.25) * 2):
        step(clock, brain, 0.25, people=[face(-30.0, near=False)])
        if player.state == "SK_GLANCE":
            player.finish()
    assert brain.phase == "DOZE"


def test_asleep_a_hand_or_a_touch_wakes_it():
    clock, player, brain, _ = setup()
    brain.on_palm()
    assert brain.phase == "LOOK" and player.state == "SK_LOOK"
    clock, player, brain, _ = setup()
    brain.on_tap()
    assert player.state == "SK_PURR" and player.as_authored
    player.finish()
    assert player.state == "SK_LOOK"


# ---- stages: one interaction at a time -------------------------------------
def test_stage_1_answers_a_touch_and_nothing_else():
    clock, player, events = Clock(), FakePlayer(), []
    player.state = "S0_IDLE"
    brain = B.Brain(player, clock=clock, stage=1)
    assert brain.rest == "S0_IDLE"
    for _ in range(8):                         # someone close: no wake at stage 1
        step(clock, brain, 0.25, people=[face(20.0)])
    assert player.log == [] and brain.phase == "SLEEP"
    brain.on_tap()
    assert player.state == "SK_PURR" and player.as_authored   # the full lift
    player.finish()
    assert player.state == "S0_IDLE"           # and back to resting


def test_each_stage_needs_only_its_own_clips():
    from robot import states as ST2
    paper = {s["clip"] for n, s in ST2.STATES.items() if not ST2.is_sidekick(n)}
    for n in B.STAGES:
        have = paper | set(B.clips_for_stage(n))
        assert ST2.validate(have, sidekick=B.clips_for_stage(n)) == [], n
    assert B.clips_for_stage(1) == ("SK_PURR",)


def test_a_passer_straight_ahead_gets_a_glance_without_a_turn():
    clock, player, brain, _ = dozing()
    step(clock, brain, 0.25, people=[face(3.0, near=False)])
    assert player.log == ["SK_GLANCE"] and player.glance == 0.0


# ---- stage 3: show it something, it looks out for it -----------------------
def teach(label="water bottle", name="a blue water bottle"):
    clock, player, brain, events = setup()
    awake(clock, player, brain)
    step(clock, brain, 0.25, people=[face()], props=[prop(label)])
    step(clock, brain, 0.25, people=[face()], props=[prop(label)])
    assert brain.phase == "TEACH" and player.state == "SK_CURIOUS"
    assert events[-1][0] == "identify" and events[-1][1]["guess"] == label
    player.finish()
    assert player.state == "SK_FOLLOW"                # follows it while it is named
    brain.on_identified(name, label)
    assert player.state == "SK_ACK" and brain.phase == "LOOK"
    assert events[-1] == ("taught", {"term": label, "name": name})
    player.finish()
    assert player.state == "SK_LOOK"
    return clock, player, brain, events


def test_hold_something_up_and_it_agrees_to_look_out_for_it():
    clock, player, brain, events = teach()
    assert brain.target["term"] == "water bottle"


def test_still_in_the_owners_hand_is_not_a_finding():
    clock, player, brain, events = teach()
    for _ in range(12):                        # they keep holding it
        step(clock, brain, 0.25, people=[face()], props=[prop("water bottle")])
    assert brain.phase == "LOOK" and "found" not in [k for k, _ in events]


def test_after_it_was_gone_seeing_it_again_calls():
    clock, player, brain, events = teach()
    for _ in range(int(B.TARGET_AWAY_S / 0.25) + 2):    # put away
        step(clock, brain, 0.25, people=[face()])
    step(clock, brain, 0.25, people=[face()],
         props=[prop("water bottle", pan=-30.0, held=False)])
    step(clock, brain, 0.25, people=[face()],
         props=[prop("water bottle", pan=-30.0, held=False)])
    assert brain.phase == "CALL" and player.state == "S5A_FOUND"
    assert player.found_pan == -30.0
    assert events[-1][0] == "found"
    brain.on_tap()                                       # "seen it"
    assert player.state == "SK_ACK"
    player.finish()
    assert player.state == "SK_LOOK"


def test_it_finds_it_while_dozing_too():
    clock, player, brain, events = teach()
    for _ in range(int(B.LOST_S / 0.25) + 2):            # everyone leaves
        step(clock, brain, 0.25)
    assert brain.phase == "DOZE"
    step(clock, brain, 0.25, props=[prop("water bottle", held=False)])
    step(clock, brain, 0.25, props=[prop("water bottle", held=False)])
    assert brain.phase == "CALL"


def test_a_new_visitor_shows_a_new_thing_and_it_replaces_the_old():
    clock, player, brain, events = teach()
    for _ in range(int(B.TEACH_AGAIN_S / 0.25) + 1):
        step(clock, brain, 0.25, people=[face()])
    step(clock, brain, 0.25, people=[face()], props=[prop("keys")])
    step(clock, brain, 0.25, people=[face()], props=[prop("keys")])
    assert brain.phase == "TEACH"
    player.finish()
    brain.on_identified("a set of keys", "keys")
    assert brain.target["term"] == "keys"


def test_the_model_could_not_tell_and_it_says_so():
    clock, player, brain, events = setup()
    awake(clock, player, brain)
    step(clock, brain, 0.25, people=[face()], props=[prop("toy")])
    step(clock, brain, 0.25, people=[face()], props=[prop("toy")])
    player.finish()
    brain.on_identified(None, None)
    assert brain.phase == "LOOK" and brain.target is None
    assert "couldn't" in brain.caption


def test_an_answer_during_the_curious_beat_waits_for_it_to_finish():
    clock, player, brain, events = setup()
    awake(clock, player, brain)
    step(clock, brain, 0.25, people=[face()], props=[prop("cup")])
    step(clock, brain, 0.25, people=[face()], props=[prop("cup")])
    brain.on_identified("a red cup", "cup")           # still SK_CURIOUS
    assert player.state == "SK_CURIOUS" and brain.phase == "TEACH"
    player.finish()                                    # -> SK_FOLLOW
    brain.tick()
    assert player.state == "SK_ACK" and brain.target["term"] == "cup"

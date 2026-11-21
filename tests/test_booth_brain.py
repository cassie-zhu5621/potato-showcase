"""The 11.24 researcher booth's decisions (session/booth_brain.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from perception.sidekick_sense import Person              # noqa: E402
from session import booth_brain as BB                     # noqa: E402
import test_sidekick_brain as T                           # noqa: E402


def setup():
    clock, player, events = T.Clock(), T.FakePlayer(), []
    player.state = "S0_IDLE"
    brain = BB.BoothBrain(player, on_event=lambda k, **kw: events.append((k, kw)),
                          clock=clock)
    return clock, player, brain, events


def who(pan, frac=0.35, pid=1):
    return Person(pid=pid, head=T.tgt(pan, 15.0), sw_frac=frac, near=frac >= 0.25)


def woken(owner_pan=0.0):
    clock, player, brain, events = setup()
    brain.on_tap()
    assert brain.phase == "LOOK"
    player.finish()                                  # the purr ends -> SK_LOOK
    assert player.state == "SK_LOOK"
    T.step(clock, brain, 0.25, people=[who(owner_pan)])
    assert brain._owner
    return clock, player, brain, events


def test_coming_close_does_not_wake_it_only_a_pat_does():
    clock, player, brain, events = setup()
    for _ in range(12):
        T.step(clock, brain, 0.25, people=[who(0.0, 0.5)])
    assert brain.phase == "SLEEP" and player.log == []
    brain.on_tap()
    assert brain.phase == "LOOK" and player.log == ["SK_PURR"]


def test_it_follows_its_owner_and_not_someone_closer_beside_them():
    clock, player, brain, events = woken(owner_pan=0.0)
    for _ in range(6):
        T.step(clock, brain, 0.25, people=[who(2.0, 0.3, pid=1), who(35.0, 0.6, pid=2)])
    assert abs(player.aim["pan"] - 2.0) < 7.0


def test_after_a_while_without_the_owner_the_closest_person_takes_over():
    clock, player, brain, events = woken(owner_pan=0.0)
    for _ in range(int(BB.OWNER_SWITCH_S / 0.5) + 2):
        T.step(clock, brain, 0.5, people=[who(50.0, 0.5, pid=2)])
    assert abs(player.aim["pan"] - 50.0) < 7.0


def test_showing_needs_an_owner_first():
    clock, player, brain, events = setup()
    brain.on_tap()
    player.finish()
    for _ in range(6):                               # nobody seen yet: no owner
        T.step(clock, brain, 0.25, props=[T.prop("cup")])
    assert brain.phase == "LOOK" and not brain._owner
    for _ in range(6):
        T.step(clock, brain, 0.25, people=[who(0.0)], props=[T.prop("cup")])
    assert brain.phase == "TEACH"


def test_owner_gone_a_minute_is_the_same_as_next():
    clock, player, brain, events = woken()
    T.show(clock, brain, "cup")
    player.finish()
    brain.on_identified("a red cup", "cup")
    assert brain.target
    clock.t += BB.OWNER_GONE_S + 1
    brain.tick()
    assert brain.phase == "SLEEP" and player.state == "S0_IDLE"
    assert brain.target is None and not brain._owner
    assert "auto_next" in [k for k, _ in events]


def test_next_forgets_owner_and_object_but_keeps_the_tof_setting():
    clock, player, brain, events = woken()
    brain.set_tof(metres=1.2, on=False)
    brain.target = dict(term="cup", name="a cup", words=["cup"], since=0)
    brain.next_visitor()
    assert brain.phase == "SLEEP" and brain.target is None and not brain._owner
    assert brain.tof_m == 1.2 and brain.tof_on is False


def test_someone_within_the_tof_distance_gets_one_stir_while_they_stay():
    clock, player, brain, events = setup()
    for _ in range(40):                               # 2 s standing at 0.6 m
        clock.t += 0.05
        brain.on_distance(600)
    assert player.log == ["SK_GLANCE"]
    player.state = "S0_IDLE"                          # the glance resumed sleep
    for _ in range(60):                               # still standing: no more
        clock.t += 0.05
        brain.on_distance(600)
    assert player.log == ["SK_GLANCE"]
    for _ in range(50):                               # they leave (2.5 s) ...
        clock.t += 0.05
        brain.on_distance(2000)
    for _ in range(10):                               # ... someone new comes
        clock.t += 0.05
        brain.on_distance(500)
    assert player.log == ["SK_GLANCE", "SK_GLANCE"]


def test_the_tof_is_ignored_when_off_far_invalid_or_awake():
    clock, player, brain, events = setup()
    brain.set_tof(on=False)
    for _ in range(20):
        clock.t += 0.05
        brain.on_distance(400)
    brain.set_tof(on=True, metres=0.5)
    for _ in range(20):
        clock.t += 0.05
        brain.on_distance(700)                        # beyond 0.5 m
        brain.on_distance(-1)                         # no valid reading
    assert player.log == []
    brain.on_tap()
    player.finish()
    for _ in range(20):
        clock.t += 0.05
        brain.on_distance(300)
    assert "SK_GLANCE" not in player.log


def test_the_tof_setting_is_kept_in_range():
    clock, player, brain, events = setup()
    brain.set_tof(metres=5)
    assert brain.tof_m == BB.TOF_MAX_M
    brain.set_tof(metres=0.0)
    assert brain.tof_m == BB.TOF_MIN_M

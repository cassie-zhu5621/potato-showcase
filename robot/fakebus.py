"""
fakebus.py -- a servo bus that is not there.

For running the sidekick booth on the laptop alone (`sidekick_loop.py
--no-robot`) and for tests: every write lands instantly, every read returns it.
The player cannot tell the difference, so the whole decision loop, the clips'
timing and the tablet run exactly as they would with the robot attached.
"""
from robot.pose import IDS, centre_units


class FakeBus:
    def __init__(self):
        self.pos = dict(centre_units())
        self.writes = 0
        self._joint = {v: k for k, v in IDS.items()}

    def ping(self, sid):
        return 0, True

    def flush_input(self):
        pass

    def read_pos(self, sid):
        return self.pos[self._joint[sid]]

    def read_voltage(self, sid):
        return 5.5

    def torque(self, sid, on):
        pass

    def write_pos(self, sid, u, time_ms=0, speed=0):
        self.pos[self._joint[sid]] = u
        self.writes += 1

    write_pos_fast = write_pos

    def close(self):
        pass
